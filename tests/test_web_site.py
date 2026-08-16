import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from tools.build_web import ROOT, api_origin, build


class SiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.hrefs = []
        self.scripts = []
        self.images = []
        self.inline_handlers = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a" and values.get("href"):
            self.hrefs.append(values["href"])
        if tag == "script":
            self.scripts.append(values.get("src"))
        if tag == "img":
            self.images.append((values.get("src"), values.get("alt")))
        self.inline_handlers.extend(name for name, _ in attrs
                                    if name.lower().startswith("on"))


class TestPublicWebsite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "build").mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=ROOT / "build")
        cls.site = build(Path(cls.tmp.name) / "site")
        cls.html = (cls.site / "index.html").read_text(encoding="utf-8")
        cls.parser = SiteParser()
        cls.parser.feed(cls.html)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_build_contains_required_public_files(self):
        required = {
            "index.html", "404.html", "styles.css", "app.js", "robots.txt",
            "beta.js", "runtime-config.js", "site.webmanifest", ".nojekyll",
            "sitemap.xml",
            "data/EVALUATION_RESULTS.json", "data/PREREGISTRATION.json",
            "data/flagship-state.json", "data/flagship-events.jsonl",
            "data/flagship-dossier.md", "data/flagship-timeline.md",
        }
        self.assertTrue(required.issubset({str(p.relative_to(self.site))
                                          for p in self.site.rglob("*")
                                          if p.is_file()}))

    def test_all_page_anchors_resolve(self):
        missing = [href for href in self.parser.hrefs
                   if href.startswith("#") and href[1:] not in self.parser.ids]
        self.assertEqual([], missing)

    def test_local_links_resolve_in_built_site(self):
        for href in self.parser.hrefs:
            if href.startswith(("#", "http://", "https://", "mailto:")):
                continue
            self.assertTrue((self.site / href).is_file(), href)

    def test_no_inline_script_or_event_handlers(self):
        self.assertEqual(["app.js", "runtime-config.js", "beta.js"],
                         self.parser.scripts)
        self.assertEqual([], self.parser.inline_handlers)

    def test_images_have_alt_text_and_are_local(self):
        self.assertTrue(self.parser.images)
        for source, alt in self.parser.images:
            self.assertIsNotNone(alt)
            self.assertFalse(source.startswith(("http://", "https://")))
            self.assertTrue((self.site / source).is_file())

    def test_site_has_no_remote_runtime_assets(self):
        css = (self.site / "styles.css").read_text(encoding="utf-8")
        js = "\n".join((self.site / name).read_text(encoding="utf-8")
                       for name in ("app.js", "runtime-config.js", "beta.js"))
        self.assertNotIn("@import url", css)
        self.assertNotIn("http://", css + js)
        self.assertNotIn("https://", css + js)
        self.assertNotIn("sk-ant-", js)

    def test_public_claims_match_machine_readable_evaluation(self):
        evaluation = json.loads(
            (self.site / "data/EVALUATION_RESULTS.json").read_text())
        origin = evaluation["workflows"]["origin_full"]
        self.assertEqual(6, origin["experiments"])
        self.assertEqual(3, origin["replications"])
        self.assertEqual(2, origin["scoped_conclusions"])
        self.assertEqual([], origin["incorrect_candidates_reported_as_winners"])
        for expected in ("CI", "research modes", "General public-web research",
                         "Zero runtime dependencies"):
            self.assertIn(expected, self.html)

    def test_research_workspace_has_guided_followups_and_live_evidence(self):
        for expected in (
            'data-intake-step="1"', 'data-intake-step="2"',
            'data-intake-step="3"', 'name="goal"', 'name="timeframe"',
            'name="scope"', 'name="priority"', 'data-research-brief',
            'data-beta-activity', 'data-beta-calls', 'data-beta-searches',
            'data-beta-input', 'data-beta-output', 'data-dossier-view',
            'No simulated updates', 'General public-web research',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.html)
        self.assertEqual(3, self.html.count('class="intake-step"'))
        self.assertEqual(4, self.html.count("data-live-stage="))

    def test_research_workspace_does_not_persist_secrets_or_render_raw_html(self):
        javascript = (self.site / "beta.js").read_text(encoding="utf-8")
        for forbidden in ("localStorage", "sessionStorage", ".innerHTML",
                          "insertAdjacentHTML", "document.write", "setInterval"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, javascript)
        for required in ("replaceChildren", "textContent", "aria-busy",
                         "provider_calls_used", "web_searches_used",
                         "input_tokens", "output_tokens", "referrerPolicy"):
            with self.subTest(required=required):
                self.assertIn(required, javascript)
        app_javascript = (self.site / "app.js").read_text(encoding="utf-8")
        self.assertIn("restoreHashPosition", app_javascript)
        self.assertIn('scrollIntoView({block: "start"})', app_javascript)

    def test_build_metadata_names_exact_evidence_sources(self):
        meta = json.loads((self.site / "build-meta.json").read_text())
        self.assertEqual("2.1.2", meta["release"])
        self.assertEqual(6, len(meta["evidence_files"]))
        self.assertEqual("versioned repository artifacts", meta["claims_source"])
        self.assertFalse(meta["interactive_beta_connected"])

    def test_beta_api_configuration_requires_bare_https_origin(self):
        self.assertEqual("https://beta.example.test",
                         api_origin("https://beta.example.test/"))
        for bad in ("http://beta.example.test", "https://beta.example.test/path",
                    "javascript:alert(1)", "//beta.example.test"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                api_origin(bad)


if __name__ == "__main__":
    unittest.main()
