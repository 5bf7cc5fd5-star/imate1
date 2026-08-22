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

INJECT = """
<link rel=\"stylesheet\" href=\"/static/edge-fix.css?v=21\">
<script src=\"/static/market-data.js?v=21\"></script>
<script src=\"/static/lock-nav.js?v=21\"></script>
<script src=\"/static/nav-rules.js?v=21\"></script>
<style id=\"fullbleed-21\">
html,body{background:#07140f!important;overflow:hidden!important;height:100dvh!important;margin:0!important;}
.space-bg,.space-bg *,#leagueFx,.league-fx{display:none!important;}
#mainApp,.app{position:fixed!important;top:0!important;left:0!important;right:0!important;bottom:56px!important;width:100%!important;max-width:none!important;overflow-y:auto!important;background:#07140f!important;z-index:2!important;}
.page,#home,#market,#machines,#team,#my{background:#07140f!important;width:100%!important;max-width:none!important;}
nav.bottom{position:fixed!important;left:0!important;right:0!important;bottom:0!important;width:100%!important;height:56px!important;z-index:2147483647!important;background:#0b0d10!important;}
body.auth-open nav.bottom{display:none!important;}
.lg-table{width:100%;color:#fff;font-size:12px;}
.lg-head,.lg-row{display:grid;grid-template-columns:1.15fr 1.25fr .8fr .75fr;gap:6px;align-items:center;padding:10px 4px;border-bottom:1px solid #163326;}
.lg-head{color:#9aa3ad;font-weight:700;font-size:11px;}
.lg-name{font-weight:700;}
.lg-shown{color:#b8c0c8;}
.lg-net,.lg-rev{text-align:right;font-weight:700;white-space:nowrap;}
.lg-rev{color:#2ee56a;}
</style>
"""

def fix_html(text):
    text = text.replace("nav.bottom,.nav{", "nav.bottom{")
    text = text.replace("top:-14px;", "top:0!important;")
    text = text.replace("max-width:430px", "max-width:none")
    text = text.replace("width:430px", "width:100%")
    if "fullbleed-21" not in text:
        if "</body>" in text:
            text = text.replace("</body>", INJECT + "\n</body>", 1)
        elif "</head>" in text:
            text = text.replace("</head>", INJECT + "\n</head>", 1)
    return text

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = fix_html(old)
        if new != old:
            p.write_text(new, encoding="utf-8")
            print("html fixed", name)

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
