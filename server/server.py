"""Codenames server: accept loop + threading + shared state.

Run from the project root:
    python -m server.server                # English word list (default)
    python -m server.server --lang he      # Hebrew word list
    python -m server.server --words path   # custom word file
"""

import argparse
import os
import socket
import threading

from shared import protocol as P
from shared.crypto_utils import get_or_create_server_keys
from shared.protocol import make_message

from server.client_handler import ClientHandler
from server.game import Game
from server.lobby import SEATS, Lobby, seat_key
from server.users import UserStore


# ---------------------------------------------------------------------------
# CONFIG (default 127.0.0.1:5555 — change here if needed)
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
PORT = 5555

# Word lists shipped with the project. The --lang flag picks one of these;
# --words <path> overrides the choice with any file the student provides.
WORD_FILES = {
    "en": "shared/words.txt",
    "he": "shared/words_he.txt",
}


class ServerState:
    """Shared state for all client threads: lobby, users, current game, lock."""

    def __init__(self, word_pool):
        self.lock = threading.Lock()
        self.users = UserStore()
        self.lobby = Lobby()
        self.game = None  # server.game.Game | None
        self.word_pool = word_pool

    # -- broadcasts --------------------------------------------------------

    def _connected_handlers(self):
        """Snapshot of currently-connected client handlers. Lock-free read."""
        return list(self.lobby.clients.values())

    def broadcast_all(self, message):
        """Send the same message to every connected client."""
        for handler in self._connected_handlers():
            try:
                handler.send(message)
            except Exception as exc:
                print(f"[server] broadcast to {handler.username} failed: {exc}")

    def broadcast_lobby(self):
        with self.lock:
            payload = self.lobby.to_payload()
        self.broadcast_all(make_message(P.LOBBY_STATE, **payload))

    def broadcast_game_state(self):
        """Send the public GAME_STATE to every player in the game."""
        with self.lock:
            if self.game is None:
                return
            payload = self.game.get_state_payload()
        self.broadcast_all(make_message(P.GAME_STATE, **payload))

    # -- game lifecycle ----------------------------------------------------

    def maybe_start_game(self):
        """Start a game when all 4 seats are filled and ready."""
        with self.lock:
            if self.game is not None:
                return
            if not self.lobby.all_seated_and_ready():
                return
            # Build the players dict for the Game class.
            players = {}
            handlers = {}
            for team, role in SEATS:
                username = self.lobby.seats[seat_key(team, role)]
                players[(team, role)] = username
                handlers[username] = self.lobby.clients[username]

            self.game = Game(players, self.word_pool)
            # Snapshot of who needs which start payload, because the
            # spymaster payload includes the key.
            start_payloads = {
                u: self.game.get_start_payload_for(u) for u in players.values()
            }
            initial_state = self.game.get_state_payload()

        # Send GAME_START to each player with their personal view.
        for username, payload in start_payloads.items():
            try:
                handlers[username].send(make_message(P.GAME_START, **payload))
            except Exception as exc:
                print(f"[server] failed to send GAME_START to {username}: {exc}")

        # And one initial GAME_STATE so the UI knows whose turn it is.
        self.broadcast_all(make_message(P.GAME_STATE, **initial_state))

    def end_game(self):
        """Clear the active game and reset ready flags so the lobby re-forms."""
        with self.lock:
            self.game = None
            for u in self.lobby.ready:
                self.lobby.ready[u] = False
        self.broadcast_lobby()


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

def _load_word_pool(path):
    if not os.path.exists(path):
        raise SystemExit(f"Missing word file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        # .upper() is a no-op for Hebrew (no case), and harmless for English.
        words = [line.strip().upper() for line in f if line.strip()]
    if len(words) < 25:
        raise SystemExit(f"Word pool too small ({len(words)} < 25)")
    return words


def _parse_args():
    parser = argparse.ArgumentParser(description="Codenames server")
    parser.add_argument(
        "--lang", choices=sorted(WORD_FILES.keys()), default="en",
        help="Word list language: en (English) or he (Hebrew). Default: en.",
    )
    parser.add_argument(
        "--words", default=None,
        help="Path to a custom words file (overrides --lang).",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    words_file = args.words if args.words else WORD_FILES[args.lang]
    print(f"[server] loading words from {words_file}")
    word_pool = _load_word_pool(words_file)
    print(f"[server] loaded {len(word_pool)} words")
    private_key, public_key = get_or_create_server_keys()
    state = ServerState(word_pool)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[server] Codenames server listening on {HOST}:{PORT}")

    try:
        while True:
            client_sock, addr = server_socket.accept()
            handler = ClientHandler(client_sock, addr, state, private_key, public_key)
            thread = threading.Thread(target=handler.run, daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\n[server] shutting down")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
