#!/usr/bin/env python3
"""Boot Own Club: patch HTML so iPhone nav stays one row, then start."""
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent

NAV_STYLE = """\n<style id=\"nav-row-live\">\nnav.bottom{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:flex-end!important;justify-content:space-between!important;position:fixed!important;left:0!important;right:0!important;bottom:0!important;width:100%!important;max-width:100%!important;min-height:58px!important;padding:6px 0 calc(8px + env(safe-area-inset-bottom,0px))!important;margin:0!important;background:#050a12!important;z-index:90!important;transform:none!important}\nnav.bottom>.nav,nav.bottom button.nav{position:relative!important;left:auto!important;right:auto!important;top:0!important;width:20%!important;max-width:20%!important;flex:1 1 20%!important;display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:flex-end!important;height:52px!important;margin:0!important;padding:0 1px 2px!important;border:0!important;background:transparent!important;transform:none!important;float:none!important;font-size:10px!important;font-weight:700!important;color:#8aa0b4!important}\nnav.bottom>.nav.nav-center{position:relative!important;left:auto!important;right:auto!important;top:0!important;transform:none!important}\nnav.bottom .nav-center-btn{width:40px!important;height:40px!important;border-radius:50%!important;margin:0 0 2px!important;transform:none!important}\n</style>\n"""

def fix_html(text):
    text = text.replace("nav.bottom,.nav, .bottom-nav", "nav.bottom,.bottom-nav")
    text = text.replace("nav.bottom,.nav{", "nav.bottom{")
    text = text.replace("nav.bottom,.nav {", "nav.bottom{")
    text = text.replace("top:-14px;", "top:0!important;")
    if "nav-row-live" not in text:
        text = text.replace("</body>", NAV_STYLE + "</body>", 1) if "</body>" in text else text + NAV_STYLE
    return text

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = fix_html(old)
        if new != old:
            p.write_text(new, encoding="utf-8")
            print("html fixed", name)

sp = root / "server.py"
if sp.exists():
    s = sp.read_text(encoding="utf-8", errors="replace")
    old = """        data = path.read_bytes()\n        self.send_response(200)\n        self.send_header(\"Content-Type\", content_type)\n        self.send_header(\"Content-Length\", str(len(data)))\n        self._cors()\n        self.end_headers()\n        self.wfile.write(data)\n"""
    new = """        data = path.read_bytes()\n        if b\"<html\" in data[:4000] or str(path).endswith(\".html\"):\n            html = data.decode(\"utf-8\", \"replace\")\n            html = html.replace(\"nav.bottom,.nav, .bottom-nav\", \"nav.bottom,.bottom-nav\")\n            html = html.replace(\"nav.bottom,.nav{\", \"nav.bottom{\")\n            html = html.replace(\"top:-14px;\", \"top:0!important;\")\n            if \"nav-row-live\" not in html:\n                html = html.replace(\"</body>\", """ + repr(NAV_STYLE) + """ + \"</body>\", 1)\n            data = html.encode(\"utf-8\")\n        self.send_response(200)\n        self.send_header(\"Content-Type\", content_type)\n        self.send_header(\"Content-Length\", str(len(data)))\n        self.send_header(\"Cache-Control\", \"no-store\")\n        self._cors()\n        self.end_headers()\n        self.wfile.write(data)\n"""
    if old in s:
        sp.write_text(s.replace(old, new, 1), encoding="utf-8")
        print("server.py patched")
    else:
        print("server.py pattern skip")

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
