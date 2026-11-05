"""Brickwright deploy, local side. Python 3.10+, standard library only.

Every command that talks to the site prints (and saves under .brickwright/out/) a short PHP call.
Run that call with an execute-php ability (Novamira `execute-php` or Bricks `bricks/execute-php`).

  setup [--project DIR] [--update]
      Copy bricks_gen.py, deploy.py and brickwright-deploy.php into DIR/.brickwright/lib/ (pinned).
  config-call [--mode one-shot|installed|inline]
      PHP call that exports the site's components, design tokens and classes.
  save-config RESULT.json
      Save that export as .brickwright/site.json (used by Build.from_site and the checks).
  prepare PIECE.bricks.json [--targets FILE] [--mode one-shot|installed|inline] [--adopt]
      Bundle a build with its targets and the last deploy's record; write the dry-run and deploy calls.
  upload FILE --url URL [--header "Name: value"]...
      PUT a file to an upload link (e.g. Novamira create-upload-link).
  record PIECE.bricks.json RESULT.json
      Save a successful deploy's record to PIECE.live.json (the next deploy uses it to spot site edits).
  render-call --post-id N [--area content] [--grep w1,w2] [--expect id1,id2]
      PHP call that renders the page server-side and checks words / element ids (no HTTP needed).
  restore-call --stamp STAMP [--backup-dir DIR]
      PHP calls (dry run, then real) that put back one deploy's backup.
  cleanup-call
      PHP call that deletes everything left in uploads/brickwright-import/.
  verify URL [--forbidden w1,w2] [--expect id1,id2]
      Fetch a public page over HTTP and check it.

Modes: one-shot = nothing installed, the server script is uploaded with the bundle and deleted
after the real run; installed = the server script is a mu-plugin or snippet; inline = no upload
route at all, everything is embedded in the call (costs many tokens: last resort).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import sys
import urllib.request

__version__ = "0.2.0"
BUNDLE_FORMAT = "brickwright-bundle/1"
UPLOAD_DIR = "brickwright-import"
HERE = pathlib.Path(__file__).resolve().parent
SERVER_SCRIPT = HERE / "brickwright-deploy.php"
SERVER_UPLOAD = "brickwright-deploy.b64.txt"
LIB_FILES = ("bricks_gen.py", "deploy.py", "brickwright-deploy.php", "test_bricks_gen.py")


def say(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=True))


def unwrap(obj):
    """Take the function's own result out of an MCP tool response ({"data": {"return_value": ...}})."""
    for _ in range(4):
        if isinstance(obj, dict) and "return_value" in obj:
            obj = obj["return_value"]
        elif isinstance(obj, dict) and isinstance(obj.get("data"), dict) and "format" not in obj and "ok" not in obj:
            obj = obj["data"]
        else:
            break
    return obj


def piece_name(path: pathlib.Path) -> str:
    return path.name.removesuffix(".json").removesuffix(".bricks")


