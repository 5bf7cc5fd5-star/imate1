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

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
