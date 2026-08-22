#!/usr/bin/env python3
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent

# Assemble split frontend if present (app.part*.html preferred)
parts = sorted(root.glob("app.part*.html"))
if not parts:
    parts = sorted(root.glob("frontend.part*.html"))
if parts:
    html = b"".join(p.read_bytes() for p in parts)
    (root / "index.html").write_bytes(html)
    (root / "frontend.html").write_bytes(html)
    print("assembled", len(html), "from", [p.name for p in parts])
else:
    print("no part files — using existing index.html / frontend.html")

# Force edge-to-edge stylesheet + aggressive inline on every HTML shell
link = b'<link rel="stylesheet" href="/static/edge-fix.css" id="edge-fix-link">'
inline = (
    b'<style id="edge-force">'
    b'html,body{width:100vw!important;max-width:100vw!important;margin:0!important;padding:0!important;overflow-x:hidden!important;background:#02060c!important;min-height:100dvh!important}'
    b'.app,#mainApp{width:100vw!important;max-width:100vw!important;margin:0!important;left:0!important;right:0!important;border-radius:0!important;padding-bottom:calc(64px + env(safe-area-inset-bottom,0px))!important}'
    b'nav.bottom,.bottom{position:fixed!important;left:0!important;right:0!important;bottom:0!important;width:100vw!important;max-width:100vw!important;transform:none!important;display:flex!important;align-items:center!important;justify-content:space-around!important;height:64px!important;padding:4px 2px calc(4px + env(safe-area-inset-bottom,0px))!important;background:#050a12!important;z-index:50!important;border-radius:0!important}'
    b'nav.bottom .nav{flex:1!important;display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;height:100%!important;top:0!important;margin:0!important;padding:2px 1px!important;transform:none!important;font-size:10px!important}'
    b'nav.bottom .nav.nav-center,nav.bottom .nav-center{top:0!important;transform:none!important;margin-top:0!important}'
    b'nav.bottom .nav-center-btn{width:28px!important;height:28px!important;border-radius:50%!important;margin:0!important;transform:none!important}'
    b'.content,header,.page{padding-left:10px!important;padding-right:10px!important;width:100%!important;max-width:100%!important}'
    b'</style>'
)
for name in ("index.html", "frontend.html", "admin.html"):
    p = root / name
    if not p.exists():
        continue
    data = p.read_bytes()
    changed = False
    if b"edge-fix.css" not in data and b"</head>" in data:
        data = data.replace(b"</head>", link + b"</head>", 1)
        changed = True
    if b"edge-force" not in data and b"</head>" in data:
        data = data.replace(b"</head>", inline + b"</head>", 1)
        changed = True
    if changed:
        p.write_bytes(data)
        print("injected edge CSS into", name)

runpy.run_path(str(root / "server.py"), run_name="__main__")
