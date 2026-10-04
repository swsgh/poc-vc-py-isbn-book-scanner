import json
from urllib.parse import quote, urlsplit

import requests
from PySide6.QtCore import QThread, Signal

import database as db
from cover_cache import download_cover


class ServerHealthCheckWorker(QThread):
    connection_checked = Signal(bool)

    def __init__(self, server_url):
        super().__init__()
        self.server_url = server_url.rstrip("/")

    def run(self):
        try:
            response = requests.get(f"{self.server_url}/health", timeout=(3, 5))
            connected = response.status_code == 200 and response.json().get("status") == "ok"
        except (requests.RequestException, ValueError, AttributeError):
            connected = False
        self.connection_checked.emit(connected)


class CoverDownloadWorker(QThread):
    cover_cached = Signal(str, bool)

    def __init__(self, isbn, cover_url):
        super().__init__()
        self.isbn = isbn
        self.cover_url = cover_url

    def run(self):
        self.cover_cached.emit(self.isbn, download_cover(self.isbn, self.cover_url))


class SyncWorker(QThread):
    auth_succeeded = Signal(str, str)
    auth_failed = Signal(str)
    sync_succeeded = Signal(list, list, int, int)
    sync_failed = Signal(str)

    def __init__(self, operation, server_url, username="", password="", token=""):
        super().__init__()
        self.operation = operation
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = token

    def stop(self):
        self.requestInterruption()

    def _check_interruption(self):
        if self.isInterruptionRequested():
            raise RuntimeError("Synchronization cancelled.")

    def run(self):
        session = requests.Session()
        session.verify = True
        try:
            self._validate_server_url()
            if self.operation in ("register", "login"):
                token = self._authenticate(session)
                self.auth_succeeded.emit(token, self.username)
                self.password = ""
            else:
                token = self.token

            downloaded, removed, uploaded, deleted = self._synchronize(session, token)
            self.sync_succeeded.emit(downloaded, removed, uploaded, deleted)
        except Exception as error:
            message = self._error_message(error)
            if self.operation in ("register", "login") and not self.token:
                self.auth_failed.emit(message)
            else:
                self.sync_failed.emit(message)
        finally:
            session.close()
            self.password = ""

    def _validate_server_url(self):
        parsed_url = urlsplit(self.server_url)
        if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.hostname:
            raise RuntimeError("Sync server URL must be an absolute http:// or https:// URL.")

    def _authenticate(self, session):
        self._check_interruption()
        if self.operation == "register":
            response = session.post(
                f"{self.server_url}/api/auth/register",
                json={"username": self.username, "password": self.password},
                timeout=(5, 20),
            )
            response.raise_for_status()

        self._check_interruption()
        response = session.post(
            f"{self.server_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=(5, 20),
        )
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            raise RuntimeError("The server login response did not include a token.")
        self.token = token
        return token

    def _synchronize(self, session, token):
        if not token:
            raise RuntimeError("Log in before synchronizing.")

        checkpoint = db.get_sync_checkpoint(self.username)
        is_initial_sync = checkpoint is None
        self._check_interruption()
        response = session.get(
            f"{self.server_url}/api/books/sync",
            params={"since": checkpoint or 0},
            headers={"Authorization": f"Bearer {token}"},
            timeout=(5, 30),
        )
        response.raise_for_status()
        payload = response.json()
        server_time = int(payload["serverTime"])
        updates = payload["updates"]
        if not isinstance(updates, list):
            raise RuntimeError("The server returned an invalid sync response.")

        pending = dict(db.get_pending_sync_actions())
        remote_isbns = set()
        downloaded = []
        removed = []

        for update in updates:
            self._check_interruption()
            isbn = update["isbn"]
            remote_isbns.add(isbn)
            if isbn in pending:
                continue

            if update.get("isDeleted", False):
                if not db.delete_book_by_isbn(isbn, queue_sync=False):
                    raise RuntimeError(f"Could not apply remote deletion for ISBN {isbn}.")
                removed.append(isbn)
                continue

            cover_url = update.get("coverUrl", "") or ""
            if cover_url:
                download_cover(isbn, cover_url)
            title = update.get("title", "")
            author = update.get("authors", "")
            engine_source = update.get("engineSource", "")
            if not db.save_book(
                isbn, title, author, cover_url,
                queue_sync=False, engine_source=engine_source,
            ):
                raise RuntimeError(f"Could not save the synchronized book {isbn} locally.")
            downloaded.append((isbn, title, author, cover_url))

        # The server timestamps records in whole seconds; retain a one-second overlap
        # so updates created during a sync are not skipped at the checkpoint boundary.
        db.set_sync_checkpoint(self.username, max(0, server_time - 1))

        queued_isbns = set(pending)
        uploaded = 0
        deleted = 0
        for isbn, action in pending.items():
            self._check_interruption()
            if action == "DELETE":
                result = session.delete(
                    f"{self.server_url}/api/books/delete/{quote(isbn, safe='')}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=(5, 20),
                )
                if result.status_code != 404:
                    result.raise_for_status()
                db.remove_pending_sync_action(isbn, action)
                deleted += 1
            elif action == "UPLOAD":
                book = db.get_book_by_isbn(isbn)
                if book is None:
                    db.remove_pending_sync_action(isbn, action)
                    continue
                self._upload_book(session, token, book)
                db.remove_pending_sync_action(isbn, action)
                uploaded += 1

        if is_initial_sync:
            for book in db.get_all_books():
                self._check_interruption()
                isbn = book[0]
                if isbn not in remote_isbns and isbn not in queued_isbns:
                    self._upload_book(session, token, book)
                    uploaded += 1

        return downloaded, removed, uploaded, deleted

    def _upload_book(self, session, token, book):
        self._check_interruption()
        isbn, title, author, engine_source, cover_url = book
        metadata = json.dumps({
            "isbn": isbn,
            "title": title,
            "authors": author,
            "engineSource": engine_source or "Python ISBN Scanner",
            "coverUrl": cover_url or "",
        })
        response = session.post(
            f"{self.server_url}/api/books/upload",
            data={"metadata": metadata},
            headers={"Authorization": f"Bearer {token}"},
            timeout=(5, 30),
        )
        response.raise_for_status()

    @staticmethod
    def _error_message(error):
        response = getattr(error, "response", None)
        if response is not None:
            try:
                detail = response.json().get("detail")
                if detail:
                    return str(detail)
            except (ValueError, AttributeError):
                pass
        return str(error)
