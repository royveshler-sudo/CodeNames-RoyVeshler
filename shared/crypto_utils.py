"""RSA encryption helpers.

We use only the primitives shown in the teacher's PDF:
- cryptography.hazmat.primitives.asymmetric.rsa
- PEM serialization
- OAEP padding

Because RSA can only encrypt short messages (max ~190 bytes per encryption
with a 2048-bit key and OAEP-SHA256), we split longer plaintexts into chunks,
encrypt each chunk separately, and concatenate the 256-byte ciphertexts.
"""

import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


# OAEP padding parameters — same as the teacher's PDF
OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)

# With RSA-2048 + OAEP-SHA256:
#   max plaintext per encryption = 190 bytes
#   ciphertext is always exactly 256 bytes
MAX_PLAIN_CHUNK = 190
ENCRYPTED_CHUNK_SIZE = 256


def generate_key_pair():
    """Generate a fresh RSA-2048 key pair. Returns (private_key, public_key)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


def save_key_pair(private_key, public_key, priv_path, pub_path, password):
    """Serialize a key pair to disk (used by the server)."""
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )
    with open(priv_path, "wb") as f:
        f.write(pem_private)

    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(pub_path, "wb") as f:
        f.write(pem_public)


def load_key_pair(priv_path, pub_path, password):
    """Load a key pair from disk (used by the server)."""
    with open(priv_path, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(), password=password, backend=default_backend()
        )
    with open(pub_path, "rb") as f:
        public_key = serialization.load_pem_public_key(
            f.read(), backend=default_backend()
        )
    return private_key, public_key


def public_key_to_pem(public_key):
    """Serialize a public key for sending over the wire."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def public_key_from_pem(pem_bytes):
    """Reconstruct a public key from PEM bytes received over the wire."""
    return serialization.load_pem_public_key(pem_bytes, backend=default_backend())


def encrypt_for(recipient_public_key, plaintext):
    """Encrypt arbitrary-length plaintext by chunking.

    Returns the concatenation of 256-byte ciphertexts, one per 190-byte chunk.
    """
    result = b""
    for i in range(0, len(plaintext), MAX_PLAIN_CHUNK):
        chunk = plaintext[i:i + MAX_PLAIN_CHUNK]
        result += recipient_public_key.encrypt(chunk, OAEP)
    # Special case: empty input still needs a single chunk so the receiver
    # has something to decrypt and gets an empty plaintext back.
    if not result:
        result = recipient_public_key.encrypt(b"", OAEP)
    return result


def decrypt_with(my_private_key, ciphertext):
    """Decrypt arbitrary-length ciphertext. Length must be a multiple of 256."""
    if len(ciphertext) == 0 or len(ciphertext) % ENCRYPTED_CHUNK_SIZE != 0:
        raise ValueError("Ciphertext length is not a positive multiple of 256")
    plaintext = b""
    for i in range(0, len(ciphertext), ENCRYPTED_CHUNK_SIZE):
        chunk = ciphertext[i:i + ENCRYPTED_CHUNK_SIZE]
        try:
            plaintext += my_private_key.decrypt(chunk, OAEP)
        except ValueError:
            raise ValueError("Decryption failed: key mismatch or corrupted data")
    return plaintext


# --------------------------------------------------------------------------
# Server key bootstrap
# --------------------------------------------------------------------------

PRIVATE_KEY_FILE = "data/private_key.pem"
PUBLIC_KEY_FILE = "data/public_key.pem"
KEY_PASSWORD = b"codenames-server-key-password"


def get_or_create_server_keys():
    """Load the server's key pair from disk, or create+save it on first run."""
    if os.path.exists(PRIVATE_KEY_FILE) and os.path.exists(PUBLIC_KEY_FILE):
        return load_key_pair(PRIVATE_KEY_FILE, PUBLIC_KEY_FILE, KEY_PASSWORD)

    os.makedirs(os.path.dirname(PRIVATE_KEY_FILE), exist_ok=True)
    private_key, public_key = generate_key_pair()
    save_key_pair(private_key, public_key, PRIVATE_KEY_FILE, PUBLIC_KEY_FILE, KEY_PASSWORD)
    return private_key, public_key


def make_client_keys():
    """Fresh in-memory key pair for a client. No disk I/O.

    We don't save client keys because multiple clients on the same machine
    would collide on filenames during testing. The ~1-2s startup cost is fine.
    """
    return generate_key_pair()
