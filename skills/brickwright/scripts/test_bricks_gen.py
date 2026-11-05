"""Fixture tests for bricks_gen. Run: python -I scripts/test_bricks_gen.py"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from bricks_gen import (Build, BuildError, Components, CssError, first_class, merge_css,  # noqa: E402
                        parse_css, route_css, strip_comments)


def squash(css):
    return " ".join(css.split())


class Parsing(unittest.TestCase):
    def test_comments_and_strings(self):
        css = '.a { content: "/* not a comment */ {"; } /* gone */ .b { color: red }'
        nodes = parse_css(strip_comments(css))
        self.assertEqual([n["selectors"] for n in nodes], [[".a"], [".b"]])
        self.assertIn('"/* not a comment */ {"', nodes[0]["items"][0]["raw"])

    def test_nested_context_kept(self):
        nodes = parse_css("@supports (display: grid) { @media (width >= 40rem) { .a { gap: 1px } } }")
        self.assertEqual(nodes[0]["ctx"], ("@supports (display: grid)", "@media (width >= 40rem)"))

    def test_selector_list_respects_parentheses(self):
        nodes = parse_css(".a:is(.x, .y), .b { color: red }")
        self.assertEqual(nodes[0]["selectors"], [".a:is(.x, .y)", ".b"])

    def test_semicolon_inside_url(self):
        nodes = parse_css(".a { background: url(data:image/svg+xml;utf8,x); color: red }")
        self.assertEqual([i["prop"] for i in nodes[0]["items"]], ["background", "color"])

    def test_statements(self):
        nodes = parse_css("@layer base, theme; .a { color: red }")
        self.assertEqual(nodes[0]["kind"], "statement")

    def test_unclosed_brace(self):
        with self.assertRaises(CssError):
            parse_css(".a { color: red")


class Routing(unittest.TestCase):
    def test_first_class(self):
        self.assertEqual(first_class(".card__title:hover"), "card__title")
        self.assertEqual(first_class(":is(.x, .y) .card"), "card")
        self.assertEqual(first_class('[data-x=".nope"] .card'), "card")
        self.assertEqual(first_class("a:not(.x)"), None)

    def test_nested_rules_stay_with_their_class(self):
        out = route_css(".card { color: red; & > .x { gap: 0 } @media (width >= 40rem) { padding: 0 } }")
        self.assertEqual(list(out), ["card"])
        self.assertIn("@media (width >= 40rem) {", out["card"])

    def test_mixed_top_level_media_is_split(self):
        out = route_css("@media (width < 40rem) { .a { color: red } .b { color: blue } }")
        self.assertEqual(squash(out["a"]), "@media (width < 40rem) { .a { color: red; } }")
        self.assertEqual(squash(out["b"]), "@media (width < 40rem) { .b { color: blue; } }")

    def test_selector_list_split_per_class(self):
        out = route_css(".a:hover, .a:focus, .b { color: red }")
        self.assertEqual(squash(out["a"]), ".a:hover, .a:focus { color: red; }")
        self.assertEqual(squash(out["b"]), ".b { color: red; }")

    def test_unmatched_css_fails(self):
        with self.assertRaises(CssError) as e:
            route_css(":root { --x: 1 } h1 { margin: 0 } .a { color: red }")
        self.assertEqual(len(e.exception.problems), 2)

    def test_explicit_owners(self):
        out = route_css("body { margin: 0 } :root:has(.menu.open) { overflow: hidden } .menu { gap: 0 }",
                        owners={"body": None, ":root:has(.menu.open)": "menu"})
        self.assertEqual(list(out), ["menu"])
        self.assertIn(":root:has(.menu.open)", out["menu"])

    def test_keyframes_go_to_their_only_user(self):
        out = route_css("@keyframes spin { to { rotate: 1turn } } .a { animation: spin 1s } .b { color: red }")
        self.assertIn("@keyframes spin", out["a"])
        self.assertNotIn("@keyframes", out["b"])

    def test_shared_keyframes_copied_to_each_user(self):
        out = route_css("@keyframes spin { to { rotate: 1turn } } .a { animation: spin 1s } .b { animation-name: spin }")
        self.assertIn("@keyframes spin", out["a"])
        self.assertIn("@keyframes spin", out["b"])

    def test_unused_keyframes_fail(self):
        with self.assertRaises(CssError):
            route_css("@keyframes spin { to { rotate: 1turn } } .a { color: red }")

    def test_host_rehomes_shortcode_markup(self):
        out = route_css(".review-card { gap: 0 } .reviews { color: red }",
                        host=lambda c: "reviews" if c.startswith("review-") else c)
        self.assertEqual(list(out), ["reviews"])
        self.assertIn(".review-card", out["reviews"])


class Merge(unittest.TestCase):
    BASE = ".card {\n  color: red;\n  gap: 1rem;\n  @media (width >= 40rem) {\n    gap: 2rem;\n  }\n}\n"

    def test_override_keep_append(self):
        out = squash(merge_css(self.BASE, ".card { gap: var(--space-m); padding: 0 }"))
        self.assertIn("color: red;", out)
        self.assertIn("gap: var(--space-m);", out)
        self.assertIn("padding: 0;", out)
        self.assertNotIn("gap: 1rem", out)

    def test_nested_media_merged(self):
        out = squash(merge_css(self.BASE, ".card { @media (width >= 40rem) { gap: 3rem; color: blue } }"))
        self.assertIn("@media (width >= 40rem) { gap: 3rem; color: blue; }", out)

    def test_remove(self):
        out = merge_css(self.BASE, ".card { color: !remove }")
        self.assertNotIn("color", out)

    def test_new_rule_appended(self):
        out = merge_css(self.BASE, ".card:hover { color: blue }")
        self.assertIn(".card:hover", out)

    def test_idempotent(self):
        once = merge_css(self.BASE, ".card { gap: 0 }")
        self.assertEqual(once, merge_css(once, ".card { gap: 0 }"))


COMPONENTS = Components({"eyebrow": {"cid": "dzcjzx", "props": {"text": "dfaave", "tag": "mzerqf"}, "required": ["text"]}})


def small_build(seed=1, **kw):
    b = Build(seed, components=COMPONENTS, **kw)
    b.add_css(".hero { padding: var(--space-l) } .hero__title { color: var(--text-primary) }")
    t = b.tree("page")
    s = t.el("section", None, "hero", "hero")
    t.el("heading", s, "title", "hero__title", tag="h1", text="Hi")
    t.comp("eyebrow", s, "eyebrow", text="New", tag="p")
    return b, t, s


class Elements(unittest.TestCase):
    def test_seeded_ids_are_stable(self):
        a, b = small_build(7), small_build(7)
        self.assertEqual(a[0].data(), b[0].data())
        self.assertNotEqual(a[0].data(), small_build(8)[0].data())

    def test_component_props(self):
        b, t, s = small_build()
        e = t.elements[-1]
        self.assertEqual((e["cid"], e["properties"]), ("dzcjzx", {"dfaave": "New", "mzerqf": "p"}))
        with self.assertRaises(BuildError):
            t.comp("eyebrow", s, "bad", colour="red")
        with self.assertRaises(BuildError):
            t.comp("eyebrow", s, "missing", tag="p")

    def test_children_linked(self):
        b, t, s = small_build()
        self.assertEqual(len(t.get(s)["children"]), 2)

    def test_write(self):
        b, *_ = small_build()
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "x.json"
            b.write(p, note="ok")
            data = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "brickwright/1")
        self.assertEqual(set(data["trees"]), {"page"})


class Checks(unittest.TestCase):
    def test_clean_build_passes(self):
        b, *_ = small_build(tokens={"--space-l", "--text-primary"})
        self.assertEqual(b.check(), [])

    def test_class_without_css_and_unused_css(self):
        b, t, s = small_build()
        t.el("div", s, "extra", "hero__extra")
        b.add_css(".orphan { color: var(--x) }")
        with self.assertRaises(BuildError) as e:
            b.check()
        text = str(e.exception)
        self.assertIn("hero__extra", text)
        self.assertIn("orphan", text)

    def test_no_css_ok_creates_empty_class(self):
        b, t, s = small_build()
        t.el("div", s, "wrap", "hero__wrap")
        b.check(no_css_ok=["hero__wrap"])
        self.assertIn("hero__wrap", b.classes)

    def test_reserved_attribute(self):
        b, t, s = small_build()
        t.get(s)["settings"]["_attributes"] = [{"name": "data-component", "value": "x"}]
        with self.assertRaisesRegex(BuildError, "reserved attribute"):
            b.check()

    def test_element_css_refused(self):
        b, t, s = small_build()
        t.get(s)["settings"]["_cssCustom"] = "%root% { color: red }"
        with self.assertRaisesRegex(BuildError, "element CSS"):
            b.check()

    def test_tokens(self):
        b, *_ = small_build(tokens={"--space-l"})
        b.add_css(".hero { border: 1px solid #ff0000; margin: 24px }")
        with self.assertRaises(BuildError) as e:
            b.check()
        text = str(e.exception)
        self.assertIn("unknown variable --text-primary", text)
        self.assertIn("raw colour", text)
        b.classes["hero"] = ".hero { padding: var(--space-l); margin: 24px }\n"
        b.classes["hero__title"] = ".hero__title { --_c: red; color: var(--_c) }\n"
        warnings = b.check(allow_raw=["hero__title"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("24px", warnings[0])

    def test_forbidden_words(self):
        b, t, s = small_build(forbidden=["acme-supplier"])
        t.el("text-basic", s, "note", None, text="Shipped by ACME-Supplier")
        with self.assertRaisesRegex(BuildError, "forbidden word"):
            b.check()


class SiteConfig(unittest.TestCase):
    SITE = {"format": "brickwright-site/1",
            "components": {"eyebrow": {"cid": "dzcjzx", "props": {"text": "dfaave", "tag": "mzerqf"}}},
            "tokens": ["--space-l", "--text-primary"], "classes": ["clickable-card", "container"],
            "locked_classes": ["container"]}

    def build(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "site.json"
            p.write_text(json.dumps(self.SITE), encoding="utf-8")
            b = Build.from_site(p, seed=3)
            self.assertEqual(Components.from_json(p).data["eyebrow"]["cid"], "dzcjzx")
        b.add_css(".hero { padding: var(--space-l) }")
        return b

    def test_from_site_passes(self):
        b = self.build()
        t = b.tree("page")
        s = t.el("section", None, "hero", "hero")
        t.comp("eyebrow", s, "eyebrow", text="Hi")
        t.el("div", s, "card", "@clickable-card")
        self.assertEqual(b.check(), [])

    def test_unknown_site_class(self):
        b = self.build()
        t = b.tree("page")
        s = t.el("section", None, "hero", "hero")
        t.el("div", s, "card", "@not-on-site")
        with self.assertRaisesRegex(BuildError, "doesn't exist on the site"):
            b.check()

    def test_locked_class_refused(self):
        b = self.build()
        b.add_css(".container { gap: 0 }")
        t = b.tree("page")
        s = t.el("section", None, "hero", ["hero", "container"])
        with self.assertRaisesRegex(BuildError, "locked"):
            b.check()


if __name__ == "__main__":
    unittest.main()
