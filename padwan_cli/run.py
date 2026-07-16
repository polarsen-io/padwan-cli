from __future__ import annotations

import json
import sys
from typing import Any

from piou import Cli, Option
from piou.tui import get_tui_context

from rich.table import Table

from padwan_llm import (
    GEMINI_MODELS,
    GROK_MODELS,
    MISTRAL_MODELS,
    OPENAI_MODELS,
    LLMClient,
)
from padwan_llm._base import OnThought
from padwan_llm.conversation import Message
from padwan_llm.errors import Provider

from .utils import console
from .batch import batch_group
from .chat import chat_group
from .talk import talk_command

CUSTOM_CSS = """
Rule.chat-mode {
    color: #87ceeb;
}
Rule.attach-warning {
    color: #fbbf24;
}
"""

cli = Cli(description="Padwan CLI for the unified LLM client library")

cli.add_command_group(batch_group)
cli.add_command_group(chat_group)

cli.command("talk", help="Speech-to-speech voice tutor (practise a language)")(
    talk_command
)


@cli.tui_on_ready
def _tui_startup_hint() -> None:
    """Show a hint pointing new users at the command palette when the TUI opens."""
    get_tui_context().set_hint("Type / to browse commands - e.g. /chat:send 'Hello'")


@cli.command("models", help="List available models")
def list_models(
    provider: Provider | None = Option(
        None, "-p", "--provider", help="Filter by provider"
    ),
) -> None:
    """List all available models, optionally filtered by provider."""
    provider_models: dict[str, list[str]] = {}
    if not provider or provider == "openai":
        provider_models["OpenAI"] = list(OPENAI_MODELS)
    if not provider or provider == "gemini":
        provider_models["Gemini"] = list(GEMINI_MODELS)
    if not provider or provider == "mistral":
        provider_models["Mistral"] = list(MISTRAL_MODELS)
    if not provider or provider == "grok":
        provider_models["Grok"] = list(GROK_MODELS)

    if not provider_models:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        return

    table = Table(title="Available Models")
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="green")

    for prov, models in provider_models.items():
        for i, model in enumerate(sorted(models)):
            table.add_row(prov if i == 0 else "", model)

    console.print(table)


@cli.command("info", help="Show library information")
def info() -> None:
    """Show library information."""
    table = Table(title="Padwan LLM Library")
    table.add_column("Provider", style="cyan")
    table.add_column("Models", style="green", justify="right")

    table.add_row("OpenAI", str(len(OPENAI_MODELS)))
    table.add_row("Gemini", str(len(GEMINI_MODELS)))
    table.add_row("Mistral", str(len(MISTRAL_MODELS)))
    table.add_row("Grok", str(len(GROK_MODELS)))

    total = (
        len(OPENAI_MODELS) + len(GEMINI_MODELS) + len(MISTRAL_MODELS) + len(GROK_MODELS)
    )
    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    console.print(table)


@cli.main(help="One-shot LLM query")
async def oneshot(
    prompt: str = Option(..., help="Prompt to send"),
    model: str = Option("gpt-4o-mini", "-m", "--model", help="Model to use"),
    stream: bool = Option(False, "--stream", "-s", help="Stream output as it arrives"),
    base_url: str | None = Option(
        None, "--base-url", help="Custom OpenAI-compatible endpoint"
    ),
    extra_params: str | None = Option(
        None,
        "--extra-params",
        help="Extra JSON object merged into the request body (e.g. '{\"temperature\": 0}')",
    ),
    stream_thinking: bool = Option(
        False,
        "--stream-thinking",
        help="Stream model reasoning/thinking tokens to stderr (requires --stream)",
    ),
) -> None:
    """Send a single prompt and print the response."""
    parsed_extra: dict[str, Any] | None = None
    if extra_params is not None:
        try:
            parsed_extra = json.loads(extra_params)
        except json.JSONDecodeError as e:
            console.print(f"[red]--extra-params is not valid JSON: {e}[/red]")
            raise SystemExit(1)
        if not isinstance(parsed_extra, dict):
            console.print("[red]--extra-params must be a JSON object[/red]")
            raise SystemExit(1)

    def _thought_streamer(chunk: str) -> None:
        sys.stderr.write(chunk)
        sys.stderr.flush()

    on_thought: OnThought | None = _thought_streamer if stream_thinking else None

    client = LLMClient(model=model, base_url=base_url, on_thought=on_thought)
    messages: list[Message] = [Message(role="user", content=prompt)]
    async with client:
        if stream:
            async for chunk in client.stream_chat(messages, extra_params=parsed_extra):
                sys.stdout.write(chunk)
                sys.stdout.flush()
        else:
            text, _ = await client.complete_chat(messages)
            print(text)
    print()


def main() -> None:
    """Entry point for the CLI."""
    cli.run(css=CUSTOM_CSS)


def main_tui() -> None:
    """Entry point for the TUI CLI."""
    cli.tui = True
    main()


if __name__ == "__main__":
    main()
