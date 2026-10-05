# ISBN Book Scanner (Python/PySide6/Qt)

A PySide6 desktop app for scanning ISBN barcodes, looking up book details, and maintaining a local bookshelf.

## Features

- Open the scanner view to start the OpenCV camera worker; hiding the view stops capture. The camera uses device index 0.
- Use manual entry when a camera is unavailable. Input accepts 10- or 13-digit ISBNs, with hyphens allowed.
- Send scanned or manually entered ISBNs to the authenticated sync server for metadata lookup.
- Browse, search, inspect, and remove books in the local library.
- Import and export the library as CSV from the cogwheel menu.
- Store server-returned book metadata and cover URLs in SQLite; download the server-cached covers into the local image cache.

The app uses the companion FastAPI server for ISBN lookup and synchronization. Local changes are queued while offline and retried the next time synchronization runs. Sign in before scanning or submitting a manual ISBN.

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

### Local data

The SQLite database is shared by both scanner clients.

| Platform | Database path |
| --- | --- |
| Windows | `%APPDATA%\Bookshelf\ISBNBookScanner\bookshelf.db` |
| Linux default | `~/.local/share/Bookshelf/ISBNBookScanner/bookshelf.db` |
| Linux with `XDG_DATA_HOME` | `$XDG_DATA_HOME/Bookshelf/ISBNBookScanner/bookshelf.db` |

Both apps use the same schema:

| Table | Columns and behavior |
| --- | --- |
| `books` | `isbn`, `title`, `authors`, `cover_url`, `publication_date`, `publisher`, `page_count` |
| `sync_queue` | `isbn`, `action_type`; one pending action per ISBN |
| `sync_state` | `username`, `checkpoint` |

### Cover cache

Cover images are cached in `QStandardPaths::CacheLocation/covers`.

| Platform | Cache path |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Bookshelf\ISBNBookScanner\cache\covers` |
| Linux default | `~/.cache/Bookshelf/ISBNBookScanner/covers` |
| Linux with `XDG_CACHE_HOME` | `$XDG_CACHE_HOME/Bookshelf/ISBNBookScanner/covers` |

Each filename is the SHA-256 hash of its ISBN with an `.img` extension. The cache can be deleted at any time; images are downloaded again from their stored URLs.

### Database compatibility and connectivity

The updated schema does not migrate older client databases. Delete the old client database before running either app. ISBN lookup requires a connection to the authenticated sync server. Without a working camera, use the manual ISBN field.

## Synchronization

Start the companion `poc-vc-py-bookshelf-sync-server` using its README instructions.

### Server URL and security

Register and Log In prompt for the server URL as well as account credentials. The URL is saved in system settings and shared with the Qt app. `BOOKSHELF_SYNC_URL` overrides the saved URL/default (`http://127.0.0.1:8000`).

Use an `http://` or `https://` URL. For HTTPS, use a certificate trusted by the operating system/Python CA bundle; certificate verification remains enabled. The Compose server itself uses HTTP, so HTTPS requires a TLS-terminating proxy or HTTPS-enabled hosting in front of it.

### Sync behavior

1. Open the settings menu and register an account or log in. Registration creates the account and signs in.
2. On the first sync for an account, server books are downloaded and local books unknown to that account are uploaded.
3. Later syncs exchange changes and deletions. Local additions and removals are queued; authenticated local changes sync automatically.
4. After reconnecting, choose **Sync Now** to retry queued work. Choose **Log Out of Sync** to clear the in-memory session.

The app keeps the authentication token in memory and stores per-account sync checkpoints and pending local actions in `bookshelf.db`. The companion server currently has a development JWT secret and should only be used in a trusted environment until configured securely.

## CSV Import and Export

Use **Import CSV...** and **Export CSV...** in the cogwheel menu. CSV files must have the exact headers `ISBN`, `Title`, `Author`, `Cover URL`, `First Publication Date`, `Publisher`, and `Page Count`, in that order. Imported books are queued for synchronization.
