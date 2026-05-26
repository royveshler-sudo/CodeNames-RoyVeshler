"""Echo client paired with demo_echo_server.py.

Sends three messages of varying length (short, >200 bytes, >500 bytes) to
verify the chunked RSA round-trip works.
"""

import socket

from shared.crypto_utils import make_client_keys, public_key_from_pem, public_key_to_pem
from shared.protocol import recv_encrypted, recv_frame, send_encrypted, send_frame


HOST = "127.0.0.1"
PORT = 5556


def main():
    print("[client] generating RSA key pair...")
    client_private_key, client_public_key = make_client_keys()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    # Handshake (plaintext): receive server's public key, send ours.
    server_pub_pem = recv_frame(sock)
    server_public_key = public_key_from_pem(server_pub_pem)
    send_frame(sock, public_key_to_pem(client_public_key))
    print("[client] handshake complete")

    test_payloads = [
        ("short", "hello"),
        ("medium-220", "A" * 220),
        ("long-500", "B" * 500),
        ("very-long-2000", "C" * 2000),
    ]

    for label, text in test_payloads:
        msg = {"type": "ECHO", "data": {"label": label, "text": text}}
        send_encrypted(sock, server_public_key, msg)
        reply = recv_encrypted(sock, client_private_key)
        echoed_text = reply["data"]["text"]
        ok = echoed_text == text
        print(f"[client] {label}: sent {len(text)} bytes, "
              f"echo matches = {ok}")
        if not ok:
            print(f"  MISMATCH: got {len(echoed_text)} bytes back")

    sock.close()
    print("[client] done")


if __name__ == "__main__":
    main()
