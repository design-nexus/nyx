"""Generate Nyx 2.0 launcher icons from app-glyphs.json.

Files, Notes, Settings, Photos, Mail, Music and Home come from Claude's
Nyx Design 2.0 Icons board. Companion glyphs follow the same satin tile,
app accent and layered geometric treatment. Run this file to regenerate all assets.

Nyx Dark is the reference look: the files in apps/ are rendered with it. The
helpers below restyle the same glyphs for another theme's background and
accents (`nyx icons sync`), and draw them in the style of an icon theme's look
(`styled`: Umbra Tinted, Frame and Colour, Vellum and Vellum Mono).
"""
import base64
import colorsys
import json
import pathlib
from xml.sax.saxutils import escape

TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{tile_top}"/><stop offset="1" stop-color="{tile_bottom}"/></linearGradient>
    <radialGradient id="glow" cx=".2" cy=".1" r=".9"><stop stop-color="{light}" stop-opacity=".22"/><stop offset="1" stop-color="{light}" stop-opacity="0"/></radialGradient>
    <linearGradient id="ink" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{light}"/><stop offset="1" stop-color="{mid}"/></linearGradient>
  </defs>
  <rect x="8" y="8" width="112" height="112" rx="28" fill="url(#tile)"/>
  <rect x="8" y="8" width="112" height="112" rx="28" fill="url(#glow)"/>
  <rect x="8.5" y="8.5" width="111" height="111" rx="27.5" fill="none" stroke="{light}" stroke-opacity=".3"/>
  <path d="{back}" fill="{light}" fill-opacity=".35"/>
  <path d="{front}" fill="url(#ink)"/>
  <path d="{detail}" fill="none" stroke="{cut}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
