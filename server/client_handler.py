"""Per-client thread: handshake, then dispatch messages until disconnect."""

import traceback

from shared import protocol as P
from shared.crypto_utils import public_key_from_pem, public_key_to_pem
from shared.protocol import recv_encrypted, recv_frame, send_encrypted, send_frame, make_message

from server.game import InvalidAction


class ClientHandler:
    """One per connected client. Runs on its own thread.

    The handler keeps a reference to a shared `ServerState` object (created
    by server.py) that holds the lock, lobby, user store, and game.
    """

    def __init__(self, sock, addr, state, server_private_key, server_public_key):
        self.sock = sock
        self.addr = addr
        self.state = state
        self.server_private_key = server_private_key
        self.server_public_key = server_public_key

        # Set after the handshake.
        self.client_public_key = None
        # Set after a successful login.
        self.username = None

    # -- entry point -------------------------------------------------------

    def run(self):
        try:
            self._handshake()
        except Exception as exc:
            print(f"[server] handshake failed with {self.addr}: {exc}")
            self._close()
            return

        print(f"[server] handshake complete with {self.addr}")

        try:
            while True:
                msg = recv_encrypted(self.sock, self.server_private_key)
                self._dispatch(msg)
        except ConnectionError:
            print(f"[server] {self.addr} disconnected")
        except Exception:
            print(f"[server] unexpected error from {self.addr}:")
            traceback.print_exc()
        finally:
            self._on_disconnect()
            self._close()

    # -- handshake ---------------------------------------------------------

    def _handshake(self):
        # Server -> client: server's public key (plaintext frame).
        send_frame(self.sock, public_key_to_pem(self.server_public_key))
        # Client -> server: client's public key (plaintext frame).
        client_pem = recv_frame(self.sock)
        self.client_public_key = public_key_from_pem(client_pem)

    # -- send helpers (used by ServerState.broadcast too) ------------------

    def send(self, message: dict):
        send_encrypted(self.sock, self.client_public_key, message)

    def send_error(self, text: str):
        self.send(make_message(P.ERROR, message=text))

    # -- dispatch ----------------------------------------------------------

    def _dispatch(self, msg: dict):
        msg_type = msg.get("type")
        data = msg.get("data", {}) or {}

        # Auth messages — allowed before login.
        if msg_type == P.SIGNUP:
            ok, err = self.state.users.signup(data.get("username", ""), data.get("password", ""))
            self.send(make_message(P.SIGNUP_RESULT, ok=ok, error=err))
            return

        if msg_type == P.LOGIN:
            username = (data.get("username") or "").strip()
            ok, err = self.state.users.login(username, data.get("password", ""))
            if ok:
                # Reject double-login of the same username.
                with self.state.lock:
                    if username in self.state.lobby.clients:
                        ok = False
                        err = "User is already logged in"
            if ok:
                self.username = username
            self.send(make_message(P.LOGIN_RESULT, ok=ok, error=err))
            return

        # All later messages require a logged-in user.
        if self.username is None:
            self.send_error("Log in first")
            return

        if msg_type == P.JOIN_LOBBY:
            with self.state.lock:
                if self.state.game is not None:
                    self.send_error("A game is already in progress")
                    return
                self.state.lobby.add_client(self.username, self)
            self.state.broadcast_lobby()
            return

        if msg_type == P.CHOOSE_SEAT:
            team = data.get("team")
            role = data.get("role")
            with self.state.lock:
                ok, err = self.state.lobby.choose_seat(self.username, team, role)
            if not ok:
                self.send_error(err)
                return
            self.state.broadcast_lobby()
            return

        if msg_type == P.READY:
            with self.state.lock:
                ok, err = self.state.lobby.set_ready(self.username, bool(data.get("ready", False)))
            if not ok:
                self.send_error(err)
                return
            self.state.broadcast_lobby()
            self.state.maybe_start_game()
            return

        if msg_type == P.GIVE_CLUE:
            self._handle_give_clue(data)
            return

        if msg_type == P.GUESS_CARD:
            self._handle_guess(data)
            return

        if msg_type == P.END_TURN:
            self._handle_end_turn()
            return

        if msg_type == P.LEAVE:
            raise ConnectionError("Client requested leave")

        self.send_error(f"Unknown message type: {msg_type}")

    # -- game actions ------------------------------------------------------

    def _handle_give_clue(self, data):
        word = data.get("word", "")
        number = data.get("number")
        with self.state.lock:
            game = self.state.game
            if game is None:
                self.send_error("No game in progress")
                return
            try:
                game.give_clue(self.username, word, number)
            except InvalidAction as exc:
                self.send_error(str(exc))
                return
            # Broadcast both CLUE_GIVEN (for UI logs) and GAME_STATE.
            team, _ = game.role_of[self.username]
            clue_msg = make_message(P.CLUE_GIVEN, team=team, word=word, number=number)
        # Outside the lock — broadcasts iterate clients but the inner sends
        # don't need to mutate game state.
        self.state.broadcast_all(clue_msg)
        self.state.broadcast_game_state()

    def _handle_guess(self, data):
        index = data.get("index")
        with self.state.lock:
            game = self.state.game
            if game is None:
                self.send_error("No game in progress")
                return
            try:
                result = game.make_guess(self.username, index)
            except InvalidAction as exc:
                self.send_error(str(exc))
                return
            guess_msg = make_message(P.GUESS_RESULT, **result)
            game_over = game.is_over()
            winner = game.winner
            reason = game.over_reason

        self.state.broadcast_all(guess_msg)
        self.state.broadcast_game_state()
        if game_over:
            self.state.broadcast_all(make_message(P.GAME_OVER, winner=winner, reason=reason))
            self.state.end_game()

    def _handle_end_turn(self):
        with self.state.lock:
            game = self.state.game
            if game is None:
                self.send_error("No game in progress")
                return
            try:
                game.end_turn(self.username)
            except InvalidAction as exc:
                self.send_error(str(exc))
                return
        self.state.broadcast_game_state()

    # -- cleanup -----------------------------------------------------------

    def _on_disconnect(self):
        if self.username is None:
            return
        with self.state.lock:
            self.state.lobby.remove_client(self.username)
            # If a game is in progress and one of the seated players left,
            # abort the game and return everyone to the lobby.
            if (self.state.game is not None
                    and self.username in self.state.game.role_of):
                self.state.game = None
                # Reset ready flags so people deliberately re-confirm.
                for u in self.state.lobby.ready:
                    self.state.lobby.ready[u] = False
        self.state.broadcast_lobby()

    def _close(self):
        try:
            self.sock.close()
        except Exception:
            pass
