"""Tiny echo server to verify the handshake + chunked RSA encryption works.

Run:  python demo_echo_server.py
Then: python demo_echo_client.py
"""

import socket
import threading

from shared.crypto_utils import (
    get_or_create_server_keys,
    public_key_from_pem,
    public_key_to_pem,
)
from shared.protocol import recv_encrypted, recv_frame, send_encrypted, send_frame


HOST = "127.0.0.1"
PORT = 5556


def handle_client(client_sock, server_private_key, server_public_key):
    try:
        # Handshake (plaintext): send our public key, receive theirs.
        send_frame(client_sock, public_key_to_pem(server_public_key))
        client_pub_pem = recv_frame(client_sock)
        client_public_key = public_key_from_pem(client_pub_pem)

        # Echo loop.
        while True:
            msg = recv_encrypted(client_sock, server_private_key)
            print(f"[server] received: type={msg.get('type')} "
                  f"len(text)={len(msg.get('data', {}).get('text', ''))}")
            send_encrypted(client_sock, client_public_key, msg)
    except ConnectionError:
        print("[server] client disconnected")
    finally:
        client_sock.close()


def main():
    server_private_key, server_public_key = get_or_create_server_keys()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen()
    print(f"[server] listening on {HOST}:{PORT}")

    while True:
        client_sock, addr = sock.accept()
        print(f"[server] connection from {addr}")
        thread = threading.Thread(
            target=handle_client,
            args=(client_sock, server_private_key, server_public_key),
            daemon=True,
        )
        thread.start()


if __name__ == "__main__":
    main()
