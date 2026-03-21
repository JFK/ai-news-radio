"""Academic paper search service using Semantic Scholar and arXiv APIs.

Both APIs are free and do not require API keys.
Semantic Scholar: 100 requests per 5 minutes rate limit.
arXiv: No strict rate limit but requests should be polite.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_API = "http://export.arxiv.org/api/query"


@dataclass
class AcademicPaper:
    """A single academic paper result."""

    title: str
    abstract: str
    authors: list[str]
    year: int | None
    url: str
    doi: str | None = None
    source: str = ""  # "semantic_scholar" or "arxiv"


@dataclass
class AcademicSearchResult:
    """Result of an academic search query."""

    query: str
    papers: list[AcademicPaper] = field(default_factory=list)
    success: bool = True
    error: str | None = None


class AcademicSearchService:
    """Search academic papers via Semantic Scholar and arXiv."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout
        self._request_count = 0

    @property
    def request_count(self) -> int:
        """Total API requests made."""
        return self._request_count

    async def search(
        self,
        query: str,
        max_results: int = 5,
        sources: list[str] | None = None,
    ) -> AcademicSearchResult:
        """Search for academic papers.

        Args:
            query: Search query string.
            max_results: Maximum papers to return per source.
            sources: List of sources to use. Defaults to ["semantic_scholar", "arxiv"].

        Returns:
            AcademicSearchResult with found papers.
        """
        if sources is None:
            sources = ["semantic_scholar", "arxiv"]

        all_papers: list[AcademicPaper] = []
        errors: list[str] = []

        tasks = []
        if "semantic_scholar" in sources:
            tasks.append(self._search_semantic_scholar(query, max_results))
        if "arxiv" in sources:
            tasks.append(self._search_arxiv(query, max_results))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif isinstance(result, list):
                all_papers.extend(result)

        return AcademicSearchResult(
            query=query,
            papers=all_papers,
            success=len(errors) == 0,
            error="; ".join(errors) if errors else None,
        )

    async def _search_semantic_scholar(self, query: str, max_results: int) -> list[AcademicPaper]:
        """Search Semantic Scholar API."""
        papers: list[AcademicPaper] = []
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                self._request_count += 1
                response = await client.get(
                    SEMANTIC_SCHOLAR_API,
                    params={
                        "query": query,
                        "limit": max_results,
                        "fields": "title,abstract,authors,year,externalIds,url",
                    },
                )
                response.raise_for_status()
                data = response.json()

            for paper_data in data.get("data", []):
                external_ids = paper_data.get("externalIds") or {}
                doi = external_ids.get("DOI")
                arxiv_id = external_ids.get("ArXiv")

                # Build URL: prefer DOI, then arXiv, then Semantic Scholar
                url = paper_data.get("url", "")
                if doi:
                    url = f"https://doi.org/{doi}"
                elif arxiv_id:
                    url = f"https://arxiv.org/abs/{arxiv_id}"

                authors = [a.get("name", "") for a in (paper_data.get("authors") or [])]

                papers.append(
                    AcademicPaper(
                        title=paper_data.get("title", ""),
                        abstract=paper_data.get("abstract") or "",
                        authors=authors[:5],  # limit to 5 authors
                        year=paper_data.get("year"),
                        url=url,
                        doi=doi,
                        source="semantic_scholar",
                    )
                )
        except Exception as e:
            logger.warning("Semantic Scholar search failed for '%s': %s", query, e)
            raise

        return papers

    async def _search_arxiv(self, query: str, max_results: int) -> list[AcademicPaper]:
        """Search arXiv API."""
        papers: list[AcademicPaper] = []
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                self._request_count += 1
                response = await client.get(
                    ARXIV_API,
                    params={
                        "search_query": f"all:{query}",
                        "start": 0,
                        "max_results": max_results,
                        "sortBy": "relevance",
                        "sortOrder": "descending",
                    },
                )
                response.raise_for_status()

            # Parse Atom XML response
            papers = self._parse_arxiv_response(response.text)
        except Exception as e:
            logger.warning("arXiv search failed for '%s': %s", query, e)
            raise

        return papers

    @staticmethod
    def _parse_arxiv_response(xml_text: str) -> list[AcademicPaper]:
        """Parse arXiv Atom XML response into AcademicPaper list."""
        import xml.etree.ElementTree as ET

        papers: list[AcademicPaper] = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return papers

        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)

            title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
            abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""

            # Extract year from published date
            year = None
            if published_el is not None and published_el.text:
                with contextlib.suppress(ValueError, IndexError):
                    year = int(published_el.text[:4])

            # Get authors
            authors = []
            for author_el in entry.findall("atom:author", ns):
                name_el = author_el.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text)

            # Get URL (prefer abs link)
            url = ""
            for link_el in entry.findall("atom:link", ns):
                if link_el.get("type") == "text/html" or link_el.get("rel") == "alternate":
                    url = link_el.get("href", "")
                    break
            if not url:
                id_el = entry.find("atom:id", ns)
                url = (id_el.text or "") if id_el is not None else ""

            # Extract DOI if present
            doi = None
            doi_el = entry.find("{http://arxiv.org/schemas/atom}doi")
            if doi_el is not None and doi_el.text:
                doi = doi_el.text

            if title:
                papers.append(
                    AcademicPaper(
                        title=title,
                        abstract=abstract,
                        authors=authors[:5],
                        year=year,
                        url=url,
                        doi=doi,
                        source="arxiv",
                    )
                )

        return papers
