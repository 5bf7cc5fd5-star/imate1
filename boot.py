#!/usr/bin/env python3
from pathlib import Path
import runpy
import subprocess
import sys

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)
(root / "data").mkdir(exist_ok=True)

for script in ("inject_ops.py", "fix_admin_phone.py"):
    p = root / script
    if p.exists():
        try:
            subprocess.check_call([sys.executable, str(p)], cwd=str(root))
        except Exception as e:
            print(script, "failed", e)

sp = root / "server.py"
if sp.exists():
    t = sp.read_text(encoding="utf-8", errors="replace")
    t2 = t.replace('+256780509960', '+256779168109')
    if t2 != t:
        sp.write_text(t2, encoding="utf-8")
        print("server.py admin phone updated")

APP_INJECT = """
<link rel=\"stylesheet\" href=\"/static/edge-fix.css?v=27\">
<script src=\"/static/market-data.js?v=27\"></script>
<script src=\"/static/lock-nav.js?v=27\"></script>
<script src=\"/static/nav-rules.js?v=27\"></script>
<script src=\"/static/member-id.js?v=27\"></script>
<script src=\"/static/tx-history.js?v=27\"></script>
<style id=\"fullbleed-27\">
html,body{background:#07140f!important;overflow:hidden!important;height:100dvh!important;margin:0!important;}
.space-bg,.space-bg *,#leagueFx,.league-fx{display:none!important;}
#mainApp,.app{position:fixed!important;top:0!important;left:0!important;right:0!important;bottom:56px!important;width:100%!important;max-width:none!important;overflow-y:auto!important;background:#07140f!important;z-index:2!important;}
nav.bottom{position:fixed!important;left:0!important;right:0!important;bottom:0!important;width:100%!important;height:56px!important;z-index:2147483647!important;background:#0b0d10!important;}
body.auth-open nav.bottom{display:none!important;}
</style>
"""

ADMIN_INJECT = """
<script src=\"/static/staff-admin.js?v=27\"></script>
"""

def inject_once(text, needle, blob):
    if needle in text:
        return text.replace("staff-admin.js?v=26", "staff-admin.js?v=27")
    if "</body>" in text:
        return text.replace("</body>", blob + "\n</body>", 1)
    return text + blob

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = inject_once(old, "fullbleed-27", APP_INJECT)
        if new != old:
            p.write_text(new, encoding="utf-8")

ap = root / "admin.html"
if ap.exists():
    old = ap.read_text(encoding="utf-8", errors="replace")
    new = inject_once(old, "staff-admin.js", ADMIN_INJECT)
    if new != old:
        ap.write_text(new, encoding="utf-8")

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
