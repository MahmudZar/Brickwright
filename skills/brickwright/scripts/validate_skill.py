"""Validate the Brickwright skill package. Run: python -I skills/brickwright/scripts/validate_skill.py"""
import pathlib
import py_compile
import re
import subprocess
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
errors = []

text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
fm = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
if not fm:
    errors.append("SKILL.md must start with YAML frontmatter")
else:
    name = (re.search(r"^name:\s*(.+)$", fm.group(1), re.M) or [None, None])[1]
    desc = (re.search(r"^description:\s*(.+)$", fm.group(1), re.M) or [None, None])[1]
    if not name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name.strip()):
        errors.append(f"invalid or missing name: {name}")
    elif name.strip() != SKILL_DIR.name:
        errors.append(f"name `{name}` must match the folder `{SKILL_DIR.name}`")
    if not desc:
        errors.append("missing description")
    else:
        if len(desc) > 1024:
            errors.append(f"description is {len(desc)} characters (max 1024)")
        if re.search(r"\b(I|me|my|you|your)\b", desc):
            errors.append("description must be third person")

if len(text.splitlines()) > 500:
    errors.append("SKILL.md must stay under 500 lines")
if "\\" in text.replace("\\`", ""):
    errors.append("use forward slashes in SKILL.md")

for folder in ("references", "assets", "scripts"):
    for entry in (SKILL_DIR / folder).iterdir():
        if entry.is_dir() and entry.name != "__pycache__":
            errors.append(f"nested folder not allowed: {folder}/{entry.name}")

for ref in sorted(set(re.findall(r"`((?:references|assets|scripts)/[\w.-]+)`", text))):
    if not (SKILL_DIR / ref).exists():
        errors.append(f"SKILL.md mentions {ref}, which doesn't exist")

for py in (SKILL_DIR / "scripts").glob("*.py"):
    try:
        py_compile.compile(str(py), doraise=True)
    except py_compile.PyCompileError as e:
        errors.append(f"{py.name}: {e.msg}")
py_compile.compile(str(SKILL_DIR / "assets" / "piece-template.bricks.py"), doraise=True)

for required in ("bricks_gen.py", "deploy.py", "brickwright-deploy.php", "test_bricks_gen.py"):
    if not (SKILL_DIR / "scripts" / required).exists():
        errors.append(f"scripts/{required} is missing")
php = (SKILL_DIR / "scripts" / "brickwright-deploy.php").read_text(encoding="utf-8")
for fn in ("brickwright_deploy", "brickwright_restore", "brickwright_site_config", "brickwright_render"):
    if f"function {fn}(" not in php:
        errors.append(f"brickwright-deploy.php lacks {fn}()")
versions = {re.search(r'__version__ = "([^"]+)"', (SKILL_DIR / "scripts" / f).read_text(encoding="utf-8")).group(1)
            for f in ("bricks_gen.py", "deploy.py")}
versions.add(re.search(r"BRICKWRIGHT_SERVER_VERSION', '([^']+)'", php).group(1))
if len(versions) != 1:
    errors.append(f"version numbers differ: {sorted(versions)}")

tests = subprocess.run([sys.executable, "-I", str(SKILL_DIR / "scripts" / "test_bricks_gen.py")], capture_output=True, text=True)
if tests.returncode != 0:
    errors.append("library tests failed:\n" + tests.stderr[-1500:])

if errors:
    print("Skill validation failed:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"Skill validation passed (version {versions.pop()}).")
