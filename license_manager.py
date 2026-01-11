import hashlib
import uuid
import platform
import os
import json
import requests
import base64
import sys
import importlib.util
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

def get_license_path():
    """
    Returns the path to the license file in a secure, user-specific directory.
    """
    app_dir_name = ".OMRChecker"
    home_dir = os.path.expanduser('~')
    app_dir_path = os.path.join(home_dir, app_dir_name)
    
    # Create the directory if it doesn't exist
    if not os.path.exists(app_dir_path):
        os.makedirs(app_dir_path)
        
    return os.path.join(app_dir_path, "license.dat")

LICENSE_FILE = get_license_path()
# Replace with your actual Google Apps Script Web App URL
LICENSE_URL = "https://script.google.com/macros/s/AKfycbx9NkcqlaNyZRc9GKVEHynJ96m3xUMqdbKT8qN5PHplkXKYemsPt97SDRIyoiC0U4TaqQ/exec"

PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAmC1anjbxtM53Qt+m1Fsb
iiEN1yetyX38HihTe7g0bAroljhew0EbNizzL6c6LcuwcbKLuRJJo9KbfoNvMgJw
BYMRllFZVlZ5vzqr54ESfStz/1xiuSw4GGLom69fs6eJUvoPaAbhaPkWfsaNPDOY
p+ZvyJXGtxr2sUPNBIuoZJbR285j64dptNq/Sxf243FwDZGRqhv+6tq3txb4ON7s
nrpQ7uQDq+jJq7UBGCdm2ihNRwJZfen9rdTG7ARlaWzq4HYO8ZF6zLGJUT/YKl+V
Hq7mlwWSEjenzW3TDjDSQrRbIMZIDhDZucPFZTIRPTgZi8VNFmFCpZr+TCD5SnDa
dwIDAQAB
-----END PUBLIC KEY-----
"""

def get_machine_hash():
    """
    Generates a unique machine hash based on MAC address and platform details.
    """
    # Get MAC address
    mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 8*6, 8)][::-1])
    
    # Get platform details
    system_info = f"{platform.system()}-{platform.machine()}-{platform.processor()}"
    
    # Combine and hash
    combined_id = f"{mac_address}-{system_info}"
    hashed_id = hashlib.sha256(combined_id.encode()).hexdigest()
    
    return hashed_id

def save_license_key(license_data):
    """
    Saves the license data in an encoded format to a secure local file.
    """
    try:
        license_string = json.dumps(license_data)
        encoded_license = base64.b64encode(license_string.encode('utf-8'))
        
        with open(LICENSE_FILE, "wb") as f: # 'wb' for writing bytes
            f.write(encoded_license)
        return True
    except (IOError, TypeError):
        return False

def load_license_key():
    """
    Loads and decodes the license data from a secure local file.
    """
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "rb") as f: # 'rb' for reading bytes
                encoded_license = f.read()
            
            # Handle potential empty file
            if not encoded_license:
                return None

            decoded_license_string = base64.b64decode(encoded_license).decode('utf-8')
            return json.loads(decoded_license_string)
        except (IOError, json.JSONDecodeError, base64.binascii.Error, TypeError):
            return None
    return None

def verify_license():
    """
    Verifies the license, performing an offline check for UNLIMITED licenses
    and an online check for all other types.
    """
    license_data = load_license_key()
    if not license_data:
        return False, "License file not found. Please register."

    license_type = license_data.get("license_type")

    # --- Offline verification for UNLIMITED licenses ---
    if license_type == "UNLIMITED":
        signature_base64 = license_data.get("server_signature")
        if not signature_base64:
            return False, "Corrupt license file: No signature found."

        payload = {k: v for k, v in license_data.items() if k != "server_signature"}
        payload_string = json.dumps(payload, sort_keys=True, separators=(',', ':'))

        try:
            public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode())
            signature_bytes = base64.b64decode(signature_base64)
            public_key.verify(
                signature_bytes, 
                payload_string.encode(), 
                padding.PKCS1v15(), 
                hashes.SHA256()
            )

            if payload.get("machine_hash") != get_machine_hash():
                return False, "License is for a different machine."

            return True, "UNLIMITED license is valid."
        except InvalidSignature:
            return False, "Invalid license signature."
        except Exception as e:
            return False, f"An error occurred during offline verification: {e}"

    # --- Online verification for all other license types ---
    else:
        license_key = license_data.get("license_key")
        if not license_key:
            return False, "Corrupt license file: No license key found."
            
        payload = {
            "key": license_key,
            "machine_hash": get_machine_hash(),
            "app_name": "OMRApp",
            "request_type": "verify"
        }

        try:
            response = requests.post(LICENSE_URL, json=payload, timeout=20)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("status") == "APPROVED":
                return True, response_data.get("message", "License is valid.")
            else:
                return False, response_data.get("message", "Online verification failed.")

        except requests.exceptions.RequestException as e:
            return False, f"Network error during online verification: {e}"
        except json.JSONDecodeError:
            return False, "Server returned an invalid response."
        except Exception as e:
            return False, f"An unexpected error occurred during online verification: {e}"

def _get_encryption_key():
    """
    Derives a static cryptographic key from a fixed password.
    This key is used for decrypting the core application modules.
    """
    hardcoded_secret = b'3456789iuytrewrgjhgr5426vbnmgfc854gbkjr' # IMPORTANT: Change this to your own secret phrase
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

def decrypt_and_load_module(module_name):
    """
    Decrypts a module's source from a .py.enc file and loads it into memory.
    Returns the loaded module on success, None on failure.
    """
    try:
        # For a bundled app (PyInstaller), resources are in a temp directory (_MEIPASS).
        # For local development, they are in the same directory.
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        encrypted_file_path = os.path.join(base_path, f"{module_name}.py.enc")

        if not os.path.exists(encrypted_file_path):
            raise FileNotFoundError(f"Encrypted module {encrypted_file_path} not found.")

        with open(encrypted_file_path, 'rb') as f:
            encrypted_data = f.read()

        # Get the static decryption key and decrypt the module source
        key = _get_encryption_key()
        fernet = Fernet(key)
        decrypted_source = fernet.decrypt(encrypted_data)

        # Create a module spec and execute the decrypted code in its namespace
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        module = importlib.util.module_from_spec(spec)
        exec(decrypted_source, module.__dict__)
        
        # Crucially, add the newly loaded module to sys.modules. This makes subsequent
        # imports of this module (e.g., "import core_omr") work application-wide.
        sys.modules[module_name] = module
        
        print(f"Successfully decrypted and loaded module: {module_name}")
        return module
    except FileNotFoundError as e:
        print(f"FATAL ERROR: {e}")
        return None
    except Exception as e:
        # This will catch various errors, including cryptography.fernet.InvalidToken,
        # which occurs if the decryption key is wrong.
        print(f"FATAL ERROR: Failed to decrypt or load module '{module_name}'. "
              f"The file may be corrupt or was encrypted with a different key. Details: {e}")
        return None

