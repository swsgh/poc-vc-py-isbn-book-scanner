# ISBN Book Scanner (Python)

A PySide6 desktop app for scanning ISBN barcodes, looking up book details, and maintaining a local bookshelf.

## Features

- Open the scanner view to start the OpenCV camera worker; hiding the view stops capture. The camera uses device index 0.
- Use manual entry when a camera is unavailable. Input accepts 10- or 13-digit ISBNs, with hyphens allowed.
- Look up metadata through Open Library, with Google Books as a fallback.
- Browse, search, inspect, and remove books in the local library.
- Export the library as CSV or Excel (`.xlsx`).
- Store book metadata and cover images in SQLite.

The app can synchronize with the companion FastAPI server project. Local changes are queued while offline and retried the next time synchronization runs.

## Requirements and setup

Use Python 3.10 or newer. Create and activate a virtual environment from this directory:

```sh
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux or macOS:

```sh
source .venv/bin/activate
```

Install the runtime dependencies:

```sh
python -m pip install -r requirements.txt
```

`pyzbar` may require the ZBar native library on your platform.

Run the application from this directory:

```sh
python main.py
```

The SQLite database is shared by both clients. On Windows its path is `%APPDATA%\Bookshelf\ISBNBookScanner\bookshelf.db`. On Linux it is `~/.local/share/Bookshelf/ISBNBookScanner/bookshelf.db`, or `$XDG_DATA_HOME/Bookshelf/ISBNBookScanner/bookshelf.db` when `XDG_DATA_HOME` is set. Both apps use the same schema: `books(isbn, title, authors, engine_source, cover_url)`, `sync_queue(isbn, action_type)` with one pending action per ISBN, and `sync_state(username, checkpoint)`. Cover images are downloaded into the per-user Qt cache and can be removed independently of the database. This schema change does not migrate old BLOB databases; delete the old client database before running either app. Metadata lookups require an internet connection. Without a working camera, use the manual ISBN field.

## Synchronization

Start the companion `poc-vc-py-bookshelf-sync-server` using its README instructions. Register and Log In prompt for the server URL as well as account credentials; the URL is saved in system settings and shared with the Qt app. `BOOKSHELF_SYNC_URL` overrides the saved URL/default (`http://127.0.0.1:8000`). Use an `http://` or `https://` URL. For HTTPS, use a certificate trusted by the operating system/Python CA bundle; certificate verification remains enabled. The Compose server itself uses HTTP, so HTTPS requires a TLS-terminating proxy or HTTPS-enabled hosting in front of it.

Open the settings menu to register an account or log in, then choose **Sync Now**. Registration creates the account and signs in. On the first sync for an account, server books are downloaded and local books unknown to that account are uploaded. Later syncs exchange changes and deletions. Local additions and removals are queued; authenticated local changes sync automatically, while queued work can be retried with **Sync Now** after reconnecting. Use **Log Out of Sync** to clear the in-memory session.

The app keeps the authentication token in memory and stores per-account sync checkpoints and pending local actions in `bookshelf.db`. The companion server currently has a development JWT secret and should only be used in a trusted environment until configured securely.
