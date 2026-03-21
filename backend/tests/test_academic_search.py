"""Tests for AcademicSearchService."""

from app.services.academic_search import AcademicSearchService


class TestArxivParsing:
    """Tests for arXiv XML response parsing."""

    def test_parse_arxiv_response(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Test Paper Title</title>
            <summary>This is the abstract of the test paper.</summary>
            <published>2024-01-15T00:00:00Z</published>
            <author><name>John Doe</name></author>
            <author><name>Jane Smith</name></author>
            <link href="http://arxiv.org/abs/2401.12345" rel="alternate" type="text/html"/>
          </entry>
        </feed>"""

        papers = AcademicSearchService._parse_arxiv_response(xml)
        assert len(papers) == 1
        assert papers[0].title == "Test Paper Title"
        assert papers[0].abstract == "This is the abstract of the test paper."
        assert papers[0].year == 2024
        assert papers[0].authors == ["John Doe", "Jane Smith"]
        assert papers[0].url == "http://arxiv.org/abs/2401.12345"
        assert papers[0].source == "arxiv"

    def test_parse_empty_response(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
        </feed>"""
        papers = AcademicSearchService._parse_arxiv_response(xml)
        assert len(papers) == 0

    def test_parse_invalid_xml(self):
        papers = AcademicSearchService._parse_arxiv_response("not xml")
        assert len(papers) == 0
