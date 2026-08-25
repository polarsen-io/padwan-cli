from rich.console import Console

from padwan_llm import (
    ANTHROPIC_MODELS,
    GEMINI_MODELS,
    GROK_MODELS,
    MISTRAL_MODELS,
    OPENAI_MODELS,
)

console = Console()

ALL_MODELS = sorted(
    [
        *OPENAI_MODELS,
        *GEMINI_MODELS,
        *MISTRAL_MODELS,
        *GROK_MODELS,
        *ANTHROPIC_MODELS,
    ]
)
