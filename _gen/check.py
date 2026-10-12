#!/usr/bin/env python3
"""Check the built site before it ships. Exit 1 on any failure.

  python3 _gen/check.py            the site this file belongs to
  python3 _gen/check.py <root>     another copy (the positive control breaks one on purpose)

Checks: every internal link, anchor and image resolves; image width/height match the file;
JSON-LD parses; one h1, a title, a description and a self-canonical per page; App Store
links carry both pt and ct, and never sit beside a 'Coming soon' (ON_STORE is all or nothing); the sitemap lists exactly the pages; and the visible copy has
no em or en dashes, no hype words from brand.md, and no named competitor.

While the domain is a placeholder (_gen/config.py, DOMAIN_IS_FINAL = False) it also holds
the site shut: every page noindex, robots.txt disallowing everything, no CNAME. With a
real domain the three flip: no noindex anywhere, robots allows, CNAME names the domain.
"""
import json
import os
import re
import sys
from html.parser import HTMLParser
from xml.etree import ElementTree

GEN = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(GEN)
from config import DOMAIN, DOMAIN_IS_FINAL

HYPE = [r"\bgame[- ]changer\b", r"\brevolutionary\b", r"\blife[- ]changing\b", r"\bthe best\b",
        r"#1\b", r"\bguaranteed?\b", r"\bnever forget\b", r"\blimited time\b", r"\bact now\b",
        r"\bdon'?t miss out\b", r"\bcrush\b", r"\bsmash\b", r"\bdominate\b"]
# Names that are also plain words (Streaks, Strong, Forest, Finch) are left out: a guide about
# streaks would trip them.
COMPETITORS = ["Habitica", "LifeRPG", "Level Up Life", "Strava", "Fitbod", "Hevy",
               "Nike Run Club", "Nike Training Club", "Zombies, Run", "Duolingo", "Todoist",
               "TickTick", "MyFitnessPal", "Fitbit", "Whoop", "Gentler Streak", "Solo Leveling"]
