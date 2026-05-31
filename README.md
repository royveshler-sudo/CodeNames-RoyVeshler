

## Install

```
python -m venv .venv
. .venv/bin/activate         # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

`requirements.txt` contains `cryptography`, `pygame`, and `python-bidi`
(used to display Hebrew / RTL text in the correct visual order — see
[Hebrew support](#hebrew-support) below). `tkinter` is part of the Python
standard library, so it isn't (and can't be) listed there. It ships with
the official Python installer on Windows and macOS. On Linux install it
via your package manager (`sudo apt install python3-tk` on
Debian/Ubuntu). On macOS Homebrew Python it's a separate formula
matching your Python version, e.g. `brew install python-tk@3.11` for
Python 3.11.

## Run

All commands are run from the project root.

1. Start the server:
   ```
   python -m server.server                  # English word list (default)
   python -m server.server --lang he        # Hebrew word list
   python -m server.server --words PATH     # any custom file
   ```
   On first run the server generates `data/private_key.pem` and
   `data/public_key.pem` automatically (its long-term identity).
   It listens on `127.0.0.1:5555`.

   Built-in word lists live in `shared/words.txt` (English, ~385 words)
   and `shared/words_he.txt` (Hebrew, ~290 words). The Hebrew client
   needs the BiDi-aware font helper to render correctly; this is handled
   by `client/text_utils.py` and the optional `python-bidi` dependency.

2. Run four clients (one per player), each in its own terminal:
   ```
   python -m client.main
   ```
   Each client takes about 1–2 seconds to start while it generates a
   fresh RSA key pair (in memory — no key files on disk for the client).

