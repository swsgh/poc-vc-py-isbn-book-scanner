import hashlib
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PySide6.QtCore import QIODevice, QSaveFile, QStandardPaths
from PySide6.QtGui import QImage


def cache_directory() -> Path:
    directory = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation)) / "covers"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def cover_path(isbn: str) -> Path:
    filename = hashlib.sha256(isbn.encode("utf-8")).hexdigest() + ".img"
    return cache_directory() / filename


def has_cached_cover(isbn: str) -> bool:
    return cover_path(isbn).is_file()


def is_server_cover_url(url: str, server_url: str) -> bool:
    try:
        parsed_url = urlsplit(url)
        parsed_server = urlsplit(server_url)
        url_port = parsed_url.port or (443 if parsed_url.scheme.lower() == "https" else 80)
        server_port = parsed_server.port or (443 if parsed_server.scheme.lower() == "https" else 80)
        return (
            parsed_url.scheme.lower() == parsed_server.scheme.lower()
            and parsed_url.hostname == parsed_server.hostname
            and url_port == server_port
            and parsed_url.path.startswith("/api/books/cover/")
        )
    except ValueError:
        return False


def server_cover_headers(url: str, server_url: str, token: str) -> dict[str, str]:
    if token and is_server_cover_url(url, server_url):
        return {"Authorization": f"Bearer {token}"}
    return {}


def download_cover(isbn: str, url: str, headers: dict[str, str] | None = None) -> bool:
    return download_cover_with_error(isbn, url, headers=headers)[0]


def download_cover_with_error(
    isbn: str, url: str, headers: dict[str, str] | None = None
) -> tuple[bool, str]:
    try:
        parsed_url = urlsplit(url)
        if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.hostname:
            return False, "Invalid cover image URL."

        response = requests.get(url, headers=headers, timeout=(5, 15))
        if response.status_code == 429:
            return False, "Cover image rate limit reached (HTTP 429). Try again shortly."
        if not response.ok:
            return False, f"Cover image request failed (HTTP {response.status_code})."
        response.raise_for_status()
        final_url = urlsplit(response.url)
        if parsed_url.scheme.lower() == "https" and final_url.scheme.lower() != "https":
            return False, "Cover image request redirected to an insecure URL."
        if not response.content or QImage.fromData(response.content).isNull():
            return False, "Cover image response was empty or invalid."

        destination = QSaveFile(str(cover_path(isbn)))
        if not destination.open(QIODevice.WriteOnly):
            return False, "Could not open the cover cache file for writing."
        if destination.write(response.content) != len(response.content):
            destination.cancelWriting()
            return False, "Could not write the cover image to the cache."
        if not destination.commit():
            return False, "Could not save the cover image to the cache."
        return True, ""
    except requests.Timeout:
        return False, "Cover image download timed out."
    except requests.RequestException as error:
        response = getattr(error, "response", None)
        if response is not None and response.status_code == 429:
            return False, "Cover image rate limit reached (HTTP 429). Try again shortly."
        if response is not None and response.status_code:
            return False, f"Cover image request failed (HTTP {response.status_code})."
        return False, f"Cover image download failed: {error}"
    except ValueError as error:
        return False, f"Invalid cover image URL: {error}"


def remove_cached_cover(isbn: str):
    cover_path(isbn).unlink(missing_ok=True)
