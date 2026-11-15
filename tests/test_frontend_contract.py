"""Offline checks for the dashboard's HTML/JS contract, not a browser substitute."""
import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids = []
        self.assets = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "script" and attrs.get("src"):
            self.assets.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append(attrs["href"])


def missing_references(html, js):
    # Dynamic selectors for generated task rows are intentionally outside this contract.
    references = set(re.findall(r'\$\(\s*["\']([^"\']+)["\']\s*\)', js))
    references.update(re.findall(r'getElementById\(\s*["\']([^"\']+)["\']\s*\)', js))
    return references - set(Page(html).ids)


class FrontendContractTests(unittest.TestCase):
    def setUp(self):
        self.html = (PUBLIC / "index.html").read_text()
        self.js = (PUBLIC / "app.js").read_text()

    def test_every_literal_element_reference_exists(self):
        self.assertEqual(missing_references(self.html, self.js), set())

    def test_contract_detects_the_previous_missing_questions_markup(self):
        broken = self.html.replace('id="questions-card"', '').replace('id="questions"', '')
        self.assertEqual(missing_references(broken, self.js), {"questions-card", "questions"})

    def test_html_ids_are_unique(self):
        duplicates = {key for key, count in Counter(Page(self.html).ids).items() if count > 1}
        self.assertEqual(duplicates, set())

    def test_frontend_versions_match_the_cache(self):
        sw = (PUBLIC / "sw.js").read_text()
        version = re.search(r'CACHE_NAME\s*=\s*["\']between-v(\d+)["\']', sw)
        self.assertIsNotNone(version)
        assets = Page(self.html).assets
        self.assertEqual({urlparse(url).path for url in assets}, {"/app.js", "/styles.css"})
        for url in assets:
            with self.subTest(asset=url):
                self.assertEqual(parse_qs(urlparse(url).query).get("v"), [version.group(1)])

    def test_every_precached_asset_exists(self):
        sw = (PUBLIC / "sw.js").read_text()
        assets = re.search(r'const ASSETS\s*=\s*\[([^\]]+)\]', sw)
        self.assertIsNotNone(assets)
        for url in re.findall(r'["\']([^"\']+)["\']', assets.group(1)):
            with self.subTest(asset=url):
                path = urlparse(url).path
                self.assertTrue((PUBLIC / ("index.html" if path == "/" else path.lstrip("/"))).is_file())


if __name__ == "__main__":
    unittest.main()
