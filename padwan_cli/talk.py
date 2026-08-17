from __future__ import annotations

import asyncio
import contextlib
import functools
import os
import queue
import signal
import sys
import termios
import threading
import tty
from pathlib import Path

from piou import Option
from piou.tui import get_tui_context

from padwan_llm.openai.realtime import (
    NO_TURN_DETECTION,
    REALTIME_SAMPLE_RATE,
    RealtimeClient,
    RealtimeConnection,
    RealtimeServerEvent,
)

from .utils import console

SR = REALTIME_SAMPLE_RATE  # 24 kHz mono PCM16, as gpt-realtime expects
CHANNELS = 1
DTYPE = "int16"
BLOCK = 1200  # 50 ms frames

# Looked up for OPENAI_API_KEY when it is not already exported.
_ENV_FILES = (
    Path.cwd() / ".env",
    Path.home() / "Projects/Polarsen/padwan-llm/.env",
)


def build_tutor_prompt(language: str, level: str) -> str:
    """Build the system prompt for a spoken-language tutor."""
    return f"""You are a warm and patient {language} conversation tutor.
The student's level is {level} and their native language is English.

How you speak:
- Talk almost entirely in {language}, but keep it simple and slow, matched to
  the student's level. Drop to short English asides only to unblock them.
- Keep each turn short (one or two sentences) so it stays a real back-and-forth.
- Always end your turn with a question or a small prompt that invites them to
  speak, so the conversation keeps flowing.
- When the student makes a meaningful mistake, gently restate the correct form
  once and move on — do not interrupt the flow with long grammar lectures.
- Be encouraging and celebrate small wins.

Start by warmly greeting the student in {language} and asking an easy opening
question (their name, their day, what they like)."""


def load_api_key() -> str | None:
    """Return OPENAI_API_KEY from the environment or a known .env file."""
    if key := os.environ.get("OPENAI_API_KEY"):
        return key
    for env_file in _ENV_FILES:
        if not env_file.is_file():
            continue
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                value = line.split("=", 1)[1].strip().strip("'\"")
                if value:
                    os.environ["OPENAI_API_KEY"] = value
                    return value
    return None


class Speaker:
    """Buffered PCM16 playback with barge-in support."""

    def __init__(self, sd) -> None:
        self._buf = bytearray()
        self._lock = threading.Lock()
        self.stream = sd.RawOutputStream(
            samplerate=SR,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK,
            callback=self._callback,
        )

    def _callback(self, outdata, frames, _time, _status) -> None:  # PortAudio thread
        need = frames * CHANNELS * 2
        with self._lock:
            take = bytes(self._buf[:need])
            del self._buf[: len(take)]
        if len(take) < need:
            take += b"\x00" * (need - len(take))  # underflow -> silence
        outdata[:] = take

    def play(self, pcm16: bytes) -> None:
        with self._lock:
            self._buf.extend(pcm16)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


def _import_sounddevice():
    """Import sounddevice lazily, with a friendly hint if the extra is missing."""
    try:
        import sounddevice as sd
    except OSError as e:  # PortAudio shared library not found
        console.print(f"[red]PortAudio unavailable: {e}[/red]")
        console.print(
            "[dim]Install the system library, e.g. `apt install libportaudio2`.[/dim]"
        )
        raise SystemExit(1)
    except ImportError:
        console.print("[red]sounddevice not installed.[/red]")
        console.print("[dim]Install the voice extra: `uv sync --extra voice`.[/dim]")
        raise SystemExit(1)
    return sd


@contextlib.contextmanager
def _cbreak(fd: int):
    """Put the terminal in cbreak mode so single keypresses arrive immediately."""
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)  # leaves ISIG on, so Ctrl-C still quits
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


