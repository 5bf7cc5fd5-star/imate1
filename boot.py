#!/usr/bin/env python3
from pathlib import Path
import runpy
import subprocess
import sys

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)
(root / "data").mkdir(exist_ok=True)

try:
    import persist
    persist.init()
except Exception as e:
    print("persist init", e)

for script in ("inject_ops.py", "fix_admin_phone.py", "migrate.py"):
    p = root / script
    if p.exists():
        try:
            subprocess.check_call([sys.executable, str(p)], cwd=str(root))
        except Exception as e:
            print(script, "failed", e)

INJECT = """
<link rel=\"stylesheet\" href=\"/static/login-tight.css?v=31\">
<script src=\"/static/login-tight.js?v=31\"></script>
<script src=\"/static/market-data.js?v=31\"></script>
<script src=\"/static/lock-nav.js?v=31\"></script>
<script src=\"/static/nav-rules.js?v=31\"></script>
<script src=\"/static/member-id.js?v=31\"></script>
<script src=\"/static/tx-history.js?v=31\"></script>
<style id=\"fb-login-31\">
#authScreen{background:#1c1c1e!important;overflow:hidden!important;}
#fbMarkWrap{width:78px;height:78px;margin:86px auto 54px;border-radius:50%;overflow:hidden;background:#000;}
#fbCreate{margin-top:auto;border:1px solid #4a90d9;color:#4a90d9;background:transparent;border-radius:22px;height:44px;}
#fbMeta{text-align:center;color:#fff;font-weight:700;margin:14px 0 6px;}
</style>
"""

def inject_once(text, needle, blob):
    if needle in text:
        return text
    if "</body>" in text:
        return text.replace("</body>", blob + "\n</body>", 1)
    return text + blob

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = inject_once(old, "fb-login-31", INJECT)
        if new != old:
            p.write_text(new, encoding="utf-8")
            print("fb login", name)

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
