"""Tests for individual news scrapers."""

from pathlib import Path
from unittest.mock import AsyncMock

import httpx

from app.services.scrapers.kab import KABScraper
from app.services.scrapers.nhk_kumamoto import NHKKumamotoScraper
from app.services.scrapers.pref_kumamoto import PrefKumamotoScraper
from app.services.scrapers.rkk import RKKScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- NHK Kumamoto (RSS, excluded from default but class still works) ---


class TestNHKKumamotoScraper:
    """Tests for NHK Kumamoto RSS scraper."""

    def test_parse_rss_extracts_articles(self):
        scraper = NHKKumamotoScraper()
        articles = scraper._parse_rss(_read_fixture("nhk_rss_sample.xml"))
        assert len(articles) == 3

    def test_parse_rss_article_fields(self):
        scraper = NHKKumamotoScraper()
        articles = scraper._parse_rss(_read_fixture("nhk_rss_sample.xml"))
        first = articles[0]
        assert first.title == "熊本市で新しい交通システムの実証実験始まる"
        assert first.url == "https://www3.nhk.or.jp/lnews/kumamoto/20260305/5000012345.html"
        assert first.source_name == "NHK熊本"
        assert first.summary == "熊本市は新しい交通システムの実証実験を開始しました。"
        assert first.published_at is not None

    def test_parse_rss_missing_description(self):
        scraper = NHKKumamotoScraper()
        articles = scraper._parse_rss(_read_fixture("nhk_rss_sample.xml"))
        third = articles[2]
        assert third.title == "県内の小学校で卒業式"
        assert third.summary is None

    async def test_scrape_http_error_returns_error_result(self):
        scraper = NHKKumamotoScraper()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(500),
        )
        result = await scraper.scrape(client)
        assert result.error is not None
        assert result.articles == []


# --- Pref Kumamoto (RSS 1.0 / RDF) ---


class TestPrefKumamotoScraper:
    """Tests for Kumamoto Prefecture RSS scraper."""

    def test_parse_rss_extracts_articles(self):
        scraper = PrefKumamotoScraper()
        articles = scraper._parse_rss(_read_fixture("pref_kumamoto_sample.html"))
        assert len(articles) == 3

    def test_parse_rss_article_fields(self):
        scraper = PrefKumamotoScraper()
        articles = scraper._parse_rss(_read_fixture("pref_kumamoto_sample.html"))
        first = articles[0]
        assert first.title == "令和7年8月豪雨に関する情報"
        assert first.url == "https://www.pref.kumamoto.jp/soshiki/1/243373.html"
        assert first.source_name == "熊本県公式"
        assert first.summary == "豪雨災害に関する最新情報をお伝えします。"
        assert first.published_at is not None

    def test_parse_rss_empty_description(self):
        scraper = PrefKumamotoScraper()
        articles = scraper._parse_rss(_read_fixture("pref_kumamoto_sample.html"))
        second = articles[1]
        assert second.title == "ウェブサイト復旧のお知らせ"
        assert second.summary is None  # empty description

    def test_parse_rss_no_description(self):
        scraper = PrefKumamotoScraper()
        articles = scraper._parse_rss(_read_fixture("pref_kumamoto_sample.html"))
        third = articles[2]
        assert third.title == "インフルエンザ予防のお願い"
        assert third.summary is None  # no description element


# --- RKK (TBS News Dig) ---


class TestRKKScraper:
    """Tests for RKK scraper via TBS News Dig."""

    def test_parse_html_extracts_rkk_articles(self):
        scraper = RKKScraper()
        articles = scraper._parse_html(_read_fixture("rkk_sample.html"))
        assert len(articles) == 3

    def test_parse_html_article_fields(self):
        scraper = RKKScraper()
        articles = scraper._parse_html(_read_fixture("rkk_sample.html"))
        assert articles[0].title == "DV理由に転居の女性　熊本市が前の住所に文書を送る「人的ミス」"
        assert articles[0].url == "https://newsdig.tbs.co.jp/articles/rkk/2510151"
        assert articles[0].source_name == "RKK熊本放送"

    def test_parse_html_skips_non_rkk_articles(self):
        """Should skip articles from /articles/-/ (national news)."""
        scraper = RKKScraper()
        articles = scraper._parse_html(_read_fixture("rkk_sample.html"))
        urls = [a.url for a in articles]
        assert not any("/articles/-/" in u for u in urls)

    def test_parse_html_strips_query_params(self):
        scraper = RKKScraper()
        articles = scraper._parse_html(_read_fixture("rkk_sample.html"))
        for a in articles:
            assert "?" not in a.url


# --- KAB (RSS + HTML fallback) ---


class TestKABScraper:
    """Tests for KAB RSS/HTML scraper."""

    def test_parse_rss_extracts_articles(self):
        scraper = KABScraper()
        articles = scraper._parse_rss(_read_fixture("kab_rss_sample.xml"))
        assert len(articles) == 2

    def test_parse_rss_article_fields(self):
        scraper = KABScraper()
        articles = scraper._parse_rss(_read_fixture("kab_rss_sample.xml"))
        first = articles[0]
        assert first.title == "熊本空港の新ターミナル利用者数100万人突破"
        assert first.url == "https://www.kab.co.jp/news/20260305001/"
        assert first.source_name == "KAB熊本朝日放送"
        assert first.published_at is not None

    def test_parse_html_extracts_only_article_links(self):
        """Should only extract /news/article/DIGITS links."""
        scraper = KABScraper()
        articles = scraper._parse_html(_read_fixture("kab_html_sample.html"))
        assert len(articles) == 3

    def test_parse_html_skips_category_links(self):
        """Should skip /news/kab/*, /news/series/* links."""
        scraper = KABScraper()
        articles = scraper._parse_html(_read_fixture("kab_html_sample.html"))
        urls = [a.url for a in articles]
        assert not any("/news/kab/" in u for u in urls)
        assert not any("/news/series/" in u for u in urls)

    def test_parse_html_article_title_from_h3(self):
        scraper = KABScraper()
        articles = scraper._parse_html(_read_fixture("kab_html_sample.html"))
        assert articles[0].title == "「燃やすごみ」と「埋め立てごみ」同じ指定袋に　熊本市のごみ収集ルール変更を説明"

    async def test_scrape_rss_success_skips_html(self):
        """When RSS succeeds, HTML fallback should not be called."""
        scraper = KABScraper()
        rss_content = _read_fixture("kab_rss_sample.xml")

        client = AsyncMock(spec=httpx.AsyncClient)
        resp = httpx.Response(200, text=rss_content, request=httpx.Request("GET", "http://test"))
        client.get.return_value = resp

        result = await scraper.scrape(client)
        assert result.error is None
        assert len(result.articles) == 2
        client.get.assert_called_once()

    async def test_scrape_rss_failure_falls_back_to_html(self):
        """When RSS fails, should try HTML fallback."""
        scraper = KABScraper()
        html_content = _read_fixture("kab_html_sample.html")

        client = AsyncMock(spec=httpx.AsyncClient)
        rss_error = httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(404),
        )
        html_resp = httpx.Response(200, text=html_content, request=httpx.Request("GET", "http://test"))
        client.get.side_effect = [rss_error, html_resp]

        result = await scraper.scrape(client)
        assert result.error is None
        assert len(result.articles) == 3
        assert client.get.call_count == 2
