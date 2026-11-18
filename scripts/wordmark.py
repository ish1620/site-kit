"""Draw a wordmark in Archivo Black Expanded (wght 900, wdth 125) as one SVG path.

Usage: python -I ../site-kit/scripts/wordmark.py <Archivo-VF.ttf> <text> <out>
  (run from a site's folder beside the kit; needs fonttools and uharfbuzz)
The font comes from https://github.com/google/fonts/tree/main/ofl/archivo (SIL Open Font License).
With src/components/Wordmark.astro as <out>, the output is the whole component: the bare SVG,
which takes the text colour (currentColor) and is named by its text (aria-label).
Shapes the text with HarfBuzz (so the font's own kerning applies), adds 0.01em tracking, and
writes the outlines with y flipped, cropped tightly to the letters. Not installed into the sites
(only src/ is).
"""
import io
import sys
from xml.sax.saxutils import quoteattr

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

AXES = {"wght": 900, "wdth": 125}
TRACKING_EM = 0.01

if len(sys.argv) != 4:
    sys.exit(__doc__)
src, text, out = sys.argv[1:]
font = instantiateVariableFont(TTFont(src), AXES)
buf_bytes = io.BytesIO()
font.save(buf_bytes)
data = buf_bytes.getvalue()
font = TTFont(io.BytesIO(data))
upem = font["head"].unitsPerEm
glyph_set = font.getGlyphSet()
order = font.getGlyphOrder()

hb_font = hb.Font(hb.Face(hb.Blob(data)))
buf = hb.Buffer()
buf.add_str(text)
buf.guess_segment_properties()
hb.shape(hb_font, buf, {"kern": True, "liga": False})

pen = SVGPathPen(glyph_set, ntos=lambda v: str(round(v)))
bounds = BoundsPen(glyph_set)
x = 0
for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
    name = order[info.codepoint]
    # y is flipped (fonts go up, SVG goes down)
    transform = (1, 0, 0, -1, x + pos.x_offset, -pos.y_offset)
    glyph_set[name].draw(TransformPen(pen, transform))
    glyph_set[name].draw(TransformPen(bounds, transform))
    x += pos.x_advance + (round(TRACKING_EM * upem) if i < len(buf.glyph_infos) - 1 else 0)

x_min, y_min, x_max, y_max = (round(v) for v in bounds.bounds)
width, height = x_max - x_min, y_max - y_min
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x_min} {y_min} {width} {height}" '
    f'role="img" aria-label={quoteattr(text)}><path fill="currentColor" d="{pen.getCommands()}"/></svg>\n'
)
open(out, "w").write(svg)
print(f"viewBox {x_min} {y_min} {width} {height}  ratio {width / height:.3f}  bytes {len(svg)}")
