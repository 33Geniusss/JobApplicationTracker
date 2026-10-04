import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest

from localization import english

ROOT = Path(__file__).resolve().parents[1]
HAN = re.compile(r"[\u3400-\u9fff]")


class StaticStrings(HTMLParser):
    def __init__(self):
        super().__init__()
        self.strings = []

    def handle_data(self, text):
        if HAN.search(text):
            self.strings.append(text.strip())

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("placeholder", "aria-label", "title") and value and HAN.search(value):
                self.strings.append(value)


class LocalizationTests(unittest.TestCase):
    def test_language_resources_cover_static_and_dynamic_strings(self):
        en = json.loads((ROOT / "static/locales/en.json").read_text(encoding="utf-8"))
        zh = json.loads((ROOT / "static/locales/zh.json").read_text(encoding="utf-8"))
        self.assertEqual(set(en), set(zh))
        parser = StaticStrings()
        parser.feed((ROOT / "static/index.html").read_text(encoding="utf-8"))
        for message in parser.strings:
            self.assertIn(message, en)
        source = (ROOT / "static/app.js").read_text(encoding="utf-8")
        for match in re.finditer(r'''\bt\(((?:"(?:[^"\\]|\\.)*")|(?:'(?:[^'\\]|\\.)*'))''', source):
            self.assertIn(ast.literal_eval(match.group(1)), en)
        for key, value in en.items():
            self.assertFalse(HAN.search(value), key)
            self.assertEqual(set(re.findall(r"\{\w+\}", key)), set(re.findall(r"\{\w+\}", value)), key)

    def test_server_validation_translations(self):
        self.assertEqual(english("公司名称不能超过 160 个字符"), "Company name must not exceed 160 characters")
        self.assertEqual(english("请填写岗位名称"), "Please enter Job title")
        self.assertEqual(english("岗位网址必须是文字"), "Job URL must be text")
        self.assertEqual(english("这条记录已不存在"), "This record no longer exists")

    def test_catalog_has_english_counterparts(self):
        data = json.loads((ROOT / "companies.json").read_text(encoding="utf-8"))
        self.assertFalse(HAN.search(data["scope_en"]))
        for company in data["companies"]:
            self.assertEqual(company["category_en"], english(company["category"]))
            self.assertEqual(company["provenance_en"], english(company["provenance"]))
        self.assertEqual(len(data["companies"]), 300)


if __name__ == "__main__":
    unittest.main()
