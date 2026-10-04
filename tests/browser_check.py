"""Real-browser acceptance check. Uses an isolated database, never user data."""
import json
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import make_server
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "test-results"
RESULTS.mkdir(exist_ok=True)


def run():
    with tempfile.TemporaryDirectory() as tmp:
        server = make_server(Path(tmp) / "browser.sqlite3", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(viewport={"width":1440,"height":1000}, locale="zh-CN")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator("#stat-directory")).to_have_text("300")
                expect(page.locator("#stat-apps")).to_have_text("0")
                page.screenshot(path=str(RESULTS / "empty-desktop.png"), full_page=True, animations="disabled")
                page.get_by_role("button", name="公司名录").click()
                expect(page.locator(".company-row")).to_have_count(300)
                page.locator("#category").select_option("AI / Machine Learning")
                page.locator("#company-search").fill("英伟达")
                expect(page.locator("#category")).to_have_value("")
                expect(page.locator("#category")).to_be_disabled()
                expect(page.locator("#records-title")).to_have_text("NVIDIA")
                expect(page.locator("#record-list")).to_contain_text("尚未申请该公司")
                page.locator("#record-list .empty-add").click()
                expect(page.locator("#company-input")).to_have_value("NVIDIA")
                page.locator("#title-input").fill("Machine Learning Engineer")
                page.locator("#url-input").fill("https://example.com/jobs/ml?team=robotics&location=us")
                page.locator("#date-input").fill("2026-10-01")
                page.locator("#save-button").click()
                expect(page.locator("#application-dialog")).not_to_be_visible()
                expect(page.locator("#stat-apps")).to_have_text("1")

                # Duplicate warning and explicit override.
                page.locator("#add-open").click()
                page.locator("#company-input").fill("  nvidia  ")
                page.locator("#title-input").fill("machine learning engineer")
                page.locator("#save-button").click()
                expect(page.locator("#duplicate-box")).to_be_visible()
                expect(page.locator("#stat-apps")).to_have_text("1")
                page.locator("#allow-duplicate").check()
                page.locator("#save-button").click()
                expect(page.locator("#application-dialog")).not_to_be_visible()
                expect(page.locator("#stat-apps")).to_have_text("2")

                # Edit, optional URL, custom company, and inert HTML text.
                page.locator("[data-edit]").first.click()
                page.locator("#title-input").fill("Robotics Software Engineer")
                page.locator("#save-button").click()
                expect(page.locator("#application-dialog")).not_to_be_visible()
                page.locator("#add-open").click()
                page.locator("#company-input").fill("My Startup <test>")
                page.locator("#title-input").fill("Research Engineer <img src=x onerror=alert(1)>")
                page.locator("#save-button").click()
                expect(page.locator("#application-dialog")).not_to_be_visible()
                expect(page.locator("#stat-apps")).to_have_text("3")
                expect(page.locator("#record-list img")).to_have_count(0)
                page.locator("#company-search").fill("英伟达")
                expect(page.locator(".record-card")).to_have_count(2)
                page.locator("#role-search").fill("robotics")
                expect(page.locator(".record-card")).to_have_count(1)
                page.locator("#role-search").fill("nonexistent-role")
                expect(page.locator("#record-list")).to_contain_text("没有匹配的岗位记录")
                page.locator("#role-search").fill("")
                page.locator("#company-search").fill("No Such Company")
                expect(page.locator("#record-list")).to_contain_text("尚未申请该公司")
                page.locator("#nav-apps").click()
                expect(page.locator(".record-card")).to_have_count(3)
                page.reload()
                expect(page.locator("#stat-apps")).to_have_text("3")

                # Download actual backup, delete a record, then restore it from the file.
                page.locator("#backup-open").click()
                with page.expect_download() as download:
                    page.locator("#export-link").click()
                backup = Path(tmp) / "backup.json"
                download.value.save_as(backup)
                assert len(json.loads(backup.read_text(encoding="utf-8"))["applications"]) == 3
                page.locator("#backup-dialog .close-dialog").click()
                page.locator("[data-delete]").first.click()
                page.locator("#delete-dialog .secondary").click()
                expect(page.locator("#stat-apps")).to_have_text("3")
                page.locator("[data-delete]").first.click()
                page.locator("#delete-confirm").click()
                expect(page.locator("#stat-apps")).to_have_text("2")
                page.locator("#backup-open").click()
                page.locator("#restore-file").set_input_files(backup)
                expect(page.locator("#restore-preview")).to_be_visible()
                page.locator("#restore-confirm").click()
                expect(page.locator("#restore-result")).to_contain_text("新增 1 条，跳过 2 条")
                expect(page.locator("#stat-apps")).to_have_text("3")
                page.locator("#restore-file").set_input_files({"name":"bad.json","mimeType":"application/json","buffer":b"not JSON"})
                expect(page.locator("#restore-result")).to_contain_text("不是有效的 JSON")
                page.locator("#backup-dialog .close-dialog").click()
                page.locator("#company-search").fill("NVIDIA")
                page.screenshot(path=str(RESULTS / "records-desktop.png"), full_page=True, animations="disabled")
                page.locator("#add-open").click()
                page.screenshot(path=str(RESULTS / "form-desktop.png"), full_page=True, animations="disabled")
                page.locator("#application-dialog .close-dialog").first.click()

                page.set_viewport_size({"width":390,"height":844})
                page.screenshot(path=str(RESULTS / "records-mobile.png"), full_page=True, animations="disabled")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal overflow"
                page.locator("#backup-quick").click()
                expect(page.locator("#backup-dialog")).to_be_visible()
                page.locator("#backup-dialog .close-dialog").click()
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()
    print("PASS: browser CRUD, alias search, duplicate override, optional URL, XSS text, persistence, backup download/restore, invalid import, responsive layout. No JavaScript errors.")


if __name__ == "__main__":
    run()
