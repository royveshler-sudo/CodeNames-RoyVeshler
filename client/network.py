"""Client-side socket wrapper: handshake, send_encrypted, recv_encrypted.

The client generates a fresh RSA key pair on startup (in memory; no disk).
This takes ~1-2 seconds but lets multiple clients run on one computer for
testing without filename collisions.
"""

import queue
import socket
import threading

from shared.crypto_utils import make_client_keys, public_key_from_pem, public_key_to_pem
from shared.protocol import recv_encrypted, recv_frame, send_encrypted, send_frame


# Default server address. The student can change this here.
HOST = "127.0.0.1"
PORT = 5555


class NetworkClient:
    """One TCP connection to the server, with a background receiver thread.

    Incoming messages are pushed into a thread-safe queue so the UI thread
    can poll with `get_message(timeout)` without blocking forever.
    """

    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port

        self.private_key, self.public_key = make_client_keys()
        self.server_public_key = None

        self.sock = None
        self.recv_thread = None
        self._closed = False

        self.incoming = queue.Queue()
        # Signals fatal connection errors to the UI thread.
        self.error = None

    # -- connection --------------------------------------------------------

    def connect(self):
        """Open the socket and complete the handshake. Raises on failure."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

        # Plaintext handshake.
        server_pem = recv_frame(self.sock)
        self.server_public_key = public_key_from_pem(server_pem)
        send_frame(self.sock, public_key_to_pem(self.public_key))

        # Start the receiver thread.
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

    def close(self):
        self._closed = True
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    # -- send / recv -------------------------------------------------------

    def send(self, message):
        """Encrypt and send a JSON message. Safe to call from the UI thread."""
        if self._closed or self.sock is None:
            return
        try:
            send_encrypted(self.sock, self.server_public_key, message)
        except Exception as exc:
            self.error = exc
            self.close()

    def get_message(self, timeout = 0.0):
        """Non-blocking poll for the next message; returns None on timeout."""
        try:
            return self.incoming.get(timeout=timeout) if timeout > 0 else self.incoming.get_nowait()
        except queue.Empty:
            return None

    def _recv_loop(self):
        try:
            while not self._closed:
                msg = recv_encrypted(self.sock, self.private_key)
                self.incoming.put(msg)
        except ConnectionError:
            self.error = ConnectionError("Disconnected from server")
        except Exception as exc:
            self.error = exc
        finally:
            self._closed = True
