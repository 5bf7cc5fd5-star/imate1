#!/usr/bin/env python3
"""Stop Shares floating to the right: never style bare .nav with left/right/width."""
from pathlib import Path

def patch(p: Path):
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8", errors="replace")
    orig = t
    t = t.replace("nav.bottom,.nav, .bottom-nav", "nav.bottom,.bottom-nav")
    t = t.replace("nav.bottom,.nav{", "nav.bottom{")
    t = t.replace("nav.bottom,.nav {", "nav.bottom{")
    t = t.replace("top:-14px;", "top:0!important;")
    if t != orig:
        p.write_text(t, encoding="utf-8")
        print("patched dangerous .nav selectors in", p.name)
    else:
        print("no selector changes in", p.name)

def main():
    root = Path(__file__).resolve().parent
    for name in ("index.html", "frontend.html"):
        patch(root / name)

if __name__ == "__main__":
    main()
