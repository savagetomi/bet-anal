from cryptography.fernet import Fernet
import os

# To generate a key for your .env:
# from cryptography.fernet import Fernet
# print(Fernet.generate_key().decode())

def get_fernet_cipher():
    # Retrieve the encryption key from environment
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        raise ValueError("ENCRYPTION_KEY not set in environment.")
    return Fernet(key.encode())

def encrypt_token(token: str) -> bytes:
    cipher = get_fernet_cipher()
    return cipher.encrypt(token.encode())

def decrypt_token(encrypted_token: bytes) -> str:
    cipher = get_fernet_cipher()
    return cipher.decrypt(encrypted_token).decode()
