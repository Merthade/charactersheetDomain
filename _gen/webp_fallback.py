#!/usr/bin/env python3
"""WebP fallback: every WebP gets a PNG twin, and every <img> showing a WebP swaps to it on error.

    python3 _gen/webp_fallback.py           twins + every page (the site generator runs it last)
    python3 _gen/webp_fallback.py --check [root]   exit 1 if a WebP <img> has no working fallback

Some company networks refuse image/webp outright (Emil's work laptop, 2026-10-30: a security error
on every .webp while PNGs load), so every image on the site showed broken. A <picture> with a PNG
<source> would not help: the browser picks the WebP it supports and never retries. The onerror is
inline so it is attached before the image can fail. Normal visitors still load only the WebPs.
Twins are full-colour PNGs: Pillow's 256-colour octree tinted screenshots pink. Same fix as
getchoru.com (`d67195b`); Holocron knowledge/engineering.md#work-networks-block-webp.
"""
import os
import re
import sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = re.compile(r"<img\b[^>]*>")
SRC = re.compile(r'\bsrc="([^"]+?)\.webp(?:\?[^"]*)?"')
SCRIPT = re.compile(r"(<script\b.*?</script>)", re.S)


def files(ext, root=SITE):
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
        for name in names:
            if name.endswith(ext):
                yield os.path.join(dirpath, name)


def local(url):
    return not url.startswith(("http:", "https:", "//", "data:"))


def with_fallback(tag):
    m = SRC.search(tag)
    if not m or not local(m.group(1)) or "onerror=" in tag:
        return tag
    return tag[:m.end()] + f" onerror=\"this.onerror=null;this.src='{m.group(1)}.png'\"" + tag[m.end():]


def tag_page(text):
    # Script blocks (JSON-LD screenshot lists, inline JS) are left alone.
    return "".join(part if SCRIPT.fullmatch(part) else IMG.sub(lambda m: with_fallback(m.group(0)), part)
                   for part in SCRIPT.split(text))


def twins():
    from PIL import Image
    made = 0
    for path in files(".webp"):
        twin = path[:-len(".webp")] + ".png"
        if not os.path.exists(twin) or os.path.getmtime(twin) < os.path.getmtime(path):
            Image.open(path).save(twin, "PNG", optimize=True)
            made += 1
    return made


def run():
    made, pages = twins(), 0
    for path in files(".html"):
        text = open(path, encoding="utf-8").read()
        new = tag_page(text)
        if new != text:
            open(path, "w", encoding="utf-8").write(new)
            pages += 1
    print(f"webp fallback: {made} PNG twins written, onerror added on {pages} pages")


def check(root=SITE):
    """Every local WebP <img> carries the onerror, and its PNG twin exists. Returns the failures."""
    fails = []
    for path in files(".html", root):
        rel = os.path.relpath(path, root)
        for part in SCRIPT.split(open(path, encoding="utf-8").read()):
            if SCRIPT.fullmatch(part):
                continue
            for tag in IMG.findall(part):
                m = SRC.search(tag)
                if not m or not local(m.group(1)):
                    continue
                twin = m.group(1) + ".png"
                if f"this.src='{twin}'" not in tag:
                    fails.append(f"{rel}: {m.group(1)}.webp has no onerror fallback")
                    continue
                file = (os.path.join(root, twin.lstrip("/")) if twin.startswith("/")
                        else os.path.normpath(os.path.join(os.path.dirname(path), twin)))
                if not os.path.isfile(file):
                    fails.append(f"{rel}: {m.group(1)}.webp falls back to a missing {twin}")
    return fails


if __name__ == "__main__":
    if sys.argv[1:2] == ["--check"]:
        problems = check(os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else SITE)
        for p in problems:
            print("FAIL", p)
        print(f"webp fallback check: {len(problems)} failures")
        sys.exit(1 if problems else 0)
    run()
