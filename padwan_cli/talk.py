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

# Terminals report no key-release: a held Space arrives as auto-repeated spaces.
# A gap longer than the keyboard's initial repeat delay (~0.66 s default) means
# the key was released; shorter turns are discarded as accidental taps.
_HOLD_RELEASE_GAP = 0.8
_MIN_TURN_SECS = 0.45

_DEFAULT_INSTRUCTIONS = """You are a friendly voice assistant.
Keep spoken replies brief and conversational — one or two sentences — so the
exchange stays a real back-and-forth."""


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
    """Consume server events: play audio, stream transcripts, prompt for the turn.

    Your own transcript arrives asynchronously and usually after the assistant has
    started answering, so assistant text is held until the "you:" line has printed
    (flushed unconditionally on response.done so nothing is ever lost).
    """
    speaking = False  # is the assistant mid-utterance on this line?
    held: list[str] = []  # assistant transcript held until the "you:" line prints
    user_shown = True  # has the current turn's input transcript been printed?
    prepaid = False  # input transcript arrived before its response was created

    def flush_held() -> None:
        nonlocal speaking
        if held:
            console.print("[cyan]assistant:[/cyan] ", end="")
            sys.stdout.write("".join(held))
            sys.stdout.flush()
            held.clear()
            speaking = True

    async for event in conn:
        kind = event.get("type")
        if kind == RealtimeServerEvent.AUDIO_DELTA:
            if pcm := conn.audio_delta_bytes(event):
                speaker.play(pcm)
        elif kind == RealtimeServerEvent.AUDIO_TRANSCRIPT_DELTA:
            delta = event.get("delta", "")
            if not user_shown:
                held.append(delta)
                continue
            if not speaking:
                console.print("[cyan]assistant:[/cyan] ", end="")
                speaking = True
            sys.stdout.write(delta)
            sys.stdout.flush()
        elif kind == RealtimeServerEvent.RESPONSE_CREATED:
            if prepaid:
                prepaid = False  # transcript already printed for this turn
            else:
                user_shown = False
        elif kind == RealtimeServerEvent.SPEECH_STARTED:  # hands-free VAD only
            speaker.clear()  # barge-in: drop queued assistant audio
            flush_held()
            if speaking:
                sys.stdout.write("\n")
                speaking = False
        elif kind == RealtimeServerEvent.INPUT_TRANSCRIPT_COMPLETED:
            text = (event.get("transcript") or "").strip()
            if speaking:
                sys.stdout.write("\n")
                speaking = False
            if text:
                console.print(f"[green]you:[/green] {text}")
            if user_shown:
                prepaid = True  # transcript beat its response.created
            else:
                user_shown = True
                flush_held()
        elif kind == RealtimeServerEvent.RESPONSE_DONE:
            flush_held()  # transcript never arrived; don't lose the assistant text
            user_shown = True
            if speaking:
                sys.stdout.write("\n")
                speaking = False
            if push_to_talk:
                console.print("[dim]· hold Space to talk[/dim]")
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

    draining = False
    sent_bytes = 0

    async def pump_mic() -> None:
        nonlocal draining, sent_bytes
        # Timed get so the executor thread exits shortly after cancellation
        # instead of blocking threading shutdown at exit.
        blocking_get = functools.partial(mic_q.get, True, 0.25)
        while True:
            try:
                chunk = await loop.run_in_executor(None, blocking_get)
            except queue.Empty:
                continue
            # The transport lets roughly one send through per read-poll tick,
            # so batch everything captured while we waited for the socket.
            parts = [chunk]
            while True:
                try:
                    parts.append(mic_q.get_nowait())
                except queue.Empty:
                    break
            draining = True
            try:
                joined = b"".join(parts)
                await conn.append_audio(joined)
                sent_bytes += len(joined)
            finally:
                draining = False

    turn_task: asyncio.Task | None = None
    last_space = 0.0
    turn_started_at = 0.0

    async def start_turn() -> None:
        nonlocal turn_started_at, sent_bytes
        with mic_q.mutex:
            mic_q.queue.clear()  # drop audio captured before the press
        speaker.clear()  # stop the assistant if it was still talking
        await conn.send_event({"type": "input_audio_buffer.clear"})
        recording.set()
        turn_started_at = loop.time()
        sent_bytes = 0
        console.print("[red]● recording…[/red] [dim]release Space to send[/dim]")

    async def end_turn() -> None:
        recording.clear()
        # Wait until everything captured actually reached the socket, so the
        # commit doesn't clip the tail of the turn.
        deadline = loop.time() + 3
        while (not mic_q.empty() or draining) and loop.time() < deadline:
            await asyncio.sleep(0.05)
        if loop.time() - turn_started_at < _MIN_TURN_SECS:
            await conn.send_event({"type": "input_audio_buffer.clear"})
            console.print("[dim](too short — hold Space while speaking)[/dim]")
            return
        await conn.commit_audio()
        await conn.create_response()
        console.print(f"[dim](sent {sent_bytes / (SR * 2):.1f}s of audio)[/dim]")

    def _spawn_turn(coro_fn) -> None:
        nonlocal turn_task
        if turn_task is not None and not turn_task.done():
            return  # previous transition still in flight
        turn_task = asyncio.create_task(coro_fn())

    def on_key() -> None:  # called by the event loop when stdin is readable
        nonlocal last_space
        try:
            data = os.read(sys.stdin.fileno(), 1)
        except OSError:
            return
        if data == b" ":
            # Held Space shows up as auto-repeated spaces; each one refreshes
            # the hold. The release watcher ends the turn once they stop.
            last_space = loop.time()
            if not recording.is_set():
                _spawn_turn(start_turn)
        elif data in (b"\r", b"\n") and recording.is_set():
            _spawn_turn(end_turn)  # manual send fallback

    async def watch_release() -> None:
        while True:
            await asyncio.sleep(0.1)
            if recording.is_set() and loop.time() - last_space > _HOLD_RELEASE_GAP:
                _spawn_turn(end_turn)

    use_keys = push_to_talk and sys.stdin.isatty()
    with mic:
        sender = asyncio.create_task(pump_mic())
        watcher = asyncio.create_task(watch_release()) if use_keys else None
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
            if watcher is not None:
                watcher.cancel()
            if turn_task is not None:
                turn_task.cancel()


