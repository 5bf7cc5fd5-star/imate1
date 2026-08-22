"""Replace old owner/momo numbers with +256779168109 / 0779168109."""
from pathlib import Path

NEW = "+256779168109"
LOCAL = "0779168109"
PAIRS = [
    ("+256780509960", NEW),
    ("+256780609970", NEW),
    ("256780509960", "256779168109"),
    ("256780609970", "256779168109"),
    ("0780509960", LOCAL),
]

def patch_text(t: str) -> str:
    for a, b in PAIRS:
        t = t.replace(a, b)
    return t

def run():
    root = Path(__file__).resolve().parent
    changed = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".py", ".html", ".js", ".md", ".txt", ".example", ".json"}:
            continue
        if "node_modules" in p.parts:
            continue
        try:
            raw = p.read_text(encoding="utf-8", errors="strict")
        except Exception:
            continue
        new = patch_text(raw)
        if new != raw:
            p.write_text(new, encoding="utf-8")
            changed.append(str(p.relative_to(root)))
    print("phone patched:", ", ".join(changed) if changed else "none")

if __name__ == "__main__":
    run()
