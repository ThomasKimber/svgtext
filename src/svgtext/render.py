from playwright.async_api import async_playwright
import asyncio, base64
import re

async def svg_to_png(browser: async_playwright, svg_text: str) -> bytes:
    wm = re.search(r'width="([\d.]+)"', svg_text)
    hm = re.search(r'height="([\d.]+)"', svg_text)
    w = int(float(wm.group(1)))
    h = int(float(hm.group(1)))

    page = await browser.new_page(viewport={"width": w, "height": h})
    try:
        await page.set_content(
            f'<body style="margin:0">{svg_text}</body>',
            wait_until="load"
        )
        await page.evaluate("document.fonts.ready")
        return await page.locator("svg").screenshot(type="png")
    finally:
        await page.close()