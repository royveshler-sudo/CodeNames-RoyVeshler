"""Network protocol: framing + encrypted send/recv + message type constants.

Framing:  [ 4-byte big-endian payload length ][ payload bytes ]
The handshake (exchange of public keys) is sent in plaintext frames.
Every later message is JSON encoded, RSA-encrypted, then framed.
"""

import json

from shared.crypto_utils import decrypt_with, encrypt_for


# ---------------------------------------------------------------------------
# Message type constants
# ---------------------------------------------------------------------------

# Client -> Server
SIGNUP = "SIGNUP"
LOGIN = "LOGIN"
JOIN_LOBBY = "JOIN_LOBBY"
CHOOSE_SEAT = "CHOOSE_SEAT"
READY = "READY"
GIVE_CLUE = "GIVE_CLUE"
GUESS_CARD = "GUESS_CARD"
END_TURN = "END_TURN"
LEAVE = "LEAVE"

# Server -> Client
SIGNUP_RESULT = "SIGNUP_RESULT"
LOGIN_RESULT = "LOGIN_RESULT"
LOBBY_STATE = "LOBBY_STATE"
GAME_START = "GAME_START"
GAME_STATE = "GAME_STATE"
CLUE_GIVEN = "CLUE_GIVEN"
GUESS_RESULT = "GUESS_RESULT"
GAME_OVER = "GAME_OVER"
ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Framing — every send is preceded by a 4-byte big-endian length
# ---------------------------------------------------------------------------

def send_frame(sock, payload: bytes):
    """Send a single length-prefixed frame."""
    length = len(payload).to_bytes(4, "big")
    sock.sendall(length + payload)


def recv_frame(sock) -> bytes:
    """Receive exactly one frame."""
    length = int.from_bytes(_recv_exact(sock, 4), "big")
    return _recv_exact(sock, length)


def _recv_exact(sock, n: int) -> bytes:
    """Read exactly n bytes from the socket, or raise ConnectionError."""
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data


# ---------------------------------------------------------------------------
# Encrypted JSON messages on top of framing
# ---------------------------------------------------------------------------

def send_encrypted(sock, remote_public_key, message: dict):
    """JSON-encode, RSA-encrypt with the recipient's public key, then frame."""
    plaintext = json.dumps(message).encode("utf-8")
    ciphertext = encrypt_for(remote_public_key, plaintext)
    send_frame(sock, ciphertext)


def recv_encrypted(sock, my_private_key) -> dict:
    """Read one frame, RSA-decrypt with our private key, then JSON-decode."""
    ciphertext = recv_frame(sock)
    plaintext = decrypt_with(my_private_key, ciphertext)
    return json.loads(plaintext.decode("utf-8"))


def make_message(msg_type: str, **data) -> dict:
    """Tiny helper: build the standard { "type": ..., "data": {...} } envelope."""
    return {"type": msg_type, "data": data}
