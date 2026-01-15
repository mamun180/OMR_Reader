import os
from PyQt6.QtCore import QSettings

def get_default_image_settings():
    """
    Returns a dictionary containing the hard-coded default image processing parameters.
    These values are used when no settings are saved or when reverting to defaults.
    """
    return {
        'contrast': 1.0, 
        'brightness': 0, 
        'blur': 2, 
        'rotation': 0,
        'adaptive_c': 7, 
        'threshold': 0.3, 
        'method': 'pixel_count',
        'grayscale': False, 
        'transparency': 150
    }

def load_image_settings():
    """
    Loads image settings from persistent application storage (QSettings).
    If a setting is not found, it falls back to the default value for that key.
    """
    settings = QSettings("OptiMark Pro", "ImageSettings")
    params = get_default_image_settings()
    
    for key, default_val in params.items():
        saved_val = settings.value(key)
        if saved_val is None:
            # If the key doesn't exist in QSettings, use the default
            params[key] = default_val
        else:
            # If the key exists, try to cast it to the correct type
            try:
                if isinstance(default_val, bool):
                    # QSettings saves bools as 'true'/'false' strings
                    params[key] = saved_val.lower() == 'true'
                elif isinstance(default_val, int):
                    params[key] = int(float(saved_val)) # Cast to float first for safety
                elif isinstance(default_val, float):
                    params[key] = float(saved_val)
                else: # string
                    params[key] = str(saved_val)
            except (ValueError, TypeError):
                # If casting fails, fall back to the default for that key
                params[key] = default_val
    return params

def save_image_settings(params):
    """
    Saves the provided dictionary of image settings to persistent application storage (QSettings).
    """
    settings = QSettings("OptiMark Pro", "ImageSettings")
    for key, value in params.items():
        settings.setValue(key, value)
    settings.sync() # Ensure settings are written to disk

def revert_image_settings():
    """
    Removes the saved image settings from persistent application storage (QSettings),
    effectively reverting the application to the hard-coded defaults on next load.
    """
    settings = QSettings("OptiMark Pro", "ImageSettings")
    settings.clear()
    settings.sync()

def save_last_path(dialog_key, path):
    """
    Saves the last used path for a specific file dialog.
    """
    if path:
        settings = QSettings("OptiMark Pro", "FileDialogPaths")
        # If the path is a file, get its directory
        if os.path.isfile(path):
            dir_path = os.path.dirname(path)
        else:
            dir_path = path
        settings.setValue(dialog_key, dir_path)
        settings.sync()

def load_last_path(dialog_key):
    """
    Loads the last used path for a specific file dialog.
    Returns an empty string if not found.
    """
    settings = QSettings("OptiMark Pro", "FileDialogPaths")
    return settings.value(dialog_key, "")