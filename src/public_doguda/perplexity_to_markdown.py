from public_doguda import app
from pydantic import BaseModel
from playwright.async_api import async_playwright
from html_to_markdown import convert
from bs4 import BeautifulSoup
import asyncio


class PerplexityResponse(BaseModel):
    url: str
    markdown: str
    raw_html: str


async def _fetch_perplexity_content(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(url, timeout=60000)

            # Wait for the challenge to pass (title shouldn't be "Just a moment...")
            # and for the content to load (looking for the prose content)
            for _ in range(30):
                title = await page.title()
                if "Just a moment" not in title and "Perplexity" not in title:
                     # Attempt to find the content container
                     # Based on investigation: class="prose dark:prose-invert ..."
                     content_element = await page.query_selector('.prose')
                     if content_element:
                         return await page.content()

                await asyncio.sleep(1)

            # If we timed out but have some content, return it anyway to try parsing
            return await page.content()

        finally:
            await browser.close()


def _extract_and_convert(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Perplexity content is usually in a div with "prose" class
    # We found: class="prose dark:prose-invert inline leading-relaxed break-words min-w-0 [word-break:break-word] prose-strong:font-medium [&_>*:first-child]:mt-0"
    content_div = soup.select_one(".prose")

    if not content_div:
        # Fallback: try to find by ID if the class selector is too brittle
        # We saw id="markdown-content-0" in the investigation
        content_div = soup.select_one('[id^="markdown-content-"]')

    if not content_div:
        return ""

    # Remove citations (small numbers/links usually) if needed,
    # but the request asked to mimic the download which usually keeps them or formats them.
    # For now, let's keep them but maybe clean up some UI specific elements if they intrude.
    # The investigation showed: <span class="citation inline" ...>

    return convert(str(content_div))


@app.doguda
async def perplexity_to_markdown(url: str) -> PerplexityResponse:
    """
    Fetches a Perplexity shared URL and extracts the content as Markdown.
    """
    raw_html = await _fetch_perplexity_content(url)
    markdown_content = _extract_and_convert(raw_html)

    return PerplexityResponse(
        url=url,
        markdown=markdown_content,
        raw_html=raw_html
    )
