"""Brickwright: build Bricks Builder data (global classes + element trees) from mockup files.

Python 3.10+, standard library only. A project keeps a pinned copy in `.brickwright/lib/`
(`deploy.py setup`). Import it from a build script by walking up to that folder:

    import sys, pathlib
    here = pathlib.Path(__file__).resolve().parent
    root = next(p for p in [here, *here.parents] if (p / ".brickwright" / "lib").is_dir())
    sys.path.insert(0, str(root / ".brickwright" / "lib"))
    from bricks_gen import Build

    b = Build.from_site(root / ".brickwright" / "site.json", seed=20261105, forbidden=["supplier-name"])
    b.add_css_files(here / "hero.css")
    t = b.tree("page")
    s = t.el("section", None, "hero", "hero")
    t.comp("eyebrow", s, "eyebrow", text="New", tag="p")
    warnings = b.check()
    b.write("hero.bricks.json")

Parts
  CSS      strip_comments, parse_css, route_css (one global class per BEM block/element,
           @media / @supports / @container kept per class, unmatched CSS is an error),
           merge_css (property-level patch of an existing class), serialize_nodes
  Elements Ids (seeded, stable), Tree.el / Tree.comp, Components (friendly prop names)
  Checks   structure, classes used both ways, reserved Bricks attributes, design tokens,
           forbidden words
"""
from __future__ import annotations

import json
import pathlib
import random
import re
import string

__all__ = [
    "CssError", "BuildError", "strip_comments", "parse_css", "parse_rule_body", "first_class",
    "route_css", "merge_css", "serialize_nodes", "Ids", "Components", "Tree", "Build",
    "load_tokens", "check_structure", "check_classes", "check_reserved_attrs", "check_tokens",
    "check_forbidden", "RESERVED_ATTRS",
]

FORMAT = "brickwright/1"
__version__ = "0.2.0"


