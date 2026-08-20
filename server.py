#!/usr/bin/env python3
from pathlib import Path
base = Path(__file__).resolve().parent
code = "".join((base / f"sb{i}.py").read_text(encoding="utf-8") for i in range(3))
exec(compile(code, str(base / "server.py"), "exec"), {"__name__": "__main__", "__file__": str(base / "server.py")})
