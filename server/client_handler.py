

import traceback

from shared import protocol as P
from shared.crypto_utils import public_key_from_pem, public_key_to_pem
from shared.protocol import recv_encrypted, recv_frame, send_encrypted, send_frame, make_message

from server.game import InvalidAction


class ClientHandler:

    def __init__(self, sock, addr, state, server_private_key, server_public_key):
        self.sock = sock
        self.addr = addr
        self.state = state
        self.server_private_key = server_private_key
        self.server_public_key = server_public_key

        self.client_public_key = None
        self.username = None


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


    def _handshake(self):
        send_frame(self.sock, public_key_to_pem(self.server_public_key))
        client_pem = recv_frame(self.sock)
        self.client_public_key = public_key_from_pem(client_pem)

    def send(self, message):
        send_encrypted(self.sock, self.client_public_key, message)

    def send_error(self, text):
        self.send(make_message(P.ERROR, message=text))


    def _dispatch(self, msg):
        msg_type = msg.get("type")
        data = msg.get("data", {}) or {}

        if msg_type == P.SIGNUP:
            ok, err = self.state.users.signup(data.get("username", ""), data.get("password", ""))
            self.send(make_message(P.SIGNUP_RESULT, ok=ok, error=err))
            return

        if msg_type == P.LOGIN:
            username = (data.get("username") or "").strip()
            ok, err = self.state.users.login(username, data.get("password", ""))
            if ok:
                with self.state.lock:
                    if username in self.state.lobby.clients:
                        ok = False
                        err = "User is already logged in"
            if ok:
                self.username = username
            self.send(make_message(P.LOGIN_RESULT, ok=ok, error=err))
            return

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

            team, _ = game.role_of[self.username]
            clue_msg = make_message(P.CLUE_GIVEN, team=team, word=word, number=number)

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


    def _on_disconnect(self):
        if self.username is None:
            return
        with self.state.lock:
            self.state.lobby.remove_client(self.username)

            if (self.state.game is not None
                    and self.username in self.state.game.role_of):
                self.state.game = None

                for u in self.state.lobby.ready:
                    self.state.lobby.ready[u] = False
        self.state.broadcast_lobby()

    def _close(self):
        try:
            self.sock.close()
        except Exception:
            pass
