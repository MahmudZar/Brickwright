# Deploy

Read this before writing anything to a site. Follow the sequence exactly. `<lib>` is `.brickwright/lib`.

## Targets File

`<piece>.targets.json` says where each tree goes:

```json
{
  "page": { "post_id": 14, "area": "content", "mode": "section", "after": "abcdef" },
  "preserve": { "page": ["ghijkl"] }
}
```

- `post_id`: the page, post or Bricks template. It must exist. Create templates first (Bricks or Novamira template ability), set their conditions there, then deploy into them.
- `area`: `content` (pages, content templates), `header` or `footer` (header/footer templates).
- `mode`: `section` (default) swaps only this tree's top-level elements in place and keeps everything else on the page. `replace` replaces the whole area: use it only when the build owns the entire page or template.
- `after` (section mode, new sections only): place the new section after this top-level element. Without it, a new section goes at the end.
- `preserve`: element ids whose live settings stay under the build's (for elements whose options are set in the builder, such as WooCommerce elements).

## The Sequence

1. **Build:** `python -I <piece>.bricks.py` (checks must pass).
2. **Prepare:** `python -I <lib>/deploy.py prepare <piece>.bricks.json` (add `--mode`, and `--backup-dir <server path>` if the user wants backups outside the web root). It writes the bundle and two PHP calls to `.brickwright/out/` and lists the files to upload.
3. **Upload** each listed file to `wp-content/uploads/brickwright-import/<name>`: create an upload link (`novamira/create-upload-link`, path `wp-content/uploads/brickwright-import/<name>`, overwrite true), then `python -I <lib>/deploy.py upload <file> --url <upload_url> --header "<token_header>: <upload_token>"`. Expect HTTP 200.
4. **Dry run:** run `.brickwright/out/<piece>.dry-run.php` with the execute-php ability. Read the report:
   - `classes.added` / `updated` / `unchanged`, and per tree `elements`, `replaces` (existing elements it will remove) and `page_elements_after`.
   - `conflicts` or `error`: stop, see "Conflicts" and `troubleshooting.md`.
5. **Show the user** the dry run in a sentence or two ("adds 12 classes, updates 2, replaces the 18-element FAQ section on the homepage"). The first real write in a session, any `replaces` they didn't ask for, `--adopt` and `force` need their go-ahead.
6. **Deploy:** run `.brickwright/out/<piece>.deploy.php`. Save the full JSON result to a file.
7. **Record:** `python -I <lib>/deploy.py record <piece>.bricks.json <result-file>` (writes `<piece>.live.json`).
8. **Verify:** `python -I <lib>/deploy.py render-call --post-id <id> --grep <forbidden words> --expect <root element ids>`, upload what it lists, run it. `ok: true` means no forbidden word was found and every expected id rendered. For public pages, `deploy.py verify <url>` also works (bot-check pages are detected). Screenshots at phone and desktop width when a browser is available.
9. **Report** to the user: what changed, `backup.stamp`, how to undo, warnings.

The real deploy deletes its uploads (bundle and one-shot server script), also when it fails. A dry run keeps them for the real run.

## What the Deploy Does (server side)

Read + md5 check → back up the class list and each target's Bricks data → map class names to ids → refuse locked classes and conflicts → Bricks' save-pipeline dry run → write classes and Bricks' class timestamp (open builders see the change) → Bricks' save pipeline per target (revision, CSS regeneration, nothing saved when nothing changed) → rebuild CSS files if Bricks loads CSS from files → digests for the record → purge page caches (LiteSpeed, WP Rocket, W3 Total Cache, WP Super Cache, SiteGround, plus a `brickwright_purge_cache` action).

## Conflicts

The deploy refuses to overwrite anything it can't account for. Nothing is written when there is a conflict.

| Conflict | Meaning | Do this |
| --- | --- | --- |
| "class `x` was changed on the site since the last deploy" | Someone edited the class in the builder after your last deploy | Read the live CSS (`get_option('bricks_global_classes')`, the class's `settings._cssCustom`), merge it into the mockup CSS (`merge_css`), rebuild, redeploy. `force` only if the user wants their site edit thrown away. |
| "`tree` on post N was edited on the site" | Someone changed elements in this section | Read the live elements, bring the change into the build script, rebuild, redeploy. Same rule for `force`. |
| "already exists and Brickwright never deployed it" | First Brickwright deploy over something that exists (or the `.live.json` was lost) | Compare live with the build, show the user the differences, then `prepare --adopt` after they agree. |
| "is locked in Bricks" | Your class name matches a locked framework class | Rename your class. Never unlock it. |

## Restore

Each real deploy backs up with a stamp (`backup.stamp` in the result and `.live.json`).

```bash
python -I <lib>/deploy.py restore-call --stamp 20261105-150207
```

Run the dry-run file first (it lists the files it will restore), then the restore file after the user agrees. Restore puts back the **whole class list** and each target's data as they were before that deploy. Class or page edits made by anyone since then are undone too: check with the user. The current state is saved first (`current_state_saved_as`), so a restore can itself be undone. After a restore, the piece's `.live.json` describes the undone deploy, so the next deploy reports "changed on the site". Delete that `.live.json`, then deploy with `--adopt` once the user confirms.

## Leftovers

If a dry run isn't followed by a deploy, or a session ends mid-way: `python -I <lib>/deploy.py cleanup-call` and run the PHP. It deletes everything in `uploads/brickwright-import/`.

## Without an Upload Route

`--mode inline` embeds the bundle (and server script) in the PHP call. Read the call from the `.php` file in `.brickwright/out/` and pass it as the code. Tell the user the token cost first. Large pages: split into several pieces.

## Without Any PHP Route

Brickwright can't write. Options for the user: enable Bricks' `bricks/execute-php` or install Novamira; or paste static parts with Bricks' HTML importer or Code2Bricks.
