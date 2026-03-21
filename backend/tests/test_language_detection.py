"""Tests for language detection in CollectorStep."""

from app.pipeline.collector import CollectorStep


class TestLanguageDetection:
    """Tests for the _detect_language static method."""

    def test_japanese_text(self):
        text = "これは日本語のニュース記事です。熊本県で大規模な地震が発生しました。"
        assert CollectorStep._detect_language(text) == "ja"

    def test_english_text(self):
        text = "This is an English news article about technology and innovation."
        assert CollectorStep._detect_language(text) == "en"

    def test_chinese_text(self):
        text = "这是一篇关于科技创新的中文新闻文章。中国经济持续增长。"
        assert CollectorStep._detect_language(text) == "zh"

    def test_korean_text(self):
        text = "이것은 한국어 뉴스 기사입니다. 서울에서 중요한 회의가 열렸습니다."
        assert CollectorStep._detect_language(text) == "ko"

    def test_empty_text(self):
        assert CollectorStep._detect_language("") == "en"

    def test_mixed_japanese_english(self):
        text = "AIニュースラジオは最新のテクノロジーニュースをお届けします。"
        assert CollectorStep._detect_language(text) == "ja"
