import sys
import time
from urllib.parse import quote
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import requests
from cover_cache import download_cover_with_error, server_cover_headers

# Conditional compilation setup: only import desktop modules when not on Android
ON_ANDROID = (sys.platform == "android") or hasattr(sys, "getandroidsdk")

if not ON_ANDROID:
    import cv2
    from pyzbar.pyzbar import decode, ZBarSymbol


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
    MIN_SCAN_INTERVAL_SECONDS = 4.0

    frame_received = Signal(QImage)
    barcode_detected = Signal(str)
    camera_unavailable = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.cap = None
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
                        if current_time - self.last_scan_time >= self.MIN_SCAN_INTERVAL_SECONDS:
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
    """Fetch book metadata and its cached cover through the authenticated server."""
    book_fetched = Signal(str, str, str, str, str, str, int)
    status_changed = Signal(str, bool)
    lookup_failed = Signal(str, str)
    lookup_not_found = Signal(str)

    def __init__(self, isbn: str, server_url: str, token: str):
        super().__init__()
        self.isbn = isbn
        self.server_url = server_url.rstrip("/")
        self.token = token

    def run(self):
        try:
            response = requests.post(
                f"{self.server_url}/api/books/lookup",
                json={"isbn": self.isbn},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=(5, 30),
            )
            if response.status_code != 200:
                if response.status_code == 404:
                    self.lookup_not_found.emit(self.isbn)
                    return
                detail = ""
                try:
                    detail = response.json().get("detail", "")
                except (ValueError, AttributeError):
                    pass
                message = detail or _provider_http_error(
                    "Book lookup server", response.status_code
                )
                self.lookup_failed.emit(self.isbn, message)
                return

            data = response.json()
            for warning in data.get("warnings", []):
                self.status_changed.emit(str(warning), False)

            cover_url = (
                f"{self.server_url}/api/books/cover/{quote(self.isbn, safe='')}"
                if data.get("hasCover", False) else ""
            )
            if cover_url:
                headers = {"Authorization": f"Bearer {self.token}"}
                succeeded, message = download_cover_with_error(
                    self.isbn, cover_url, headers=headers
                )
                if not succeeded:
                    self.status_changed.emit(f"Cover image: {message}", True)

            self.book_fetched.emit(
                data.get("isbn", self.isbn),
                data.get("title", "Unknown Title"),
                data.get("authors", "Unknown Author"),
                cover_url,
                data.get("publicationDate", "") or "",
                data.get("publisher", "") or "",
                int(data.get("pageCount", 0) or 0),
            )
        except requests.Timeout:
            self.lookup_failed.emit(self.isbn, "Book lookup request timed out.")
        except requests.RequestException as error:
            self.lookup_failed.emit(
                self.isbn, _provider_request_error("Book lookup server", error)
            )
        except (ValueError, TypeError, AttributeError) as error:
            self.lookup_failed.emit(self.isbn, f"Invalid book lookup response: {error}")


