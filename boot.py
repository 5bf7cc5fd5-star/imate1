#!/usr/bin/env python3
from pathlib import Path
import runpy
import re
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
<link rel=\"stylesheet\" href=\"/static/edge-fix.css?v=14\">
<script src=\"/static/market-data.js?v=14\"></script>
<script src=\"/static/lock-nav.js?v=14\"></script>
<style id=\"fullbleed-14\">
html,body,#mainApp,.app,.app-shell,.space-bg,.page,.content{
  width:100%!important;max-width:none!important;min-width:0!important;
  margin:0!important;left:0!important;right:0!important;
}
@media (min-width:768px){
  .app,#mainApp,#authScreen,.wiyak-auth,nav.bottom{
    max-width:none!important;width:100%!important;margin:0!important;
    left:0!important;right:0!important;transform:none!important;
  }
}
nav.bottom{
  position:fixed!important;left:0!important;right:0!important;bottom:0!important;
  width:100%!important;max-width:none!important;transform:none!important;
}
</style>
"""

def fix_html(text):
    text = text.replace("nav.bottom,.nav{", "nav.bottom{")
    text = text.replace("top:-14px;", "top:0!important;")
    text = text.replace("max-width:430px", "max-width:none")
    text = text.replace("width:430px", "width:100%")
    if "fullbleed-14" not in text:
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
