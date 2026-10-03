import cv2
import requests
import time
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol

class CameraWorker(QThread):
    frame_received = Signal(QImage)
    barcode_detected = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.cap = None
        self.last_scanned_barcode = None
        self.last_scan_time = 0

    def run(self):
        self.cap = cv2.VideoCapture(0)
        while self.running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                continue

            frame = cv2.flip(frame, 1)

            barcodes = pyzbar.decode(frame, symbols=[ZBarSymbol.EAN13, ZBarSymbol.UPCA])
            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8")
                # FIXED: Core bounding constraint logic safely updated to tuple check
                if len(barcode_data) in (10, 13) and barcode_data.isdigit():
                    current_time = time.time()
                    if barcode_data != self.last_scanned_barcode or (current_time - self.last_scan_time > 2.0):
                        self.last_scanned_barcode = barcode_data
                        self.last_scan_time = current_time
                        self.barcode_detected.emit(barcode_data)

            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.frame_received.emit(q_img)

    def stop(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.wait()


class FetchBookWorker(QThread):
    """Asynchronous worker that cycles through free API backends if one fails."""
    book_fetched = Signal(str, str, str, bytes)  # isbn, title, author, cover_bytes

    def __init__(self, isbn):
        super().__init__()
        self.isbn = isbn

    def run(self):
        # 1. TRY PRIMARY DATABASE: Open Library API
        print(f"[API] Querying Primary Database (Open Library) for ISBN {self.isbn}...")
        success, title, author, cover_bytes = self.fetch_from_open_library()

        # 2. TRY SECONDARY DATABASE FALLBACK: Google Books API
        if not success or title.startswith("Unknown Book"):
            print(f"[API] Open Library missed/failed. Falling back to Google Books...")
            success, title, author, cover_bytes = self.fetch_from_google_books()

        # If everything fails, deliver a structured fallback card
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

                    # Fetch cover if available
                    cover_bytes = b""
                    cover_url = info.get("cover", {}).get("medium") or info.get("cover", {}).get("small")
                    if cover_url:
                        img_res = requests.get(cover_url, timeout=4)
                        if img_res.status_code == 200:
                            cover_bytes = img_res.content
                    return True, title, authors, cover_bytes
        except Exception as e:
            print(f"[API Error] Open Library exception: {e}")
        return False, "", "", b""

    def fetch_from_google_books(self):
        try:
            # Query Google Books Volume Lookup using native query filters
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {"q": f"isbn:{self.isbn}"}
            res = requests.get(url, params=params, timeout=4)

            if res.status_code == 200:
                data = res.json()
                if "items" in data and len(data["items"]) > 0:
                    volume_info = data["items"][0].get("volumeInfo", {})
                    title = volume_info.get("title", "Unknown Title")
                    authors = ", ".join(volume_info.get("authors", [])) or "Unknown Author"

                    # Fetch thumbnail artwork asset
                    cover_bytes = b""
                    img_links = volume_info.get("imageLinks", {})
                    cover_url = img_links.get("thumbnail") or img_links.get("smallThumbnail")
                    if cover_url:
                        # Google uses http paths occasionally; force secure routing safely
                        if cover_url.startswith("http://"):
                            cover_url = cover_url.replace("http://", "https://")
                        img_res = requests.get(cover_url, timeout=4)
                        if img_res.status_code == 200:
                            cover_bytes = img_res.content
                    return True, title, authors, cover_bytes
        except Exception as e:
            print(f"[API Error] Google Books exception: {e}")
        return False, "", "", b""
