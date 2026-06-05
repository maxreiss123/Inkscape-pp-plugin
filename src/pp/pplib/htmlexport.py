"""Export the presentation as a self-contained HTML file.

Two modes:
* vector  -- inline the interactive SVG (text stays selectable); optional font
             embedding for identical rendering anywhere.
* raster  -- one cairosvg PNG per slide in a tiny keyboard/click viewer, for
             guaranteed-identical rendering with no font dependencies.
"""

import base64

import lxml.etree as ET

from . import jsexport, slides

_VECTOR_HTML = (
    "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>{title}</title><style>html,body{{margin:0;height:100%;background:#000;"
    "overflow:hidden}}svg{{position:fixed;inset:0;width:100vw;height:100vh}}{fontcss}"
    "</style></head><body>\n{svg}\n</body></html>\n"
)

_RASTER_HTML = (
    "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>{title}</title><style>html,body{{margin:0;height:100%;background:#000}}"
    "#pp-img{{position:fixed;inset:0;width:100%;height:100%;object-fit:contain}}"
    "</style></head><body><img id=\"pp-img\" alt=\"slide\">\n"
    "<script>\nvar imgs={imgs};var i={start};var el=document.getElementById('pp-img');"
    "function show(n){{i=(n+imgs.length)%imgs.length;el.src=imgs[i];}}"
    "document.addEventListener('keydown',function(e){{"
    "if(['ArrowRight',' ','PageDown','Enter'].indexOf(e.key)>=0)show(i+1);"
    "else if(['ArrowLeft','PageUp','Backspace'].indexOf(e.key)>=0)show(i-1);"
    "else if(e.key==='Home')show(0);else if(e.key==='End')show(imgs.length-1);"
    "else if(e.key==='f'||e.key==='F'){{if(document.fullscreenElement)"
    "document.exitFullscreen();else document.documentElement.requestFullscreen();}}"
    "else return;e.preventDefault();}});"
    "el.addEventListener('click',function(e){{show(e.clientX<innerWidth/3?i-1:i+1);}});"
    "show(i);\n</script></body></html>\n"
)


def build_vector(pres, transition="fade", loop=False, title="Presentation",
                 embed_fonts=False):
    tree = jsexport.build(pres, transition=transition, loop=loop)
    root = tree.getroot()
    fontcss = ""
    if embed_fonts:
        from . import fonts
        css = fonts.embed_css(root)
        if css:
            fontcss = css
    svg = ET.tostring(root, encoding="unicode")
    return _VECTOR_HTML.format(title=_esc(title), svg=svg, fontcss=fontcss)


def build_raster(pres, scale=2.0, title="Presentation", start=0):
    import json

    uris = []
    for slide in pres.slides():
        png, _ = slides.slide_png_bytes(pres, slide, scale=scale)
        uris.append("data:image/png;base64," + base64.b64encode(png).decode("ascii"))
    return _RASTER_HTML.format(title=_esc(title), imgs=json.dumps(uris), start=int(start))


def write(pres, path, mode="vector", **kw):
    html = build_raster(pres, **kw) if mode == "raster" else build_vector(pres, **kw)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


def _esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