async def talk_command(
    voice: str = Option("marin", "--voice", help="Realtime voice (marin, cedar, …)"),
    model: str = Option("gpt-realtime", "-m", "--model", help="Realtime model"),
    instructions: str | None = Option(
        None, "--instructions", help="System prompt for the voice assistant"
    ),
    hands_free: bool = Option(
        False, "--hands-free", help="Auto voice detection instead of push-to-talk"
    ),
    check: bool = Option(
        False, "--check", help="List audio devices and key status, then exit"
    ),
) -> None:
    """Talk with a real-time voice assistant (speech-to-speech)."""
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
        key_found = bool(os.environ.get("OPENAI_API_KEY"))
        console.print(
            f"OPENAI_API_KEY: {'found' if key_found else '[red]MISSING[/red]'}"
        )
        console.print(f"model={model}  voice={voice}")
        return

    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]OPENAI_API_KEY not set[/red] — export it or add it to .env")
        raise SystemExit(1)

    push_to_talk = not hands_free
    if push_to_talk and not sys.stdin.isatty():
        console.print(
            "[yellow]push-to-talk needs a terminal; using --hands-free.[/yellow]"
        )
        push_to_talk = False

    prompt = instructions or _DEFAULT_INSTRUCTIONS
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
                        "[green]Ready.[/green] [dim]Hold Space while talking, "
                        "release to send. Ctrl-C to quit.[/dim]\n"
                    )
                else:
                    console.print(
                        "[green]Go ahead.[/green] [dim](hands-free — just speak. "
                        "Ctrl-C to quit.)[/dim]\n"
                    )
                await _converse(conn, sd, speaker, push_to_talk=push_to_talk)
    except asyncio.CancelledError:
        console.print("\n[dim]Bye! 👋[/dim]")
    finally:
        if task is not None:
            loop.remove_signal_handler(signal.SIGINT)


def main() -> None:
    """Headless entry point (`padwan-talk`): run the voice chat without the TUI."""
    # Deferred import avoids a circular import (run imports talk at module load).
    from .run import cli

    cli.run_with_args("talk", *sys.argv[1:])