async def _handle_events(
    conn: RealtimeConnection, speaker: Speaker, *, push_to_talk: bool
) -> None:
    """Consume server events: play audio, stream transcripts, prompt for the turn."""
    speaking = False  # is the tutor mid-utterance on this line?
    async for event in conn:
        kind = event.get("type")
        if kind == RealtimeServerEvent.AUDIO_DELTA:
            if pcm := conn.audio_delta_bytes(event):
                speaker.play(pcm)
        elif kind == RealtimeServerEvent.AUDIO_TRANSCRIPT_DELTA:
            if not speaking:
                console.print("[cyan]tutor:[/cyan] ", end="")
                speaking = True
            sys.stdout.write(event.get("delta", ""))
            sys.stdout.flush()
        elif kind == RealtimeServerEvent.SPEECH_STARTED:  # hands-free VAD only
            speaker.clear()  # barge-in: drop queued tutor audio
            if speaking:
                sys.stdout.write("\n")
                speaking = False
        elif kind == RealtimeServerEvent.INPUT_TRANSCRIPT_COMPLETED:
            text = (event.get("transcript") or "").strip()
            if text:
                console.print(f"[green]you:[/green] {text}")
        elif kind == RealtimeServerEvent.RESPONSE_DONE:
            if speaking:
                sys.stdout.write("\n")
                speaking = False
            if push_to_talk:
                console.print("[dim]· tap Space to talk[/dim]")
        elif kind == RealtimeServerEvent.ERROR:
            console.print(f"\n[dim][error] {event.get('error')}[/dim]")


async def _converse(
    conn: RealtimeConnection, sd, speaker: Speaker, *, push_to_talk: bool
) -> None:
    """Pump mic → model and run the event loop, in push-to-talk or hands-free mode."""
    loop = asyncio.get_running_loop()
    mic_q: queue.Queue[bytes] = queue.Queue()
    recording = threading.Event()
    if not push_to_talk:
        recording.set()  # hands-free: stream continuously, server VAD picks turns

    def mic_callback(indata, _frames, _time, _status) -> None:  # PortAudio thread
        if recording.is_set():
            mic_q.put(bytes(indata))

    mic = sd.RawInputStream(
        samplerate=SR,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=BLOCK,
        callback=mic_callback,
    )

    async def pump_mic() -> None:
        # Timed get so the executor thread exits shortly after cancellation
        # instead of blocking threading shutdown at exit.
        blocking_get = functools.partial(mic_q.get, True, 0.25)
        while True:
            try:
                chunk = await loop.run_in_executor(None, blocking_get)
            except queue.Empty:
                continue
            await conn.append_audio(chunk)

    async def start_turn() -> None:
        with mic_q.mutex:
            mic_q.queue.clear()  # drop audio captured before the press
        speaker.clear()  # stop the tutor if it was still talking
        await conn.send_event({"type": "input_audio_buffer.clear"})
        recording.set()
        console.print("[red]● recording…[/red] [dim]Space to send[/dim]")

    async def end_turn() -> None:
        recording.clear()
        await asyncio.sleep(0.15)  # let the last queued chunks reach the socket
        await conn.commit_audio()
        await conn.create_response()

    turn_task: asyncio.Task | None = None

    def on_key() -> None:  # called by the event loop when stdin is readable
        nonlocal turn_task
        try:
            data = os.read(sys.stdin.fileno(), 1)
        except OSError:
            return
        if data in (b" ", b"\r", b"\n"):
            if turn_task is not None and not turn_task.done():
                return  # previous toggle still in flight; ignore the press
            coro = end_turn() if recording.is_set() else start_turn()
            turn_task = asyncio.create_task(coro)

    use_keys = push_to_talk and sys.stdin.isatty()
    with mic:
        sender = asyncio.create_task(pump_mic())
        fd = sys.stdin.fileno()
        try:
            if use_keys:
                with _cbreak(fd):
                    loop.add_reader(fd, on_key)
                    try:
                        await _handle_events(conn, speaker, push_to_talk=True)
                    finally:
                        loop.remove_reader(fd)
            else:
                await _handle_events(conn, speaker, push_to_talk=False)
        finally:
            sender.cancel()
            if turn_task is not None:
                turn_task.cancel()


