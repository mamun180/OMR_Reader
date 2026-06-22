import os
import json
import pandas as pd
from PyQt6.QtCore import QStandardPaths, QSettings # Added QSettings

# --- Cache Setup ---
CACHE_DIR_NAME = "cache"
APP_DATA_PATH = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
CACHE_PATH = os.path.join(APP_DATA_PATH, CACHE_DIR_NAME)
CACHE_INFO_FILE = os.path.join(CACHE_PATH, "cache_info.json")

# --- Cache Filenames ---
STUDENT_DATA_CACHE_FILE = os.path.join(CACHE_PATH, "student_data_cache.parquet")
TEMPLATE_DATA_CACHE_FILE = os.path.join(CACHE_PATH, "template_data_cache.json")

def _get_cache_dir():
    """Ensures the cache directory exists and returns its path."""
    if not os.path.exists(CACHE_PATH):
        os.makedirs(CACHE_PATH)
    return CACHE_PATH

def _load_cache_info():
    """Loads the cache metadata file."""
    _get_cache_dir()
    if os.path.exists(CACHE_INFO_FILE):
        try:
            with open(CACHE_INFO_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def _save_cache_info(info):
    """Saves the cache metadata file."""
    _get_cache_dir()
    try:
        with open(CACHE_INFO_FILE, 'w') as f:
            json.dump(info, f, indent=4)
    except IOError:
        pass # Failed to write, cache will be invalid next time

# Global variable to store identifier references
_identifier_references_cache = {}

def _load_identifier_reference_mappings():
    """
    Loads all identifier reference mappings from QSettings.
    Returns a dictionary: {roi_name: [{"scanned": "...", "used": "..."}, ...]}
    """
    settings = QSettings("OptiMark Pro", "IdentifierReferences")
    references = {}
    settings.beginGroup("IdentifierMappings")
    for key in settings.allKeys():
        roi_name = key
        raw_data = settings.value(roi_name, [], type=list)
        parsed_data = []
        for item in raw_data:
            try:
                scanned, used = item.split("::", 1)
                parsed_data.append({"scanned": scanned, "used": used})
            except ValueError:
                pass # Skip malformed entries
        references[roi_name] = parsed_data
    settings.endGroup()
    return references

def refresh_identifier_references():
    """
    Refreshes the in-memory cache of identifier reference mappings from QSettings.
    """
    global _identifier_references_cache
    _identifier_references_cache = _load_identifier_reference_mappings()

# Initialize the cache when the module is loaded
refresh_identifier_references()

def apply_identifier_reference(roi_name, scanned_value):
    """
    Applies reference mapping for a given ROI and scanned value.
    If a mapping exists, returns the 'used' value, otherwise returns the original 'scanned_value'.
    """
    # Use the globally managed cache
    if roi_name not in _identifier_references_cache:
        return scanned_value

    for mapping in _identifier_references_cache[roi_name]:
        if mapping["scanned"] == scanned_value:
            return mapping["used"]
    
    return scanned_value

def get_student_data(student_data_path):
    """
    Gets student data, using a cache if possible.
    Returns a pandas DataFrame or None if loading fails completely.
    """
    cache_info = _load_cache_info()
    
    # --- Try to use cache first ---
    # The cache is considered usable if the path in settings matches what's cached
    # and the physical cache file exists.
    use_cache = cache_info.get("original_student_path") == student_data_path and \
                os.path.exists(STUDENT_DATA_CACHE_FILE)

    if use_cache:
        # If original file still exists, check if it has been modified.
        if os.path.exists(student_data_path):
            try:
                original_mtime = os.path.getmtime(student_data_path)
                # If file is unchanged, load from fast parquet cache
                if cache_info.get("student_file_mtime") == original_mtime:
                    return pd.read_parquet(STUDENT_DATA_CACHE_FILE)
            except (OSError, pd.errors.EmptyDataError, Exception):
                pass # Fall through to re-load from original if cache is corrupt or mtime check fails
        # If original file has been deleted, trust the cache we have.
        else:
            try:
                return pd.read_parquet(STUDENT_DATA_CACHE_FILE)
            except Exception:
                return None # Cache is corrupt and original is gone.

    # --- Cache is invalid or not found, load from original file ---
    if not student_data_path or not os.path.exists(student_data_path):
        return None

    try:
        if student_data_path.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(student_data_path, dtype=str)
        elif student_data_path.lower().endswith('.csv'):
            df = pd.read_csv(student_data_path, dtype=str)
        else:
            return None # Unsupported format
        
        df.columns = df.columns.astype(str)

        # --- Update cache ---
        df.to_parquet(STUDENT_DATA_CACHE_FILE)
        cache_info["original_student_path"] = student_data_path
        cache_info["student_file_mtime"] = os.path.getmtime(student_data_path)
        _save_cache_info(cache_info)
        
        return df
    except Exception:
        # If loading from original fails, clear any old cache entries and return None
        clear_student_cache()
        return None

def get_template_data(template_path):
    """
    Gets template data, using a cache if possible.
    Returns a dictionary or None if loading fails completely.
    """
    cache_info = _load_cache_info()

    use_cache = cache_info.get("original_template_path") == template_path and \
                os.path.exists(TEMPLATE_DATA_CACHE_FILE)

    if use_cache:
        if os.path.exists(template_path):
            try:
                original_mtime = os.path.getmtime(template_path)
                if cache_info.get("template_file_mtime") == original_mtime:
                    with open(TEMPLATE_DATA_CACHE_FILE, 'r') as f: return json.load(f)
            except (OSError, Exception):
                pass
        else: # Original file deleted
            try:
                with open(TEMPLATE_DATA_CACHE_FILE, 'r') as f: return json.load(f)
            except Exception:
                return None

    # --- Cache is invalid, load from original ---
    if not template_path or not os.path.exists(template_path):
        return None

    try:
        with open(template_path, 'r') as f:
            data = json.load(f)

        # --- Update cache ---
        with open(TEMPLATE_DATA_CACHE_FILE, 'w') as f:
            json.dump(data, f)
        
        cache_info["original_template_path"] = template_path
        cache_info["template_file_mtime"] = os.path.getmtime(template_path)
        _save_cache_info(cache_info)

        return data
    except Exception:
        clear_template_cache()
        return None

def clear_student_cache():
    """Removes student data cache files and metadata."""
    if os.path.exists(STUDENT_DATA_CACHE_FILE):
        try: os.remove(STUDENT_DATA_CACHE_FILE)
        except OSError: pass
    
    info = _load_cache_info()
    if "original_student_path" in info:
        del info["original_student_path"]
    if "student_file_mtime" in info:
        del info["student_file_mtime"]
    _save_cache_info(info)

def clear_template_cache():
    """Removes template data cache files and metadata."""
    if os.path.exists(TEMPLATE_DATA_CACHE_FILE):
        try: os.remove(TEMPLATE_DATA_CACHE_FILE)
        except OSError: pass
    
    info = _load_cache_info()
    if "original_template_path" in info:
        del info["original_template_path"]
    if "template_file_mtime" in info:
        del info["template_file_mtime"]
    _save_cache_info(info)

