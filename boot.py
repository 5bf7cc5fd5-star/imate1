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
    t = t.replace("+256780509960", "+256779168109")
    old = "DATA_DIR = Path(__file__).parent / \"data\"\nDATA_DIR.mkdir(exist_ok=True)"
    new = """try:\n    import persist as _persist\n    DATA_DIR = _persist.init()\nexcept Exception:\n    DATA_DIR = Path(__file__).parent / \"data\"\n    DATA_DIR.mkdir(exist_ok=True)"""
    if old in t and "import persist as _persist" not in t:
        t = t.replace(old, new, 1)
        print("server DATA_DIR -> persist")
    old_save = """def save_json(path, data):\n    with open(path, \"w\", encoding=\"utf-8\") as f:\n        json.dump(data, f, indent=2, ensure_ascii=False)"""
    new_save = """def save_json(path, data):\n    try:\n        import persist as _p\n        _p.backup(Path(path))\n    except Exception:\n        pass\n    tmp = Path(str(path) + \".tmp\")\n    with open(tmp, \"w\", encoding=\"utf-8\") as f:\n        json.dump(data, f, indent=2, ensure_ascii=False)\n    tmp.replace(Path(path))"""
    if old_save in t and "_p.backup" not in t:
        t = t.replace(old_save, new_save, 1)
        print("server save_json safe")
    sp.write_text(t, encoding="utf-8")

APP_INJECT = """
<link rel=\"stylesheet\" href=\"/static/edge-fix.css?v=28\">
<script src=\"/static/market-data.js?v=28\"></script>
<script src=\"/static/lock-nav.js?v=28\"></script>
<script src=\"/static/nav-rules.js?v=28\"></script>
<script src=\"/static/member-id.js?v=28\"></script>
<script src=\"/static/tx-history.js?v=28\"></script>
<style id=\"fullbleed-28\">
html,body{background:#07140f!important;overflow:hidden!important;height:100dvh!important;margin:0!important;}
.space-bg,.space-bg *,#leagueFx,.league-fx{display:none!important;}
#mainApp,.app{position:fixed!important;top:0!important;left:0!important;right:0!important;bottom:56px!important;width:100%!important;max-width:none!important;overflow-y:auto!important;background:#07140f!important;z-index:2!important;}
nav.bottom{position:fixed!important;left:0!important;right:0!important;bottom:0!important;width:100%!important;height:56px!important;z-index:2147483647!important;background:#0b0d10!important;}
body.auth-open nav.bottom{display:none!important;}
</style>
"""
ADMIN_INJECT = """
<script src=\"/static/staff-admin.js?v=28\"></script>
"""

def inject_once(text, needle, blob):
    if needle in text:
        return text.replace("staff-admin.js?v=27", "staff-admin.js?v=28")
    if "</body>" in text:
        return text.replace("</body>", blob + "\n</body>", 1)
    return text + blob

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = inject_once(old, "fullbleed-28", APP_INJECT)
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
