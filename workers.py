import sys
import time
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
import requests

# Conditional compilation setup: only import desktop modules when not on Android
ON_ANDROID = (sys.platform == "android") or hasattr(sys, "getandroidsdk")

if not ON_ANDROID:
    import cv2
    from pyzbar.pyzbar import decode, ZBarSymbol


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
    book_fetched = Signal(str, str, str, bytes)

    def __init__(self, isbn: str):
        super().__init__()
        self.isbn = isbn

    def run(self):
        success, title, author, cover_bytes = self.fetch_from_open_library()
        if not success or title.startswith("Unknown Book"):
            success, title, author, cover_bytes = self.fetch_from_google_books()

        if not success:
            title = f"Unknown Book ({self.isbn})"
            author = "Unknown Author"
            cover_bytes = b""

        self.book_fetched.emit(self.isbn, title, author, cover_bytes)

    def fetch_from_open_library(self):
        try:
            url = "https://openlibrary.org/api/books"
            params = {"bibkeys": f"ISBN:{self.isbn}", "format": "json", "jscmd": "data"}
            res = requests.get(url, params=params, timeout=4)
            if res.status_code == 200:
                data = res.json()
                key = f"ISBN:{self.isbn}"
                if key in data:
                    info = data[key]
                    title = info.get("title", "Unknown Title")
                    authors = ", ".join([a.get("name", "Unknown") for a in info.get("authors", [])]) or "Unknown Author"

                    cover_bytes = b""
                    cover_url = info.get("cover", {}).get("medium") or info.get("cover", {}).get("small")
                    if cover_url:
                        img_res = requests.get(cover_url, timeout=4)
                        if img_res.status_code == 200:
                            cover_bytes = img_res.content
                    return True, title, authors, cover_bytes
        except Exception as e:
            print(f"[API Error] Open Library skipped: {e}")
        return False, "", "", b""

    def fetch_from_google_books(self):
        try:
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {"q": f"isbn:{self.isbn}"}
            res = requests.get(url, params=params, timeout=4)
            if res.status_code == 200:
                data = res.json()
                if "items" in data and len(data["items"]) > 0:
                    vol_info = data["items"][0].get("volumeInfo", {})
                    title = vol_info.get("title", "Unknown Title")
                    authors = ", ".join(vol_info.get("authors", [])) or "Unknown Author"

                    cover_bytes = b""
                    img_links = vol_info.get("imageLinks", {})
                    cover_url = img_links.get("thumbnail") or img_links.get("smallThumbnail")
                    if cover_url:
                        if cover_url.startswith("http://"):
                            cover_url = cover_url.replace("http://", "https://")
                        img_res = requests.get(cover_url, timeout=4)
                        if img_res.status_code == 200:
                            cover_bytes = img_res.content
                    return True, title, authors, cover_bytes
        except Exception as e:
            print(f"[API Error] Google Books skipped: {e}")
        return False, "", "", b""
