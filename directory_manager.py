import os
from PyQt6.QtCore import QSettings, QStandardPaths

def get_documents_dir():
    """Returns the user's documents directory."""
    return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)

def get_default_base_dir_path():
    """Returns the default base directory path without creating it."""
    return os.path.join(get_documents_dir(), "Optimark Pro")

def get_base_dir():
    """
    Gets the base directory for OptiMark Pro data.
    Checks for a custom base directory in settings.
    If not found, defaults to 'Documents/Optimark Pro'.
    Creates the directory if it doesn't exist.
    Returns the path or None on failure.
    """
    settings = QSettings("OptiMark Pro", "Defaults")
    base_dir = settings.value("base_directory", "")
    
    if not base_dir or not os.path.isdir(base_dir):
        base_dir = get_default_base_dir_path()
    
    try:
        os.makedirs(base_dir, exist_ok=True)
        return base_dir
    except OSError:
        return None

def get_answer_key_dir():
    """Gets the directory for answer keys. Returns None on failure."""
    base = get_base_dir()
    if not base: return None
    path = os.path.join(base, "answer keys")
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        return None

def get_template_dir():
    """Gets the directory for templates. Returns None on failure."""
    base = get_base_dir()
    if not base: return None
    path = os.path.join(base, "templates")
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        return None

def get_results_dir():
    """Gets the directory for results. Returns None on failure."""
    base = get_base_dir()
    if not base: return None
    path = os.path.join(base, "results")
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        return None

def get_scanned_images_dir():
    """Gets the directory for scanned images. Returns None on failure."""
    settings = QSettings("OptiMark Pro", "Defaults")
    path = settings.value("scanned_images_directory", "")
    
    if not path:
        base = get_base_dir()
        if not base: return None
        path = os.path.join(base, "scanned")
        
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        return None
