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
            headless=False,
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

            # 1. Close login modal if it's blocking the view
            close_modal_button = page.locator('button[data-testid="close-modal"], button[aria-label="Close"]').first
            try:
                # Wait briefly for modal to appear
                await close_modal_button.wait_for(state="visible", timeout=5000)
                await close_modal_button.click()
                # Wait for modal to disappear
                await asyncio.sleep(1)
            except Exception:
                # Modal might not be there, proceed
                pass

            # 2. Wait for the page to load correctly and find dots button
            dots_button = None
            for _ in range(30):
                title = await page.title()
                if "Just a moment" not in title:
                    # Try to find the dots button (Thread Actions)
                    dots_button = page.locator('button[aria-label*="작업"], button[aria-label*="Actions"], button:has(use[xlink\\:href="#pplx-icon-dots"])').first
                    if await dots_button.is_visible():
                        break
                await asyncio.sleep(1)

            if not dots_button or not await dots_button.is_visible():
                return "", await page.content()

            # 3. Click the dots button to open the menu
            await dots_button.click()
            await asyncio.sleep(1)
            
            # 4. Look for "Markdown으로 내보내기" or "Export to Markdown"
            # Try multiple detection strategies for the export button
            export_button = page.locator('div:has-text("Markdown으로 내보내기"), div:has-text("Export to Markdown"), button:has(use[xlink\\:href="#pplx-icon-markdown"])').last
            
            try:
                # Wait for the menu item to be visible and clickable
                await export_button.wait_for(state="visible", timeout=10000)
                
                async with page.expect_download(timeout=30000) as download_info:
                    await export_button.click()
                
                download = await download_info.value
                path = await download.path()
                with open(path, "r", encoding="utf-8") as f:
                    markdown_content = f.read()
                
                return markdown_content, await page.content()
            except Exception:
                # Fallback to a simpler text search if the complex locator fails
                try:
                    export_button = page.get_by_text("Markdown으로 내보내기").first
                    if not await export_button.is_visible():
                        export_button = page.get_by_text("Export to Markdown").first
                    
                    await export_button.wait_for(state="visible", timeout=5000)
                    async with page.expect_download(timeout=30000) as download_info:
                        await export_button.click()
                        
                    download = await download_info.value
                    path = await download.path()
                    with open(path, "r", encoding="utf-8") as f:
                        markdown_content = f.read()
                    return markdown_content, await page.content()
                except Exception:
                    pass
            
            return "", await page.content()

        finally:
            await browser.close()


@app.doguda
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