def load_json(path: pathlib.Path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def project_dir(args) -> pathlib.Path:
    return pathlib.Path(getattr(args, "project", None) or ".").resolve()


def out_dir(args) -> pathlib.Path:
    d = project_dir(args) / ".brickwright" / "out"
    d.mkdir(parents=True, exist_ok=True)
    return d


def php_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def loader(mode: str, final: bool, outd: pathlib.Path) -> tuple[str, list[str]]:
    """PHP that makes the brickwright_* functions available, and the files to upload first."""
    server = SERVER_SCRIPT.read_bytes()
    smd5 = hashlib.md5(server).hexdigest()
    if mode == "installed":
        return "if (!function_exists('brickwright_deploy')) return 'Brickwright server script is not installed: use --mode one-shot'; ", []
    if mode == "inline":
        b64 = base64.b64encode(server).decode("ascii")
        return (f"$c = base64_decode('{b64}'); if (md5($c) !== '{smd5}') return 'server script damaged in transit'; "
                "$t = tempnam(get_temp_dir(), 'bw'); file_put_contents($t, $c); require_once $t; unlink($t); "), []
    sfile = outd / SERVER_UPLOAD
    sfile.write_bytes(base64.b64encode(server))
    code = (f"$u = wp_upload_dir()['basedir'] . '/{UPLOAD_DIR}/{SERVER_UPLOAD}'; "
            "$c = base64_decode((string) @file_get_contents($u)); "
            f"if (md5($c) !== '{smd5}') return 'server script missing or changed: upload {SERVER_UPLOAD} again'; "
            "$t = tempnam(get_temp_dir(), 'bw'); file_put_contents($t, $c); require_once $t; unlink($t); ")
    if final:
        code += "@unlink($u); "
    return code, [str(sfile)]


def write_call(outd: pathlib.Path, name: str, code: str) -> str:
    p = outd / f"{name}.php"
    p.write_text(code + "\n", encoding="utf-8")
    return str(p)


# ----------------------------------------------------------------------------------------------

def cmd_setup(args) -> int:
    lib = project_dir(args) / ".brickwright" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    existing = (lib / "deploy.py")
    if existing.exists() and not args.update:
        m = re.search(r'__version__ = "([^"]+)"', existing.read_text(encoding="utf-8"))
        have = m.group(1) if m else "?"
        if have != __version__:
            sys.exit(f"{lib} has Brickwright {have}; this is {__version__}. Re-run with --update to replace it.")
    for f in LIB_FILES:
        shutil.copy2(HERE / f, lib / f)
    gi = project_dir(args) / ".brickwright" / ".gitignore"
    if not gi.exists():
        gi.write_text("out/\n*.b64.txt\n", encoding="utf-8")
    say({"ok": True, "version": __version__, "lib": str(lib), "copied": list(LIB_FILES),
         "next": "python -I .brickwright/lib/deploy.py config-call, run it, then save-config"})
    return 0


def cmd_config_call(args) -> int:
    outd = out_dir(args)
    load, uploads = loader(args.mode, True, outd)
    code = load + "return brickwright_site_config();"
    say({"upload_first": [f"{u} -> wp-content/uploads/{UPLOAD_DIR}/{SERVER_UPLOAD}" for u in uploads],
         "php_file": write_call(outd, "site-config", code),
         "php": code if args.mode != "inline" else "(long: read the php_file)"})
    return 0


def cmd_save_config(args) -> int:
    data = load_json(pathlib.Path(args.result))
    data = unwrap(data)
    if not isinstance(data, dict) or data.get("format") != "brickwright-site/1":
        sys.exit("not a brickwright_site_config() result")
    dest = project_dir(args) / ".brickwright" / "site.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    s = data.get("settings", {})
    say({"saved": str(dest), "components": sorted(data.get("components", {})), "tokens": len(data.get("tokens", [])),
         "classes": len(data.get("classes", [])), "locked_classes": len(data.get("locked_classes", [])),
         "bricks": data.get("bricks_version"), "css_loading": s.get("css_loading"),
         "save_pipeline": s.get("save_pipeline"), "code_execution": s.get("code_execution"),
         "multisite": s.get("multisite")})
    return 0


def cmd_prepare(args) -> int:
    src = pathlib.Path(args.piece)
    data = load_json(src)
    if data.get("format") != "brickwright/1":
        sys.exit(f"{src}: not a brickwright/1 build output (write it with bricks_gen Build.write)")
    name = piece_name(src)
    tpath = pathlib.Path(args.targets) if args.targets else src.with_name(f"{name}.targets.json")
    if not tpath.exists():
        sys.exit(f"no targets file: {tpath} (which post does each tree go to?)")
    targets = load_json(tpath)
    preserve = targets.pop("preserve", {})
    missing = [t for t in data["trees"] if t not in targets]
    if missing:
        sys.exit(f"{tpath}: no target for tree(s) {', '.join(missing)}")
    for t, v in targets.items():
        if t in data["trees"] and not isinstance(v.get("post_id"), int):
            sys.exit(f"{tpath}: `{t}` needs a numeric post_id")
    live = src.with_name(f"{name}.live.json")
    previous = load_json(live)["record"] if live.exists() else {"classes": {}, "trees": {}}
    bundle = {"format": BUNDLE_FORMAT, "piece": name, "classes": data["classes"], "trees": data["trees"],
              "targets": {k: targets[k] for k in data["trees"]}, "previous": previous, "preserve": preserve}
    raw = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    md5 = hashlib.md5(raw).hexdigest()
    outd = out_dir(args)
    adopt = ", 'adopt' => true" if args.adopt else ""
    backup = f", 'backup_dir' => {php_str(args.backup_dir)}" if args.backup_dir else ""
    uploads = []
    if args.mode == "inline":
        src_arg = f"'data' => '{base64.b64encode(raw).decode('ascii')}'"
    else:
        bfile = outd / f"{name}.bundle.b64.txt"
        bfile.write_bytes(base64.b64encode(raw))
        uploads.append(f"{bfile} -> wp-content/uploads/{UPLOAD_DIR}/{bfile.name}")
        src_arg = f"'file' => '{UPLOAD_DIR}/{bfile.name}'"
    opts = f"{src_arg}, 'md5' => '{md5}'{adopt}{backup}"
    load_dry, up = loader(args.mode, False, outd)
    load_final, _ = loader(args.mode, True, outd)
    uploads += [f"{u} -> wp-content/uploads/{UPLOAD_DIR}/{SERVER_UPLOAD}" for u in up]
    dry = load_dry + f"return brickwright_deploy([{opts}, 'dry_run' => true]);"
    final = load_final + f"return brickwright_deploy([{opts}]);"
    short = args.mode != "inline"
    say({"piece": name, "md5": md5, "bytes": len(raw), "classes": len(data["classes"]),
         "trees": {k: len(v) for k, v in data["trees"].items()}, "first_deploy": not live.exists(),
         "upload_first": uploads,
         "dry_run_file": write_call(outd, f"{name}.dry-run", dry), "deploy_file": write_call(outd, f"{name}.deploy", final),
         "php_dry_run": dry if short else "(long: read dry_run_file)", "php_deploy": final if short else "(long: read deploy_file)"})
    return 0


def cmd_upload(args) -> int:
    body = pathlib.Path(args.file).read_bytes()
    req = urllib.request.Request(args.url, data=body, method="PUT")
    req.add_header("Content-Type", "text/plain")
    for h in args.header or []:
        k, v = h.split(":", 1)
        req.add_header(k.strip(), v.strip())
    with urllib.request.urlopen(req, timeout=120) as r:
        print(r.status, r.read(400).decode("utf-8", "replace"))
    return 0


def cmd_record(args) -> int:
    src = pathlib.Path(args.piece)
    result = load_json(pathlib.Path(args.result)) if args.result != "-" else json.load(sys.stdin)
    result = unwrap(result)
    if not result.get("ok") or "record" not in result or result.get("dry_run"):
        sys.exit(f"not a successful real deploy: {result.get('error', 'no record')}")
    live = src.with_name(f"{piece_name(src)}.live.json")
    live.write_text(json.dumps({
        "deployed": dt.datetime.now().isoformat(timespec="seconds"),
        "trees": {k: {kk: v.get(kk) for kk in ("post_id", "area", "mode", "saved_elements", "revision")}
                  for k, v in result.get("trees", {}).items()},
        "backup": result.get("backup"),
        "record": result["record"],
    }, indent=2), encoding="utf-8")
    print(f"recorded {len(result['record']['classes'])} classes, {len(result['record']['trees'])} tree(s) -> {live}")
    return 0


def cmd_render_call(args) -> int:
    outd = out_dir(args)
    load, uploads = loader(args.mode, True, outd)
    a = {"post_id": args.post_id, "area": args.area,
         "grep": [w for w in (args.grep or "").split(",") if w], "expect": [i for i in (args.expect or "").split(",") if i]}
    code = load + "return brickwright_render(json_decode(" + php_str(json.dumps(a)) + ", true));"
    say({"upload_first": uploads, "php_file": write_call(outd, f"render-{args.post_id}", code),
         "php": code if args.mode != "inline" else "(long: read php_file)"})
    return 0


def cmd_restore_call(args) -> int:
    outd = out_dir(args)
    a = {"stamp": args.stamp}
    if args.backup_dir:
        a["backup_dir"] = args.backup_dir
    load_dry, uploads = loader(args.mode, False, outd)
    load_final, _ = loader(args.mode, True, outd)
    dry = load_dry + "return brickwright_restore(array_merge(json_decode(" + php_str(json.dumps(a)) + ", true), ['dry_run' => true]));"
    real = load_final + "return brickwright_restore(json_decode(" + php_str(json.dumps(a)) + ", true));"
    say({"upload_first": uploads, "dry_run_file": write_call(outd, f"restore-{args.stamp}.dry-run", dry),
         "restore_file": write_call(outd, f"restore-{args.stamp}", real)})
    return 0


def cmd_cleanup_call(args) -> int:
    code = (f"$d = wp_upload_dir()['basedir'] . '/{UPLOAD_DIR}'; $gone = []; "
            "foreach ((array) glob($d . '/*') as $f) { if (is_file($f)) { unlink($f); $gone[] = basename($f); } } "
            "@rmdir($d); return ['deleted' => $gone, 'folder_gone' => !is_dir($d)];")
    say({"php": code})
    return 0


def cmd_verify(args) -> int:
    req = urllib.request.Request(args.url, headers={"User-Agent": "Mozilla/5.0 brickwright-verify", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    problems = []
    if re.search(r"checking your browser|cf-browser-verification|captcha", html, re.I) and len(html) < 20000:
        problems.append("got a bot-check page, not the site: use render-call instead")
    for w in filter(None, (args.forbidden or "").split(",")):
        if re.search(re.escape(w), html, re.I):
            problems.append(f"forbidden word on the page: {w}")
    for i in filter(None, (args.expect or "").split(",")):
        if f"brxe-{i}" not in html:
            problems.append(f"element {i} isn't on the page")
    say({"url": args.url, "bytes": len(html), "problems": problems})
    return 1 if problems else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="deploy.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def mode_arg(a):
        a.add_argument("--mode", choices=["one-shot", "installed", "inline"], default="one-shot")
        a.add_argument("--project", default=".")

    a = sub.add_parser("setup"); a.add_argument("--project", default="."); a.add_argument("--update", action="store_true"); a.set_defaults(fn=cmd_setup)
    a = sub.add_parser("config-call"); mode_arg(a); a.set_defaults(fn=cmd_config_call)
    a = sub.add_parser("save-config"); a.add_argument("result"); a.add_argument("--project", default="."); a.set_defaults(fn=cmd_save_config)
    a = sub.add_parser("prepare"); a.add_argument("piece"); a.add_argument("--targets"); mode_arg(a)
    a.add_argument("--adopt", action="store_true", help="take over classes/sections that already exist on the site")
    a.add_argument("--backup-dir", help="server folder for backups (default wp-content/brickwright-backups)")
    a.set_defaults(fn=cmd_prepare)
    a = sub.add_parser("upload"); a.add_argument("file"); a.add_argument("--url", required=True); a.add_argument("--header", action="append"); a.set_defaults(fn=cmd_upload)
    a = sub.add_parser("record"); a.add_argument("piece"); a.add_argument("result"); a.set_defaults(fn=cmd_record)
    a = sub.add_parser("render-call"); a.add_argument("--post-id", type=int, required=True); a.add_argument("--area", default="content")
    a.add_argument("--grep"); a.add_argument("--expect"); mode_arg(a); a.set_defaults(fn=cmd_render_call)
    a = sub.add_parser("restore-call"); a.add_argument("--stamp", required=True); a.add_argument("--backup-dir"); mode_arg(a); a.set_defaults(fn=cmd_restore_call)
    a = sub.add_parser("cleanup-call"); a.set_defaults(fn=cmd_cleanup_call)
    a = sub.add_parser("verify"); a.add_argument("url"); a.add_argument("--forbidden"); a.add_argument("--expect"); a.set_defaults(fn=cmd_verify)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
