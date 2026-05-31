

import json

from shared.crypto_utils import decrypt_with, encrypt_for


# לקוח שולח לשרת
SIGNUP      = "SGUP"
LOGIN       = "LGIN"
JOIN_LOBBY  = "JLBY"
CHOOSE_SEAT = "CHST"
READY       = "REDY"
GIVE_CLUE   = "GCLU"
GUESS_CARD  = "GUSD"
END_TURN    = "ETRN"
LEAVE       = "LEAV"

# שרת שולח ללקוח
SIGNUP_RESULT = "SGRS"
LOGIN_RESULT  = "LGRS"
LOBBY_STATE   = "LBST"
GAME_START    = "GMST"
GAME_STATE    = "GMSE"
CLUE_GIVEN    = "CLGV"
GUESS_RESULT  = "GSRS"
GAME_OVER     = "GMOV"
ERROR         = "ERRR"


def send_frame(sock, payload):
    length = len(payload).to_bytes(4, "big")
    sock.sendall(length + payload)


def recv_frame(sock):
    length = int.from_bytes(_recv_exact(sock, 4), "big")
    return _recv_exact(sock, length)


def _recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data


def send_encrypted(sock, remote_public_key, message):
    plaintext = json.dumps(message).encode("utf-8")
    ciphertext = encrypt_for(remote_public_key, plaintext)
    send_frame(sock, ciphertext)


def recv_encrypted(sock, my_private_key):
    ciphertext = recv_frame(sock)
    plaintext = decrypt_with(my_private_key, ciphertext)
    return json.loads(plaintext.decode("utf-8"))


def make_message(msg_type, **data):
    return {"type": msg_type, "data": data}
