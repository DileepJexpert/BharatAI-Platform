"""Tests for core/language/detector.py — LANG-001 through LANG-005."""

import pytest

from core.language.detector import detect, LanguageResult


class TestLANG001Hindi:
    """LANG-001: Hindi detection — Devanagari text → 'hi', confidence > 0.9."""

    @pytest.mark.asyncio
    async def test_hindi_devanagari(self):
        result = await detect("मरीज़ का नाम राम है और उसे बुखार है")
        assert result.language_code == "hi"
        assert result.confidence > 0.9
        assert result.mixed_script is False

    @pytest.mark.asyncio
    async def test_hindi_longer_text(self):
        result = await detect("मेरा नाम राम है और मुझे बुखार है, मैं अस्पताल जाना चाहता हूँ")
        assert result.language_code == "hi"
        assert result.confidence > 0.9


class TestLANG002MarathiVsHindi:
    """LANG-002: Marathi vs Hindi — 'माझे नाव...' → 'mr', not 'hi'."""

    @pytest.mark.asyncio
    async def test_marathi_detection(self):
        result = await detect("माझे नाव सुरेश आहे आणि मला ताप आहे")
        assert result.language_code == "mr"
        assert result.mixed_script is False

    @pytest.mark.asyncio
    async def test_marathi_markers(self):
        result = await detect("मला सांगा करतो आहे माझा")
        assert result.language_code == "mr"


class TestLANG003Hinglish:
    """LANG-003: Hinglish — 'patient ka fever hai' → 'hi', mixed_script: true."""

    @pytest.mark.asyncio
    async def test_hinglish_code_mix(self):
        result = await detect("patient ka fever hai")
        assert result.language_code == "hi"
        assert result.mixed_script is True

    @pytest.mark.asyncio
    async def test_hinglish_with_devanagari(self):
        result = await detect("patient का fever है")
        assert result.language_code == "hi"
        assert result.mixed_script is True


class TestLANG004Tamil:
    """LANG-004: Tamil detection — Tamil script → 'ta'."""

    @pytest.mark.asyncio
    async def test_tamil_script(self):
        result = await detect("என் பெயர் ராம்")
        assert result.language_code == "ta"
        assert result.mixed_script is False

    @pytest.mark.asyncio
    async def test_tamil_longer(self):
        result = await detect("நான் மருத்துவமனைக்கு செல்ல வேண்டும்")
        assert result.language_code == "ta"


class TestLANG005SingleWord:
    """LANG-005: Single word — 'हाँ' → returns result, no exception."""

    @pytest.mark.asyncio
    async def test_single_word(self):
        result = await detect("हाँ")
        assert isinstance(result, LanguageResult)
        assert result.language_code in ("hi", "mr")
        assert isinstance(result.confidence, float)

    @pytest.mark.asyncio
    async def test_empty_string(self):
        result = await detect("")
        assert isinstance(result, LanguageResult)
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_only(self):
        result = await detect("   ")
        assert isinstance(result, LanguageResult)
        assert result.confidence == 0.0


class TestLanguageDetectorEdgeCases:
    """Additional edge case tests."""

    @pytest.mark.asyncio
    async def test_bengali(self):
        result = await detect("আমার নাম রাম")
        assert result.language_code == "bn"

    @pytest.mark.asyncio
    async def test_telugu(self):
        result = await detect("నా పేరు రాము")
        assert result.language_code == "te"

    @pytest.mark.asyncio
    async def test_gujarati(self):
        result = await detect("મારું નામ રામ છે")
        assert result.language_code == "gu"

    @pytest.mark.asyncio
    async def test_pure_english(self):
        result = await detect("My name is Ram")
        assert result.language_code == "hi"  # defaults to Hindi for Latin
        assert result.mixed_script is True
