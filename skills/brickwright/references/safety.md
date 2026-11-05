# Safety and Edge Cases

Read this when something about the site is unusual, before a first deploy to a new site, and when a deploy behaves unexpectedly. Each entry: the situation, what Brickwright does, what the agent does.

## The Site

| Situation | Brickwright | Agent |
| --- | --- | --- |
| Someone has the target page open in the builder | Can't see it | Ask the user to close builder tabs for the target pages before a real deploy. An open builder can save its old copy over the deploy. |
| Bricks writes CSS to files (`settings.css_loading = file`) | Rebuilds Bricks' CSS files after a class change (every page using the class needs it) | Mention it can take a moment on big sites. If the report says it couldn't, ask the user to run Bricks > Settings > Performance > Regenerate CSS files. |
| A page cache or CDN | Purges LiteSpeed, WP Rocket, W3TC, WP Super Cache, SiteGround and fires `brickwright_purge_cache` | Other caches (Cloudflare, host panels): tell the user to purge, or verify with `render-call`, which bypasses caches. |
| Locked classes (framework classes) | Refused in the build and on the server | Rename. Never unlock or edit them. |
| Multisite | Refuses (Bricks may keep classes on the main site) | Tell the user. Continue with `allow_multisite` only after checking where the classes live. |
| Bricks older than 2.4 | Saves without Bricks' validator (warning in the report) | Tell the user and verify the page carefully. |
| Code execution off, or the deploy user lacks it | Bricks refuses code-sensitive data (`{echo:}` tags, Code elements, PHP queries) | Remove those from the build or ask the user to allow code execution for that user. |
| Query filters | Bricks requires filter element ids to be unique site-wide; the save pipeline checks | Give every piece its own seed. After adding filters, Bricks' filter index may need a reindex. |
| Revisions | Bricks keeps a revision before each changed save (`revision` in the report) | Mention it as a second way back, next to `restore-call`. |
| Hosting firewall blocks big request bodies | Bundles travel as base64 `.txt` uploads, not as request JSON | If an upload or call is blocked, split the piece or use the upload route instead of inline. |
| Bot checks on the public site | `verify` reports a bot-check page | Use `render-call` (server-side render). |
| Draft or private target | Works | Verify with `render-call`. Public HTTP checks see nothing. |

## The Data

| Situation | Brickwright | Agent |
| --- | --- | --- |
| The build's class name already exists on the site | Conflict "never deployed" | Prefix block names with something unique to the project. Adopt only after comparing. |
| A class was removed from the mockup | Stays on the site (deploys never delete classes) | Delete unused classes in the builder or ask the user; mention it in the report. |
| A section was removed from the build | Section mode leaves it on the page | Remove it in the builder, or use `replace` mode if the build owns the whole page. |
| A tree root already exists elsewhere on the page | Refused (duplicate id) | Change the seed or the `_id`. |
| `.live.json` lost or out of date | Next deploy reports "never deployed" | Confirm the live page matches the build (or what the user wants), then `--adopt`. |
| Builder edits to a section the build owns | Conflict on the next deploy | Bring the edits into the files first. |
| Two pieces on one page | Each swaps only its own sections | Fine. Use different seeds. |
| A header or footer template | `area: header` / `footer` and the template's post id | Create the template and its conditions first. |
| Text with non-English characters | Bundles are UTF-8 JSON in base64 | Nothing to do. |

## The Agent's Own Safety

- One deploy at a time per site. Wait for each report.
- Never run a real deploy, restore, `--adopt` or `force` that the user hasn't seen as a dry run in this session.
- Never edit `brickwright-deploy.php` for a single job. If the server code needs a change, change it in the skill, test it, and re-pin with `setup --update`.
- Keep secrets out of files: upload tokens are short-lived, never write them into the project.
- When the site export, a dry run or a report shows something you didn't expect (classes you don't recognise being replaced, a different Bricks version, a much bigger `replaces` count), stop and ask.