async def talk_command(
    language: str = Option("Italian", "-l", "--language", help="Language to practise"),
    level: str = Option(
        "beginner (A1-A2)", "--level", help="Student level woven into the persona"
    ),
    voice: str = Option("marin", "--voice", help="Realtime voice (marin, cedar, …)"),
    model: str = Option("gpt-realtime", "-m", "--model", help="Realtime model"),
    instructions: str | None = Option(
        None, "--instructions", help="Override the tutor persona entirely"
    ),
    hands_free: bool = Option(
        False, "--hands-free", help="Auto voice detection instead of push-to-talk"
    ),
    check: bool = Option(
        False, "--check", help="List audio devices and key status, then exit"
    ),
) -> None:
    """Speak with a real-time voice tutor (speech-to-speech) to practise a language."""
    # A live mic/speaker session needs the whole terminal; the Textual TUI owns it,
    # so this command only works headless. Fail loudly instead of hanging silently.
    if get_tui_context().is_tui:
        console.print(
            "[yellow]`talk` is a full-terminal voice session and can't run inside "
            "the TUI.[/yellow]\n[dim]Run it headless:[/dim] [bold]uv run padwan-talk"
            "[/bold] [dim](or `python -m padwan_cli talk`).[/dim]"
        )
        return

    sd = _import_sounddevice()

    if check:
        console.print(sd.query_devices())
        console.print(f"\nDefault (input, output): {sd.default.device}")
        console.print(
            f"OPENAI_API_KEY: {'found' if load_api_key() else '[red]MISSING[/red]'}"
        )
        console.print(f"model={model}  voice={voice}  language={language}")
        return

    if not load_api_key():
        console.print(
            "[red]OPENAI_API_KEY not set[/red] and not found in "
            + " or ".join(str(p) for p in _ENV_FILES)
        )
        raise SystemExit(1)

    push_to_talk = not hands_free
    if push_to_talk and not sys.stdin.isatty():
        console.print(
            "[yellow]push-to-talk needs a terminal; using --hands-free.[/yellow]"
        )
        push_to_talk = False

    prompt = instructions or build_tutor_prompt(language, level)
    speaker = Speaker(sd)
    # Push-to-talk disables server VAD so we commit each turn ourselves.
    turn_detection = NO_TURN_DETECTION if push_to_talk else None

    client = RealtimeClient(model=model)
    console.print(f"[dim]connecting to {model} (voice: {voice})…[/dim]")
    # Route Ctrl-C through task cancellation: a raw KeyboardInterrupt tears the
    # loop down without unwinding connect()/mic/speaker, leaking pending tasks.
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    if task is not None:
        loop.add_signal_handler(signal.SIGINT, task.cancel)
    try:
        async with client.connect(
            instructions=prompt, voice=voice, turn_detection=turn_detection
        ) as conn:
            with speaker.stream:
                if push_to_talk:
                    console.print(
                        "[green]Ready.[/green] [dim]Tap Space to talk, Space again "
                        "to send. Ctrl-C to quit.[/dim]\n"
                    )
                else:
                    console.print(
                        "[green]Parla pure![/green] [dim](hands-free — just speak. "
                        "Ctrl-C to quit.)[/dim]\n"
                    )
                await _converse(conn, sd, speaker, push_to_talk=push_to_talk)
    except asyncio.CancelledError:
        console.print("\n[dim]Ciao! 👋[/dim]")
    finally:
        if task is not None:
            loop.remove_signal_handler(signal.SIGINT)


def main() -> None:
    """Headless entry point (`padwan-talk`): run the voice tutor without the TUI."""
    # Deferred import avoids a circular import (run imports talk at module load).
    from .run import cli

    cli.run_with_args("talk", *sys.argv[1:])
