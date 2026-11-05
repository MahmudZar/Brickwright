# Build Scripts

Read this before writing or changing a `<piece>.bricks.py`. Start from `assets/piece-template.bricks.py`.

A build script turns a mockup into Bricks data: global classes (from the CSS) and element trees (written by hand in Python). The library `bricks_gen.py` does the CSS routing, ids and checks.

## Skeleton

```python
from bricks_gen import Build                      # after adding .brickwright/lib to sys.path (see the template)

b = Build.from_site(ROOT / ".brickwright" / "site.json", seed=4521, forbidden=["supplier-name"])
b.add_css_files(HERE / "hero.css")                # one global class per BEM class
t = b.tree("page")                                # one tree per target in hero.targets.json
s = t.el("section", None, "hero", "hero")         # (element, parent id, label, class or [classes], **settings)
c = t.el("container", s, "container", "hero__container")
t.comp("eyebrow", c, "eyebrow", text="New in", tag="p")
t.el("heading", c, "title", "hero__title", tag="h1", text="Hello")
print(b.check(no_css_ok=["hero__container"]))     # raises on errors, returns warnings
b.write(HERE / "hero.bricks.json")
```

## Elements

- `t.el(name, parent, label, cls=None, **settings)` returns the new element id. `name` is the Bricks element name (`section`, `container`, `block`, `div`, `heading`, `text-basic`, `text`, `text-link`, `button`, `image`, `svg`, `icon`, `shortcode`, `form`, `accordion-nested`, `nav-nested`, `offcanvas`, query filters, WooCommerce elements...). Settings are Bricks' own keys.
- A Div with another tag: `t.el("div", p, "list", "cards", tag="custom", customTag="ul")`.
- Existing site classes: write `"@name"` (for example `"@clickable-card"`). The deploy maps names to ids. They must exist on the site (`site.json`).
- Fixed id (to keep an id the site already uses): `_id="abcdef"`.
- Attributes: `_attributes=[{"name": "aria-label", "value": "Close"}]`. Never use Bricks' reserved ones (`data-component`, `data-id`, `data-element-id`...): the check refuses them.
- Never put CSS on an element (`_cssCustom`): the check refuses it. CSS belongs in the class.
- When unsure of a setting key, read the element's settings from an existing Bricks page (export it with the execute-php ability), or Bricks' own schema ability if available. Don't guess keys for forms, filters, interactions or queries.

## Components

`t.comp("eyebrow", parent, "label", text="...", tag="p")`. Property names come from `site.json` (`props`). Raw property ids also work. Unknown properties fail the build. Conditions on a component instance are ignored by Bricks: wrap it in a Div and put the condition there.

## Query Loops and Dynamic Data

```python
card = t.el("div", grid, "card", "card", tag="custom", customTag="li",
            hasLoop=True, query={"objectType": "post", "post_type": ["post"], "posts_per_page": 6})
t.el("heading", card, "title", "card__title", tag="h3", text="{post_title}")
```

- Terms: `{"objectType": "term", "taxonomy": ["category"]}`. ACF repeater: `{"objectType": "acf_<field>"}`. Archive templates: `{"objectType": "post", "is_archive_main_query": True}`.
- Dynamic tags work in any text setting: `{post_title}`, `{acf_<field>}`, `{featured_image}`, `{term_name}`.
- `{echo:function}` tags need Bricks code execution on and the function whitelisted (`bricks/code/echo_function_names`), or they print nothing. Code-sensitive data (`{echo:}`, Code elements, PHP queries) is also refused by Bricks' save pipeline when the user running the deploy lacks code-execution permission.
- Conditions on a loop element run before the loop: they hide the whole loop. Filter rows with CSS or the query.

## CSS Routing

`add_css` / `add_css_files` split the CSS into one global class per class name:

- A rule belongs to the first class in its selector. Nest states, children, `@media` and `@container` inside the class.
- Selector lists and top-level `@media` blocks that mix classes are split per class automatically.
- `@keyframes` are copied into every class that uses them (Bricks prints only classes on the page).
- **CSS no class can own fails the build** (`:root`, `body`, `h1 {}`, `@font-face`): pass `owners={"selector": "class" or None}`. `None` drops it (for preview-only CSS).
- Markup printed by a shortcode or plugin has no element of its own. Re-home its rules with `host=lambda cls: "owning-class" if cls.startswith("plugin-") else cls`.
- Each element is a separate global class. Don't write Sass-style `&__title` inside a block: it's invalid CSS.

## Checks

`b.check()` raises `BuildError` listing every problem:

- ids are unique six-character ids; parents and children link up
- every class on an element has CSS (or is listed in `no_css_ok`, which creates an empty class) and every CSS class is used
- no reserved Bricks attributes, no element CSS
- no forbidden words anywhere (pass `forbidden=[...]`)
- no locked site classes reused; every `@name` exists on the site
- `var(--x)` exists in the site's tokens or is declared in the CSS (`--_` private variables are allowed); no raw colours (allow with `allow_raw=["class"]`)

It returns warnings (raw spacing and font-size lengths). `check(strict=True)` turns them into errors. Warnings are advice: the project's own standard decides.

## Seeds and IDs

- The seed makes element ids repeatable: the same build always gives the same ids, so redeploys replace the same elements and references (`#brxe-<id>`, filter targets, load-more) stay valid.
- Give every piece its own seed. Two pieces with the same seed collide on one page, and Bricks requires query-filter element ids to be unique across the whole site.
- Changing the seed of a deployed piece changes every id: the next deploy adds a new copy instead of replacing. Don't, unless you mean it.

## Patching a Live Class

To bring a builder edit back into the files, or to patch one value: `merge_css(existing, patch)` merges property by property (`prop: !remove` deletes). Put the result in the mockup CSS, rebuild, redeploy.

## Library Self-Test

`python -I .brickwright/lib/test_bricks_gen.py` (35 tests). Run it after `setup --update`.
