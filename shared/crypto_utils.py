_author_ = 'Roy'
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class KeyPair:

    _PRIVATE_KEY_FILE = "data/private_key.pem"
    _PUBLIC_KEY_FILE = "data/public_key.pem"
    _KEY_PASSWORD = b"codenames-server-key-password"

    _OAEP = padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )
    _MAX_PLAIN_CHUNK = 190
    _ENCRYPTED_CHUNK_SIZE = 256

    def __init__(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.private_key = private_key
        self.public_key = private_key.public_key()

    def load_from_files(self, priv_path, pub_path, password):
        with open(priv_path, "rb") as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(), password=password, backend=default_backend()
            )
        with open(pub_path, "rb") as f:
            self.public_key = serialization.load_pem_public_key(
                f.read(), backend=default_backend()
            )

    def load_or_create_server(self):
        if os.path.exists(self._PRIVATE_KEY_FILE) and os.path.exists(self._PUBLIC_KEY_FILE):
            self.load_from_files(self._PRIVATE_KEY_FILE, self._PUBLIC_KEY_FILE, self._KEY_PASSWORD)
        else:
            os.makedirs(os.path.dirname(self._PRIVATE_KEY_FILE), exist_ok=True)
            self.save(self._PRIVATE_KEY_FILE, self._PUBLIC_KEY_FILE, self._KEY_PASSWORD)

    def save(self, priv_path, pub_path, password):
        pem_private = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(password),
        )
        with open(priv_path, "wb") as f:
            f.write(pem_private)

        pem_public = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        with open(pub_path, "wb") as f:
            f.write(pem_public)

    def public_pem(self):
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def public_key_from_pem(self, pem_bytes):
        return serialization.load_pem_public_key(pem_bytes, backend=default_backend())

    def encrypt_for(self, recipient_public_key, plaintext):
        result = b""
        for i in range(0, len(plaintext), self._MAX_PLAIN_CHUNK):
            chunk = plaintext[i:i + self._MAX_PLAIN_CHUNK]
            result += recipient_public_key.encrypt(chunk, self._OAEP)
        if not result:
            result = recipient_public_key.encrypt(b"", self._OAEP)
        return result

    def decrypt(self, ciphertext):
        if len(ciphertext) == 0 or len(ciphertext) % self._ENCRYPTED_CHUNK_SIZE != 0:
            raise ValueError("Ciphertext length is not a positive multiple of 256")
        plaintext = b""
        for i in range(0, len(ciphertext), self._ENCRYPTED_CHUNK_SIZE):
            chunk = ciphertext[i:i + self._ENCRYPTED_CHUNK_SIZE]
            try:
                plaintext += self.private_key.decrypt(chunk, self._OAEP)
            except ValueError:
                raise ValueError("Decryption failed: key mismatch or corrupted data")
        return plaintext
