import cv2
import requests
import time
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
        self.last_scanned_barcode = None
        self.last_scan_time = 0

    def run(self):
        self.cap = cv2.VideoCapture(0)
        while self.running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                continue

            frame = cv2.flip(frame, 1)

            barcodes = pyzbar.decode(frame)
            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8")
                if len(barcode_data) in [10, 13] and barcode_data.isdigit():
                    current_time = time.time()
                    # 2-second cooldown for the same barcode to avoid duplicate requests
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
    book_fetched = Signal(str, str, str, bytes)

    def __init__(self, isbn):
        super().__init__()
        self.isbn = isbn

    def run(self):
        title = f"Unknown Book ({self.isbn})"
        author = "Unknown Author"
        cover_bytes = b""

        try:
            url = "https://openlibrary.org"
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
                    cover_url = covers.get("medium") or covers.get("large") or covers.get("small")

                    if cover_url:
                        img_res = requests.get(cover_url, timeout=5)
                        if img_res.status_code == 200:
                            cover_bytes = img_res.content
        except Exception as e:
            print(f"Network error searching ISBN {self.isbn}: {e}")

        self.book_fetched.emit(self.isbn, title, author, cover_bytes)
