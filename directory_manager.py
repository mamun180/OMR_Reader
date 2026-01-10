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
    """
    settings = QSettings("OptiMark Pro", "Defaults")
    base_dir = settings.value("base_directory", "")
    
    if not base_dir or not os.path.isdir(base_dir):
        base_dir = get_default_base_dir_path()
    
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

def get_answer_key_dir():
    """Gets the directory for answer keys."""
    path = os.path.join(get_base_dir(), "answer keys")
    os.makedirs(path, exist_ok=True)
    return path

def get_template_dir():
    """Gets the directory for templates."""
    path = os.path.join(get_base_dir(), "templates")
    os.makedirs(path, exist_ok=True)
    return path

def get_results_dir():
    """Gets the directory for results."""
    path = os.path.join(get_base_dir(), "results")
    os.makedirs(path, exist_ok=True)
    return path
