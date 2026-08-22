#!/usr/bin/env python3
from pathlib import Path
import runpy
import subprocess
import sys

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)
(root / "data").mkdir(exist_ok=True)

inj = root / "inject_ops.py"
if inj.exists():
    try:
        subprocess.check_call([sys.executable, str(inj)], cwd=str(root))
    except Exception as e:
        print("inject_ops failed", e)

APP_INJECT = """
<link rel=\"stylesheet\" href=\"/static/edge-fix.css?v=25\">
<script src=\"/static/market-data.js?v=25\"></script>
<script src=\"/static/lock-nav.js?v=25\"></script>
<script src=\"/static/nav-rules.js?v=25\"></script>
<script src=\"/static/member-id.js?v=25\"></script>
<style id=\"fullbleed-25\">
html,body{background:#07140f!important;overflow:hidden!important;height:100dvh!important;margin:0!important;}
.space-bg,.space-bg *,#leagueFx,.league-fx{display:none!important;}
#mainApp,.app{position:fixed!important;top:0!important;left:0!important;right:0!important;bottom:56px!important;width:100%!important;max-width:none!important;overflow-y:auto!important;background:#07140f!important;z-index:2!important;}
nav.bottom{position:fixed!important;left:0!important;right:0!important;bottom:0!important;width:100%!important;height:56px!important;z-index:2147483647!important;background:#0b0d10!important;}
body.auth-open nav.bottom{display:none!important;}
</style>
"""

ADMIN_INJECT = """
<script src=\"/static/staff-admin.js?v=25\"></script>
"""

def inject_once(text, needle, blob):
    if needle in text:
        return text.replace("/static/staff-admin.js?v=24", "/static/staff-admin.js?v=25")
    if "</body>" in text:
        return text.replace("</body>", blob + "\n</body>", 1)
    return text + blob

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = old.replace("nav.bottom,.nav{", "nav.bottom{")
        new = new.replace("max-width:430px", "max-width:none")
        new = inject_once(new, "fullbleed-25", APP_INJECT)
        if new != old:
            p.write_text(new, encoding="utf-8")
            print("html fixed", name)

ap = root / "admin.html"
if ap.exists():
    old = ap.read_text(encoding="utf-8", errors="replace")
    new = inject_once(old, "staff-admin.js", ADMIN_INJECT)
    if new != old:
        ap.write_text(new, encoding="utf-8")
        print("admin staff injected")

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
