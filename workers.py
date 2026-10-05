import sys
import time
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import requests
from cover_cache import download_cover_with_error

# Conditional compilation setup: only import desktop modules when not on Android
ON_ANDROID = (sys.platform == "android") or hasattr(sys, "getandroidsdk")

if not ON_ANDROID:
    import cv2
    from pyzbar.pyzbar import decode, ZBarSymbol


def _unique_cover_urls(urls):
    result = []
    for url in urls:
        if url:
            normalized = url.replace("http://", "https://", 1) if url.startswith("http://") else url
            if normalized not in result:
                result.append(normalized)
    return result


def _open_library_cover_urls(info):
    cover = info.get("cover", {})
    return _unique_cover_urls((cover.get(size) for size in ("large", "medium", "small")))


def _google_books_cover_urls(volume_info):
    image_links = volume_info.get("imageLinks", {})
    return _unique_cover_urls(
        image_links.get(size)
        for size in ("extraLarge", "large", "medium", "small", "thumbnail", "smallThumbnail")
    )


def _provider_http_error(provider, status_code, detail=""):
    if status_code == 429:
        return f"{provider} rate limit reached (HTTP 429). Try again shortly."
    if status_code in (401, 403):
        return f"{provider} rejected the request (HTTP {status_code}). Check API access settings."
    suffix = f": {detail}" if detail else ""
    return f"{provider} request failed (HTTP {status_code}){suffix}"


def _provider_request_error(provider, error):
    response = getattr(error, "response", None)
    if response is not None and response.status_code:
        return _provider_http_error(provider, response.status_code)
    if isinstance(error, requests.Timeout):
        return f"{provider} request timed out."
    return f"{provider} network request failed: {error}"


class CameraWorker(QThread):
    frame_received = Signal(QImage)
    barcode_detected = Signal(str)
    camera_unavailable = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.cap = None
        self.last_scanned_barcode = None
        self.last_scan_time = 0

    def run(self):
        # NATIVE ANDROID OVERRIDE: Let QtMultimedia handle mobile lenses directly
        if ON_ANDROID:
            print("[Camera] Running on Android. System hooks managed via QtMultimedia.")
            return

        # DESKTOP FALLBACK: Run standard fast OpenCV track loop on PC
        self.cap = cv2.VideoCapture(0)
        try:
            if not self.cap.isOpened():
                self.camera_unavailable.emit("No camera detected. Use the manual ISBN field instead.")
                print("[Camera] No webcam found on device 0. Falling back to manual ISBN entry.")
                return

            while self.running:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    self.camera_unavailable.emit("Camera stream unavailable. Use the manual ISBN field instead.")
                    break

                frame = cv2.flip(frame, 1)
                height, width = frame.shape[:2]
                crop_width = int(width * 0.7)
                crop_height = int(height * 0.25)
                crop_x = (width - crop_width) // 2
                crop_y = (height - crop_height) // 2
                scan_zone = frame[crop_y:crop_y + crop_height, crop_x:crop_x + crop_width]
                barcodes = decode(scan_zone, symbols=[ZBarSymbol.EAN13, ZBarSymbol.UPCA])
                for barcode in barcodes:
                    barcode_data = barcode.data.decode("utf-8")
                    if len(barcode_data) in (10, 13) and barcode_data.isdigit():
                        current_time = time.time()
                        if barcode_data != self.last_scanned_barcode or (current_time - self.last_scan_time > 2.5):
                            self.last_scanned_barcode = barcode_data
                            self.last_scan_time = current_time
                            self.barcode_detected.emit(barcode_data)

                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channels = rgb_image.shape
                bytes_per_line = channels * width
                q_img = QImage(rgb_image.data, width, height, bytes_per_line, QImage.Format_RGB888)
                self.frame_received.emit(q_img)
        finally:
            self.cap.release()
            self.cap = None

    def stop(self):
        self.running = False
        self.wait()


