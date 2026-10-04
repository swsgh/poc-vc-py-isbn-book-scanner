# ISBN Book Scanner (Python)

A PySide6 desktop app for scanning ISBN barcodes, looking up book details, and maintaining a local bookshelf.

## Features

- Open the scanner view to start the OpenCV camera worker; hiding the view stops capture. The camera uses device index 0.
- Use manual entry when a camera is unavailable. Input accepts 10- or 13-digit ISBNs, with hyphens allowed.
- Look up metadata through Open Library, with Google Books as a fallback.
- Browse, search, inspect, and remove books in the local library.
- Export the library as CSV or Excel (`.xlsx`).
- Store book metadata and cover images in SQLite.

This app is a standalone local library client; it does not currently synchronize with the FastAPI server project.

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
python -m pip install PySide6 opencv-python pyzbar requests pandas openpyxl
```

`requirements.txt` currently lists PySide6 only; the other packages above are also imported by the application. `pyzbar` may require the ZBar native library on your platform.

Run the application from this directory:

```sh
python main.py
```

The SQLite database is named `books.db` and is created in the process's current working directory. Metadata lookups require an internet connection. Without a working camera, use the manual ISBN field.
