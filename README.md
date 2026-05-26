# Codenames — Networked Multiplayer

A four-player networked Codenames game written in Python for an 11th-grade
cyber/networking project. The server is authoritative; clients only show
the GUI and send user actions. All client-server traffic is encrypted with
RSA (chunked, since RSA can only encrypt short messages).

## Layout

```
codenames/
├── server/          # Python server (sockets + threading + rules engine)
│   ├── server.py
│   ├── client_handler.py
│   ├── game.py
│   ├── lobby.py
│   └── users.py
├── client/          # Python client (tkinter login + pygame game)
│   ├── main.py
│   ├── login_window.py
│   ├── lobby_window.py
│   ├── game_window.py
│   └── network.py
├── shared/          # Code used by both sides
│   ├── crypto_utils.py
│   ├── protocol.py
│   └── words.txt
├── data/            # Generated at runtime (RSA keys, users.json)
├── requirements.txt
├── README.md
└── PROTOCOL.md
```

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

## How to play

1. **Sign up** with a username/password, then **log in**.
2. The **lobby** opens automatically. Click a seat to claim it
   (Red Spymaster, Red Operative, Blue Spymaster, Blue Operative).
   Click **Ready** when you are happy with your seat.
3. When all 4 seats are filled and ready, the server starts the game.
4. Each turn the **current team's Spymaster** types a one-word clue and
   a number, then clicks **Send Clue**. The **Operative** clicks word
   cards to guess them. After at least one guess the **End Turn** button
   appears so the Operative can voluntarily stop.
5. Reveal all of your team's words to win. Guessing the **Assassin**
   (black card) loses the game instantly.

See `codenames_rules_spec.md` for the full rules.

## Hebrew support

Hebrew (and other non-ASCII) text is supported everywhere a player can
enter or see text:

- **Usernames** — sign up / log in with Hebrew characters (passwords are
  hashed as UTF-8, the user store and JSON file are UTF-8).
- **Clue words** — the Spymaster can type Hebrew clues in the input box.
- **Board words** — replace `shared/words.txt` with your own list (one
  word per line, ≥ 25 entries) to play in Hebrew. The server's clue
  validation (duplicate / substring checks) is Unicode-safe.
- **Rendering** — the pygame lobby and game windows use a Hebrew-capable
  system font (`Arial Hebrew` on macOS, `DejaVu Sans` / `Noto Sans
  Hebrew` on Linux, `Arial` / `Segoe UI` on Windows) and run text
  through the Unicode Bidirectional Algorithm via `python-bidi`, so
  Hebrew and mixed Hebrew/English strings appear in correct
  right-to-left visual order.

See `client/text_utils.py` for the font fallback list and BiDi wrapper.

## Encryption — short version

- The **server** has a long-term RSA-2048 key pair, saved to `data/`.
- Each **client** generates a fresh RSA-2048 key pair on every startup
  (in memory only). This avoids file-name collisions when running
  multiple clients on the same computer for testing.
- On every connection:
  1. The server sends its public key in plaintext (public keys are public).
  2. The client sends its public key in plaintext.
  3. All later messages are JSON, then RSA-encrypted with the recipient's
     public key, then sent inside a length-prefixed frame.
- Because RSA-2048 + OAEP-SHA256 can only encrypt up to **190 bytes** per
  encryption, longer messages are **chunked**: split into 190-byte pieces,
  each encrypted separately, and the 256-byte ciphertexts concatenated.
  The receiver does the reverse.

See `PROTOCOL.md` for the full protocol description.

## Files generated at runtime

- `data/private_key.pem` — server's RSA private key (encrypted with a
  password set in `shared/crypto_utils.py`).
- `data/public_key.pem` — server's RSA public key.
- `data/users.json` — user accounts (username -> `salt:sha256(salt+password)`).

Delete these files and they will be regenerated on the next server start.

## Sanity check

`test_end_to_end.py` spins up four scripted clients against a running
server (no GUI). After starting the server, run:

```
python test_end_to_end.py
```

It logs in 4 users, claims seats, starts a game, gives a clue, makes a
guess, and ends the turn — useful for verifying the networking layer
works without touching the GUI.

`demo_echo_server.py` + `demo_echo_client.py` test the chunked RSA
round-trip on its own.
