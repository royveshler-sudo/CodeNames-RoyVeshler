

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



HOST = "127.0.0.1"
PORT = 5555


WORD_FILES = {
    "en": "shared/words.txt",
    "he": "shared/words_he.txt",
}


class ServerState:

    def __init__(self, word_pool):
        self.lock = threading.Lock()
        self.users = UserStore()
        self.lobby = Lobby()
        self.game = None  # server.game.Game | None
        self.word_pool = word_pool


    def _connected_handlers(self):
        return list(self.lobby.clients.values())

    def broadcast_all(self, message):
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
        with self.lock:
            if self.game is None:
                return
            payload = self.game.get_state_payload()
        self.broadcast_all(make_message(P.GAME_STATE, **payload))


    def maybe_start_game(self):
        with self.lock:
            if self.game is not None:
                return
            if not self.lobby.all_seated_and_ready():
                return
            players = {}
            handlers = {}
            for team, role in SEATS:
                username = self.lobby.seats[seat_key(team, role)]
                players[(team, role)] = username
                handlers[username] = self.lobby.clients[username]

            self.game = Game(players, self.word_pool)
            start_payloads = {
                u: self.game.get_start_payload_for(u) for u in players.values()
            }
            initial_state = self.game.get_state_payload()

        for username, payload in start_payloads.items():
            try:
                handlers[username].send(make_message(P.GAME_START, **payload))
            except Exception as exc:
                print(f"[server] failed to send GAME_START to {username}: {exc}")

        self.broadcast_all(make_message(P.GAME_STATE, **initial_state))

    def end_game(self):
        with self.lock:
            self.game = None
            for u in self.lobby.ready:
                self.lobby.ready[u] = False
        self.broadcast_lobby()



def _load_word_pool(path):
    if not os.path.exists(path):
        raise SystemExit(f"Missing word file: {path}")
    with open(path, "r", encoding="utf-8") as f:
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
