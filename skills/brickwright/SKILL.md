---
name: brickwright
description: Builds and deploys Bricks Builder pages, sections and templates from local files (HTML/CSS mockup plus a small Python build script) and writes them to a WordPress site through an execute-php ability (Novamira MCP or Bricks' own MCP), using Bricks' save pipeline, backups and edit-conflict protection. Use when building, rebuilding, deploying, restoring or reviewing Bricks content with global classes, components, query loops, conditions or design tokens (TwoKit or any Bricks variables), or when a Bricks page should be kept as editable files. Don't use for non-Bricks sites, React/Next.js/Tailwind work, or a one-off static paste that will never be edited again (use Bricks' HTML importer or Code2Bricks for that).
---

# Brickwright

Brickwright keeps a Bricks site as files: a mockup (HTML + CSS), a build script that turns it into Bricks global classes and element trees, and a deploy step that writes them to the site with Bricks' own save code. The large Bricks JSON never passes through the chat, so builds and edits stay cheap, repeatable and reversible.

Scripts live in this skill's `scripts/` folder. References live in `references/`. Templates live in `assets/`.

## Golden Rules

These protect the user's live site. Follow them every time.

1. **Dry run first, always.** Every deploy, restore and adopt starts with a dry run. Show the user what it will add, update and replace.
2. **Ask before the first real write to a site in a session**, before any `adopt`, and before any `force`. Quote the dry run's class and element counts.
3. **Never use `force`** unless the user explicitly says to overwrite edits made on the site. A conflict means someone changed the site: bring their change into the files instead (see `references/deploy.md`, "Conflicts").
4. **Never paste a build's JSON into a tool call.** Upload it as a file. The inline mode is a last resort for sites with no upload route; tell the user it costs many tokens.
5. **Files are the source of truth.** Change the mockup or the build script, rebuild, redeploy. Don't hand-edit live Bricks data a build owns, or the next deploy reports a conflict.
6. **Uploads are public.** A real deploy deletes its upload. After a dry run you don't follow with a deploy, run `deploy.py cleanup-call`.
7. **Never touch locked classes** (framework classes such as TwoKit's). The library and the server both refuse them. Rename your class.
8. **Record every successful real deploy** with `deploy.py record`. Without the record, the next deploy can't tell site edits from your own.
9. **Report honestly:** what was written, the backup stamp, conflicts, warnings, and anything not verified.

## Decide the Route

| The request | Route |
| --- | --- |
| A section, page or template that has dynamic parts (query loops, ACF or dynamic data, components, conditions, filters, WooCommerce) or will be edited again | **Build script** (the main workflow below) |
| A quick build from a screenshot where the user wants no files in their project | **Quick mode**: work in `.brickwright/quick/<name>/`, same workflow. Tell the user the folder exists and is safe to delete. |
| A one-off static section, never edited again | Bricks' HTML importer or Code2Bricks. Say why Brickwright isn't needed. |
| One text change or one class value on a page Brickwright doesn't own | Bricks' or Novamira's own abilities directly |
| A change to a page Brickwright owns | Edit the files, rebuild, redeploy |

## First Time on a Project (once)

Read `references/setup.md`. In short:

1. Check what's available: Python 3.10+, an execute-php ability, an upload route (Novamira `create-upload-link`, or none → inline mode). Run the checks in `references/setup.md` instead of assuming.
2. Pin the scripts into the project: `python -I <skill>/scripts/deploy.py setup` (creates `.brickwright/lib/`).
3. Export the site config: `python -I .brickwright/lib/deploy.py config-call`, upload what it lists, run the PHP it prints, save the result to a file, then `deploy.py save-config <file>`. This writes `.brickwright/site.json` (components, tokens, classes, locked classes, Bricks settings).
4. Read the export's settings and tell the user anything unusual: Bricks older than 2.4 (no save pipeline), multisite, CSS loading from files, code execution off (dynamic `{echo:}` tags and Code elements need it).

## Main Workflow (every piece)

1. **Plan.** Ask only for what blocks the work: which page or template it goes on (post id), whether it replaces an existing section, and any content source. Find the post id yourself when you can.
2. **Mockup.** Write `<piece>.html` + `<piece>.css` with BEM classes and the site's tokens. Follow the project's own standards first. If the project has none, use `references/css.md`, `references/html.md` and `references/copywriting.md` as defaults.
3. **Build script.** Copy `assets/piece-template.bricks.py` to `<piece>.bricks.py` and fill in the element tree. Use a seed no other piece uses. See `references/build-scripts.md` for the API, loops, components and the CSS router.
4. **Build and check.** `python -I <piece>.bricks.py`. Fix every error. Show warnings to the user only when they matter.
5. **Targets.** Write `<piece>.targets.json` (copy `assets/targets.example.json`): which post each tree goes to, `content`/`header`/`footer`, `section` (swap in place, keep the rest of the page) or `replace` (whole area).
6. **Deploy.** Follow `references/deploy.md` exactly: `prepare` → upload → dry run → show the user → real deploy → `record` → verify with `render-call` (or `verify` for public pages).
7. **Tell the user** what changed, the backup stamp, how to undo (`restore-call`), and what you didn't verify.

## When Something Goes Wrong

Read `references/troubleshooting.md` for every error message and its fix. The common ones:

- **Conflict "changed on the site since the last deploy":** someone edited it in the builder. Read the live CSS or element, merge it into the files (`merge_css` for CSS), rebuild, redeploy. Never `force` without the user's go-ahead.
- **Conflict "never deployed":** the site already has that class or section. Compare live with yours, show the user, deploy with `--adopt` only after they agree.
- **"uses classes that exist nowhere":** an `@name` class isn't on the site. Re-export `site.json` if it was just added, or fix the name.
- **Bricks rejected the tree:** Bricks' validator found invalid data. Its message names the element. Fix the build script.
- **Page broken after a deploy:** `deploy.py restore-call --stamp <stamp>`, dry run, then real.

## References

Read only what the task needs:

- `references/setup.md`: requirements, first-time setup, project layout, site export.
- `references/build-scripts.md`: library API, writing a build script, loops, components, CSS routing, checks.
- `references/deploy.md`: modes, the exact deploy sequence, targets, conflicts, restore, verify.
- `references/safety.md`: edge cases and what to do in each (caching, open builders, locked classes, CSS files, multisite, code signatures, filters, revisions).
- `references/troubleshooting.md`: error messages and fixes.
- `references/workflow.md`: the whole workflow explained for humans.
- `references/bricks-mcp.md`: what Brickwright uses from Bricks' own MCP and why.
- `references/css.md`, `references/html.md`, `references/copywriting.md`: default standards, used only where the project has none of its own.

## Quick Command Reference

All from the project root. `<lib>` is `.brickwright/lib`.

```bash
python -I <skill>/scripts/deploy.py setup                      # once per project (add --update to upgrade)
python -I <lib>/deploy.py config-call                          # then save-config <result.json>
python -I <piece>.bricks.py                                    # build + checks
python -I <lib>/deploy.py prepare <piece>.bricks.json          # bundle + dry-run/deploy calls
python -I <lib>/deploy.py upload <file> --url <url> --header "X-Novamira-Upload-Token: <token>"
python -I <lib>/deploy.py record <piece>.bricks.json <result.json>
python -I <lib>/deploy.py render-call --post-id <id> --grep <forbidden words> --expect <element ids>
python -I <lib>/deploy.py restore-call --stamp <stamp>
python -I <lib>/deploy.py cleanup-call
python -I <lib>/test_bricks_gen.py                             # library self-test
```

On Windows with Git Bash, prefix commands that pass server paths starting with `/` with `MSYS_NO_PATHCONV=1`.
