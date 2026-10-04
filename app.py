"""Local application notebook. Runtime dependencies: Python standard library only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import json
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import unicodedata
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
APP_ID = "local-job-application-tracker"


def checked_status(value):
    if not isinstance(value, str) or value not in ("reviewing", "refused", "accepted"):
        raise ValueError("状态须为 reviewing、refused 或 accepted；long reviewing 根据申请日期自动计算")
    return value


def display_status(status, applied_date, today=None):
    if status == "reviewing" and ((today or dt.date.today()) - dt.date.fromisoformat(applied_date)).days > 30:
        return "long reviewing"
    return status


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def clean(value, label, limit, required=True):
    if not isinstance(value, str):
        raise ValueError(f"{label}必须是文字")
    value = " ".join(value.split())
    if required and not value:
        raise ValueError(f"请填写{label}")
    if len(value) > limit:
        raise ValueError(f"{label}不能超过 {limit} 个字符")
    return value


def fields(data):
    if not isinstance(data, dict):
        raise ValueError("记录格式不正确")
    company = clean(data.get("company", ""), "公司名称", 160)
    title = clean(data.get("title", ""), "岗位名称", 240)
    url = clean(data.get("url", ""), "岗位网址", 2048, False)
    if url:
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError()
            _ = parsed.port
        except ValueError:
            raise ValueError("岗位网址须为完整的 http:// 或 https:// 链接") from None
    date = data.get("applied_date", dt.date.today().isoformat())
    if not isinstance(date, str):
        raise ValueError("申请日期格式不正确")
    try:
        if dt.date.fromisoformat(date).isoformat() != date:
            raise ValueError()
    except ValueError:
        raise ValueError("申请日期格式须为 YYYY-MM-DD") from None
    return company, title, url, date


class Conflict(Exception):
    def __init__(self, message, duplicates=None):
        super().__init__(message)
        self.duplicates = duplicates or []


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    normalized TEXT NOT NULL UNIQUE, category TEXT NOT NULL,
                    aliases TEXT NOT NULL DEFAULT '[]', source TEXT NOT NULL DEFAULT '',
                    preset INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
                    title TEXT NOT NULL, title_key TEXT NOT NULL, url TEXT NOT NULL,
                    applied_date TEXT NOT NULL, created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'reviewing' CHECK(status IN ('reviewing','refused','accepted'))
                );
                CREATE INDEX IF NOT EXISTS app_company ON applications(company_id);
            """)
            if "status" not in {row["name"] for row in db.execute("PRAGMA table_info(applications)")}:
                db.execute("ALTER TABLE applications ADD COLUMN status TEXT NOT NULL DEFAULT 'reviewing' CHECK(status IN ('reviewing','refused','accepted'))")
            seed = json.loads((ROOT / "companies.json").read_text(encoding="utf-8"))
            for c in seed["companies"]:
                db.execute("INSERT OR IGNORE INTO companies(name,normalized,category,aliases,source,preset) VALUES(?,?,?,?,?,1)",
                           (c["name"], normalize(c["name"]), c["category"], json.dumps(c.get("aliases", []), ensure_ascii=False), c.get("source", "")))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def resolve(self, db, name):
        key = normalize(name)
        for c in db.execute("SELECT * FROM companies"):
            if key == c["normalized"] or key in [normalize(a) for a in json.loads(c["aliases"])]:
                return c["id"]
        return db.execute("INSERT INTO companies(name,normalized,category) VALUES(?,?,?)", (name, key, "自定义公司")).lastrowid

    def snapshot(self, today=None):
        with self.connect() as db:
            # A read transaction keeps company counts and records in the same snapshot.
            db.execute("BEGIN")
            companies = [dict(c) for c in db.execute("SELECT c.*,COUNT(a.id) AS count FROM companies c LEFT JOIN applications a ON a.company_id=c.id GROUP BY c.id ORDER BY c.name COLLATE NOCASE")]
            for c in companies:
                c["aliases"] = json.loads(c["aliases"])
            applications = [dict(a) for a in db.execute("SELECT a.*, c.name AS company FROM applications a JOIN companies c ON c.id=a.company_id ORDER BY applied_date DESC,created_at DESC,id")]
            for a in applications:
                a["display_status"] = display_status(a["status"], a["applied_date"], today)
            return {"companies": companies, "applications": applications}

    def save(self, data, app_id=None):
        company, title, url, date = fields(data)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone() if app_id else None
            if app_id and not old:
                raise LookupError("这条记录已不存在，请刷新页面")
            status = checked_status(data.get("status", old["status"] if old else "reviewing"))
            company_id = self.resolve(db, company)
            duplicates = [dict(a) for a in db.execute("SELECT id,title,url,applied_date FROM applications WHERE company_id=? AND title_key=? AND id!=?", (company_id, normalize(title), app_id or ""))]
            if duplicates and data.get("allow_duplicate") is not True:
                raise Conflict("该公司已有同名岗位的申请记录", duplicates)
            if app_id:
                db.execute("UPDATE applications SET company_id=?,title=?,title_key=?,url=?,applied_date=?,status=? WHERE id=?", (company_id, title, normalize(title), url, date, status, app_id))
            else:
                app_id = str(uuid.uuid4())
                db.execute("INSERT INTO applications(id,company_id,title,title_key,url,applied_date,created_at,status) VALUES(?,?,?,?,?,?,?,?)", (app_id, company_id, title, normalize(title), url, date, dt.datetime.now(dt.timezone.utc).isoformat(), status))
        return {"id": app_id}

    def set_status(self, app_id, data):
        if not isinstance(data, dict):
            raise ValueError("状态格式不正确")
        status = checked_status(data.get("status"))
        with self.connect() as db:
            if not db.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id)).rowcount:
                raise LookupError("这条记录已不存在，请刷新页面")
        return {"id": app_id, "status": status}

    def delete(self, app_id):
        with self.connect() as db:
            if not db.execute("DELETE FROM applications WHERE id=?", (app_id,)).rowcount:
                raise LookupError("这条记录已不存在")

    def export(self):
        state = self.snapshot()
        return {"format": APP_ID, "version": 2, "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "applications": [{k: a[k] for k in ("id", "company", "title", "url", "applied_date", "created_at", "status")} for a in state["applications"]]}

    def restore(self, data):
        if not isinstance(data, dict) or data.get("format") != APP_ID or data.get("version") not in (1, 2):
            raise ValueError("请选择本软件导出的 JSON 备份文件")
        records = data.get("applications")
        if not isinstance(records, list) or len(records) > 50000:
            raise ValueError("备份记录格式不正确或超过 50000 条")
        added = skipped = 0
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for a in records:
                company, title, url, date = fields(a)
                status = checked_status(a.get("status") if data["version"] == 2 else "reviewing")
                try:
                    app_id = str(uuid.UUID(a.get("id", "")))
                    created_at = a["created_at"]
                    if not isinstance(created_at, str) or len(created_at) > 50:
                        raise ValueError()
                    dt.datetime.fromisoformat(created_at)
                except (ValueError, TypeError, KeyError, AttributeError):
                    raise ValueError("备份内的记录编号或时间不正确，未导入任何记录") from None
                company_id = self.resolve(db, company)
                old = db.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
                if old:
                    if (old["company_id"], old["title"], old["url"], old["applied_date"], old["created_at"]) != (company_id, title, url, date, created_at):
                        raise Conflict("备份包含已被修改的同一条记录。为避免覆盖，整个导入已取消；请保留两份备份。")
                    if data["version"] == 2 and old["status"] != status:
                        raise Conflict("备份中的申请状态与当前记录冲突，整个导入已取消，当前状态已保留。")
                    skipped += 1
                    continue
                db.execute("INSERT INTO applications(id,company_id,title,title_key,url,applied_date,created_at,status) VALUES(?,?,?,?,?,?,?,?)", (app_id, company_id, title, normalize(title), url, date, created_at, status))
                added += 1
        return {"added": added, "skipped": skipped}


class Handler(BaseHTTPRequestHandler):
    server_version = "ApplicationNotebook/1.0"

    def send(self, status, value, content_type="application/json; charset=utf-8", extra=None):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8") if not isinstance(value, bytes) else value
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def allowed_host(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def do_GET(self):
        if not self.allowed_host():
            return self.send(403, {"error": "只允许本机访问"})
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self.send(200, {"app": APP_ID, "data_path": str(self.server.store.path.resolve())})
        if path == "/api/state":
            return self.send(200, {**self.server.store.snapshot(), "token": self.server.token})
        if path == "/api/backup":
            name = "applications-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
            return self.send(200, self.server.store.export(), extra={"Content-Disposition": f'attachment; filename="{name}"'})
        files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        if path in files:
            name, mime = files[path]
            return self.send(200, (ROOT / "static" / name).read_bytes(), mime)
        self.send(404, {"error": "页面不存在"})

    def mutate(self):
        if not self.allowed_host() or not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.token):
            return self.send(403, {"error": "页面已过期，请刷新后重试"})
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
            return self.send(403, {"error": "请求来源不正确"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 20 * 1024 * 1024:
                return self.send(413, {"error": "备份文件不能超过 20 MB"})
            raw = self.rfile.read(length)
            data = json.loads(raw) if raw else {}
            path = urlsplit(self.path).path
            if self.command == "POST" and path == "/api/applications":
                return self.send(201, self.server.store.save(data))
            if self.command == "POST" and path == "/api/restore":
                return self.send(200, self.server.store.restore(data))
            if self.command == "POST" and path == "/api/shutdown":
                self.send(200, {"stopped": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if path.startswith("/api/applications/"):
                app_id = path.rsplit("/", 1)[1]
                if self.command == "PUT":
                    return self.send(200, self.server.store.save(data, app_id))
                if self.command == "PATCH":
                    return self.send(200, self.server.store.set_status(app_id, data))
                if self.command == "DELETE":
                    self.server.store.delete(app_id)
                    return self.send(200, {"deleted": True})
            self.send(404, {"error": "操作不存在"})
        except Conflict as e:
            self.send(409, {"error": str(e), "duplicates": e.duplicates})
        except LookupError as e:
            self.send(404, {"error": str(e)})
        except (ValueError, UnicodeDecodeError) as e:
            self.send(400, {"error": str(e) if not isinstance(e, json.JSONDecodeError) else "JSON 文件格式不正确"})
        except sqlite3.Error:
            self.send(500, {"error": "保存失败，请检查数据文件权限和磁盘空间后重试"})

    do_POST = do_PUT = do_DELETE = do_PATCH = mutate


def make_server(path, port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.store = Store(path)
    server.token = secrets.token_hex(32)
    return server


def main():
    parser = argparse.ArgumentParser(description="Local job application notebook")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "applications.sqlite3")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--stop", action="store_true", help="Stop the local instance on the selected port")
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    if args.stop:
        from urllib.request import Request, urlopen
        try:
            with urlopen(url + "/api/health", timeout=2) as response:
                if json.load(response).get("app") != APP_ID:
                    raise ValueError("Different application on this port")
            with urlopen(url + "/api/state", timeout=2) as response:
                token = json.load(response)["token"]
            with urlopen(Request(url + "/api/shutdown", data=b"{}", headers={"X-CSRF-Token": token, "Content-Type": "application/json"}), timeout=3):
                pass
            print("Application stopped. Saved records are preserved.")
        except Exception as error:
            print("No running application found, or unable to stop: " + str(error))
        return
    try:
        server = make_server(args.data, args.port)
    except OSError:
        # Reopening the normal launcher reuses only a verified instance of this app.
        from urllib.request import urlopen
        try:
            with urlopen(url + "/api/health", timeout=2) as response:
                health = json.load(response)
                same_app = health.get("app") == APP_ID and health.get("data_path") == str(args.data.resolve())
        except Exception:
            same_app = False
        if same_app:
            if not args.no_browser:
                webbrowser.open(url)
            print("Application is already running: " + url)
            return
        print(f"Cannot start on port {args.port}. Try: python app.py --port {args.port + 1}")
        sys.exit(1)
    print(f"Application notebook: {url}\nDatabase: {args.data}\nPress Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
