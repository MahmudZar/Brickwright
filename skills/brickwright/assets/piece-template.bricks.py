"""Build script for one piece: <piece>.html + <piece>.css -> <piece>.bricks.json.

Copy this file next to the mockup as <piece>.bricks.py, rename PIECE, pick a SEED no other piece
uses, then write the element tree. Run: python -I <piece>.bricks.py
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = next(p for p in [HERE, *HERE.parents] if (p / ".brickwright" / "lib").is_dir())
sys.path.insert(0, str(ROOT / ".brickwright" / "lib"))
from bricks_gen import Build  # noqa: E402

PIECE = "hero"          # file names: hero.css -> hero.bricks.json
SEED = 1001             # unique per piece; never change it after the first deploy
FORBIDDEN = []          # words that must never reach the site, e.g. supplier names

b = Build.from_site(ROOT / ".brickwright" / "site.json", seed=SEED, forbidden=FORBIDDEN)
b.add_css_files(HERE / f"{PIECE}.css")   # owners={...} / host=... when needed (references/build-scripts.md)

# One tree per target in <piece>.targets.json. Element ids are stable as long as SEED stays.
t = b.tree("page")
section = t.el("section", None, "hero", "hero")
container = t.el("container", section, "container", "hero__container")
t.el("heading", container, "title", "hero__title", tag="h1", text="Replace this heading")
t.el("text-basic", container, "text", "hero__text", tag="p", text="Replace this text.")
# t.comp("eyebrow", container, "eyebrow", text="New in", tag="p")      # a live component (names in site.json)
# t.el("div", container, "card", "@clickable-card")                    # an existing site class

warnings = b.check(no_css_ok=[])         # list wrapper classes that need no CSS
for w in warnings:
    print("warning:", w)
b.write(HERE / f"{PIECE}.bricks.json")
print(f"{PIECE}: {len(b.classes)} classes, " + ", ".join(f"{n} {len(tr)} elements" for n, tr in b.trees.items()))
