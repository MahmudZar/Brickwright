# Brickwright

Agent skill for building and maintaining Bricks Builder sites from files.

Your AI agent writes a mockup (HTML + CSS) and a short build script. Brickwright turns them into native Bricks global classes and element trees and writes them to your site with **Bricks' own save code**: validated, backed up, revisioned, and protected against overwriting edits someone made in the builder. The big Bricks JSON never passes through the chat, so builds and later edits cost a fraction of the tokens.

[![Agent Skills](https://img.shields.io/badge/Agent_Skills-Compatible-blue?style=flat-square)](#)
[![Bricks Builder](https://img.shields.io/badge/Builder-Bricks_2.4+-black?style=flat-square)](https://bricksbuilder.io/)

## Install

```bash
npx skills add https://github.com/MahmudZar/Brickwright
```

Then ask your coding agent, for example:

```text
Use brickwright. Set it up for this project and export my site's components and variables.
```

```text
Use brickwright. Build this hero section from hero.html and hero.css and add it to the homepage (page 14) after the header section.
```

```text
Use brickwright. The FAQ section on the homepage: change the question cards to two columns on desktop and redeploy.
```

```text
Use brickwright. Undo the last deploy of the pricing section.
```

## What You Need

- **Bricks Builder 2.4 or newer** (older works, without Bricks' validator).
- **A way for the agent to run PHP on the site**: Novamira MCP's `execute-php`, or Bricks' own `bricks/execute-php` (Bricks > Settings > AI / Abilities).
- **A way to upload a file** (Novamira's upload links). Without one, Brickwright still works in "inline" mode, at a higher token cost.
- **Python 3.10+** on the machine the agent runs on. Standard library only, nothing to install.
- **An agent with file access** (Claude Code, Cursor, Codex and similar).

## Nothing Installed on Your Site

By default nothing is installed on the site. For each deploy, the server script travels with the data, its fingerprint is checked, it runs once and both files are deleted. The only thing left behind is a backup in `wp-content/brickwright-backups/` (blocked from the web), or wherever you choose.

Prefer it installed on your own sites? Copy `skills/brickwright/scripts/brickwright-deploy.php` to `wp-content/mu-plugins/`. It's about 560 lines of readable PHP.

## Why Use It

| | Bricks JSON through MCP | Bricks HTML importer | Brickwright |
| --- | --- | --- | --- |
| Query loops, ACF / dynamic data, components, conditions, filters, WooCommerce | by hand | static shell only | yes, in one build script |
| CSS kept as global-class custom CSS | yes | mapped to Style-panel settings first | yes, checked |
| Same element ids on every rebuild | no | no | yes |
| Refuses to overwrite builder edits | partly | no | yes (classes and sections) |
| Backups + one-command restore | no | no | yes |
| Tokens to build a large page | ~40k per write | ~10k + follow-up calls | ~17k once |
| Tokens per later edit | ~40-80k | many small calls | a few hundred |

Use Bricks' importer or [Code2Bricks](https://code2bricks.com/) instead for a one-off static section you'll never edit again.

## How It Works

```text
mockup (HTML + CSS)  ->  build script (Python)  ->  checks  ->  dry run  ->  deploy  ->  record  ->  verify
```

1. **Setup (once per project):** the agent pins the scripts into `.brickwright/lib/` and exports your site's components, variables and classes into `.brickwright/site.json`.
2. **Build:** the CSS becomes one global class per BEM class (media and container queries kept with their class). The element tree, with loops, components and dynamic data, is written in a few lines of Python.
3. **Checks:** classes used both ways, unknown variables, raw colours, locked framework classes, missing site classes, reserved Bricks attributes, forbidden words.
4. **Dry run, then deploy:** Bricks validates the data before anything is written. The deploy backs up, refuses conflicts, saves through Bricks' pipeline (revision + CSS regeneration), rebuilds CSS files when Bricks uses them, and purges common page caches.
5. **Record and verify:** a small `.live.json` per piece lets the next deploy spot edits made on the site. A server-side render check works even for drafts and behind bot checks.

## Safety Built In

- Dry run before every write; the agent shows you what will change.
- Backups before every write, and `restore` puts them back (after saving the current state).
- Edits made in the builder since the last deploy are never overwritten silently.
- Framework classes locked in Bricks are never touched.
- Uploads are deleted after every real run, even a failed one.
- Section mode swaps only the deployed sections; the rest of the page stays as it is.

Details for agents: `skills/brickwright/references/safety.md` and `troubleshooting.md`.

## Works With

- **Bricks Builder's own MCP:** Brickwright uses Bricks' save pipeline, validator and revisions on the server. See `references/bricks-mcp.md`.
- **Novamira MCP:** `execute-php` and upload links.
- **TwoKit** or any framework stored as Bricks global variables: the variables become the design tokens the build checks against.
- **Code2Bricks:** for hand edits in the builder. Brickwright notices those edits on the next deploy so they can be brought into the files.

## Included Guidance

`skills/brickwright/SKILL.md` is the agent's entry point. Detailed rules live in `references/`:

- `setup.md`, `build-scripts.md`, `deploy.md`, `safety.md`, `troubleshooting.md`: the workflow and every edge case.
- `workflow.md`, `bricks-mcp.md`: the reasoning, for humans.
- `css.md`, `html.md`, `copywriting.md`: default standards, used only where your project has none.

## Repository Layout

```text
skills/
  brickwright/
    SKILL.md
    references/
    assets/        piece-template.bricks.py, targets.example.json
    scripts/       bricks_gen.py, deploy.py, brickwright-deploy.php, tests, validator
skill.sh
```

## Validation

```bash
python -I skills/brickwright/scripts/validate_skill.py
```

Checks the skill package, compiles the scripts and runs the library tests.

## Credits

- Copywriting guidance draws on Harry Dry (x.com/harrydry), GPTZero's writing guides and George Blackman's anti-slop prompt.
- The CSS router and property-level merge are ported from Code2Bricks' CSS engine.
- Built and tested on a live WooCommerce store running Bricks 2.4.4 with TwoKit.

## License

MIT
