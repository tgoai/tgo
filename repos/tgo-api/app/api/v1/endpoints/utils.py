"""Utility endpoints for various helper functions."""

from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl

from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.models.staff import Staff

logger = get_logger("endpoints.utils")
router = APIRouter()

# Constants
REQUEST_TIMEOUT = 10.0  # seconds
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class WebsiteMetadataRequest(BaseModel):
    """Request schema for extracting website metadata."""

    url: HttpUrl = Field(..., description="The URL of the website to extract metadata from")


class WebsiteMetadataResponse(BaseModel):
    """Response schema for website metadata extraction."""

    url: str = Field(..., description="The original URL")
    title: Optional[str] = Field(None, description="The website title from <title> tag")
    description: Optional[str] = Field(
        None,
        description="The website description from meta description or og:description tag"
    )
    favicon: Optional[str] = Field(None, description="The favicon URL if found")
    og_image: Optional[str] = Field(None, description="Open Graph image URL if found")
    success: bool = Field(..., description="Whether the extraction was successful")
    error: Optional[str] = Field(None, description="Error message if extraction failed")


def _extract_metadata(html: str, base_url: str) -> dict:
    """Extract metadata from HTML content."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title = None
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = title_tag.string.strip()

    # Extract description (try meta description first, then og:description)
    description = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()
    else:
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()

    # Extract favicon
    favicon = None
    icon_link = soup.find("link", rel=lambda x: x and "icon" in x.lower() if x else False)
    if icon_link and icon_link.get("href"):
        favicon = icon_link["href"]
        # Make absolute URL if relative
        if favicon.startswith("/"):
            from urllib.parse import urljoin
            favicon = urljoin(base_url, favicon)

    # Extract Open Graph image
    og_image = None
    og_img_tag = soup.find("meta", attrs={"property": "og:image"})
    if og_img_tag and og_img_tag.get("content"):
        og_image = og_img_tag["content"]

    return {
        "title": title,
        "description": description,
        "favicon": favicon,
        "og_image": og_image,
    }


@router.post(
    "/extract-website-metadata",
    response_model=WebsiteMetadataResponse,
    summary="Extract Website Metadata",
    description="""
    Extract metadata (title, description, favicon, og:image) from a given website URL.

    This endpoint fetches the HTML content of the specified URL and extracts:
    - **title**: From the `<title>` tag
    - **description**: From `<meta name="description">` or `<meta property="og:description">`
    - **favicon**: From `<link rel="icon">` or similar
    - **og_image**: From `<meta property="og:image">`
    """,
    responses={
        200: {"description": "Metadata extracted successfully"},
        400: {"description": "Invalid URL format"},
        502: {"description": "Failed to fetch the website"},
        504: {"description": "Request timeout"},
    },
)
async def extract_website_metadata(
    request: WebsiteMetadataRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> WebsiteMetadataResponse:
    """Extract metadata from a website URL."""
    url = str(request.url)
    logger.info("Extracting website metadata", extra={"url": url, "user_id": str(current_user.id)})

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        metadata = _extract_metadata(response.text, url)
        return WebsiteMetadataResponse(url=url, success=True, **metadata)

    except httpx.TimeoutException:
        logger.warning("Website metadata extraction timeout", extra={"url": url})
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Request timeout while fetching {url}"
        )
    except httpx.HTTPStatusError as e:
        logger.warning("Website returned error status", extra={"url": url, "status": e.response.status_code})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Website returned status {e.response.status_code}"
        )
    except httpx.RequestError as e:
        logger.warning("Failed to fetch website", extra={"url": url, "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to {url}: {type(e).__name__}"
        )
    except Exception as e:
        logger.error("Unexpected error extracting metadata", extra={"url": url, "error": str(e)})
        return WebsiteMetadataResponse(url=url, success=False, error=str(e))

