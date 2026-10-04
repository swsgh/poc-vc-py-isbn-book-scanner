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


def download_cover(isbn: str, url: str) -> bool:
    try:
        parsed_url = urlsplit(url)
        if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.hostname:
            return False

        response = requests.get(url, timeout=(5, 15))
        response.raise_for_status()
        final_url = urlsplit(response.url)
        if parsed_url.scheme.lower() == "https" and final_url.scheme.lower() != "https":
            return False
        if not response.content or QImage.fromData(response.content).isNull():
            return False

        destination = QSaveFile(str(cover_path(isbn)))
        if not destination.open(QIODevice.WriteOnly):
            return False
        if destination.write(response.content) != len(response.content):
            destination.cancelWriting()
            return False
        return destination.commit()
    except (requests.RequestException, ValueError):
        return False


def remove_cached_cover(isbn: str):
    cover_path(isbn).unlink(missing_ok=True)
