"""Script-based language detection using Unicode ranges."""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Unicode ranges for Indian scripts
SCRIPT_RANGES: dict[str, tuple[int, int]] = {
    "devanagari": (0x0900, 0x097F),
    "tamil": (0x0B80, 0x0BFF),
    "telugu": (0x0C00, 0x0C7F),
    "kannada": (0x0C80, 0x0CFF),
    "malayalam": (0x0D00, 0x0D7F),
    "bengali": (0x0980, 0x09FF),
    "gujarati": (0x0A80, 0x0AFF),
    "gurmukhi": (0x0A00, 0x0A7F),  # Punjabi
}

# Script -> default language mapping
SCRIPT_TO_LANG: dict[str, str] = {
    "devanagari": "hi",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
    "bengali": "bn",
    "gujarati": "gu",
    "gurmukhi": "pa",
}

# Common Marathi marker words (to distinguish from Hindi)
MARATHI_MARKERS: set[str] = {
    "माझे", "माझा", "माझी", "आहे", "आहेत", "करतो", "करते",
    "करतात", "नाव", "मला", "तुम्ही", "तुमचे", "आम्ही",
    "होतो", "होते", "होती", "केले", "केला", "केली",
    "हे", "ही", "हा", "त्या", "या", "ते",
}

# Common Hindi marker words (to distinguish from Marathi)
HINDI_MARKERS: set[str] = {
    "मेरा", "मेरी", "मेरे", "है", "हैं", "करता", "करती",
    "करते", "नाम", "मुझे", "आप", "आपका", "हम",
    "था", "थी", "थे", "किया", "की", "किये",
    "यह", "वह", "इस", "उस", "को", "से", "में",
}


@dataclass
class LanguageResult:
    """Result of language detection."""
    language_code: str
    confidence: float
    mixed_script: bool


def _count_script_chars(text: str) -> dict[str, int]:
    """Count characters belonging to each script."""
    counts: dict[str, int] = {}
    for char in text:
        code_point = ord(char)
        for script, (start, end) in SCRIPT_RANGES.items():
            if start <= code_point <= end:
                counts[script] = counts.get(script, 0) + 1
                break
    return counts


def _has_latin(text: str) -> bool:
    """Check if text contains Latin script characters."""
    return bool(re.search(r"[a-zA-Z]", text))


def _distinguish_devanagari(text: str) -> str:
    """Distinguish Marathi from Hindi for Devanagari text."""
    words = set(text.split())
    marathi_score = len(words & MARATHI_MARKERS)
    hindi_score = len(words & HINDI_MARKERS)

    if marathi_score > hindi_score:
        return "mr"
    return "hi"


async def detect(text: str) -> LanguageResult:
    """Detect language from text using script analysis.

    Args:
        text: input text to analyse.

    Returns:
        LanguageResult with language_code, confidence, and mixed_script flag.
    """
    if not text or not text.strip():
        return LanguageResult(language_code="hi", confidence=0.0, mixed_script=False)

    text = text.strip()
    script_counts = _count_script_chars(text)
    has_latin = _has_latin(text)
    total_script_chars = sum(script_counts.values())

    # Pure Latin text (no Indian scripts detected) — default to Hindi (Hinglish)
    if total_script_chars == 0 and has_latin:
        return LanguageResult(language_code="hi", confidence=0.5, mixed_script=True)

    # No recognisable characters at all
    if total_script_chars == 0:
        return LanguageResult(language_code="hi", confidence=0.1, mixed_script=False)

    # Find dominant script
    dominant_script = max(script_counts, key=script_counts.get)  # type: ignore[arg-type]
    dominant_count = script_counts[dominant_script]
    confidence = dominant_count / max(total_script_chars, 1)

    # Mixed script detection: Latin + Indian script
    mixed_script = has_latin and total_script_chars > 0

    # Map script to language
    lang = SCRIPT_TO_LANG.get(dominant_script, "hi")

    # For Devanagari, distinguish Marathi vs Hindi
    if dominant_script == "devanagari":
        lang = _distinguish_devanagari(text)
        # Lower confidence slightly if short text (harder to distinguish)
        word_count = len(text.split())
        if word_count <= 3:
            confidence = min(confidence, 0.7)

    # Adjust confidence for mixed script
    if mixed_script:
        confidence *= 0.8

    return LanguageResult(
        language_code=lang,
        confidence=round(min(confidence, 1.0), 2),
        mixed_script=mixed_script,
    )
