import os
import sys
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

def _get_encryption_key():
    """
    Derives a static cryptographic key from a fixed password.
    This key is used for encrypting the core application modules.
    MUST be identical to the function in license_manager.py
    """
    password = b'_Your_Secret_Password_Here_Change_Me_!' # IMPORTANT: Use the same secret phrase as in license_manager.py
    salt = b'_omr_checker_salt_'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

def encrypt_file(file_path):
    """
    Encrypts a file and saves it with a .enc extension.
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    try:
        # Read the source code
        with open(file_path, 'rb') as f:
            source_data = f.read()

        # Get the static key and encrypt the data
        key = _get_encryption_key()
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(source_data)

        # Define the output path
        output_path = file_path + ".enc"

        # Write the encrypted data to the new file
        with open(output_path, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"Successfully encrypted '{file_path}' to '{output_path}'")

    except Exception as e:
        print(f"An error occurred during encryption: {e}")

if __name__ == "__main__":
    files_to_encrypt = ["core_omr.py", "corner_detector.py"]
    
    print(f"Starting encryption for {len(files_to_encrypt)} files...")
    
    for file_name in files_to_encrypt:
        encrypt_file(file_name)
        
    print("\nEncryption process finished.")
    print("IMPORTANT: Remember to change the hardcoded password in both this script and in license_manager.py!")