class CssError(ValueError):
    """CSS that can't be parsed or routed. `problems` lists every issue found."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n  " + "\n  ".join(self.problems))


class BuildError(ValueError):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__(f"{len(self.problems)} problem(s):\n  " + "\n  ".join(self.problems))


# =============================================================================================
# CSS: scanning helpers
# =============================================================================================

def strip_comments(text: str) -> str:
    """Remove /* comments */ but leave strings (content: "/*") alone."""
    out, i, n, quote = [], 0, len(text), None
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _skip_string(s: str, i: int) -> int:
    """s[i] is a quote; return the index just after the closing quote."""
    q, i = s[i], i + 1
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == q:
            return i + 1
        i += 1
    return i


def _match_brace(s: str, open_i: int) -> int:
    """s[open_i] == '{'; return the index of its matching '}' (strings skipped)."""
    depth, i = 0, open_i
    while i < len(s):
        ch = s[i]
        if ch in "\"'":
            i = _skip_string(s, i)
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise CssError([f"unclosed '{{' near: {s[open_i - 40 if open_i > 40 else 0:open_i + 1].strip()!r}"])


def _find_top(s: str, i: int, chars: str) -> int:
    """First index >= i of one of `chars` outside strings and parentheses, or -1."""
    paren = 0
    while i < len(s):
        ch = s[i]
        if ch in "\"'":
            i = _skip_string(s, i)
            continue
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif paren == 0 and ch in chars:
            return i
        i += 1
    return -1


def _split_top(s: str, sep: str = ",") -> list[str]:
    """Split on `sep` outside strings, () and [] (so :is(.a, .b) stays whole)."""
    parts, buf, depth, i = [], [], 0, 0
    while i < len(s):
        ch = s[i]
        if ch in "\"'":
            j = _skip_string(s, i)
            buf.append(s[i:j])
            i = j
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf).strip())
    return [p for p in parts if p]


def _norm(sel: str) -> str:
    sel = re.sub(r"\s+", " ", sel.strip())
    return re.sub(r"\s*([>+~,])\s*", r" \1 ", sel).replace(" , ", ", ").strip()


# =============================================================================================
# CSS: parsing
# =============================================================================================

NESTED_AT = {"@media", "@supports", "@container", "@layer", "@scope", "@document", "@starting-style"}


def _at_name(header: str) -> str:
    m = re.match(r"@[-\w]+", header)
    return m.group(0).lower() if m else ""


def _decl_prop(raw: str) -> str | None:
    m = re.match(r"\s*(--[-\w]+|[-\w]+)\s*:", raw)
    return m.group(1).lower() if m else None


def parse_rule_body(body: str) -> dict:
    """Split a rule body into declarations and nested child blocks.

    {"items": [{"prop", "raw"}], "children": [{"selector", "body"}]}
    """
    items, children, i, start = [], [], 0, 0
    while True:
        j = _find_top(body, i, ";{")
        if j < 0:
            tail = body[start:].strip()
            if tail:
                items.append({"prop": _decl_prop(tail), "raw": tail})
            break
        if body[j] == ";":
            seg = body[start:j].strip()
            if seg:
                items.append({"prop": _decl_prop(seg), "raw": seg})
            i = start = j + 1
            continue
        close = _match_brace(body, j)
        sel = body[start:j].strip()
        if sel:
            children.append({"selector": sel, "body": body[j + 1:close]})
        i = start = close + 1
    return {"items": items, "children": children}


def parse_css(text: str) -> list[dict]:
    """Parse CSS (comments already stripped) into nodes, keeping at-rule context.

    rule       {"kind": "rule", "ctx": ("@supports …", "@media …"), "selectors": [...],
                "items": [...], "children": [...]}
    whole      {"kind": "whole", "ctx", "header", "body"}   @keyframes, @font-face, @property …
    statement  {"kind": "statement", "ctx", "header"}       @import …; @layer a, b;
    """
    nodes: list[dict] = []

    def walk(s: str, ctx: tuple):
        i = 0
        while True:
            while i < len(s) and s[i].isspace():
                i += 1
            if i >= len(s):
                return
            j = _find_top(s, i, ";{}")
            if j < 0 or s[j] == "}":
                raise CssError([f"unexpected text: {s[i:i + 60].strip()!r}"])
            header = s[i:j].strip()
            if s[j] == ";":
                if header:
                    nodes.append({"kind": "statement", "ctx": ctx, "header": header})
                i = j + 1
                continue
            close = _match_brace(s, j)
            body = s[j + 1:close]
            i = close + 1
            if header.startswith("@"):
                if _at_name(header) in NESTED_AT:
                    walk(body, ctx + (re.sub(r"\s+", " ", header),))
                else:
                    nodes.append({"kind": "whole", "ctx": ctx, "header": re.sub(r"\s+", " ", header), "body": body})
                continue
            parsed = parse_rule_body(body)
            nodes.append({"kind": "rule", "ctx": ctx, "selectors": _split_top(header),
                          "items": parsed["items"], "children": parsed["children"]})

    walk(text, ())
    return nodes


# =============================================================================================
# CSS: serializing
# =============================================================================================

def _fmt_body(items: list, children: list, level: int) -> str:
    ind = "  " * level
    lines = [ind + it["raw"].strip() + ";" for it in items if it["raw"].strip()]
    for ch in children:
        sub = parse_rule_body(ch["body"])
        inner = _fmt_body(sub["items"], sub["children"], level + 1)
        sel = re.sub(r"\s+", " ", ch["selector"].strip())
        lines.append(f"{ind}{sel} {{\n{inner}\n{ind}}}" if inner else f"{ind}{sel} {{\n{ind}}}")
    return "\n".join(lines)


def _fmt_node(n: dict, level: int) -> str:
    ind = "  " * level
    if n["kind"] == "statement":
        return f"{ind}{n['header']};"
    if n["kind"] == "whole":
        sub = parse_rule_body(n["body"])
        inner = _fmt_body(sub["items"], sub["children"], level + 1)
        return f"{ind}{n['header']} {{\n{inner}\n{ind}}}"
    sel = (",\n" + ind).join(n["selectors"])
    inner = _fmt_body(n["items"], n["children"], level + 1)
    return f"{ind}{sel} {{\n{inner}\n{ind}}}" if inner else f"{ind}{sel} {{\n{ind}}}"


def serialize_nodes(nodes: list[dict]) -> str:
    """Nodes back to CSS. Consecutive nodes with the same at-rule context share one wrapper."""

    def emit(group: list[dict], depth: int) -> list[str]:
        out, k = [], 0
        while k < len(group):
            n = group[k]
            if len(n["ctx"]) == depth:
                out.append(_fmt_node(n, depth))
                k += 1
                continue
            head = n["ctx"][depth]
            run = []
            while k < len(group) and len(group[k]["ctx"]) > depth and group[k]["ctx"][depth] == head:
                run.append(group[k])
                k += 1
            ind = "  " * depth
            out.append(f"{ind}{head} {{\n" + "\n\n".join(emit(run, depth + 1)) + f"\n{ind}}}")
        return out

    return "\n\n".join(emit(nodes, 0)).strip()


# =============================================================================================
# CSS: routing to global classes
# =============================================================================================

_PSEUDO_FN = re.compile(r"::?[-\w]+\(")


def _strip_pseudo(sel: str) -> str:
    """Remove :pseudo(...) (balanced), ::pseudo, :pseudo and [attr] parts of a selector."""
    out, i = [], 0
    while i < len(sel):
        ch = sel[i]
        if ch in "\"'":
            i = _skip_string(sel, i)
            continue
        if ch == "[":
            depth = 0
            while i < len(sel):
                if sel[i] == "[":
                    depth += 1
                elif sel[i] == "]":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            i += 1
            continue
        if ch == ":":
            m = _PSEUDO_FN.match(sel, i)
            if m:
                depth, i = 1, m.end()
                while i < len(sel) and depth:
                    depth += {"(": 1, ")": -1}.get(sel[i], 0)
                    i += 1
                continue
            m = re.compile(r"::?[-\w]+").match(sel, i)
            i = m.end() if m else i + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def first_class(selector: str) -> str | None:
    """The class a rule belongs to: the first .class outside :pseudo() and [attr], or None."""
    m = re.search(r"\.(-?[_a-zA-Z][\w-]*)", _strip_pseudo(selector))
    return m.group(1) if m else None


def _keyframe_users(name: str, owned: dict[str, list]) -> list[str]:
    pat = re.compile(r"animation(?:-name)?\s*:[^;{}]*?(?<![\w-])" + re.escape(name) + r"(?![\w-])")
    return [cls for cls, nodes in owned.items() if pat.search(serialize_nodes(nodes))]


def route_css(text: str, owners: dict | None = None, host=None) -> dict[str, str]:
    """Split CSS into {class name: custom CSS}.

    Each selector goes to its first class (`first_class`). A rule whose selector list spans
    several classes is split; a top-level @media mixing classes is split per class.
    owners  {selector or at-rule header: class | [classes] | None}: explicit owner, None = drop.
            Keys are matched after whitespace normalisation, e.g. "body", ":root",
            "@keyframes spin", "@font-face".
    host    callable(class) -> class | [classes] | None: re-home a class's rules (markup printed
            by a shortcode/plugin has no element of its own, so its CSS must live on the class of
            the element that prints it). None = drop.
    @keyframes without an owner are copied into every class whose CSS uses them (Bricks prints
    only the classes on the page, so a single shared copy could go missing); unused keyframes
    are an error. Anything else without an owner is an error, never a silent default.
    """
    owners = {_norm(k): v for k, v in (owners or {}).items()}
    nodes = parse_css(strip_comments(text))
    owned: dict[str, list] = {}
    problems: list[str] = []
    keyframes: list[dict] = []

    def where(n):
        return (" inside " + " > ".join(n["ctx"])) if n["ctx"] else ""

    def targets(name):
        if host is None:
            return [name]
        h = host(name)
        return [] if h is None else ([h] if isinstance(h, str) else list(h))

    for n in nodes:
        if n["kind"] == "rule":
            groups: dict[str, list[str]] = {}
            for sel in n["selectors"]:
                key = _norm(sel)
                if key in owners:
                    o = owners[key]
                    dest = [] if o is None else ([o] if isinstance(o, str) else list(o))
                else:
                    c = first_class(sel)
                    if c is None:
                        problems.append(f"no class to own `{sel}`{where(n)}: add it to owners (or None to drop)")
                        continue
                    dest = targets(c)
                for d in dest:
                    groups.setdefault(d, []).append(sel)
            for d, sels in groups.items():
                owned.setdefault(d, []).append({**n, "selectors": sels})
            continue
        key = _norm(n["header"])
        if key in owners:
            o = owners[key]
            for d in ([] if o is None else ([o] if isinstance(o, str) else list(o))):
                owned.setdefault(d, []).append(n)
        elif n["kind"] == "whole" and _at_name(n["header"]) in ("@keyframes", "@-webkit-keyframes"):
            keyframes.append(n)
        else:
            problems.append(f"no owner for `{n['header']}`{where(n)}: add it to owners (or None to drop)")

    for n in keyframes:
        name = n["header"].split(None, 1)[1].strip() if " " in n["header"] else ""
        users = _keyframe_users(name, owned)
        if not users:
            problems.append(f"`{n['header']}` isn't used by any class: remove it or give it an owner")
        for u in users:  # Bricks prints only classes on the page, so every user carries its own copy
            owned[u].append(n)

    if problems:
        raise CssError(problems)
    return {cls: serialize_nodes(ns) + "\n" for cls, ns in owned.items()}


# =============================================================================================
# CSS: property-level merge (patch one live class without rebuilding the piece)
# =============================================================================================

REMOVE = "!remove"


def _merge_items(target: list, incoming: list) -> None:
    for inc in incoming:
        prop = inc["prop"]
        value = inc["raw"].split(":", 1)[1].strip() if prop else ""
        if prop is None:
            if all(t["raw"].strip() != inc["raw"].strip() for t in target):
                target.append(dict(inc))
            continue
        hits = [k for k, t in enumerate(target) if t["prop"] == prop]
        if value == REMOVE:
            for k in reversed(hits):
                del target[k]
        elif hits:
            target[hits[-1]] = dict(inc)
        else:
            target.append(dict(inc))


def _merge_children(existing: list, incoming: list) -> list:
    result = [dict(c) for c in existing]
    index = {_norm(c["selector"]): k for k, c in enumerate(result)}
    for inc in incoming:
        key = _norm(inc["selector"])
        if key in index:
            k = index[key]
            a, b = parse_rule_body(result[k]["body"]), parse_rule_body(inc["body"])
            _merge_items(a["items"], b["items"])
            kids = _merge_children(a["children"], b["children"])
            result[k] = {"selector": result[k]["selector"], "body": _fmt_body(a["items"], kids, 0)}
        else:
            index[key] = len(result)
            result.append(dict(inc))
    return result


def merge_css(existing: str, incoming: str) -> str:
    """Merge `incoming` into `existing`, property by property.

    Same selector (and at-rule context): incoming declarations replace the same property,
    other declarations stay, new ones are appended, nested rules are merged the same way.
    A value of `!remove` deletes the property (e.g. `gap: !remove;`).
    """
    result = parse_css(strip_comments(existing))
    for n in result:
        if n["kind"] == "rule":
            n["items"] = [dict(i) for i in n["items"]]

    def key(n):
        if n["kind"] == "rule":
            return ("rule", n["ctx"], _norm(", ".join(n["selectors"])))
        return (n["kind"], n["ctx"], _norm(n["header"]))

    index = {key(n): k for k, n in enumerate(result)}
    for inc in parse_css(strip_comments(incoming)):
        k = index.get(key(inc))
        if k is None:
            index[key(inc)] = len(result)
            result.append(inc)
        elif inc["kind"] == "rule":
            _merge_items(result[k]["items"], inc["items"])
            result[k]["children"] = _merge_children(result[k]["children"], inc["children"])
        else:
            result[k] = inc
    return serialize_nodes(result) + "\n"


# =============================================================================================
# Elements
# =============================================================================================

class Ids:
    """Seeded six-letter Bricks element ids: the same seed gives the same ids on every run."""

    def __init__(self, seed: int):
        self._rnd = random.Random(seed)
        self.used: set[str] = set()

    def reserve(self, *ids: str) -> None:
        """Mark ids that already exist on the site (they won't be generated)."""
        self.used.update(ids)

    def new(self) -> str:
        while True:
            i = "".join(self._rnd.choice(string.ascii_lowercase) for _ in range(6))
            if i not in self.used:
                self.used.add(i)
                return i


class Components:
    """Live Bricks components by friendly name.

    {"eyebrow": {"cid": "dzcjzx", "props": {"text": "dfaave", "tag": "mzerqf"}, "required": ["text"]}}
    """

    def __init__(self, data: dict | None = None):
        self.data = data or {}

    @classmethod
    def from_json(cls, path) -> "Components":
        """A components file, or a site.json (its "components" key)."""
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        return cls(data.get("components", data) if data.get("format") == "brickwright-site/1" else data)

    def resolve(self, name: str, props: dict) -> tuple[str, dict]:
        if name not in self.data:
            raise BuildError([f"unknown component `{name}` (known: {', '.join(sorted(self.data)) or 'none'})"])
        c = self.data[name]
        ids = c.get("props", {})
        out, problems = {}, []
        for k, v in props.items():
            if k in ids:
                out[ids[k]] = v
            elif k in ids.values():
                out[k] = v
            else:
                problems.append(f"component `{name}` has no property `{k}` (has: {', '.join(ids)})")
        missing = [r for r in c.get("required", []) if ids.get(r, r) not in out]
        problems += [f"component `{name}` needs `{r}`" for r in missing]
        if problems:
            raise BuildError(problems)
        return c["cid"], out


class Tree:
    """One element tree (a page, template or section)."""

    def __init__(self, build: "Build", name: str):
        self.build, self.name = build, name
        self.elements: list[dict] = []
        self._by_id: dict[str, dict] = {}

    def _add(self, e: dict) -> str:
        if e["parent"]:
            if e["parent"] not in self._by_id:
                raise BuildError([f"{self.name}: parent `{e['parent']}` of `{e['label']}` isn't in this tree"])
            self._by_id[e["parent"]]["children"].append(e["id"])
        self.elements.append(e)
        self._by_id[e["id"]] = e
        return e["id"]

    def el(self, name: str, parent: str | None, label: str, cls=None, **settings) -> str:
        """Add a Bricks element; returns its id. `_id=` keeps a fixed id. cls: name or list.
        Existing live classes are written "@name" (mapped to ids at deploy)."""
        eid = settings.pop("_id", None) or self.build.ids.new()
        if eid in self._by_id:
            raise BuildError([f"{self.name}: duplicate id `{eid}`"])
        self.build.ids.used.add(eid)
        if cls:
            settings["_cssGlobalClasses"] = [cls] if isinstance(cls, str) else list(cls)
        return self._add({"id": eid, "name": name, "parent": parent, "children": [], "settings": settings, "label": label})

    def comp(self, component: str, parent: str | None, label: str, settings: dict | None = None, **props) -> str:
        """Add a live component instance. Props by friendly name (or raw property id)."""
        cid, properties = self.build.components.resolve(component, props)
        e = {"id": self.build.ids.new(), "name": "div", "cid": cid, "parent": parent, "children": [],
             "settings": {"tag": "div", **(settings or {})}, "properties": properties, "label": label}
        return self._add(e)

    def get(self, eid: str) -> dict:
        return self._by_id[eid]

    def __iter__(self):
        return iter(self.elements)

    def __len__(self):
        return len(self.elements)


# =============================================================================================
# Checks
# =============================================================================================

RESERVED_ATTRS = {"data-component", "data-component-id", "data-id", "data-parent-id", "data-script-id",
                  "data-element-id", "data-index"}


def check_structure(trees: dict[str, list]) -> list[str]:
    problems, seen = [], {}
    for tname, els in trees.items():
        by_id = {}
        for e in els:
            if not re.fullmatch(r"[a-z0-9]{6}", e["id"]):
                problems.append(f"{tname}: id `{e['id']}` isn't six lowercase letters/digits")
            if e["id"] in seen:
                problems.append(f"{tname}: id `{e['id']}` also used in {seen[e['id']]}")
            seen[e["id"]] = tname
            by_id[e["id"]] = e
        for e in els:
            if e["parent"] and e["parent"] not in by_id:
                problems.append(f"{tname}: `{e['label']}` has a missing parent `{e['parent']}`")
            for c in e["children"]:
                if c not in by_id or by_id[c]["parent"] != e["id"]:
                    problems.append(f"{tname}: `{e['label']}` lists child `{c}` that doesn't point back")
    return problems


def _used_classes(trees: dict[str, list]) -> set[str]:
    used = set()
    for els in trees.values():
        for e in els:
            for c in e["settings"].get("_cssGlobalClasses", []):
                if not c.startswith("@"):
                    used.add(c)
    return used


def check_classes(classes: dict[str, str], trees: dict[str, list], no_css_ok=()) -> list[str]:
    """Every class on an element has CSS (or is in no_css_ok) and every CSS class is used."""
    used = _used_classes(trees)
    problems = [f"class `{c}` is on an element but has no CSS (add CSS or list it in no_css_ok)"
                for c in sorted(used - classes.keys() - set(no_css_ok))]
    problems += [f"class `{c}` has CSS but no element uses it" for c in sorted(classes.keys() - used)]
    return problems


def check_reserved_attrs(trees: dict[str, list]) -> list[str]:
    problems = []
    for tname, els in trees.items():
        for e in els:
            if any(k.startswith("_cssCustom") for k in e["settings"]):
                problems.append(f"{tname}: `{e['label']}` has element CSS (_cssCustom): put it in a global class")
            for a in e["settings"].get("_attributes", []) or []:
                if str(a.get("name", "")).strip().lower() in RESERVED_ATTRS:
                    problems.append(f"{tname}: `{e['label']}` uses reserved attribute `{a['name']}` (locks builder selection)")
    return problems


def load_tokens(path) -> set[str]:
    """Design-token names from JSON: a list of names, or {"name": value} / {"tokens": [...]}."""
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("tokens", data)
    names = data.keys() if isinstance(data, dict) else data
    return {n if n.startswith("--") else "--" + n for n in names}


_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(\s*[\d.]")
_LENGTH = re.compile(r"(?<![\w.-])(\d*\.?\d+)(px|rem|em)\b")
LENGTH_PROPS = re.compile(r"^(margin|padding|gap|row-gap|column-gap|font-size|border(-[a-z]+)*-radius|"
                          r"(margin|padding)-(top|right|bottom|left|block|inline)(-(start|end))?)$")


def _walk_decls(css: str):
    """Yield (prop, value) for every declaration in a class's CSS, nested ones included."""

    def body(items, children):
        for it in items:
            if it["prop"]:
                yield it["prop"], it["raw"].split(":", 1)[1]
        for ch in children:
            sub = parse_rule_body(ch["body"])
            yield from body(sub["items"], sub["children"])

    for n in parse_css(strip_comments(css)):
        if n["kind"] == "rule":
            yield from body(n["items"], n["children"])
        elif n["kind"] == "whole":
            sub = parse_rule_body(n["body"])
            yield from body(sub["items"], sub["children"])


def check_tokens(classes: dict[str, str], tokens: set[str] | None, allow_raw=(), allow_vars_prefix=("--_",)):
    """(errors, warnings) for design-token use.

    errors    var(--x) that is neither a token nor declared in the CSS itself (typos),
              raw colours (#hex, rgb(0 …), oklch(0.5 …)) outside allow_raw classes
    warnings  raw px/rem/em lengths above 2px in spacing, font-size and radius properties
    """
    errors, warnings = [], []
    local = set()
    for css in classes.values():
        local.update(p for p, _ in _walk_decls(css) if p.startswith("--"))
        local.update(re.findall(r"@property\s+(--[\w-]+)", css))
    for cls, css in sorted(classes.items()):
        for prop, value in _walk_decls(css):
            if tokens is not None:
                for v in re.findall(r"var\(\s*(--[\w-]+)", value):
                    if v not in tokens and v not in local and not v.startswith(tuple(allow_vars_prefix)):
                        errors.append(f"`{cls}`: unknown variable {v} in `{prop}`")
            if cls in allow_raw or prop.startswith("--"):
                continue
            if _COLOUR.search(value):
                errors.append(f"`{cls}`: raw colour in `{prop}:{value.strip()}` (use a colour variable)")
            if LENGTH_PROPS.match(prop):
                for num, unit in _LENGTH.findall(value):
                    if unit != "px" or float(num) > 2:
                        warnings.append(f"`{cls}`: raw length {num}{unit} in `{prop}` (use a spacing/type variable?)")
    return errors, warnings


def check_forbidden(classes: dict[str, str], trees: dict[str, list], words=()) -> list[str]:
    """Words that must never reach the front end (e.g. supplier names), case-insensitive."""
    if not words:
        return []
    pat = re.compile("|".join(re.escape(w) for w in words), re.I)
    problems = [f"class `{c}`: forbidden word `{m.group(0)}`" for c, css in classes.items() for m in [pat.search(c + css)] if m]
    for tname, els in trees.items():
        for e in els:
            m = pat.search(json.dumps(e, ensure_ascii=False))
            if m:
                problems.append(f"{tname}: `{e['label']}` contains forbidden word `{m.group(0)}`")
    return problems


# =============================================================================================
# Build
# =============================================================================================

class Build:
    """Collects global classes and element trees for one piece, checks them and writes the JSON."""

    def __init__(self, seed: int, components: Components | None = None, tokens: set[str] | None = None,
                 forbidden=(), allow_vars_prefix=("--_",), site_classes: set[str] | None = None,
                 locked_classes: set[str] | None = None):
        self.ids = Ids(seed)
        self.components = components or Components()
        self.tokens = tokens
        self.forbidden = tuple(forbidden)
        self.allow_vars_prefix = tuple(allow_vars_prefix)
        self.site_classes = site_classes
        self.locked_classes = locked_classes or set()
        self.classes: dict[str, str] = {}
        self.trees: dict[str, Tree] = {}

    @classmethod
    def from_site(cls, site_json, seed: int, forbidden=(), **kw) -> "Build":
        """Build configured from `.brickwright/site.json` (made by `deploy.py save-config`)."""
        data = json.loads(pathlib.Path(site_json).read_text(encoding="utf-8"))
        return cls(seed, components=Components(data.get("components", {})), tokens=set(data.get("tokens", [])) or None,
                   forbidden=forbidden, site_classes=set(data.get("classes", [])),
                   locked_classes=set(data.get("locked_classes", [])), **kw)

    def add_css(self, css: str, owners: dict | None = None, host=None) -> dict[str, str]:
        routed = route_css(css, owners=owners, host=host)
        for cls, text in routed.items():
            self.classes[cls] = (self.classes[cls].rstrip() + "\n\n" + text) if cls in self.classes else text
        return routed

    def add_css_files(self, *paths, owners: dict | None = None, host=None) -> dict[str, str]:
        return self.add_css("\n".join(pathlib.Path(p).read_text(encoding="utf-8") for p in paths), owners, host)

    def tree(self, name: str) -> Tree:
        if name in self.trees:
            raise BuildError([f"tree `{name}` already exists"])
        self.trees[name] = Tree(self, name)
        return self.trees[name]

    def _plain_trees(self) -> dict[str, list]:
        return {n: t.elements for n, t in self.trees.items()}

    def check(self, no_css_ok=(), allow_raw=(), strict=False) -> list[str]:
        """Run every check. Raises BuildError on errors; returns warnings (errors if strict)."""
        trees = self._plain_trees()
        for c in no_css_ok:
            if c in _used_classes(trees) and c not in self.classes:
                self.classes[c] = f".{c} {{\n}}\n"  # Bricks needs the global class to exist
        errors = check_structure(trees) + check_classes(self.classes, trees, no_css_ok)
        errors += check_reserved_attrs(trees) + check_forbidden(self.classes, trees, self.forbidden)
        errors += [f"class `{c}` is locked on the site (a framework class): give yours another name"
                   for c in sorted(self.classes.keys() & self.locked_classes)]
        if self.site_classes is not None:
            refs = {c[1:] for els in trees.values() for e in els for c in e["settings"].get("_cssGlobalClasses", []) if c.startswith("@")}
            errors += [f"`@{c}` doesn't exist on the site (re-export site.json if it was just added)" for c in sorted(refs - self.site_classes)]
        tok_err, warnings = check_tokens(self.classes, self.tokens, allow_raw, self.allow_vars_prefix)
        errors += tok_err
        if strict:
            errors, warnings = errors + warnings, []
        if errors:
            raise BuildError(errors)
        return warnings

    def data(self, **extra) -> dict:
        return {"format": FORMAT, "classes": self.classes, "trees": self._plain_trees(), **extra}

    def write(self, path, **extra) -> dict:
        d = self.data(**extra)
        pathlib.Path(path).write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        return d
