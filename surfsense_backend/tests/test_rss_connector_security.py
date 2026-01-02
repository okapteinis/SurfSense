"""
Unit tests for RSS Connector SSRF protection.

Tests the security methods added to prevent SSRF attacks via redirect chains:
- _validate_redirect_url(): Validates redirect URLs against SSRF blocklist
- _safe_get_with_redirects(): Safely follows redirects with validation
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException
import httpx

from app.connectors.rss_connector import RSSConnector


class TestValidateRedirectUrl:
    """Test suite for _validate_redirect_url method."""

    @pytest.mark.asyncio
    async def test_validate_redirect_url_blocks_private_ip(self):
        """Test that redirects to private IP addresses are blocked."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        private_ips = [
            "http://192.168.1.1/feed",
            "http://10.0.0.1/internal",
            "http://172.16.0.1/admin",
        ]

        for url in private_ips:
            with pytest.raises(HTTPException) as exc_info:
                await connector._validate_redirect_url(url)

            assert exc_info.value.status_code == 400
            assert "private" in exc_info.value.detail.lower() or "blocked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validate_redirect_url_blocks_localhost(self):
        """Test that redirects to localhost are blocked."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        localhost_urls = [
            "http://127.0.0.1/feed",
            "http://localhost/admin",
            "http://[::1]/internal",
        ]

        for url in localhost_urls:
            with pytest.raises(HTTPException) as exc_info:
                await connector._validate_redirect_url(url)

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_validate_redirect_url_blocks_cloud_metadata(self):
        """Test that redirects to cloud metadata endpoints are blocked."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        # AWS metadata endpoint
        with pytest.raises(HTTPException) as exc_info:
            await connector._validate_redirect_url("http://169.254.169.254/latest/meta-data/")
        assert exc_info.value.status_code == 400
        assert "169.254.169.254" in exc_info.value.detail

        # Note: GCP metadata.google.internal and Azure 100.100.100.200 require DNS resolution
        # These are tested via the validate_url_safe_for_ssrf integration

    @pytest.mark.asyncio
    async def test_validate_redirect_url_blocks_non_http_schemes(self):
        """Test that non-HTTP(S) schemes are blocked."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        non_http_urls = [
            "file:///etc/passwd",
            "gopher://internal.server/data",
            "ftp://server.local/files",
        ]

        for url in non_http_urls:
            with pytest.raises(HTTPException) as exc_info:
                await connector._validate_redirect_url(url)

            assert exc_info.value.status_code == 400
            assert "scheme" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validate_redirect_url_allows_valid_https(self):
        """Test that valid HTTPS URLs pass validation."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        valid_urls = [
            "https://www.aljazeera.com/news/2025/article",
            "https://www.bbc.com/news/world",
            "https://example.com/rss/feed.xml",
        ]

        for url in valid_urls:
            # Should not raise any exception
            try:
                await connector._validate_redirect_url(url)
            except HTTPException:
                pytest.fail(f"Valid URL {url} was incorrectly blocked")