class FetchBookWorker(QThread):
    """Network metadata lookup remains universal across PC and Android."""
    book_fetched = Signal(str, str, str, str, str, str, int)
    status_changed = Signal(str, bool)

    def __init__(self, isbn: str):
        super().__init__()
        self.isbn = isbn
        self.cover_candidates = []

    def run(self):
        success, title, author, cover_url, publication_date, publisher, page_count = (
            self.fetch_from_open_library()
        )
        used_google_books = False
        if not success or title.startswith("Unknown Book"):
            google_result = self.fetch_from_google_books()
            used_google_books = True
            if google_result[0]:
                (success, title, author, cover_url, publication_date, publisher, page_count) = (
                    google_result
                )
        elif not self.cover_candidates:
            google_result = self.fetch_from_google_books()
            used_google_books = True
            if google_result[0] and google_result[3]:
                cover_url = google_result[3]

        if not success:
            title = f"Unknown Book ({self.isbn})"
            author = "Unknown Author"
            cover_url = ""
            publication_date = ""
            publisher = ""
            page_count = 0

        cover_url = self._download_best_cover(cover_url)
        if not cover_url and not used_google_books:
            google_result = self.fetch_from_google_books()
            if google_result[0]:
                google_cover_url = self._download_best_cover(google_result[3])
                if google_cover_url:
                    (success, title, author, _, publication_date, publisher, page_count) = (
                        google_result
                    )
                    cover_url = google_cover_url
        if not cover_url:
            cover_url = ""
            if not success:
                self.status_changed.emit(
                    f"No metadata found for ISBN {self.isbn}; adding it as an unknown book.", True
                )
        self.book_fetched.emit(
            self.isbn, title, author, cover_url, publication_date, publisher, page_count
        )

    def _download_best_cover(self, cover_url):
        last_error = ""
        for candidate in self.cover_candidates or ([cover_url] if cover_url else []):
            downloaded, error = download_cover_with_error(self.isbn, candidate)
            if downloaded:
                return candidate
            last_error = error
        if last_error:
            self.status_changed.emit(last_error, True)
        return ""

    def fetch_from_open_library(self):
        try:
            url = "https://openlibrary.org/api/books"
            params = {"bibkeys": f"ISBN:{self.isbn}", "format": "json", "jscmd": "data"}
            res = requests.get(url, params=params, timeout=4)
            if res.status_code != 200:
                self.status_changed.emit(
                    _provider_http_error("Open Library", res.status_code), True
                )
                return False, "", "", "", "", "", 0
            if res.status_code == 200:
                data = res.json()
                key = f"ISBN:{self.isbn}"
                if key in data:
                    info = data[key]
                    title = info.get("title", "Unknown Title")
                    authors = ", ".join([a.get("name", "Unknown") for a in info.get("authors", [])]) or "Unknown Author"

                    self.cover_candidates = _open_library_cover_urls(info)
                    cover_url = self.cover_candidates[0] if self.cover_candidates else ""
                    publishers = info.get("publishers", [])
                    first_publisher = publishers[0] if publishers else ""
                    if isinstance(first_publisher, dict):
                        first_publisher = first_publisher.get("name", "")
                    try:
                        page_count = int(info.get("number_of_pages") or 0)
                    except (TypeError, ValueError):
                        page_count = 0
                    return (True, title, authors, cover_url or "",
                            info.get("publish_date", "") or "", str(first_publisher), page_count)
        except requests.RequestException as error:
            self.status_changed.emit(_provider_request_error("Open Library", error), True)
        except ValueError as error:
            self.status_changed.emit(f"Open Library returned invalid data: {error}", True)
        return False, "", "", "", "", "", 0

    def fetch_from_google_books(self):
        try:
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {"q": f"isbn:{self.isbn}"}
            res = requests.get(url, params=params, timeout=4)
            if res.status_code != 200:
                self.status_changed.emit(
                    _provider_http_error("Google Books", res.status_code), True
                )
                return False, "", "", "", "", "", 0
            if res.status_code == 200:
                data = res.json()
                if "items" in data and len(data["items"]) > 0:
                    vol_info = data["items"][0].get("volumeInfo", {})
                    title = vol_info.get("title", "Unknown Title")
                    authors = ", ".join(vol_info.get("authors", [])) or "Unknown Author"

                    self.cover_candidates = _google_books_cover_urls(vol_info)
                    cover_url = self.cover_candidates[0] if self.cover_candidates else ""
                    try:
                        page_count = int(vol_info.get("pageCount") or 0)
                    except (TypeError, ValueError):
                        page_count = 0
                    return (True, title, authors, cover_url or "",
                            vol_info.get("publishedDate", "") or "",
                            vol_info.get("publisher", "") or "", page_count)
        except requests.RequestException as error:
            self.status_changed.emit(_provider_request_error("Google Books", error), True)
        except ValueError as error:
            self.status_changed.emit(f"Google Books returned invalid data: {error}", True)
        return False, "", "", "", "", "", 0


class RefreshCoverCacheWorker(QThread):
    cover_refreshed = Signal(str, str, bool)
    refresh_finished = Signal(int, int)
    status_changed = Signal(str, bool)

    def __init__(self, isbns):
        super().__init__()
        self.isbns = list(isbns)

    def run(self):
        refreshed = 0
        for isbn in self.isbns:
            success = False
            selected_url = ""
            last_error = ""
            for provider in (self._open_library_urls, self._google_books_urls):
                candidates = provider(isbn)
                for candidate in candidates:
                    downloaded, error = download_cover_with_error(isbn, candidate)
                    if downloaded:
                        selected_url = candidate
                        success = True
                        break
                    last_error = error
                if success:
                    break
            if success:
                refreshed += 1
            elif last_error:
                self.status_changed.emit(f"ISBN {isbn}: {last_error}", True)
            self.cover_refreshed.emit(isbn, selected_url, success)
        self.refresh_finished.emit(refreshed, len(self.isbns))

    def _open_library_urls(self, isbn):
        try:
            response = requests.get(
                "https://openlibrary.org/api/books",
                params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
                timeout=4,
            )
            if response.status_code != 200:
                if response.status_code != 404:
                    self.status_changed.emit(
                        _provider_http_error("Open Library", response.status_code), True
                    )
                return []
            info = response.json().get(f"ISBN:{isbn}", {})
            return _open_library_cover_urls(info)
        except requests.RequestException as error:
            self.status_changed.emit(_provider_request_error("Open Library", error), True)
            return []
        except ValueError as error:
            self.status_changed.emit(f"Open Library returned invalid data: {error}", True)
            return []

    def _google_books_urls(self, isbn):
        try:
            response = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={"q": f"isbn:{isbn}"},
                timeout=4,
            )
            if response.status_code != 200:
                self.status_changed.emit(
                    _provider_http_error("Google Books", response.status_code), True
                )
                return []
            items = response.json().get("items", [])
            if not items:
                return []
            volume_info = items[0].get("volumeInfo", {})
            return _google_books_cover_urls(volume_info)
        except requests.RequestException as error:
            self.status_changed.emit(_provider_request_error("Google Books", error), True)
            return []
        except ValueError as error:
            self.status_changed.emit(f"Google Books returned invalid data: {error}", True)
            return []
