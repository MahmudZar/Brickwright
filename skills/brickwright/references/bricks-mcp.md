# Brickwright + the Bricks MCP: what we take, and why

Bricks 2.4 ships its own MCP (`includes/abilities/`, about 190 abilities, guide `start-here.md`). Brickwright keeps what it's best at (files as the source, local build scripts, the JSON never passing through the chat) and uses Bricks' own code for what Bricks is best at: knowing whether its data is valid and saving it safely.

**How:** the deploy runs **on the server**, in one execute-php call (Novamira or Bricks' own `bricks/execute-php`), so it can call Bricks' PHP classes in-process. Nothing extra goes through the chat, and it works even when Bricks' MCP abilities are switched off (as on the reference site).

## Taken from Bricks

| Bricks part | Used in | What it gives us |
| --- | --- | --- |
| `Save_Pipeline::dry_run()` | every dry run and deploy, before any write | Bricks' own validation: ids, parent/child links, links, dynamic tags, **component instances and slot children**, circular references, query-filter ids unique site-wide, code-execution rules. Local checks can't know these. |
| `Save_Pipeline::execute()` | the write | Revision snapshot before saving, post CSS regeneration, **nothing saved when nothing changed**, filter-registry lock. Passing the current page as the "baseline" keeps other sections' element CSS untouched. |
| `Assets_Files::regenerate_css_files()` | after a class change, when Bricks loads CSS from files | Every page using a changed class gets fresh CSS. |
| Global-class timestamp (`bricks_global_classes_timestamp` / `_user`) | after a class write | Open builders know the classes changed. |
| Locked classes (`bricks_global_classes_locked`) | build checks and deploy | Framework classes are never changed. |
| HTML/CSS page import | route choice | For one-off **static** pages: mockup → Bricks importer, no build script. |
| `commit-exact-site-edits` | quick fixes | One-line edits on pages **not** built with Brickwright. Pages built with Brickwright: edit the files and redeploy, so the files stay the source. |

## Built Our Own (and why)

- **Edit protection per class and per section.** Bricks' page digest covers the whole page, so it would block a deploy whenever anyone edited a *different* section. Brickwright records a fingerprint of each class and each deployed section (`<piece>.live.json`) and refuses only when *its own* parts changed on the site.
- **Site export** (`brickwright_site_config()`): reads components, variables and classes directly, because Bricks' `get-design-context` ability may be switched off.
- **Server-side render check** (`brickwright_render()`): renders a target with Bricks' frontend, for drafts and sites behind bot checks.
- **Files are the source.** Bricks' agent files and workspaces send the whole page tree through the chat both ways (about 40k tokens each way for a large page). Brickwright sends a few hundred tokens per edit.
- **Class custom CSS only.** Bricks' importer and style normalizer move mappable CSS into Style-panel settings. Brickwright keeps CSS in global classes and refuses element CSS.
- **Dynamic sections in one file:** loops, conditions, interactions, components, filters, WooCommerce.
- **Seeded ids**, so redeploys replace the same elements and references stay valid.
- **Design-token, locked-class and forbidden-word checks** before anything reaches the site.

## Version Notes

- Tested with Bricks **2.4.3** source and a live **2.4.4** site (2026-11-05).
- `Save_Pipeline` is internal Bricks code. After a Bricks update, run one dry run on a draft page before trusting a real deploy. If the class is missing, the deploy still saves (without Bricks' validation) and says so.
