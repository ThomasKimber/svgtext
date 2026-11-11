from typing import Hashable
import tempfile, os, io, functools
import base64
import re
from resvg_py import svg_to_bytes
from fontTools.ttLib import TTFont

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


@functools.lru_cache(maxsize=8)
def _prepare_fonts(svg: str) -> tuple[str, ...]:
    fonts = [
        base64.b64decode(m)
        for m in re.findall(r'data:application/x-font-ttf;base64,([A-Za-z0-9+/=]+)', svg)
    ]
    tmp_dir = tempfile.mkdtemp(prefix="resvg_fonts_")
    paths = []
    print(len(fonts))
    for i, f in enumerate(fonts):
        path = os.path.join(tmp_dir, f"font_{i}.ttf")
        with open(path, "wb") as fh:
            fh.write(f)
        paths.append(path)
    return tuple(paths)

def render_svg(svg: str, width: int = 2048) -> bytes:
    font_paths = _prepare_fonts(svg)
    print(font_paths)
    return svg_to_bytes(
        svg_string=svg,
        font_files=list(font_paths),
        skip_system_fonts=True,
        width=width,
    )

def svg_to_png_data_uri(svg : str)->str:
    _psvg, _pfonts=prepare_for_resvg(svg)
    return base64_text_to_data_url(binary_data_to_base64_text(render_svg(_psvg)),
                            data_format='png')

def get_internal_family(font_bytes: bytes) -> str:
    font = TTFont(io.BytesIO(font_bytes))
    for record in font['name'].names:
        if record.nameID == 1 and record.platformID == 3:  # Windows platform
            return record.toUnicode()
    return ""

def prepare_for_resvg(svg: str) -> tuple[str, list[bytes]]:
    font_matches = list(re.finditer(
        r'@font-face\s*{[^}]*font-family\s*:\s*["\']([^"\']+)["\'][^}]*data:[^;]+;base64,([A-Za-z0-9+/=]+)',
        svg
    ))
    
    fonts = []
    replacements = {}
    
    for m in font_matches:
        declared_name = m.group(1)
        font_bytes = base64.b64decode(m.group(2))
        internal_name = get_internal_family(font_bytes)
        fonts.append(font_bytes)
        if declared_name != internal_name:
            replacements[declared_name] = internal_name
    
    # Global replace — catches attributes, CSS rules, AND inline styles
    for declared, internal in replacements.items():
        svg = svg.replace(declared, internal)
    
    return svg, fonts