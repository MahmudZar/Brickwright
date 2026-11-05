# Troubleshooting

Find the message, apply the fix. Never work around a refusal with `force` or by editing the server script.

## Build (`python -I <piece>.bricks.py`)

| Message | Fix |
| --- | --- |
| `no class to own \`...\`` | The CSS rule starts with a tag, `:root`, `body` or an id. Move it inside a class, or pass `owners={"selector": "class"}` (`None` to drop preview-only CSS). |
| `@keyframes x isn't used by any class` | Delete it, or give it an owner. |
| `class \`x\` is on an element but has no CSS` | Add CSS for it, or list it in `check(no_css_ok=[...])` for wrappers that need none. |
| `class \`x\` has CSS but no element uses it` | Put the class on an element, or delete the CSS. |
| `unknown variable --x` | Typo, or a variable the site doesn't have. Re-export `site.json` if it was just added. |
| `raw colour in ...` | Use a colour variable, or allow the class with `allow_raw=["class"]` for brand colours that aren't the site's. |
| `uses reserved attribute` | Rename the data attribute. |
| `has element CSS (_cssCustom)` | Move the CSS to the element's class. |
| `is locked on the site` | Rename your class. |
| `\`@x\` doesn't exist on the site` | Fix the name, or re-export `site.json`. |
| `unknown component` / `has no property` | Check the names in `site.json` → `components`. |
| `duplicate id` | Two elements got the same `_id`. |
| `unexpected text` / `unclosed '{'` | Broken CSS: fix the braces. |

## Prepare and Upload

| Message | Fix |
| --- | --- |
| `not a brickwright/1 build output` | The build script didn't call `b.write(...)`, or this is an older generator's JSON. |
| `no targets file` / `no target for tree` / `needs a numeric post_id` | Write `<piece>.targets.json` with a target per tree. |
| Upload HTTP 401/403 | The upload link expired or the token header is wrong: create a new link. |
| Upload HTTP 413 or blocked | The file is too big for the host: split the piece. |
| A server path turned into `C:/Program Files/Git/...` | Git Bash on Windows: prefix the command with `MSYS_NO_PATHCONV=1`. |

## Deploy Report

| `error` / `conflicts` | Fix |
| --- | --- |
| `server script missing or changed` | Upload `brickwright-deploy.b64.txt` again (a real run or another call deleted it). |
| `bundle not found` | Upload the bundle again (a real run deletes it, also after a failure). |
| `md5 mismatch` | The file changed or the upload was cut off: `prepare` again and re-upload. |
| `target post N doesn't exist` | Create the page or template first, or fix `post_id`. |
| `uses classes that exist nowhere` | An `@name` isn't on the site. |
| `element id ... is already used elsewhere on post N` | Another piece uses the same seed or `_id`. |
| `'after' element ... is not on post N` | Fix `after` in the targets file. |
| `changed on the site since the last deploy` / `was edited on the site` | See `deploy.md` → Conflicts. |
| `never deployed` | Compare, show the user, then `prepare --adopt`. |
| `is locked in Bricks` | Rename the class. |
| `Bricks rejected ...` | Bricks' validator found bad data (the message names the element or rule). Fix the build script. |
| `Bricks couldn't save ...` with `classes_already_written: true` | Classes were written but the page wasn't. Fix the cause and redeploy, or restore with the stamp in the message. |
| `multisite is untested` | See `safety.md`. |
| `Bricks is not active` | Wrong site, or Bricks is off. |
| `PHP error: ...` | Report it to the user with the file and line. Don't retry blindly. |
| `warning: Bricks save pipeline not found` | Bricks older than 2.4: data saved without Bricks validation. Verify carefully. |
| `css_files: not regenerated` | Ask the user to regenerate CSS files in Bricks > Settings > Performance. |

## After Deploy

| Symptom | Fix |
| --- | --- |
| Page looks unstyled | A cache served the old page (purge it), or CSS loading is "file" and files weren't rebuilt (see above). Check with `render-call`. |
| Next deploy says "never deployed" | `record` wasn't run after the last deploy, or `.live.json` was lost: compare and `--adopt`. |
| Wrong content went live | `restore-call --stamp <stamp>`, dry run, then real. |