'''

# The Nyx Dark tile: gradient stops and the colour detail strokes are cut in.
TILE = {"tile_top": "#26262a", "tile_bottom": "#121214", "cut": "#151517"}
NYX_DARK_BG, NYX_DARK_TEXT = "#09090a", "#e8e8ea"

# Nyx Dark's swatches and the hand-tuned light/mid glyph pair for each.
SWATCHES = {
    "blue": "#5b9cff", "violet": "#9d7bff", "pink": "#ff6fae", "red": "#ff6b6b",
    "coral": "#ff7a59", "amber": "#f2b545", "green": "#46d08a", "teal": "#4cc9d6",
    "graphite": "#a3a3ab",
}
TUNED = {
    "blue": ("#86baff", "#4b8ef5"), "violet": ("#bba6ff", "#8f6bff"),
    "pink": ("#ff97c6", "#fa5d9f"), "red": ("#ff9a9e", "#ee5864"),
    "coral": ("#ffa184", "#fb6f4a"), "amber": ("#ffd27a", "#f0a83a"),
    "green": ("#79e6ad", "#3cc57f"), "teal": ("#7ee2ee", "#35afc9"),
    "graphite": ("#a7b1c7", "#8590a8"),
}


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(rgb):
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def mix(a, b, t):
    """`a` moved towards `b` by `t`, as #rrggbb."""
    return _hex(x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b)))


def tile_for(bg, text, light):
    """The tile for a theme's background and text colours."""
    bg, text = bg.lower(), text.lower()
    if (bg, text) == (NYX_DARK_BG, NYX_DARK_TEXT):
        return dict(TILE)
    if light:
        return {"tile_top": mix(bg, "#ffffff", .7), "tile_bottom": mix(bg, text, .07),
                "cut": mix(bg, "#ffffff", .5)}
    return {"tile_top": mix(bg, text, .13), "tile_bottom": mix(bg, text, .04), "cut": mix(bg, text, .05)}


def family(color):
    """The Nyx swatch name a glyph colour belongs to, by hue."""
    h, s, _ = colorsys.rgb_to_hsv(*_rgb(color))
    if s < .25:
        return "graphite"
    def distance(name):
        other = colorsys.rgb_to_hsv(*_rgb(TUNED[name][0]))[0]
        return min(abs(h - other), 1 - abs(h - other))
    return min((n for n in TUNED if n != "graphite"), key=distance)


def glyph_colors(accent):
    """The light/mid glyph pair for one accent colour."""
    accent = accent.lower()
    for name, swatch in SWATCHES.items():
        if swatch == accent:
            return TUNED[name]
    return mix(accent, "#ffffff", .28), mix(accent, "#000000", .08)


def themed(glyph, accent=None, tile=None):
    """`glyph` in `accent` on `tile`. A glyph keeps its own colours while
    the accent is still the Nyx Dark swatch it was drawn for."""
    glyph = dict(glyph)
    if accent and accent.lower() != SWATCHES[family(glyph["light"])]:
        glyph["light"], glyph["mid"] = glyph_colors(accent)
    return render_glyph(glyph, tile)


def render_glyph(glyph, tile=None):
    """Render a curated glyph on the canonical Nyx tile, or on `tile`."""
    values = {key: escape(value, {chr(34): "&quot;"}) for key, value in glyph.items()}
    return TEMPLATE.format(**{**TILE, **(tile or {}), **values})


def _logo_image(png):
    logo = base64.b64encode(png).decode("ascii")
    return ('<image x="28" y="28" width="72" height="72" preserveAspectRatio="xMidYMid meet" '
            'href="data:image/png;base64,' + logo + '"/>')


def render_logo(png, light="#a7b1c7", mid="#8590a8", tile=None):
    """Embed a rasterized original logo without recoloring third-party artwork."""
    svg = render_glyph(dict(light=light, mid=mid, back="", front="", detail=""), tile)
    return svg.replace("</svg>", _logo_image(png) + "</svg>")


# ---------- Styles: app icons matching an icon theme's look ----------
#
# Umbra Tinted, Frame and Colour and Vellum (Paper) and Vellum Mono each have an app-icon
# style; `nyx icons` draws in the style of the look in use, else on the Nyx tile above.
# A style takes the glyph, its accent and the theme's bg, text and light.

STYLES = ("tinted", "frame", "colour", "paper", "mono")
SQUIRCLE = 'x="8" y="8" width="112" height="112" rx="28"'


def _tones(glyph, accent):
    """The glyph's light and mid colours in `accent`, as themed() picks them."""
    if accent.lower() == SWATCHES[family(glyph["light"])]:
        return glyph["light"], glyph["mid"]
    return glyph_colors(accent)


def _linear(id_, top, bottom, x2=0, top_opacity=1, bottom_opacity=1):
    return (f'<linearGradient id="{id_}" x1="0" y1="0" x2="{x2}" y2="1">'
            f'<stop stop-color="{top}" stop-opacity="{top_opacity}"/>'
            f'<stop offset="1" stop-color="{bottom}" stop-opacity="{bottom_opacity}"/></linearGradient>')


def _svg(body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
            f'<defs>{defs}</defs>{body}</svg>\n')


def _detail(glyph, colour, width=5):
    if not glyph.get("detail"):
        return ""
    return (f'<path d="{escape(glyph["detail"])}" fill="none" stroke="{colour}" stroke-width="{width}" '
            'stroke-linecap="round" stroke-linejoin="round"/>')


def _layers(glyph, light, cut, ink="url(#ink)"):
    """The glyph's 35% back, its front and its detail cut in."""
    return (f'<path d="{escape(glyph["back"])}" fill="{light}" fill-opacity=".35"/>'
            f'<path d="{escape(glyph["front"])}" fill="{ink}"/>' + _detail(glyph, cut))


def _paper(theme):
    bg, text = theme["bg"], theme["text"]
    if theme["light"]:
        return "#ffffff", mix(bg, text, .03), mix(bg, text, .14), .18
    return mix(bg, text, .24), mix(bg, text, .17), mix(bg, text, .32), .55


def _base(style, accent, theme, tones=None):
    """A style's tile: (defs, body, the colour details are cut in). `tones` is the
    glyph's light and mid pair, for Colour's tile."""
    bg, text, light = theme["bg"], theme["text"], theme["light"]
    if style == "tinted":
        tile = tile_for(bg, text, light)
        top, bottom = ((mix(tile["tile_top"], accent, .1), mix(tile["tile_bottom"], accent, .16)) if light else
                       (mix(tile["tile_top"], accent, .2), mix(tile["tile_bottom"], accent, .1)))
        defs = (_linear("tile", top, bottom, 1)
                + f'<radialGradient id="glow" cx=".2" cy=".1" r=".9"><stop stop-color="{accent}" stop-opacity=".2"/>'
                  f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>')
        body = (f'<rect {SQUIRCLE} fill="url(#tile)"/><rect {SQUIRCLE} fill="url(#glow)"/>'
                f'<rect x="8.5" y="8.5" width="111" height="111" rx="27.5" fill="none" stroke="{accent}" '
                'stroke-opacity=".42"/>')
        return defs, body, mix(bottom, accent, .12)
    if style == "frame":
        return "", (f'<rect x="10" y="10" width="108" height="108" rx="27" fill="{accent}" fill-opacity=".07" '
                    f'stroke="{accent}" stroke-opacity=".6" stroke-width="3"/>'), bg
    if style == "colour":
        hi, lo = tones or glyph_colors(accent)
        defs = (_linear("tile", hi, mix(lo, "#000000", .12), .6)
                + '<radialGradient id="sheen" cx=".2" cy=".05" r=".8"><stop stop-color="#ffffff" stop-opacity=".28"/>'
                  '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient>')
        body = (f'<rect {SQUIRCLE} fill="url(#tile)"/><rect {SQUIRCLE} fill="url(#sheen)"/>'
                '<rect x="8.75" y="8.75" width="110.5" height="110.5" rx="27.25" fill="none" stroke="#ffffff" '
                'stroke-opacity=".22" stroke-width="1.5"/>')
        return defs, body, lo
    if style == "paper":
        top, bottom, edge, shadow = _paper(theme)
        defs = (_linear("card", mix(accent, top, .92), mix(accent, bottom, .84))
                + f'<filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">'
                  f'<feGaussianBlur in="SourceAlpha" stdDeviation="3"/><feOffset dy="3" result="b"/>'
                  f'<feFlood flood-color="#000000" flood-opacity="{shadow}"/><feComposite in2="b" operator="in"/>'
                  '<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
        body = (f'<rect x="10" y="10" width="108" height="108" rx="27" fill="url(#card)" filter="url(#shadow)"/>'
                f'<rect x="10.5" y="10.5" width="107" height="107" rx="26.5" fill="none" stroke="{edge}"/>')
        return defs, body, top
    if style == "mono":
        tile = tile_for(bg, text, light)
        defs = _linear("tile", tile["tile_top"], tile["tile_bottom"], 1)
        body = (f'<rect {SQUIRCLE} fill="url(#tile)"/><rect x="8.5" y="8.5" width="111" height="111" rx="27.5" '
                f'fill="none" stroke="{text}" stroke-opacity=".12"/>')
        return defs, body, tile["cut"]
    raise ValueError(f"unknown style {style}")


def styled(glyph, accent, theme, style):
    """`glyph` in `accent` as an app icon in `style` (one of STYLES), for a theme's bg,
    text and light."""
    defs, base, cut = _base(style, accent, theme, _tones(glyph, accent))
    if style == "colour":
        hi, lo = _tones(glyph, accent)
        defs += _linear("ink", "#ffffff", mix(hi, "#ffffff", .7))
        body = (f'<path d="{escape(glyph["back"])}" fill="#ffffff" fill-opacity=".38"/>'
                f'<path d="{escape(glyph["front"])}" fill="url(#ink)"/>' + _detail(glyph, lo))
    elif style == "mono":
        ink = theme["text"]
        defs += _linear("ink", ink, mix(ink, theme["bg"], .3))
        back = (f'<path d="{escape(glyph["back"])}" fill="{ink}" fill-opacity=".2"/>' if glyph.get("detail") else
                f'<path d="{escape(glyph["back"])}" fill="{accent}" fill-opacity=".8"/>')
        body = back + f'<path d="{escape(glyph["front"])}" fill="url(#ink)"/>' + _detail(glyph, accent, 5.5)
    else:
        hi, lo = (accent, mix(accent, "#000000", .2)) if style == "paper" and theme["light"] else _tones(glyph, accent)
        defs += _linear("ink", hi, lo, 1)
        body = _layers(glyph, hi, cut)
    return _svg(base + body, defs)


def styled_logo(png, accent, theme, style):
    """A third-party logo, never recoloured, on `style`'s tile (white for Colour)."""
    if style == "colour":
        return _svg(f'<rect {SQUIRCLE} fill="#ffffff"/>' + _logo_image(png))
    defs, base, _cut = _base(style, accent, theme)
    return _svg(base + _logo_image(png), defs)


def main():
    base = pathlib.Path(__file__).resolve().parent
    out = base / "apps"
    out.mkdir(exist_ok=True)
    icons = json.loads((base / "app-glyphs.json").read_text())
    for name, glyph in icons.items():
        (out / f"io.github.design_nexus.nyx.{name}.svg").write_text(
            render_glyph(glyph))
    print(f"{len(icons)} Nyx 2.0 icons in {out}")

if __name__ == "__main__":
    main()
