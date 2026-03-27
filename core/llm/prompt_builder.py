"""Build the messages array for Ollama from plugin prompts and conversation history."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Max conversation history turns to include
MAX_HISTORY_TURNS: int = 5


def build_messages(
    system_prompt: str,
    user_text: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build the Ollama messages array.

    Args:
        system_prompt: the system prompt from the plugin.
        user_text: current user input.
        conversation_history: previous turns [{'role': 'user'|'assistant', 'text': '...'}].

    Returns:
        List of message dicts with 'role' and 'content' keys.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    # Add conversation history (trimmed to max turns)
    if conversation_history:
        recent = conversation_history[-(MAX_HISTORY_TURNS * 2):]
        for turn in recent:
            role = turn.get("role", "user")
            text = turn.get("text", "")
            if role in ("user", "assistant") and text:
                messages.append({"role": role, "content": text})

    # Add current user message
    messages.append({"role": "user", "content": user_text})

    return messages


def build_system_prompt(
    template: str,
    language: str,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """Render a system prompt template with language and optional context.

    Args:
        template: prompt template with {language} placeholder.
        language: ISO 639-1 code.
        extra_context: additional key-value pairs for formatting.

    Returns:
        Rendered system prompt string.
    """
    context = {"language": language}
    if extra_context:
        context.update(extra_context)

    try:
        return template.format(**context)
    except KeyError as exc:
        logger.warning("Prompt template has unresolved placeholder: %s", exc)
        return template.replace("{language}", language)
