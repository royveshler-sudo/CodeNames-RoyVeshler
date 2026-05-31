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
SIGNUP      = "SGUP"
LOGIN       = "LGIN"
JOIN_LOBBY  = "JLBY"
CHOOSE_SEAT = "CHST"
READY       = "REDY"
GIVE_CLUE   = "GCLU"
GUESS_CARD  = "GUSD"
END_TURN    = "ETRN"
LEAVE       = "LEAV"

# Server -> Client
SIGNUP_RESULT = "SGRS"
LOGIN_RESULT  = "LGRS"
LOBBY_STATE   = "LBST"
GAME_START    = "GMST"
GAME_STATE    = "GMSE"
CLUE_GIVEN    = "CLGV"
GUESS_RESULT  = "GSRS"
GAME_OVER     = "GMOV"
ERROR         = "ERRR"


# ---------------------------------------------------------------------------
# Framing — every send is preceded by a 4-byte big-endian length
# ---------------------------------------------------------------------------

def send_frame(sock, payload):
    """Send a single length-prefixed frame."""
    length = len(payload).to_bytes(4, "big")
    sock.sendall(length + payload)


def recv_frame(sock):
    """Receive exactly one frame."""
    length = int.from_bytes(_recv_exact(sock, 4), "big")
    return _recv_exact(sock, length)


def _recv_exact(sock, n):
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

def send_encrypted(sock, remote_public_key, message):
    """JSON-encode, RSA-encrypt with the recipient's public key, then frame."""
    plaintext = json.dumps(message).encode("utf-8")
    ciphertext = encrypt_for(remote_public_key, plaintext)
    send_frame(sock, ciphertext)


def recv_encrypted(sock, my_private_key):
    """Read one frame, RSA-decrypt with our private key, then JSON-decode."""
    ciphertext = recv_frame(sock)
    plaintext = decrypt_with(my_private_key, ciphertext)
    return json.loads(plaintext.decode("utf-8"))


def make_message(msg_type, **data):
    """Tiny helper: build the standard { "type": ..., "data": {...} } envelope."""
    return {"type": msg_type, "data": data}
