#!/usr/bin/env python3
from pathlib import Path
import runpy, subprocess, sys, base64, re

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)
(root / "data").mkdir(exist_ok=True)

bp = root / "static" / "logo.b64"
if bp.exists():
    try:
        data = base64.b64decode(bp.read_text().strip())
        (root / "own-club-logo.jpg").write_bytes(data)
        (root / "static" / "own-club-logo.jpg").write_bytes(data)
        print("logo written", len(data))
    except Exception as e:
        print("logo decode", e)

src = root / "own-club-logo.jpg"
dst = root / "static" / "own-club-logo.jpg"
if src.exists():
    dst.write_bytes(src.read_bytes())
    print("logo copied to static", dst.stat().st_size)

try:
    import persist; persist.init()
except Exception as e:
    print("persist init", e)

for script in ("inject_ops.py", "fix_admin_phone.py", "patch_phones.py", "migrate.py"):
    p = root / script
    if p.exists():
        try:
            subprocess.check_call([sys.executable, str(p)], cwd=str(root))
        except Exception as e:
            print(script, "failed", e)

srv = root / "server.py"
if srv.exists():
    st = srv.read_text(encoding="utf-8", errors="replace")
    needle = 'if path.startswith("/static/"):'
    patch = '''if path in ("/own-club-logo.jpg", "/own-club-logo.jpeg", "/logo.jpg"):
            p = Path(__file__).parent / "own-club-logo.jpg"
            if not p.is_file():
                p = Path(__file__).parent / "static" / "own-club-logo.jpg"
            if p.is_file():
                return self._serve_file(str(p), "image/jpeg", absolute=True)
        if path.startswith("/static/"):'''
    if 'if path in ("/own-club-logo.jpg"' not in st and needle in st:
        srv.write_text(st.replace(needle, patch, 1), encoding="utf-8")
        print("server logo route patched")

INJECT = [
    '<link rel="stylesheet" href="/static/app-shell-fix.css?v=49">',
    '<script src="/static/login-tight.js?v=49"></script>',
    '<script src="/static/app-shell-fix.js?v=49"></script>',
]
block = "\n".join(INJECT)
for name in ("index.html", "frontend.html"):
    p = root / name
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    t2 = re.sub(r'<script[^>]*login-tight\\.js[^>]*></script>', '', t)
    t2 = re.sub(r'<link[^>]*app-shell-fix\\.css[^>]*>', '', t2)
    t2 = re.sub(r'<script[^>]*app-shell-fix\\.js[^>]*></script>', '', t2)
    if "</body>" in t2:
        t2 = t2.replace("</body>", block + "\n</body>", 1)
    else:
        t2 += "\n" + block
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        print("injected v49", name)

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
