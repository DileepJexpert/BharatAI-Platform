"""Translation stub — IndicTrans2 integration planned for post-MVP."""

import logging

logger = logging.getLogger(__name__)


class TranslationNotAvailableError(Exception):
    """Raised when translation is called but not yet implemented."""
    pass


async def translate(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text between Indian languages.

    MVP: stub that returns the original text.
    Post-MVP: will use IndicTrans2.

    Args:
        text: text to translate.
        source_lang: source ISO 639-1 code.
        target_lang: target ISO 639-1 code.

    Returns:
        Translated text (MVP: returns original text unchanged).
    """
    if source_lang == target_lang:
        return text

    logger.warning(
        "Translation not implemented (MVP stub). "
        "Returning original text. source=%s target=%s",
        source_lang, target_lang,
    )
    return text
