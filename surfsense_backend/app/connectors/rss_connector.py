"""
RSS Feed Connector for fetching and parsing RSS/Atom feeds.

Supports:
- RSS 1.0, 2.0, and Atom feeds
- OPML file import
- Feed health checking
- Deduplication via GUIDs and content hashing
"""

import asyncio
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

import feedparser
import httpx
from fastapi import HTTPException
from markdownify import markdownify as md

from app.utils.url_validator import format_ip_for_url, validate_url_safe_for_ssrf, is_ip_blocked

logger = logging.getLogger(__name__)


class RSSConnector:
    """Client for fetching and parsing RSS/Atom feeds."""

    def __init__(self, feed_urls: list[str], timeout: int = 30):
        """
        Initialize RSS connector.

        Args:
            feed_urls: List of RSS/Atom feed URLs
            timeout: Request timeout in seconds
        """
        self.feed_urls = feed_urls
        self.timeout = timeout
        self.max_redirects = 5  # Limit redirect chains

    async def _validate_redirect_url(self, url: str) -> list[str] | None:
        """
        Validate a redirect URL to prevent SSRF attacks.

        Args:
            url: The redirect URL to validate

        Returns:
            List of validated IP addresses if hostname resolved, or None if already an IP

        Raises:
            HTTPException: If URL is unsafe (private IP, metadata endpoint, etc.)
        """
        try:
            # Use the centralized validator which handles:
            # - Scheme validation (http/https)
            # - Blocked IPs and hostnames
            # - IPv6 support
            # - DNS resolution to check for private IPs (anti-rebinding)
            _, validated_ips = await validate_url_safe_for_ssrf(url, allow_private=False)
            logger.debug(f"Redirect URL validated: {url}")
            return validated_ips

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating redirect URL {url}: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid redirect URL: {url}"
            ) from e

    async def _safe_get_with_redirects(
        self, client: httpx.AsyncClient, url: str, headers: dict
    ) -> httpx.Response:
        """
        Safely follow redirects with SSRF validation on each redirect.

        Args:
            client: httpx AsyncClient instance
            url: Initial URL to fetch (must be pre-validated!)
            headers: Request headers

        Returns:
            Final HTTP response after following safe redirects

        Raises:
            HTTPException: If any redirect URL is unsafe or max redirects exceeded
        """
        # Defensive: re-validate the initial URL here to ensure SSRF protection
        try:
            validated_url, validated_ips = await validate_url_safe_for_ssrf(url, allow_private=False)
        except HTTPException as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid initial URL for redirect handling: {e.detail}",
            ) from e

        # If validation returned specific IPs, lock the request to the first IP
        current_url = validated_url
        if validated_ips:
            parsed_initial = urlparse(validated_url)
            ip_formatted = format_ip_for_url(validated_ips[0])

            current_url = f"{parsed_initial.scheme}://{ip_formatted}"
            if parsed_initial.port:
                current_url += f":{parsed_initial.port}"
            current_url += parsed_initial.path or "/"
            if parsed_initial.query:
                current_url += f"?{parsed_initial.query}"

            # Ensure Host header reflects the original hostname
            headers["Host"] = parsed_initial.hostname or headers.get("Host")

        redirect_count = 0

        while redirect_count < self.max_redirects:
            # Perform the request
            if not isinstance(current_url, str) or not current_url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid redirect URL detected: {current_url}")

            response = await client.get(current_url, headers=headers, follow_redirects=False)

            # If not a redirect, return the response
            if response.status_code not in (301, 302, 303, 307, 308):
                return response

            # Extract redirect location
            location = response.headers.get("location")
            if not location:
                raise HTTPException(
                    status_code=500,
                    detail="Server returned redirect without Location header"
                )

            # Resolve relative URLs
            from urllib.parse import urljoin
            redirect_url = urljoin(str(response.url), location)

            # Validate the redirect URL for SSRF and get resolved IPs
            logger.info(f"Validating redirect from {current_url} to {redirect_url}")
            validated_ips = await self._validate_redirect_url(redirect_url)

            # Construct safe URL using validated IP to prevent DNS rebinding (TOCTOU)
            if validated_ips:
                parsed = urlparse(redirect_url)
                ip_formatted = format_ip_for_url(validated_ips[0])

                target_url = f"{parsed.scheme}://{ip_formatted}"
                if parsed.port:
                    target_url += f":{parsed.port}"
                target_url += parsed.path or "/"
                if parsed.query:
                    target_url += f"?{parsed.query}"

                # Update Host header for the redirected request
                headers["Host"] = parsed.hostname
                current_url = target_url
            else:
                # Hostname is likely an IP address already or validation returned None
                current_url = redirect_url

            redirect_count += 1

        # Max redirects exceeded
        raise HTTPException(
            status_code=400,
            detail=f"Too many redirects (max {self.max_redirects})"
        )

    @staticmethod
    def parse_opml(opml_content: str) -> list[dict[str, str]]:
        """
        Parse OPML file content to extract feed URLs.

        Args:
            opml_content: OPML XML content as string

        Returns:
            List of dicts with feed info (url, title, category)
        """
        feeds = []
        try:
            root = ET.fromstring(opml_content)

            # Build parent map to find parent elements (ElementTree doesn't support "..")
            parent_map = {child: parent for parent in root.iter() for child in parent}

            # Find all outline elements with xmlUrl attribute (these are feeds)
            for outline in root.iter("outline"):
                xml_url = outline.get("xmlUrl")
                if xml_url:
                    feed_info = {
                        "url": xml_url,
                        "title": outline.get("title") or outline.get("text") or xml_url,
                        "html_url": outline.get("htmlUrl", ""),
                        "category": "",
                    }

                    # Try to get category from parent outline
                    parent = parent_map.get(outline)
                    if parent is not None and parent.get("text"):
                        feed_info["category"] = parent.get("text", "")

                    feeds.append(feed_info)

            logger.info(f"Parsed {len(feeds)} feeds from OPML")
            return feeds

        except ET.ParseError as e:
            logger.error(f"Failed to parse OPML: {e}")
            raise ValueError(f"Invalid OPML format: {e}") from e

    async def validate_feed(
        self, url: str, validated_ips: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Validate a feed URL and check its health.

        Args:
            url: Feed URL to validate
            validated_ips: Pre-validated IP addresses to prevent DNS rebinding (TOCTOU protection)

        Returns:
            Dict with validation results (valid, title, last_updated, item_count, error)
        """
        result = {
            "url": url,
            "valid": False,
            "title": "",
            "last_updated": None,
            "item_count": 0,
            "error": None,
        }

        # Validate URL for SSRF protection (unless already validated externally)
        if not validated_ips:
            try:
                url, validated_ips = await validate_url_safe_for_ssrf(url, allow_private=False)
            except HTTPException as e:
                result["error"] = e.detail
                return result

        try:
            # Build request URL using validated IPs if available
            if validated_ips:
                parsed = urlparse(url)
                ip_formatted = format_ip_for_url(validated_ips[0])

                target_url = f"{parsed.scheme}://{ip_formatted}"
                if parsed.port:
                    target_url += f":{parsed.port}"
                target_url += parsed.path or "/"
                if parsed.query:
                    target_url += f"?{parsed.query}"

                headers = {
                    "User-Agent": "SurfSense RSS Reader/1.0",
                    "Host": parsed.hostname,
                }
            else:
                target_url = url
                headers = {"User-Agent": "SurfSense RSS Reader/1.0"}

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Use safe redirect handling to validate each redirect URL
                response = await self._safe_get_with_redirects(
                    client,
                    target_url,
                    headers,
                )
                response.raise_for_status()

                # Parse the feed
                feed = feedparser.parse(response.text)

                if feed.bozo and not feed.entries:
                    result["error"] = str(feed.bozo_exception)
                    return result

                result["valid"] = True
                result["title"] = feed.feed.get("title", url)
                result["item_count"] = len(feed.entries)

                # Check last updated
                if feed.feed.get("updated_parsed"):
                    result["last_updated"] = datetime(
                        *feed.feed.updated_parsed[:6],
                        tzinfo=timezone.utc
                    ).isoformat()
                elif feed.entries and feed.entries[0].get("published_parsed"):
                    result["last_updated"] = datetime(
                        *feed.entries[0].published_parsed[:6],
                        tzinfo=timezone.utc
                    ).isoformat()

                # Check if feed seems dead (no items or very old)
                if result["item_count"] == 0:
                    result["error"] = "Feed has no items"
                    result["valid"] = False

        except httpx.HTTPStatusError as e:
            result["error"] = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
        except httpx.RequestError as e:
            result["error"] = f"Request failed: {str(e)}"
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"

        return result

    async def fetch_feed(
        self, url: str, validated_ips: list[str] | None = None
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """
        Fetch and parse a single feed.

        Args:
            url: Feed URL
            validated_ips: Pre-validated IP addresses to prevent DNS rebinding (TOCTOU protection)

        Returns:
            Tuple of (feed_info, list of entries)
        """
        # Validate URL for SSRF protection (unless already validated externally)
        if not validated_ips:
            try:
                url, validated_ips = await validate_url_safe_for_ssrf(url, allow_private=False)
            except HTTPException as e:
                logger.warning(f"Unsafe URL rejected: {url} - {e.detail}")
                return None, []

        try:
            # Build request URL using validated IPs if available
            if validated_ips:
                parsed = urlparse(url)
                ip_formatted = format_ip_for_url(validated_ips[0])

                target_url = f"{parsed.scheme}://{ip_formatted}"
                if parsed.port:
                    target_url += f":{parsed.port}"
                target_url += parsed.path or "/"
                if parsed.query:
                    target_url += f"?{parsed.query}"

                headers = {
                    "User-Agent": "SurfSense RSS Reader/1.0",
                    "Host": parsed.hostname,
                }
            else:
                target_url = url
                headers = {"User-Agent": "SurfSense RSS Reader/1.0"}

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Use safe redirect handling to validate each redirect URL
                response = await self._safe_get_with_redirects(
                    client,
                    target_url,
                    headers,
                )
                response.raise_for_status()

                feed = feedparser.parse(response.text)

                if feed.bozo and not feed.entries:
                    logger.warning(f"Feed parse error for {url}: {feed.bozo_exception}")
                    return None, []

                feed_info = {
                    "title": feed.feed.get("title", url),
                    "link": feed.feed.get("link", url),
                    "description": feed.feed.get("description", ""),
                    "url": url,
                }

                entries = []
                for entry in feed.entries:
                    parsed_entry = self._parse_entry(entry, feed_info)
                    if parsed_entry:
                        entries.append(parsed_entry)

                return feed_info, entries

        except Exception as e:
            logger.error(f"Failed to fetch feed {url}: {e}")
            return None, []

    def _parse_entry(self, entry: Any, feed_info: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse a feed entry into a standardized format.

        Args:
            entry: feedparser entry object
            feed_info: Parent feed information

        Returns:
            Parsed entry dict or None
        """
        try:
            # Get published date
            published = None
            if entry.get("published_parsed"):
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif entry.get("updated_parsed"):
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                published = datetime.now(timezone.utc)

            # Get content
            content = ""
            if entry.get("content"):
                content = entry.content[0].get("value", "")
            elif entry.get("summary"):
                content = entry.summary
            elif entry.get("description"):
                content = entry.description

            # Generate unique identifier for deduplication
            guid = entry.get("id") or entry.get("guid") or entry.get("link", "")
            unique_id = self._generate_unique_id(
                guid=guid,
                title=entry.get("title", ""),
                link=entry.get("link", ""),
                published=published.isoformat() if published else ""
            )

            return {
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link", ""),
                "content": content,
                "summary": entry.get("summary", ""),
                "published": published.isoformat() if published else None,
                "author": entry.get("author", ""),
                "guid": guid,
                "unique_id": unique_id,
                "feed_title": feed_info["title"],
                "feed_url": feed_info["url"],
                "categories": [tag.term for tag in entry.get("tags", [])],
            }

        except Exception as e:
            logger.error(f"Failed to parse entry: {e}")
            return None

    @staticmethod
    def _generate_unique_id(guid: str, title: str, link: str, published: str) -> str:
        """
        Generate a unique identifier for deduplication.

        Primary: Use GUID if available
        Fallback: Hash of title + link + published date
        """
        if guid:
            return hashlib.sha256(guid.encode()).hexdigest()

        # Fallback: create hash from content
        content = f"{title}|{link}|{published}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def fetch_all_feeds(self) -> list[dict[str, Any]]:
        """
        Fetch all configured feeds and return all entries.

        Returns:
            List of all entries from all feeds
        """
        if not self.feed_urls:
            return []

        # Fetch all feeds in parallel using asyncio.gather
        results = await asyncio.gather(
            *[self.fetch_feed(url) for url in self.feed_urls],
            return_exceptions=True
        )

        all_entries = []
        for url, result in zip(self.feed_urls, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch feed {url}: {result}")
                continue

            feed_info, entries = result
            if entries:
                all_entries.extend(entries)
                logger.info(f"Fetched {len(entries)} entries from {url}")
            else:
                logger.warning(f"No entries fetched from {url}")

        return all_entries

    @staticmethod
    def format_entry_to_markdown(entry: dict[str, Any]) -> str:
        """
        Format a feed entry to markdown for indexing.

        Args:
            entry: Parsed feed entry

        Returns:
            Markdown formatted content
        """
        lines = []

        # Title
        lines.append(f"# {entry['title']}")
        lines.append("")

        # Metadata
        lines.append("## Metadata")
        lines.append(f"- **Feed**: {entry['feed_title']}")
        if entry.get("author"):
            lines.append(f"- **Author**: {entry['author']}")
        if entry.get("published"):
            lines.append(f"- **Published**: {entry['published']}")
        if entry.get("link"):
            lines.append(f"- **Link**: {entry['link']}")
        if entry.get("categories"):
            lines.append(f"- **Categories**: {', '.join(entry['categories'])}")
        lines.append("")

        # Content
        lines.append("## Content")
        content = entry.get("content") or entry.get("summary") or "No content available"

        # Convert HTML to markdown using markdownify for safer sanitization
        # This properly parses HTML instead of using fragile regex patterns
        content = md(
            content,
            heading_style="ATX",
            strip=['script', 'style', 'iframe', 'object', 'embed', 'form', 'input']
        )
        # Normalize excessive newlines
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content.strip()

        lines.append(content)

        return "\n".join(lines)
