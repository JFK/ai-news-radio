"""Tests for TTS utility functions."""

from app.services.tts_utils import expand_reading_hints


class TestExpandReadingHints:
    """Tests for reading hint expansion."""

    def test_basic_expansion(self):
        """Kanji with hiragana reading in parens should be replaced."""
        assert expand_reading_hints("健軍（けんぐん）駐屯地") == "けんぐん駐屯地"

    def test_multiple_hints(self):
        """Multiple reading hints in one text."""
        text = "菊陽町（きくようまち）の合志市（こうしし）で"
        assert expand_reading_hints(text) == "きくようまちのこうししで"

    def test_katakana_reading(self):
        """Katakana readings should also be expanded."""
        assert expand_reading_hints("TSMC（ティーエスエムシー）") == "ティーエスエムシー"

    def test_non_reading_parens_preserved(self):
        """Parentheses with non-kana content should be left alone."""
        text = "熊本市（人口73万人）では"
        assert expand_reading_hints(text) == "熊本市（人口73万人）では"

    def test_empty_string(self):
        assert expand_reading_hints("") == ""

    def test_no_hints(self):
        """Text without reading hints should be unchanged."""
        text = "熊本市の公共交通計画について"
        assert expand_reading_hints(text) == text

    def test_mixed_content(self):
        """Mix of reading hints and regular parentheses."""
        text = "健軍（けんぐん）駐屯地（約500人が勤務）では"
        result = expand_reading_hints(text)
        assert "けんぐん" in result
        assert "約500人が勤務" in result
