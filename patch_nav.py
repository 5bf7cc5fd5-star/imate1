#!/usr/bin/env python3
"""Align bottom nav labels on one line + football Shares icon."""
from pathlib import Path

FOOTBALL = (
    '<svg viewBox="0 0 24 24" fill="#fff" width="22" height="22">'
    '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 2.07c1.81.2 3.47.97 4.77 2.12l-1.6 1.6A6.97 6.97 0 0 0 13 4.07zM6.83 6.83A7.96 7.96 0 0 1 11 4.07v2.86L7.94 9.99 6.83 6.83zM4.07 11H6.9l-1.5 1.5A6.9 6.9 0 0 1 4.07 11zM11 19.93A7.96 7.96 0 0 1 4.07 13H6.9l3.07 3.07v3.86H11zm2 0v-3.86L16.07 13H19.93A7.96 7.96 0 0 1 13 19.93zM19.93 11h-2.86l1.5-1.5c.4.9.64 1.88.64 2.93 0-.35-.04-.69-.1-1.02l.82-.41zM14.06 9.99 17.17 6.83A7.96 7.96 0 0 0 13 4.07v2.86l1.06 3.06zM9.5 12c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5-.67 1.5-1.5 1.5-1.5-.67-1.5-1.5z"/>'
    '</svg>'
)

def patch(p: Path):
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8", errors="replace")
    orig = t

    t = t.replace(
        "nav.bottom .nav.nav-center{\n  position:relative; top:-14px;\n}",
        "nav.bottom .nav.nav-center{\n  position:relative; top:0!important; transform:none!important;\n}",
    )
    t = t.replace("top:-14px;", "top:0!important;")

    old_btn = """nav.bottom .nav-center-btn{\n  width:52px;height:52px;border-radius:50%;\n  background:linear-gradient(145deg,#00c853,#009624);\n  display:flex;align-items:center;justify-content:center;\n  box-shadow:0 6px 18px rgba(0,200,83,.4);\n}"""
    new_btn = """nav.bottom .nav-center-btn{\n  width:46px;height:46px;border-radius:50%;\n  background:linear-gradient(145deg,#00c853,#009624);\n  display:flex;align-items:center;justify-content:center;\n  box-shadow:0 4px 12px rgba(0,200,83,.35);\n  margin-top:-18px!important;\n}"""
    if old_btn in t:
        t = t.replace(old_btn, new_btn)

    import re
    t2, n = re.subn(
        r'(<span class="nav-center-btn"[^>]*>)\s*<svg[\s\S]*?</svg>',
        r"\1" + FOOTBALL,
        t,
        count=1,
    )
    if n:
        t = t2
        print("replaced center Shares icon with football")

    if t != orig:
        p.write_text(t, encoding="utf-8")
        print("patched nav in", p.name, "len", len(t))
    else:
        print("no nav changes needed in", p.name)

def main():
    root = Path(__file__).resolve().parent
    for name in ("index.html", "frontend.html"):
        patch(root / name)

if __name__ == "__main__":
    main()
