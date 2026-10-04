"""Status acceptance flow with simulated date rollover and isolated data."""
import datetime as dt
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Store, make_server
from playwright.sync_api import sync_playwright, expect


def run():
    output = Path(__file__).resolve().parents[1] / "test-results"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        server = make_server(Path(tmp) / "status.sqlite3", 0)
        simulated_today = [dt.date.today()]
        server.store.snapshot = lambda: Store.snapshot(server.store, today=simulated_today[0])
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width":1440,"height":1100})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                now = dt.datetime.now()
                page.clock.install(time=now)
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator("#stat-directory")).to_have_text("300")
                page.locator("#add-open").click()
                expect(page.locator("#status-input")).to_have_value("reviewing")
                page.locator("#company-input").fill("NVIDIA")
                page.locator("#title-input").fill("Machine Learning Engineer")
                page.locator("#date-input").fill((simulated_today[0] - dt.timedelta(days=30)).isoformat())
                page.locator("#save-button").click()
                select = page.locator("[data-status]")
                expect(select).to_have_class("status-select status-reviewing")
                # Leave the page open: status changes at day 31 without user refresh.
                simulated_today[0] += dt.timedelta(days=1)
                page.clock.set_system_time(now + dt.timedelta(days=1))
                page.clock.fast_forward(60001)
                expect(select).to_have_class("status-select status-long-reviewing")
                expect(select.locator("option:checked")).to_have_text("long reviewing")
                for status in ("refused", "accepted"):
                    select.select_option(status)
                    expect(select).to_have_class("status-select status-" + status)
                    page.reload()
                    expect(select).to_have_value(status)
                page.locator("[data-edit]").click()
                expect(page.locator("#status-input")).to_have_value("accepted")
                page.locator("#title-input").fill("Robotics Engineer")
                page.locator("#save-button").click()
                expect(page.locator("#application-dialog")).not_to_be_visible()
                expect(select).to_have_value("accepted")
                select.select_option("reviewing")
                expect(select).to_have_class("status-select status-long-reviewing")
                page.screenshot(path=str(output / "status-desktop.png"), full_page=True, animations="disabled")
                page.locator("[data-edit]").click()
                page.locator("#status-input").select_option("refused")
                page.screenshot(path=str(output / "status-form.png"), full_page=True, animations="disabled")
                page.locator("#save-button").click()
                expect(page.locator("#application-dialog")).not_to_be_visible()
                expect(select).to_have_value("refused")
                page.set_viewport_size({"width":390,"height":844})
                page.screenshot(path=str(output / "status-mobile.png"), full_page=True, animations="disabled")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()
    print("PASS: default reviewing, day 30/31 rollover on open page, refused/accepted persistence, edit status, reset automatic reviewing, responsive status controls.")


if __name__ == "__main__":
    run()
