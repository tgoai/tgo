"""
Web crawler service using crawl4ai.

This module provides website crawling functionality for RAG document generation,
utilizing the crawl4ai library for efficient and LLM-friendly content extraction.

Uses crawl4ai's built-in deep crawling strategies for optimal performance.
"""

import fnmatch
import hashlib
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter

from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CrawlOptions:
    """Configuration options for web crawling."""

    render_js: bool = False
    respect_robots_txt: bool = True
    delay_seconds: float = 1.0
    user_agent: Optional[str] = None
    timeout_seconds: int = 30
    headers: Optional[Dict[str, str]] = None


@dataclass
class CrawledPage:
    """Represents a crawled web page."""

    url: str
    url_hash: str
    title: Optional[str]
    content_markdown: str
    content_length: int
    content_hash: str
    meta_description: Optional[str]
    http_status_code: int
    depth: int
    links: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


def url_hash(url: str) -> str:
    """Generate SHA-256 hash of URL."""
    return hashlib.sha256(url.encode()).hexdigest()


def content_hash(content: str) -> str:
    """Generate SHA-256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


class WebCrawlerService:
    """
    Website crawler service using crawl4ai's built-in deep crawling.

    This service provides async website crawling with:
    - BFS deep crawling strategy (native crawl4ai)
    - Depth-limited crawling via max_depth
    - URL pattern filtering via FilterChain
    - Content extraction optimized for RAG
    - Rate limiting via delay_between_requests
    - Automatic deduplication
    """

    def __init__(
        self,
        start_url: str,
        max_pages: int = 100,
        max_depth: int = 3,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        options: Optional[CrawlOptions] = None,
    ):
        self.start_url = start_url
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.options = options or CrawlOptions()

        # Tracking
        self._pages_crawled = 0
        self._pages_discovered = 0

    def _should_exclude(self, url: str) -> bool:
        """Check if URL matches any exclude pattern."""
        return any(fnmatch.fnmatch(url, pattern) for pattern in self.exclude_patterns)

    def _extract_links(self, result) -> List[str]:
        """Extract internal links from crawl result."""
        links = []
        if not result.links:
            return links

        for link_info in result.links.get("internal", []):
            link_url = link_info.get("href") if isinstance(link_info, dict) else str(link_info)
            if link_url:
                links.append(link_url)

        return list(set(links))

    def _build_crawled_page(self, result, depth: int) -> CrawledPage:
        """Build CrawledPage from crawl4ai result."""
        markdown_content = result.markdown or ""
        metadata = result.metadata or {}

        return CrawledPage(
            url=result.url,
            url_hash=url_hash(result.url),
            title=metadata.get("title"),
            content_markdown=markdown_content,
            content_length=len(markdown_content),
            content_hash=content_hash(markdown_content),
            meta_description=metadata.get("description"),
            http_status_code=result.status_code or 200,
            depth=depth,
            links=self._extract_links(result),
            metadata={
                "crawled_at": time.time(),
                "word_count": len(markdown_content.split()),
                "score": metadata.get("score"),
            }
        )

    def _get_browser_config(self) -> BrowserConfig:
        """Create browser configuration."""
        config = BrowserConfig(
            headless=True,
            verbose=False,
        )

        if self.options.user_agent:
            config.user_agent = self.options.user_agent

        return config

    async def crawl_website(self) -> AsyncGenerator[CrawledPage, None]:
        """
        Crawl website using crawl4ai's native deep crawling.

        Uses BFSDeepCrawlStrategy for breadth-first exploration with:
        - max_depth: Controls crawl depth
        - max_pages: Limits total pages crawled
        - include_external=False: Stay within same domain

        Yields:
            CrawledPage objects for each successfully crawled page
        """
        # Build filter chain for URL patterns
        filter_chain = None
        if self.include_patterns:
            try:
                filter_chain = FilterChain([
                    URLPatternFilter(patterns=self.include_patterns)
                ])
            except Exception as e:
                logger.warning(f"Failed to create filter chain: {e}")

        # Configure deep crawl strategy (BFS - breadth first)
        deep_crawl_strategy = BFSDeepCrawlStrategy(
            max_depth=self.max_depth,
            max_pages=self.max_pages,
            include_external=False,
            filter_chain=filter_chain,
        )

        # Configure crawler run
        run_config = CrawlerRunConfig(
            deep_crawl_strategy=deep_crawl_strategy,
            scraping_strategy=LXMLWebScrapingStrategy(),
            word_count_threshold=10,
            remove_overlay_elements=True,
            exclude_external_links=True,
            verbose=False,
        )

        logger.info(
            f"Starting deep crawl of {self.start_url} "
            f"(max_depth={self.max_depth}, max_pages={self.max_pages})"
        )

        async with AsyncWebCrawler(config=self._get_browser_config()) as crawler:
            results = await crawler.arun(url=self.start_url, config=run_config)

            # Ensure results is iterable
            if not isinstance(results, list):
                results = [results]

            for result in results:
                if not result.success:
                    logger.warning(f"Failed to crawl {result.url}: {result.error_message}")
                    continue

                if self._should_exclude(result.url):
                    logger.debug(f"Skipping excluded URL: {result.url}")
                    continue

                self._pages_crawled += 1
                depth = (result.metadata or {}).get("depth", 0)

                logger.info(
                    f"Crawled page {self._pages_crawled}/{self.max_pages}: "
                    f"{result.url} (depth={depth})"
                )

                page = self._build_crawled_page(result, depth)
                self._pages_discovered += len(page.links)

                yield page

        logger.info(f"Deep crawl completed. Total pages: {self._pages_crawled}")

    async def crawl_page(self, url: str, depth: int = 0) -> Optional[CrawledPage]:
        """
        Crawl a single page using crawl4ai.

        This method is for crawling individual pages outside of deep crawl.
        For full website crawling, use crawl_website() instead.

        Args:
            url: URL to crawl
            depth: Current depth from start URL

        Returns:
            CrawledPage object or None if crawl failed
        """
        try:
            run_config = CrawlerRunConfig(
                word_count_threshold=10,
                remove_overlay_elements=True,
                exclude_external_links=True,
            )

            async with AsyncWebCrawler(config=self._get_browser_config()) as crawler:
                result = await crawler.arun(url=url, config=run_config)

                if not result.success:
                    logger.warning(f"Failed to crawl {url}: {result.error_message}")
                    return None

                return self._build_crawled_page(result, depth)

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None

    @property
    def pages_crawled(self) -> int:
        """Get number of pages crawled so far."""
        return self._pages_crawled

    @property
    def pages_discovered(self) -> int:
        """Get number of pages discovered so far."""
        return self._pages_discovered

