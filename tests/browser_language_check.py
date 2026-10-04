"""Exercise English UI, persisted language choice, and shared Chinese/English data."""
import json
from pathlib import Path
import re
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import make_server
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def run():
    with tempfile.TemporaryDirectory() as tmp:
        server = make_server(Path(tmp) / "languages.sqlite3", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(viewport={"width":1440,"height":1100}, locale="en-US")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                base = f"http://127.0.0.1:{server.server_port}"
                page.goto(base)
                expect(page.locator("#stat-directory")).to_have_text("300")
                page.locator("#language-toggle").click()
                expect(page.locator("html")).to_have_attribute("lang", "en-US")
                expect(page.locator("#add-open")).to_have_text("＋ Record application")
                expect(page.locator("#stat-directory")).to_have_text("300")
                assert not re.search(r"[\u3400-\u9fff]", page.locator("body").inner_text().replace("中文", ""))
                page.locator("#nav-directory").click()
                page.locator("#category").select_option(label="Chips / Hardware")
                page.locator("#company-search").fill("英伟达")
                expect(page.locator("#records-title")).to_have_text("NVIDIA")
                expect(page.locator("#record-list")).to_contain_text("No applications to this company yet")
                page.locator(".empty-add").click()
                expect(page.locator("#form-title")).to_have_text("Record application")
                page.locator("#title-input").fill(" ")
                page.locator("#save-button").click()
                expect(page.locator("#form-error")).to_have_text("Please enter Job title")
                page.locator("#title-input").fill("ML Engineer")
                page.screenshot(path=str(ROOT / "test-results/language-form-en.png"), full_page=True, animations="disabled")
                page.locator("#save-button").click()
                expect(page.locator("#stat-apps")).to_have_text("1")
                page.locator("[data-status]").select_option("accepted")
                expect(page.locator("[data-status]")).to_have_class("status-select status-accepted")
                page.locator("#add-open").click()
                page.locator("#title-input").fill("ML Engineer")
                page.locator("#save-button").click()
                expect(page.locator("#duplicate-box")).to_contain_text("You have recorded this role before")
                expect(page.locator("#duplicate-details")).to_contain_text("There is 1 record")
                page.locator("#application-dialog .close-dialog").first.click()
                page.locator("#company-search").fill("")
                page.screenshot(path=str(ROOT / "test-results/language-desktop-en.png"), full_page=True, animations="disabled")
                page.locator("#backup-open").click()
                with page.expect_download() as download:
                    page.locator("#export-link").click()
                backup = Path(tmp) / "backup.json"
                download.value.save_as(backup)
                page.locator("#restore-file").set_input_files(backup)
                expect(page.locator("#restore-summary")).to_contain_text("Contains 1 application")
                page.locator("#restore-confirm").click()
                expect(page.locator("#restore-result")).to_have_text("Restore complete: added 0, skipped 1 identical records.")
                page.locator("#restore-file").set_input_files({"name":"invalid.json","mimeType":"application/json","buffer":b"bad json"})
                expect(page.locator("#restore-result")).to_have_text("This file is not a valid JSON backup.")
                page.locator("#backup-dialog .close-dialog").click()
                # A fresh tab without ?lang preserves the preference.
                another = context.new_page()
                another.goto(base)
                expect(another.locator("html")).to_have_attribute("lang", "en-US")
                another.close()
                # Chinese input is kept verbatim while the interface language changes.
                page.locator("#add-open").click()
                page.locator("#company-input").fill("我的公司")
                page.locator("#title-input").fill("研究员")
                page.locator("#save-button").click()
                expect(page.locator("#stat-apps")).to_have_text("2")
                expect(page.locator("#record-list")).to_contain_text("研究员")
                page.locator("#language-toggle").click()
                expect(page.locator("html")).to_have_attribute("lang", "zh-CN")
                expect(page.locator("#stat-apps")).to_have_text("2")
                expect(page.locator("#record-list")).to_contain_text("研究员")
                expect(page.locator("[data-status]").last).to_have_value("accepted")
                page.locator("#language-toggle").click()
                expect(page.locator("html")).to_have_attribute("lang", "en-US")
                page.locator("#company-search").fill("NVIDIA")
                page.set_viewport_size({"width":390,"height":844})
                page.screenshot(path=str(ROOT / "test-results/language-mobile-en.png"), full_page=True, animations="disabled")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.locator("[data-delete]").click()
                expect(page.locator("#delete-dialog")).to_contain_text("Delete this application?")
                page.locator("#delete-confirm").click()
                expect(page.locator("#stat-apps")).to_have_text("1")
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()
    print("PASS: English search, form validation, CRUD, status, duplicates, backups, persisted language, bilingual data, responsive layout; no JavaScript errors.")


if __name__ == "__main__":
    (ROOT / "test-results").mkdir(exist_ok=True)
    run()
