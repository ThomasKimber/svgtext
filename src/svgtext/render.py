from typing import Hashable
from playwright.async_api import async_playwright
import asyncio, base64
import re
import base64

def binary_data_to_base64_text(binary_data):
    """Convert binary data to text data in Base64 format."""
    return base64.b64encode(binary_data).decode('utf-8').replace('\n', '')


def base64_text_to_data_url(base64_text, data_format):
    """Convert data in form of base64 text to a data URL with suitable prefix."""
    # Argument processing
    if data_format == 'jpg':
        data_format = 'jpeg'

    # Transformation
    # - MIME type
    if data_format in ['jpeg', 'png', 'gif', 'webp']:
        mime_type = 'image/' + data_format
    elif data_format == 'svg':
        mime_type = 'image/svg+xml'
    elif data_format == 'pdf':
        mime_type = 'application/pdf'
    elif data_format in ['eps', 'ps']:
        mime_type = 'application/postscript'
    else:
        msg = 'Unknown data format. Can not assign a suitable MIME type.'
        raise ValueError(msg)
    # - Data URL
    data_url = 'data:{};base64,{}'.format(mime_type, base64_text)
    return data_url

async def batch_svg_to_png(svg_dict : dict)->dict:

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        sem = asyncio.Semaphore(8)
        async def convert(key : Hashable, svg:str)->tuple[Hashable,bytes]:
            async with sem:
                png = await svg_to_png(browser, svg)
                return key, png

        results = await asyncio.gather(*(convert(k,s) for k,s in svg_dict.items()))
        await browser.close()

    return dict(results)
        

async def svg_to_png(browser: async_playwright, svg_text: str, scale : int=2) -> bytes:
    wm = re.search(r'width="([\d.]+)"', svg_text)
    hm = re.search(r'height="([\d.]+)"', svg_text)
    w = int(float(wm.group(1)))
    h = int(float(hm.group(1)))

    page = await browser.new_page(viewport={"width": w, "height": h},
                                  device_scale_factor=scale)
    try:
        await page.set_content(
            f'<body style="margin:0">{svg_text}</body>',
            wait_until="load"
        )
        await page.evaluate("document.fonts.ready")
        return await page.locator("svg").screenshot(type="png")
    finally:
        await page.close()