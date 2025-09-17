"""
Cryptographic utilities using PyNaCl.
"""
import nacl.secret
import nacl.hash
import nacl.signing
import nacl.encoding
import nacl.utils
from nacl.public import PrivateKey, PublicKey, Box
import hashlib
from typing import Tuple, Optional


def generate_keypair() -> Tuple[bytes, bytes]:
    """Generate an Ed25519 keypair. Returns (private_key, public_key)."""
    signing_key = nacl.signing.SigningKey.generate()
    return bytes(signing_key), bytes(signing_key.verify_key)


def sign(message: bytes, private_key: bytes) -> bytes:
    """Sign a message with Ed25519."""
    signing_key = nacl.signing.SigningKey(private_key)
    signed = signing_key.sign(message)
    return signed.signature


def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify an Ed25519 signature."""
    try:
        verify_key = nacl.signing.VerifyKey(public_key)
        verify_key.verify(message, signature)
        return True
    except nacl.exceptions.BadSignatureError:
        return False


def hash(data: bytes, size: int = 16) -> bytes:
    """BLAKE2b hash. Default 16 bytes (128 bits) for event IDs."""
    return nacl.hash.blake2b(data, digest_size=size, encoder=nacl.encoding.RawEncoder)


def generate_secret() -> bytes:
    """Generate a random 32-byte secret."""
    return nacl.utils.random(32)


def encrypt(plaintext: bytes, key: bytes, nonce: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """
    Encrypt with XChaCha20-Poly1305.
    Returns (ciphertext, nonce).
    """
    box = nacl.secret.SecretBox(key)
    if nonce is None:
        nonce = nacl.utils.random(24)
    encrypted = box.encrypt(plaintext, nonce)
    # PyNaCl prepends nonce, we want it separate
    return encrypted[24:], encrypted[:24]


def decrypt(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
    """Decrypt with XChaCha20-Poly1305."""
    box = nacl.secret.SecretBox(key)
    # PyNaCl expects nonce prepended
    return box.decrypt(nonce + ciphertext)


def seal(plaintext: bytes, public_key: bytes) -> bytes:
    """Seal a message to a public key (anonymous sender)."""
    # Convert Ed25519 to X25519 for encryption
    verify_key = nacl.signing.VerifyKey(public_key)
    public = verify_key.to_curve25519_public_key()
    return nacl.public.SealedBox(public).encrypt(plaintext)


def unseal(ciphertext: bytes, private_key: bytes, public_key: bytes) -> bytes:
    """Unseal a message with a private key."""
    # Convert Ed25519 to X25519 for encryption
    signing_key = nacl.signing.SigningKey(private_key)
    private = signing_key.to_curve25519_private_key()
    return nacl.public.SealedBox(private).decrypt(ciphertext)


def kdf(input_material: bytes, salt: bytes, size: int = 32) -> bytes:
    """Key derivation function using BLAKE2b (simple concat)."""
    return nacl.hash.blake2b(
        input_material + salt,
        digest_size=size,
        encoder=nacl.encoding.RawEncoder,
    )


def derive_hex_kdf(input_str: str, *, salt_name: str = "quiet_kdf_salt_v1", size: int = 32) -> str:
    """
    Derive a deterministic hex key from a UTF-8 string using BLAKE2b(KDF).

    Args:
        input_str: Secret input as string
        salt_name: Salt domain label (SHA-256 to 16 bytes)
        size: Output length in bytes (default 32)

    Returns:
        Hex-encoded derived key string
    """
    salt = hashlib.sha256(salt_name.encode('utf-8')).digest()[:16]
    return kdf(input_str.encode('utf-8'), salt=salt, size=size).hex()


def derive_invite_pubkey(invite_secret: str) -> str:
    """
    Derive the invite public key from an invite secret using a fixed salt label.
    Compatible with the prior invite KDF usage.
    """
    return derive_hex_kdf(invite_secret, salt_name="quiet_invite_kdf_v1", size=32)
