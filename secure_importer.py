import sys
import os
import importlib.abc
import importlib.util
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class SecureModuleLoader(importlib.abc.Loader):
    def __init__(self, encrypted_data, key):
        self.encrypted_data = encrypted_data
        self.key = key

    def create_module(self, spec):
        return None  # Use default module creation

    def exec_module(self, module):
        # Decrypt in memory
        iv = self.encrypted_data[:16]
        ciphertext = self.encrypted_data[16:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_code = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Remove padding (PKCS7-like)
        padding_len = decrypted_code[-1]
        decrypted_code = decrypted_code[:-padding_len]
        
        # Execute decrypted code in module's namespace
        exec(decrypted_code, module.__dict__)

class SecureModuleFinder(importlib.abc.MetaPathFinder):
    def __init__(self, key, encrypted_dir):
        self.key = key
        self.encrypted_dir = encrypted_dir

    def find_spec(self, fullname, path, target=None):
        # Only handle modules that exist as .py.enc files in our encrypted_dir
        enc_file_path = os.path.join(self.encrypted_dir, fullname.replace('.', '/') + ".py.enc")
        
        if os.path.exists(enc_file_path):
            with open(enc_file_path, "rb") as f:
                encrypted_data = f.read()
            
            loader = SecureModuleLoader(encrypted_data, self.key)
            return importlib.util.spec_from_loader(fullname, loader)
        
        return None

def initialize_security(aes_key, encrypted_dir):
    """
    Hooks the secure importer into the Python import system.
    """
    sys.meta_path.insert(0, SecureModuleFinder(aes_key, encrypted_dir))
