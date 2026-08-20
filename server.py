#!/usr/bin/env python3
# Own Club loader — stitches body parts then runs
from pathlib import Path
import runpy, sys
base = Path(__file__).resolve().parent
code = (base / "server_body_a.py").read_text(encoding="utf-8")
code += (base / "server_body_b.py").read_text(encoding="utf-8")
ns = {"__name__": "__main__", "__file__": str(base / "server.py")}
exec(compile(code, str(base / "server.py"), "exec"), ns)
