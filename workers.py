import cv2
import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from pyzbar import pyzbar

class CameraWorker(QThread):
    frame_received = Signal(QImage)
    barcode_detected = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.cap = None

    def run(self):
        # Open local hardware webcam
        self.cap = cv2.VideoCapture(0)
        while self.running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                continue

            # 1. FIX: Flip horizontally BEFORE performing tracking/conversions
            #frame = cv2.flip(frame, 1)

            # Scan the live frame matrix for any valid 1D barcode layouts
            barcodes = pyzbar.decode(frame)
            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8")
                # 2. FIX: Restored valid length evaluation condition safely
                if len(barcode_data) in [10, 13] and barcode_data.isdigit():
                    self.barcode_detected.emit(barcode_data)

            # Convert OpenCV frame to native Qt RGB Image format
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
    """Asynchronous worker to fetch book information from the Open Library API."""
    book_fetched = Signal(str, str, str, bytes)  # isbn, title, author, cover_bytes

    def __init__(self, isbn):
        super().__init__()
        self.isbn = isbn

    def run(self):
        title = f"Unknown Book ({self.isbn})"
        author = "Unknown Author"
        cover_bytes = b""

        try:
            # 3. FIX: Clean, explicit parameter dictionary assignment to avoid malformed host parse breaks
            url = "https://openlibrary.org/api/books"
            query_params = {
                "bibkeys": f"ISBN:{self.isbn}",
                "format": "json",
                "jscmd": "data"
            }

            response = requests.get(url, params=query_params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                book_key = f"ISBN:{self.isbn}"

                if book_key in data:
                    book_info = data[book_key]
                    title = book_info.get("title", title)

                    authors = book_info.get("authors", [])
                    if authors:
                        author = ", ".join([a.get("name", "Unknown") for a in authors])

                    covers = book_info.get("cover", {})
                    cover_url = covers.get("medium") or covers.get("small")

                    if cover_url:
                        img_res = requests.get(cover_url, timeout=5)
                        if img_res.status_code == 200:
                            cover_bytes = img_res.content
        except Exception as e:
            print(f"Network error searching ISBN {self.isbn}: {e}")

        self.book_fetched.emit(self.isbn, title, author, cover_bytes)
