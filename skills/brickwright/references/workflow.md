# The Brickwright workflow

How an AI agent (Claude Code or any agent with file access and a WordPress MCP) builds and maintains Bricks Builder pages from files. Every step leaves files behind, so a later session can rebuild or change a piece without the chat history.

```
source ─▶ mockup ─▶ build script ─▶ checks ─▶ deploy ─▶ verify ─▶ (pull)
```

## 0. Pick the route

| The piece is... | Route |
|---|---|
| Dynamic (query loops, custom fields, conditions, components, filters, WooCommerce), or will be edited again | **Build script** (this guide) |
| Static, one-off, never edited again | Mockup → **Bricks MCP HTML importer** (`commit-html-css-page-import`). Note: it maps CSS to Style-panel settings first. |
| **Quick build** ("build this screenshot", the user wants no project files) | **Quick mode**: the agent still writes HTML + CSS, but in a hidden working folder (`.brickwright/quick/<name>/`), never in the user's project. The agent writes a short build script for it as usual (an automatic HTML-to-elements converter is planned), the normal checks and deploy run, and the folder is kept only so a later "change the button colour" is cheap; deleting it loses nothing on the site. Without file access at all (a plain chat), use the Bricks importer. |

## 1. Source

Any of these works; it only changes how exact the mockup is on the first try.

| Source | How the agent reads it | Accuracy |
|---|---|---|
| **Figma file** | A Figma MCP (e.g. figma-console): screenshot of the frame + exact sizes, gaps, padding, colours, text | Best: real values, fewest fix rounds |
| **Screenshot** | Vision only | Good layout, guessed values (spacing, sizes, colours): expect 1-3 rounds of comparing preview vs screenshot |
| **Existing HTML/site** | Fetch or read the source | Exact, but needs cleaning into BEM + tokens |
| **Written brief** | Text | The agent designs it; review the mockup |

Whatever the source: translate raw values into the site's **design-system variables** (spacing, type, colour, radius). Don't copy pixels.

## 2. Mockup (`<piece>.html` + `<piece>.css`)

- Semantic HTML, **BEM** classes (`block`, `block__element`, `block--modifier`), one class per element.
- CSS: every rule starts with the class that owns it; states, children and `@media` / `@container` live inside that class (native nesting).
- Design-system variables for anything systemic; raw values only for one-off geometry.
- Header comment in the CSS = the element tree, one line per class and the Bricks element it becomes.
- Preview locally at 390 / 768 / 1440 px and compare with the source.
- Reuse live components (buttons, eyebrows) and existing global classes instead of rebuilding them.

## 3. Build script (`<piece>.bricks.py` → `<piece>.bricks.json`)

The script encodes what HTML can't:
- Bricks element types chosen by hand (Section, Container, Block, Div with custom tag, Heading, Basic text, Image with media ids, SVG from an icon set, Shortcode, Form, Accordion, filters, WooCommerce elements...).
- **Component instances** (component id + property ids).
- **Query loops** (posts, terms, custom-field repeaters, main query), **dynamic tags**, **conditions**, **interactions**, ARIA ids per loop item.
- CSS routed into **global classes, class custom CSS only** (nothing in the Style panel). Existing classes referenced by name.
- **Seeded element ids**: re-runs give the same ids, so references (filters, load more, `#brxe-...`) and diffs stay stable.

## 4. Checks (the build fails on any of these)

- A class without CSS, or CSS for a class that isn't used.
- CSS that matches no class (tag selectors, `:root`, stray keyframes) unless given an explicit owner.
- Raw colour / spacing values where a design-system variable exists.
- Reserved Bricks attributes in `_attributes` (`data-component`, `data-component-id`, `data-id`, `data-parent-id`, `data-script-id`, `data-element-id`, `data-index`): they lock selection in the builder.
- Duplicate ids, missing component properties, forbidden words (e.g. supplier names) anywhere in the output.

## 5. Deploy

1. Upload the JSON as a **file** (an upload link or a private endpoint), never as a chat/tool parameter: it's tens of thousands of tokens.
2. Server side, in one step, using Bricks' own save code (details: [bricks-mcp.md](bricks-mcp.md)):
   - back up the classes and the target content;
   - map class names to ids; **dry-run Bricks' save pipeline** (its validator) and stop on any error;
   - write global classes and the page with `Save_Pipeline::execute()`, after comparing each class and section with the **record from the last deploy**: if the page or a class was edited in the builder since, Bricks refuses and you run `pull` first;
   - Bricks takes a revision and regenerates CSS; clear the page cache;
   - store the new digests in `<piece>.live.json` (`deploy.py record`).
3. Delete the uploaded file afterwards (uploads are public).

Transport: **Novamira MCP** (`execute-php`, upload links) or the **Bricks MCP** abilities. The JSON is native Bricks data, so both work.

## 6. Verify

- Bricks `get-page-elements` / `render-elements` summary (counts, hierarchy, heading order, unresolved class references); HTML counts (elements, loop items, ids, ARIA, dynamic values, no empty attributes).
- Headless screenshots at phone and desktop width; compare with the mockup and the source.
- Interactions and edge cases (empty states, no results, long text).
- Grep the rendered page for forbidden words.

## 7. Pull (keep files and site in sync)

People will edit in the builder (by hand or with **Code2Bricks**). The deploy notices: it refuses to overwrite a class or section changed since the last deploy. Bring the change into the files (read the live CSS or elements, merge CSS with `merge_css`), rebuild and redeploy. A `pull` command that does this automatically is planned; until then it's the manual steps in [deploy.md](deploy.md) under Conflicts.

## 8. Record it

One dated line per decision (with the reason and backup file names), a row per piece in the project's README, and any new Bricks gotcha written down so nobody rediscovers it.
