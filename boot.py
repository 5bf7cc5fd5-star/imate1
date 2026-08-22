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
<link rel=\"stylesheet\" href=\"/static/edge-fix.css?v=17\">
<script src=\"/static/market-data.js?v=17\"></script>
<script src=\"/static/lock-nav.js?v=17\"></script>
<style id=\"fullbleed-17\">
html,body{
  background:#07140f!important;
  overflow:hidden!important;
  height:100%!important;height:100dvh!important;
  margin:0!important;padding:0!important;
}
.space-bg,.space-bg *,.warp-img,.warp-stars,#particleCanvas,
#leagueFx,.league-fx,.ucl-stars,.ucl-title,.ucl-bg{
  display:none!important;visibility:hidden!important;opacity:0!important;
}
#mainApp,.app{
  position:fixed!important;
  top:0!important;left:0!important;right:0!important;
  bottom:56px!important;
  width:100%!important;max-width:none!important;
  overflow-y:auto!important;overflow-x:hidden!important;
  background:#07140f!important;
  z-index:2!important;
  margin:0!important;border-radius:0!important;
}
.page,#home,#market,#machines,#team,#my,#account,#income{
  background:#07140f!important;
  min-height:100%!important;
  width:100%!important;max-width:none!important;
}
nav.bottom{
  position:fixed!important;left:0!important;right:0!important;bottom:0!important;
  width:100%!important;max-width:none!important;height:56px!important;
  z-index:2147483647!important;transform:none!important;
  background:#0b0d10!important;margin:0!important;
}
body.auth-open nav.bottom{display:none!important;}
#homeMarkets .mkt-row{padding:14px 0!important;}
@media (min-width:768px){
  .app,#mainApp,#authScreen,nav.bottom{
    max-width:none!important;width:100%!important;margin:0!important;transform:none!important;
  }
}
</style>
"""

def fix_html(text):
    text = text.replace("nav.bottom,.nav{", "nav.bottom{")
    text = text.replace("top:-14px;", "top:0!important;")
    text = text.replace("max-width:430px", "max-width:none")
    text = text.replace("width:430px", "width:100%")
    if "fullbleed-17" not in text:
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