VOID = {"meta", "link", "img", "br", "hr", "input", "source", "area", "base", "col", "embed",
        "param", "track", "wbr"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors = [], []
        self.links, self.imgs, self.ids = [], [], set()
        self.text, self.jsonld, self.h1 = [], [], 0
        self.title = self.desc = self.canonical = None
        self.noindex = False
        self._skip = 0          # inside <script>/<style>: not visible copy
        self._ld = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.links.append(a["href"])
        if tag == "link" and a.get("rel") in ("stylesheet", "icon", "apple-touch-icon"):
            self.links.append(a["href"])
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a["href"]
        if tag == "img":
            self.imgs.append(a)
        if tag == "meta" and a.get("name") == "robots" and "noindex" in a.get("content", ""):
            self.noindex = True
        if tag == "meta" and a.get("name") == "description":
            self.desc = a.get("content", "")
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._in_title = True
        if tag in ("script", "style"):
            self._skip += 1
            if a.get("type") == "application/ld+json":
                self._ld = []

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unbalanced </{tag}> (open: {self.stack[-3:]})")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()
        if tag in ("script", "style"):
            self._skip -= 1
            if self._ld is not None:
                self.jsonld.append("".join(self._ld))
                self._ld = None
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        if self._in_title:
            self.title = (self.title or "") + data
        if not self._skip:
            self.text.append(data)


def target(path):
    """Site-root path -> file on disk."""
    p = path.split("#")[0].split("?")[0]
    if p.endswith("/"):
        p += "index.html"
    return os.path.join(ROOT, p.lstrip("/"))


def main():
    fails = []
    pages = {}
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
        for f in files:
            if f.endswith(".html"):
                full = os.path.join(dirpath, f)
                rel = "/" + os.path.relpath(full, ROOT).replace("index.html", "")
                pg = Page()
                pg.feed(open(full, encoding="utf-8").read())
                pg.close()
                pages[rel] = pg

    for rel, pg in sorted(pages.items()):
        where = rel
        for e in pg.errors:
            fails.append(f"{where}: {e}")
        if pg.stack:
            fails.append(f"{where}: unclosed {pg.stack}")
        if pg.h1 != 1:
            fails.append(f"{where}: {pg.h1} h1 elements")
        if not pg.title or not pg.desc:
            fails.append(f"{where}: missing title or description")
        elif len(pg.desc) > 160:
            fails.append(f"{where}: description {len(pg.desc)} chars (Google cuts at about 160)")
        if pg.title and len(pg.title) > 60:
            fails.append(f"{where}: title {len(pg.title)} chars (Google cuts at about 60)")
        if pg.noindex == DOMAIN_IS_FINAL:
            fails.append(f"{where}: " + ("noindex on a live domain" if DOMAIN_IS_FINAL
                                         else "no noindex while the domain is a placeholder"))
        expected = DOMAIN + ("/404.html" if rel == "/404.html" else rel)
        if pg.canonical != expected:
            fails.append(f"{where}: canonical {pg.canonical} != {expected}")
        for block in pg.jsonld:
            try:
                json.loads(block)
            except ValueError as e:
                fails.append(f"{where}: JSON-LD does not parse: {e}")
        for href in pg.links:
            if href.startswith("https://apps.apple.com/"):
                if "/app/apple-store/" in href and not ("pt=" in href and "ct=" in href):
                    fails.append(f"{where}: App Store link without pt and ct: {href}")
            elif href.startswith("#"):
                if href[1:] not in pg.ids:
                    fails.append(f"{where}: anchor {href} has no target")
            elif href.startswith("/"):
                if not os.path.isfile(target(href)):
                    fails.append(f"{where}: broken link {href}")
                elif "#" in href:
                    frag = href.split("#", 1)[1]
                    other = pages.get(href.split("#")[0] or "/")
                    if other is None or frag not in other.ids:
                        fails.append(f"{where}: anchor {href} has no target")
            elif not href.startswith(("https://", "mailto:")):
                fails.append(f"{where}: odd link {href}")
        for img in pg.imgs:
            src = img.get("src", "")
            path = target(src)
            if not os.path.isfile(path):
                fails.append(f"{where}: missing image {src}")
                continue
            if src.endswith((".png", ".webp")) and "width" in img:
                from PIL import Image
                # width/height reserve the layout box: the ratio must match the file, the
                # size may be a display size (the 180px icon shown at 34px in the nav)
                w, h = Image.open(path).size
                tw, th = int(img.get("width")), int(img.get("height"))
                if abs(w / h - tw / th) > 0.01:
                    fails.append(f"{where}: {src} is {w}x{h}, tagged {tw}x{th}")
            if "alt" not in img:
                fails.append(f"{where}: img without alt {src}")
        copy = " ".join(" ".join(pg.text).split()) + " " + (pg.title or "") + " " + (pg.desc or "")
        for ch, name in (("—", "em dash"), ("–", "en dash")):
            if ch in copy:
                i = copy.index(ch)
                fails.append(f"{where}: {name}: ...{copy[max(0, i - 40):i + 40]}...")
        for pat in HYPE:
            m = re.search(pat, copy, re.I)
            if m:
                fails.append(f"{where}: hype word '{m.group(0)}'")
        for name in COMPETITORS:
            if re.search(r"\b" + re.escape(name) + r"\b", copy):
                fails.append(f"{where}: names a competitor: {name}")

    # ON_STORE in build.py: either every download is a store link or every one reads
    # "Coming soon". A mix, or a Smart App Banner while coming soon, is a half-done switch.
    soon_pages, store_pages = [], []
    for rel in pages:
        raw = open(target(rel), encoding="utf-8").read()
        soon = "soon-pill" in raw or "nav-cta--soon" in raw
        store = "apps.apple.com/app/" in raw or "apple-itunes-app" in raw
        if soon and store:
            fails.append(f"{rel}: both 'Coming soon' and an App Store link or banner")
        (soon_pages if soon else store_pages if store else []).append(rel)
    if soon_pages and store_pages:
        fails.append(f"site: coming soon on {len(soon_pages)} pages, store links on {sorted(store_pages)}")

    sm = ElementTree.parse(os.path.join(ROOT, "sitemap.xml")).getroot()
    locs = sorted(e.text for e in sm.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"))
    want = sorted(DOMAIN + rel for rel in pages if rel != "/404.html")
    if locs != want:
        fails.append(f"sitemap: extra {sorted(set(locs) - set(want))}, missing {sorted(set(want) - set(locs))}")
    robots = open(os.path.join(ROOT, "robots.txt")).read()
    cname = os.path.join(ROOT, "CNAME")
    host = DOMAIN.split("://", 1)[1]
    if DOMAIN_IS_FINAL:
        if not os.path.isfile(cname) or open(cname).read().strip() != host:
            fails.append(f"CNAME is not {host}")
        if "Disallow: /" in robots or f"Sitemap: {DOMAIN}/sitemap.xml" not in robots:
            fails.append("robots.txt does not open the live site")
    else:
        if os.path.exists(cname):
            fails.append("CNAME exists while the domain is a placeholder")
        if "Disallow: /" not in robots:
            fails.append("robots.txt allows crawling while the domain is a placeholder")

    for f in fails:
        print("FAIL", f)
    print(f"{len(pages)} pages, {len(locs)} sitemap urls, {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
