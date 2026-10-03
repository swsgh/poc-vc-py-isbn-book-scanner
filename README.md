# VibeScan Studio - Desktop ISBN Book Scanner

A fast, cross-platform desktop application built with **Python 3** and **Qt 6 (PySide6)** that scans 1D book barcodes (ISBN-10/ISBN-13) using your webcam, automatically fetches book metadata via public APIs, and saves your library to a local SQLite database.

## 🛠️ Architecture & Tech Stack

The project uses a clean, decoupled MVC-like architectural layout. Complex tasks (camera handling and API data fetching) are shifted off the main thread to prevent the UI from freezing.

- **Frontend / Framework:** Python + PySide6 (Qt 6)
- **Computer Vision:** OpenCV (`opencv-python`) + `pyzbar` for barcode recognition
- **Database:** Local embedded SQLite3
- **Network Layer:** Python `requests` with automated failover logic
- **Styles & Themes:** Forced Dark Mode via a customized Qt Fusion Palette

### File Layout Map

- `main.py` — The entry bootloader point. Enforces the dark Fusion palette and initializes the application event loop.
- `ui.py` — Layout orchestrator. Wireframe shell that mounts the sub-views and handles multi-threaded signals and slots.
- `scanner_view.py` — UI View widget managing the horizontal mirror webcam canvas, a pulsing red laser animation, and manual string inputs.
- `bookshelf_view.py` — UI View grid layout presenting saved book cards, handling deletion sweeps, and sheet exports.
- `book_details_view.py` — Slide-out context sidebar widget providing book analytics, high-res covers, and individual removal buttons.
- `workers.py` — Threading components (`QThread`) hosting the continuous camera processing stream and metadata fetching loops.
- `database.py` — Pure transactions module handling SQLite storage records, blobs, and wipes.

## 📡 API Fallback Chain

When an ISBN barcode is parsed, the worker queries public archives sequentially until a record match hits:
1. **Primary Source:** Open Library Data API
2. **Secondary Fallback Source:** Google Books Volumes API

---

## 🚀 Quick Setup & Installation

### 1. Prerequisites
Ensure you have Python 3.10+ installed. If you are on **Windows**, you may need the [Visual C++ Redistributable](https://aka.ms) for `pyzbar` to run. If you are on **Linux/macOS**, make sure your system has the native zbar tools installed (`zbar-tools` or `brew install zbar`).

### 2. Environment Setup
Clone this repository and step into your virtual environment:

```bash
# Set up environment
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install dependencies
pip install PySide6 opencv-python pyzbar requests pandas openpyxl
```

### 3. Launching the App
Run the main script to boot up the application dashboard:
```bash
python main.py
```

---

## 🤖 Guide for AI Coding Agents (Prompting Tips)

When working on this codebase with an AI agent (like Claude Code, Cursor, or Copilot Workspace), follow these rules:
- **Keep it decoupled:** Do not add layout trees into `workers.py` or background requests into `scanner_view.py`. Keep UI separate from processing threads.
- **Maintain clean signals:** Sub-widgets (`scanner_view.py`, `bookshelf_view.py`) must pass data up via `Signal` objects. Let `ui.py` act as the master manager controller.
- **Enforce type hints and slots:** Always tag interface slots with the `@Slot()` decorator to keep performance clean.
