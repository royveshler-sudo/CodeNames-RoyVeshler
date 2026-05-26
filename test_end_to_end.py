"""Quick end-to-end test: spin 4 'clients' against the real server.

This skips the GUI — just exercises the network protocol and server logic.
Useful sanity check before manual play with pygame.
"""

import socket
import threading
import time

from shared import protocol as P
from shared.crypto_utils import make_client_keys, public_key_from_pem, public_key_to_pem
from shared.protocol import (
    make_message, recv_encrypted, recv_frame, send_encrypted, send_frame,
)


HOST = "127.0.0.1"
PORT = 5555


class TestClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.priv, self.pub = make_client_keys()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((HOST, PORT))
        server_pem = recv_frame(self.sock)
        self.server_pub = public_key_from_pem(server_pem)
        send_frame(self.sock, public_key_to_pem(self.pub))

        self.messages = []
        self.lock = threading.Lock()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def _recv_loop(self):
        try:
            while True:
                msg = recv_encrypted(self.sock, self.priv)
                with self.lock:
                    self.messages.append(msg)
        except Exception:
            pass

    def send(self, msg):
        send_encrypted(self.sock, self.server_pub, msg)

    def wait_for(self, msg_type, timeout=3.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                for m in self.messages:
                    if m.get("type") == msg_type:
                        return m
            time.sleep(0.05)
        raise TimeoutError(f"{self.username}: timed out waiting for {msg_type}")

    def drain_messages_of(self, msg_type):
        with self.lock:
            results = [m for m in self.messages if m.get("type") == msg_type]
            self.messages = [m for m in self.messages if m.get("type") != msg_type]
        return results


def main():
    seats = [
        ("alice", "red", "spymaster"),
        ("bob",   "red", "operative"),
        ("carol", "blue", "spymaster"),
        ("dave",  "blue", "operative"),
    ]
    clients = {}
    for name, _, _ in seats:
        c = TestClient(name, "pw1234")
        # signup (ignore "already taken" — fine on reruns)
        c.send(make_message(P.SIGNUP, username=name, password="pw1234"))
        c.wait_for(P.SIGNUP_RESULT)
        c.send(make_message(P.LOGIN, username=name, password="pw1234"))
        login_result = c.wait_for(P.LOGIN_RESULT)
        assert login_result["data"]["ok"], login_result
        clients[name] = c
    print("4 clients logged in")

    # Join lobby + claim seats + ready up
    for name, team, role in seats:
        clients[name].send(make_message(P.JOIN_LOBBY))
    time.sleep(0.2)
    for name, team, role in seats:
        clients[name].send(make_message(P.CHOOSE_SEAT, team=team, role=role))
    time.sleep(0.2)
    for name, _, _ in seats:
        clients[name].send(make_message(P.READY, ready=True))

    # Wait for GAME_START on every client
    starts = {}
    for name, _, _ in seats:
        starts[name] = clients[name].wait_for(P.GAME_START)
    print("all 4 clients received GAME_START")

    # Spymaster keys exist only for spymasters
    assert starts["alice"]["data"]["key"] is not None
    assert starts["bob"]["data"]["key"] is None

    # Find out which team starts
    starting_team = starts["alice"]["data"]["starting_team"]
    spy = "alice" if starting_team == "red" else "carol"
    op = "bob" if starting_team == "red" else "dave"
    print(f"{starting_team} starts; {spy} gives the clue, {op} guesses")

    key = starts[spy]["data"]["key"]
    # Find an own-team unrevealed card
    own_card = next(i for i, c in enumerate(key) if c == starting_team)

    # Wrong-team spymaster tries to give a clue
    other_spy = "carol" if spy == "alice" else "alice"
    clients[other_spy].send(make_message(P.GIVE_CLUE, word="ANIMAL", number=2))
    err = clients[other_spy].wait_for(P.ERROR)
    print("expected error from wrong-team spymaster:", err["data"]["message"])

    # Correct spymaster gives clue. Pick a word that isn't a substring of any
    # grid word — "BRIGHTNESS" is safe.
    clients[spy].send(make_message(P.GIVE_CLUE, word="BRIGHTNESS", number=2))
    clients[spy].wait_for(P.CLUE_GIVEN)
    print("clue given")

    # Operative guesses the own-team card.
    clients[op].send(make_message(P.GUESS_CARD, index=own_card))
    g = clients[op].wait_for(P.GUESS_RESULT)
    print(f"guess result: {g['data']['color']}")
    assert g["data"]["color"] == starting_team

    # End turn voluntarily.
    clients[op].send(make_message(P.END_TURN))
    time.sleep(0.3)

    # Now the other team is current.
    print("test passed")

    for c in clients.values():
        c.sock.close()


if __name__ == "__main__":
    main()
