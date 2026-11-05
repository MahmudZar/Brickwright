# Setup

Read this the first time Brickwright is used on a project or a site.

## Requirements

| Need | Check | If missing |
| --- | --- | --- |
| Python 3.10 or newer | `python --version` (or `python3`) | Ask the user to install it. Brickwright's scripts use only the standard library. |
| Bricks Builder 2.4+ on the site | the site export's `bricks_version` and `settings.save_pipeline` | Older Bricks: deploys still work but without Bricks' validator. Tell the user. |
| A way to run PHP on the site | an execute-php ability: Novamira `novamira/execute-php`, or Bricks `bricks/execute-php` (Bricks > Settings > AI / Abilities) | Brickwright can't write to the site. Offer the Bricks HTML importer or Code2Bricks instead, or ask the user to enable one. |
| A way to upload a file | Novamira `novamira/create-upload-link` + `deploy.py upload` | Use `--mode inline` (everything travels inside the PHP call; costs many tokens, fine for small pieces). |
| File access to the project | the agent can read and write files | Without files, Brickwright doesn't apply: use Bricks' importer. |

Find the abilities with the MCP's discovery tool (for example `mcp-adapter-discover-abilities`). Don't assume their names.

## Pin the Scripts Into the Project

```bash
python -I <skill>/scripts/deploy.py setup
```

This copies `bricks_gen.py`, `deploy.py`, `brickwright-deploy.php` and `test_bricks_gen.py` into `.brickwright/lib/` and adds `.brickwright/.gitignore` (ignores `out/` and uploads). Build scripts import the pinned copy, so the project keeps working when the skill updates. To upgrade: `setup --update`, then run `python -I .brickwright/lib/test_bricks_gen.py`.

## Project Layout

Brickwright doesn't impose a folder structure for the mockups. The defaults:

```text
project/
  .brickwright/
    lib/               pinned scripts (commit it)
    site.json          site export (commit it; re-export when the site changes)
    out/               bundles and PHP calls (ignored)
    quick/             quick-mode work (optional, safe to delete)
  any/folder/
    hero.html          mockup
    hero.css           mockup CSS = the global classes
    hero.bricks.py     build script
    hero.bricks.json   build output (can be committed or rebuilt)
    hero.targets.json  where it goes on the site
    hero.live.json     record of the last real deploy (commit it)
```

Keep `*.live.json` with the project. If it's lost, the next deploy sees everything as "never deployed" and needs `--adopt`.

## Export the Site Config

```bash
python -I .brickwright/lib/deploy.py config-call
```

1. Upload the file it lists (one-shot mode) with an upload link and `deploy.py upload`.
2. Run the printed PHP with the execute-php ability.
3. Save the returned JSON to a file (for example `.brickwright/out/site-config.json`).
4. `python -I .brickwright/lib/deploy.py save-config .brickwright/out/site-config.json`

`site.json` holds:

- `components`: each Bricks component's id and its properties by readable name (`eyebrow: {cid, props: {text, tag, style}}`).
- `tokens`: every Bricks global variable as `--name` (TwoKit or any other framework stored as Bricks variables).
- `classes` and `locked_classes`: every global class name, and the ones locked in Bricks.
- `settings`: CSS loading (inline or file), code execution, save pipeline present, multisite.

Re-export after the site gains components, variables or classes the build uses. The export output can be large on big sites (it passes through the chat once).

## Modes

| Mode | Use when | What happens |
| --- | --- | --- |
| `one-shot` (default) | Any site with an upload route | The server script is uploaded next to the bundle, its md5 is checked, it runs for one request and is deleted. Nothing stays installed. |
| `installed` | The user installed `brickwright-deploy.php` as a mu-plugin or code snippet | No server-script upload. Fastest. |
| `inline` | No upload route | Bundle and server script travel inside the PHP call. Many tokens: keep pieces small or ask the user to add an upload route. |

Pass `--mode` to `config-call`, `prepare`, `render-call` and `restore-call`.

## Tell the User

After setup, summarise in plain words: Bricks version, mode, where backups go (`wp-content/brickwright-backups/`, blocked from the web; or a `--backup-dir` outside the web root), and anything from the export that needs their attention.
