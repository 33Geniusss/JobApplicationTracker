import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

from app import Conflict, Store, make_server, display_status


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def record(self, **changes):
        return {"company": "NVIDIA", "title": "ML Engineer", "url": "", "applied_date": "2026-10-03", **changes}

    def test_presets_are_not_applications(self):
        state = self.store.snapshot()
        self.assertEqual(len(state["companies"]), 300)
        self.assertEqual(state["applications"], [])
        self.assertTrue(all(c["count"] == 0 for c in state["companies"]))
        identifiers = []
        for c in state["companies"]:
            identifiers.extend([c["normalized"], *[a.casefold() for a in c["aliases"]]])
        self.assertEqual(len(identifiers), len(set(identifiers)), "Canonical names and aliases must not collide")

    def test_aliases_case_whitespace_and_persistence(self):
        self.store.save(self.record(company="  英伟达  "))
        self.store.save(self.record(company="ｎｖｉｄｉａ", title="Robotics Engineer"))
        state = Store(self.path).snapshot()
        applied = [c for c in state["companies"] if c["count"]]
        self.assertEqual([(c["name"], c["count"]) for c in applied], [("NVIDIA", 2)])

    def test_duplicates_need_explicit_override_and_edit_excludes_self(self):
        ident = self.store.save(self.record())["id"]
        with self.assertRaises(Conflict):
            self.store.save(self.record(company="nvidia", title="  ml   engineer "))
        self.store.save(self.record(), ident)
        self.store.save(self.record(allow_duplicate=True))
        self.assertEqual(len(self.store.snapshot()["applications"]), 2)

    def test_custom_company_edit_delete(self):
        ident = self.store.save(self.record(company="My New Startup"))["id"]
        self.store.save(self.record(company="Another Startup", title="Research Scientist", url="https://example.org/job?id=42"), ident)
        app = self.store.snapshot()["applications"][0]
        self.assertEqual(app["company"], "Another Startup")
        self.assertEqual(app["title"], "Research Scientist")
        self.store.delete(ident)
        self.assertEqual(self.store.snapshot()["applications"], [])
        with self.assertRaises(LookupError):
            self.store.delete(ident)

    def test_invalid_input_never_creates_a_company(self):
        for changes in [{"company":"  "}, {"title":""}, {"url":"javascript:alert(1)"}, {"url":"file:///tmp/x"}, {"url":"https://"}, {"applied_date":"2026-02-30"}, {"title":5}, {"company":"x"*161}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.store.save(self.record(**changes))
        self.assertEqual(len(self.store.snapshot()["companies"]), 300)

    def test_backup_round_trip_and_idempotence(self):
        self.store.save(self.record(company="A Small Startup", url="https://example.com/1"))
        self.store.save(self.record(title="Robotics Engineer"))
        backup = self.store.export()
        other = Store(Path(self.temp.name) / "restored.sqlite3")
        self.assertEqual(other.restore(backup), {"added":2,"skipped":0})
        self.assertEqual(other.restore(backup), {"added":0,"skipped":2})
        self.assertEqual(other.export()["applications"], backup["applications"])

    def test_backup_is_atomic_on_bad_record(self):
        self.store.save(self.record())
        backup = self.store.export()
        first = copy.deepcopy(backup["applications"][0])
        first.update(id=str(uuid.uuid4()), company="Must Roll Back")
        bad = {**first, "id":str(uuid.uuid4()), "url":"javascript:alert(1)"}
        backup["applications"] = [first, bad]
        with self.assertRaises(ValueError):
            self.store.restore(backup)
        self.assertEqual(len(self.store.snapshot()["applications"]), 1)
        self.assertFalse(any(c["name"] == "Must Roll Back" for c in self.store.snapshot()["companies"]))

    def test_modified_record_conflict_does_not_overwrite(self):
        ident = self.store.save(self.record())["id"]
        backup = self.store.export()
        self.store.save(self.record(title="Updated Title"), ident)
        with self.assertRaises(Conflict):
            self.store.restore(backup)
        self.assertEqual(self.store.snapshot()["applications"][0]["title"], "Updated Title")

    def test_status_default_and_strict_thirty_day_boundary(self):
        ident = self.store.save(self.record(applied_date="2026-09-03"))["id"]
        on_day_30 = self.store.snapshot(today=dt.date(2026, 10, 3))["applications"][0]
        self.assertEqual(on_day_30["status"], "reviewing")
        self.assertEqual(on_day_30["display_status"], "reviewing")
        self.assertEqual(self.store.snapshot(today=dt.date(2026, 10, 4))["applications"][0]["display_status"], "long reviewing")
        for status in ("refused", "accepted"):
            self.store.set_status(ident, {"status":status})
            self.assertEqual(Store(self.path).snapshot(today=dt.date(2030, 1, 1))["applications"][0]["display_status"], status)
        self.store.set_status(ident, {"status":"reviewing"})
        self.assertEqual(self.store.snapshot(today=dt.date(2026, 10, 4))["applications"][0]["display_status"], "long reviewing")
        self.assertEqual(display_status("reviewing", "2027-01-01", dt.date(2026, 10, 3)), "reviewing")

    def test_edit_preserves_status_and_recomputes_age(self):
        ident = self.store.save(self.record(status="accepted"))["id"]
        self.store.save(self.record(title="Edited"), ident)
        self.assertEqual(self.store.snapshot()["applications"][0]["status"], "accepted")
        self.store.save(self.record(applied_date="2026-01-01", status="reviewing"), ident)
        self.assertEqual(self.store.snapshot(today=dt.date(2026, 10, 3))["applications"][0]["display_status"], "long reviewing")

    def test_legacy_database_migration_preserves_records(self):
        self.store.save(self.record())
        with self.store.connect() as db:
            db.execute("ALTER TABLE applications DROP COLUMN status")
            before = [tuple(row) for row in db.execute("SELECT * FROM applications")]
        migrated = Store(self.path)
        with migrated.connect() as db:
            after = [tuple(row) for row in db.execute("SELECT id,company_id,title,title_key,url,applied_date,created_at FROM applications")]
        self.assertEqual(before, after)
        self.assertEqual(migrated.snapshot()["applications"][0]["status"], "reviewing")
        self.assertEqual(len(Store(self.path).snapshot()["applications"]), 1)

    def test_status_backup_roundtrip_and_legacy_compatibility(self):
        ident = self.store.save(self.record(status="accepted"))["id"]
        backup = self.store.export()
        self.assertEqual(backup["version"], 2)
        other = Store(Path(self.temp.name) / "status-backup.sqlite3")
        other.restore(backup)
        self.assertEqual(other.snapshot()["applications"][0]["status"], "accepted")
        legacy = copy.deepcopy(backup)
        legacy["version"] = 1
        del legacy["applications"][0]["status"]
        self.assertEqual(self.store.restore(legacy), {"added":0,"skipped":1})
        self.assertEqual(self.store.snapshot()["applications"][0]["status"], "accepted")
        other.delete(ident)
        other.restore(legacy)
        self.assertEqual(other.snapshot()["applications"][0]["status"], "reviewing")
        self.store.set_status(ident, {"status":"refused"})
        with self.assertRaises(Conflict):
            self.store.restore(backup)
        self.assertEqual(self.store.snapshot()["applications"][0]["status"], "refused")

    def test_invalid_status_rejected_without_changes(self):
        ident = self.store.save(self.record())["id"]
        for status in ("long reviewing", "unknown", "", None, []):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.store.set_status(ident, {"status":status})
        with self.assertRaises(ValueError):
            self.store.save(self.record(company="Invalid Status Startup", status="unknown"))
        self.assertEqual(len(self.store.snapshot()["companies"]), 300)
        backup = self.store.export()
        backup["applications"][0]["status"] = "unknown"
        with self.assertRaises(ValueError):
            self.store.restore(backup)
        self.assertEqual(self.store.snapshot()["applications"][0]["status"], "reviewing")


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = make_server(Path(cls.temp.name) / "http.sqlite3", 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, method="GET", data=None, **headers):
        req = Request(self.base + path, data=None if data is None else json.dumps(data).encode(), method=method, headers=headers)
        return urlopen(req)

    def test_local_api_and_mutation_protection(self):
        with self.request("/api/state") as response:
            token = json.load(response)["token"]
        record = {"company":"NVIDIA", "title":"HTTP Test"}
        with self.assertRaises(HTTPError) as denied:
            self.request("/api/applications", "POST", record)
        self.assertEqual(denied.exception.code, 403)
        with self.assertRaises(HTTPError) as denied:
            self.request("/api/applications", "POST", record, **{"X-CSRF-Token":token, "Origin":"https://example.com"})
        self.assertEqual(denied.exception.code, 403)
        with self.request("/api/applications", "POST", record, **{"X-CSRF-Token":token}) as response:
            self.assertEqual(response.status, 201)
            ident = json.load(response)["id"]
        with self.assertRaises(HTTPError) as denied:
            self.request("/api/applications/" + ident, "PATCH", {"status":"accepted"})
        self.assertEqual(denied.exception.code, 403)
        with self.request("/api/applications/" + ident, "PATCH", {"status":"accepted"}, **{"X-CSRF-Token":token}) as response:
            self.assertEqual(json.load(response)["status"], "accepted")
        with self.request("/api/applications/" + ident, "DELETE", **{"X-CSRF-Token":token}) as response:
            self.assertTrue(json.load(response)["deleted"])

    def test_host_guard_and_static_path_allowlist(self):
        with self.assertRaises(HTTPError) as denied:
            self.request("/api/state", Host="attacker.example")
        self.assertEqual(denied.exception.code, 403)
        with self.assertRaises(HTTPError) as denied:
            self.request("/../app.py")
        self.assertEqual(denied.exception.code, 404)
        with self.request("/") as response:
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            self.assertIn("投递簿", response.read().decode())

    def test_shutdown_requires_token_and_stops_server(self):
        server = make_server(Path(self.temp.name) / "shutdown.sqlite3", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/shutdown"
            with self.assertRaises(HTTPError) as denied:
                urlopen(Request(url, data=b"{}"))
            self.assertEqual(denied.exception.code, 403)
            with urlopen(Request(url, data=b"{}", headers={"X-CSRF-Token":server.token})) as response:
                self.assertTrue(json.load(response)["stopped"])
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        finally:
            server.shutdown(); server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