class TestSafeGetWithRedirects:
    """Test suite for _safe_get_with_redirects method."""

    @pytest.mark.asyncio
    async def test_safe_get_with_redirects_follows_safe_redirect(self):
        """Test that safe redirects are followed and final response is returned."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        # Mock httpx.AsyncClient
        mock_client = AsyncMock()

        # First request: redirect (302)
        redirect_response = Mock()
        redirect_response.status_code = 302
        redirect_response.headers = {"location": "https://example.com/feed/new"}
        redirect_response.url = "http://example.com/feed"

        # Second request: final response (200)
        final_response = Mock()
        final_response.status_code = 200
        final_response.text = "<rss>...</rss>"
        final_response.url = "https://example.com/feed/new"

        # Configure mock to return redirect first, then final response
        mock_client.get = AsyncMock(side_effect=[redirect_response, final_response])

        result = await connector._safe_get_with_redirects(
            mock_client,
            "http://example.com/feed",
            {"User-Agent": "Test"}
        )

        assert result == final_response
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_safe_get_with_redirects_blocks_malicious_redirect(self):
        """Test that redirects to private IPs are blocked."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        mock_client = AsyncMock()

        # Mock redirect to private IP
        redirect_response = Mock()
        redirect_response.status_code = 302
        redirect_response.headers = {"location": "http://192.168.1.1/internal"}
        redirect_response.url = "https://example.com/feed"

        mock_client.get = AsyncMock(return_value=redirect_response)

        with pytest.raises(HTTPException) as exc_info:
            await connector._safe_get_with_redirects(
                mock_client,
                "https://example.com/feed",
                {"User-Agent": "Test"}
            )

        assert exc_info.value.status_code == 400
        assert "private" in exc_info.value.detail.lower() or "blocked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_safe_get_with_redirects_max_redirects_exceeded(self):
        """Test that redirect loops are detected and blocked."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        mock_client = AsyncMock()

        # Mock infinite redirect loop
        redirect_response = Mock()
        redirect_response.status_code = 302
        redirect_response.headers = {"location": "https://example.com/feed"}
        redirect_response.url = "https://example.com/feed"

        mock_client.get = AsyncMock(return_value=redirect_response)

        with pytest.raises(HTTPException) as exc_info:
            await connector._safe_get_with_redirects(
                mock_client,
                "https://example.com/feed",
                {"User-Agent": "Test"}
            )

        assert exc_info.value.status_code == 400
        assert "too many redirects" in exc_info.value.detail.lower()
        assert "5" in exc_info.value.detail  # max_redirects limit

    @pytest.mark.asyncio
    async def test_safe_get_with_redirects_no_redirect_returns_immediately(self):
        """Test that non-redirect responses are returned immediately."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        mock_client = AsyncMock()

        # Mock successful response (no redirect)
        success_response = Mock()
        success_response.status_code = 200
        success_response.text = "<rss>...</rss>"

        mock_client.get = AsyncMock(return_value=success_response)

        result = await connector._safe_get_with_redirects(
            mock_client,
            "https://example.com/feed",
            {"User-Agent": "Test"}
        )

        assert result == success_response
        assert mock_client.get.call_count == 1  # No redirect, single request

    @pytest.mark.asyncio
    async def test_safe_get_with_redirects_handles_relative_redirects(self):
        """Test that relative redirect URLs are correctly resolved."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        mock_client = AsyncMock()

        # Mock redirect with relative URL
        redirect_response = Mock()
        redirect_response.status_code = 302
        redirect_response.headers = {"location": "/new-feed"}
        redirect_response.url = httpx.URL("https://example.com/feed")

        # Mock final response
        final_response = Mock()
        final_response.status_code = 200

        mock_client.get = AsyncMock(side_effect=[redirect_response, final_response])

        result = await connector._safe_get_with_redirects(
            mock_client,
            "https://example.com/feed",
            {"User-Agent": "Test"}
        )

        # Verify the second request was made to the resolved absolute URL
        second_call_url = mock_client.get.call_args_list[1][0][0]
        assert "https://example.com/new-feed" in str(second_call_url)

    @pytest.mark.asyncio
    async def test_safe_get_with_redirects_validates_each_hop(self):
        """Test that each redirect in a chain is validated."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        mock_client = AsyncMock()

        # Mock chain: safe -> safe -> malicious
        redirect1 = Mock()
        redirect1.status_code = 302
        redirect1.headers = {"location": "https://example.com/feed2"}
        redirect1.url = httpx.URL("https://example.com/feed")

        redirect2 = Mock()
        redirect2.status_code = 302
        redirect2.headers = {"location": "http://10.0.0.1/malicious"}
        redirect2.url = httpx.URL("https://example.com/feed2")

        mock_client.get = AsyncMock(side_effect=[redirect1, redirect2])

        with pytest.raises(HTTPException) as exc_info:
            await connector._safe_get_with_redirects(
                mock_client,
                "https://example.com/feed",
                {"User-Agent": "Test"}
            )

        # Should fail on the second redirect (to private IP)
        assert exc_info.value.status_code == 400
        assert mock_client.get.call_count == 2  # Stopped after detecting malicious redirect


class TestIntegrationSSRFProtection:
    """Integration tests for SSRF protection in validate_feed and fetch_feed methods."""

    @pytest.mark.asyncio
    async def test_validate_feed_with_safe_url(self):
        """Test that validate_feed works with safe URLs."""
        connector = RSSConnector(feed_urls=["https://example.com/feed"])

        # Mock the HTTP response
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = """<?xml version="1.0"?>
                <rss version="2.0">
                    <channel>
                        <title>Test Feed</title>
                        <item><title>Test Item</title></item>
                    </channel>
                </rss>
            """

            # Mock _safe_get_with_redirects to return the response
            connector._safe_get_with_redirects = AsyncMock(return_value=mock_response)

            result = await connector.validate_feed("https://example.com/feed")

            assert result["valid"] is True
            assert result["title"] == "Test Feed"
            assert result["item_count"] == 1

    @pytest.mark.asyncio
    async def test_validate_feed_blocks_initial_private_ip(self):
        """Test that validate_feed blocks private IPs in initial URL."""
        connector = RSSConnector(feed_urls=[])

        result = await connector.validate_feed("http://192.168.1.1/feed")

        assert result["valid"] is False
        assert result["error"] is not None
        assert "private" in result["error"].lower() or "blocked" in result["error"].lower()


# Mark all tests with security marker for easy filtering
pytestmark = pytest.mark.security
