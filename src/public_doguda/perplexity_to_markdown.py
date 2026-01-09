from public_doguda import app
from pydantic import BaseModel
from playwright.async_api import async_playwright
import asyncio


class PerplexityResponse(BaseModel):
    url: str
    markdown: str
    raw_html: str


async def _fetch_perplexity_content(url: str) -> tuple[str, str]:
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

            # 1. Handle login modal or other overlays
            close_modal = page.locator('button[data-testid="close-modal"], button[aria-label="Close"]').first
            try:
                # If it appears within 5 seconds, close it
                await close_modal.wait_for(state="visible", timeout=5000)
                await close_modal.click()
                await close_modal.wait_for(state="hidden", timeout=3000)
            except Exception:
                pass

            # 2. Wait for the page structure to be ready
            # We look for the dots button as a sign of logical readiness
            dots_selector = 'button[aria-label*="작업"], button[aria-label*="Actions"], button:has(use[xlink\\:href="#pplx-icon-dots"])'
            dots_button = page.locator(dots_selector).first
            
            try:
                await dots_button.wait_for(state="visible", timeout=30000)
            except Exception:
                # If dots button never appears, we can't proceed with export
                return "", await page.content()

            # 3. Attempt to click dots and export with retries
            # Perplexity's UI can sometimes be unresponsive or menus can close immediately
            for attempt in range(3):
                try:
                    # Click the dots button
                    await dots_button.click(delay=100)
                    
                    # Wait for export menu item
                    export_selector = 'div:has-text("Markdown으로 내보내기"), div:has-text("Export to Markdown"), [role="menuitem"]:has-text("Markdown"), button:has(use[xlink\\:href="#pplx-icon-markdown"])'
                    export_button = page.locator(export_selector).last
                    
                    # Ensure it becomes visible
                    await export_button.wait_for(state="visible", timeout=5000)
                    
                    # Start download interception before clicking
                    async with page.expect_download(timeout=30000) as download_info:
                        await export_button.click()
                    
                    download = await download_info.value
                    path = await download.path()
                    with open(path, "r", encoding="utf-8") as f:
                        markdown_content = f.read()
                    
                    if markdown_content:
                        return markdown_content, await page.content()
                except Exception:
                    if attempt == 2: # Last attempt
                        break
                    # Wait a bit before retry to let UI settle
                    await asyncio.sleep(2)
                    # Re-verify dots button visibility before retrying
                    if not await dots_button.is_visible():
                        await page.reload()
                        await dots_button.wait_for(state="visible", timeout=10000)

            return "", await page.content()

        finally:
            await browser.close()


@app.doguda()
async def perplexity_to_markdown(url: str) -> PerplexityResponse:
    """
    Fetches a Perplexity shared URL and extracts the content as Markdown using the official export feature.
    """
    downloaded_markdown, raw_html = await _fetch_perplexity_content(url)

    if not downloaded_markdown:
        raise ValueError("Failed to download markdown from Perplexity. The export button might not be available or the page failed to load correctly.")

    return PerplexityResponse(
        url=url,
        markdown=downloaded_markdown,
        raw_html=raw_html
    )
