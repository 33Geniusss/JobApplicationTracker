"""Shared English translations for server validation and bundled catalog metadata."""
import json
from pathlib import Path
import re

ENGLISH = json.loads((Path(__file__).resolve().parent / "static" / "locales" / "en.json").read_text(encoding="utf-8"))


def english(message):
    if message in ENGLISH:
        return ENGLISH[message]
    for source in ("{label}必须是文字", "请填写{label}", "{label}不能超过 {limit} 个字符"):
        pattern = re.escape(source).replace(r"\{label\}", "(?P<label>.+?)").replace(r"\{limit\}", "(?P<limit>[0-9]+)")
        match = re.fullmatch(pattern, message)
        if match:
            params = match.groupdict()
            params["label"] = ENGLISH.get(params["label"], params["label"])
            return ENGLISH[source].format(**params)
    return message


def bilingual_catalog(catalog):
    """Add English counterparts without changing names, aliases, or Chinese fields."""
    catalog["scope_en"] = english(catalog["scope"])
    for company in catalog["companies"]:
        company["category_en"] = english(company["category"])
        company["provenance_en"] = english(company["provenance"])
    return catalog
