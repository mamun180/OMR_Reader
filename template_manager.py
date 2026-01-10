from PyQt6.QtCore import QSettings
import json

TEMPLATE_SETTINGS_GROUP = "SavedTemplates"

class NumpyEncoder(json.JSONEncoder):
    """ Custom JSON encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int_)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float_)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

def get_template_names():
    """
    Returns a list of all saved template names.
    """
    settings = QSettings("OptiMark Pro", "Application")
    settings.beginGroup(TEMPLATE_SETTINGS_GROUP)
    names = settings.childKeys()
    settings.endGroup()
    return sorted(names)

def load_template(name):
    """
    Loads a specific template by its name.
    Returns the template data as a dictionary, or None if not found.
    """
    settings = QSettings("OptiMark Pro", "Application")
    settings.beginGroup(TEMPLATE_SETTINGS_GROUP)
    template_json = settings.value(name)
    settings.endGroup()

    if template_json:
        try:
            return json.loads(template_json)
        except json.JSONDecodeError:
            return None
    return None

def save_template(name, template_data):
    """
    Saves a template under a specific name.
    The template_data dictionary is converted to a JSON string for storage.
    Returns True on success, False on failure.
    """
    if not name:
        return False

    try:
        # Use the custom encoder to handle numpy types
        template_json = json.dumps(template_data, cls=NumpyEncoder, indent=4)
    except TypeError:
        return False

    settings = QSettings("OptiMark Pro", "Application")
    settings.beginGroup(TEMPLATE_SETTINGS_GROUP)
    settings.setValue(name, template_json)
    settings.endGroup()
    settings.sync()
    return True

def delete_template(name):
    """
    Deletes a template by its name.
    """
    settings = QSettings("OptiMark Pro", "Application")
    settings.beginGroup(TEMPLATE_SETTINGS_GROUP)
    if settings.contains(name):
        settings.remove(name)
        settings.endGroup()
        settings.sync()
        return True
    settings.endGroup()
    return False
