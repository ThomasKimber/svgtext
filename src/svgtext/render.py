from typing import Hashable, Any, Callable, Iterable, Iterator
import tempfile, os, io, functools
import base64
import re
from resvg_py import svg_to_bytes
from fontTools.ttLib import TTFont
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from itertools import islice

class BatchThreadProcessor:
    """Apply a function to items from an iterable in bounded thread batches."""

    def __init__(
        self,
        function: Callable[[Any], Any],
        batch_size: int,
        pool_size: int,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if pool_size < 1:
            raise ValueError("pool_size must be at least 1")

        self.function = function
        self.batch_size = batch_size
        self.pool_size = pool_size

    @staticmethod
    def _batched(items: Iterable[Any], batch_size: int) -> Iterator[list[Any]]:
        iterator = iter(items)

        while True:
            batch = list(islice(iterator, batch_size))
            if not batch:
                return
            yield batch

    def process(self, items: Iterable[Any]) -> list[Any]:
        """Apply the function to every item and collect outputs in input order."""
        outputs: list[Any] = []

        for batch in self._batched(items, self.batch_size):
            with ThreadPoolExecutor(max_workers=self.pool_size) as executor:
                futures = [
                    executor.submit(self.function, item)
                    for item in batch
                ]
                outputs.extend(future.result() for future in futures)

        return outputs


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
    for i, f in enumerate(fonts):
        path = os.path.join(tmp_dir, f"font_{i}.ttf")
        with open(path, "wb") as fh:
            fh.write(f)
        paths.append(path)
    return tuple(paths)

def render_svg(svg: str, width: int = 2048) -> bytes:
    font_paths = _prepare_fonts(svg)
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

@lru_cache(maxsize=None)
def svg_to_png_data_uri_cached(svg_component: str) -> str:
    return svg_to_png_data_uri(svg_component)

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