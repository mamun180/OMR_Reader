import requests
import json
import logging
from PyQt6.QtCore import QSettings

class ExportManager:
    def __init__(self):
        self.settings = QSettings("OptiMark Pro", "ExportSettings")
        self.logger = logging.getLogger(__name__)

    def get_config(self):
        config = {
            "type": self.settings.value("type", "None"),
            "url": self.settings.value("url", ""),
            "headers": self.settings.value("headers", {}), # Expecting a dict
            "mysql_host": self.settings.value("mysql_host", ""),
            "mysql_user": self.settings.value("mysql_user", ""),
            "mysql_pass": self.settings.value("mysql_pass", ""),
            "mysql_db": self.settings.value("mysql_db", ""),
            "mysql_table": self.settings.value("mysql_table", "")
        }
        return config

    def export_data(self, data):
        config = self.get_config()
        export_type = config["type"]

        if export_type == "REST/Supabase/Firebase":
            return self._export_rest(data, config)
        elif export_type == "MySQL":
            return self._export_mysql(data, config)
        else:
            self.logger.info("No export type configured.")
            return True, "No export configured."

    def _export_rest(self, data, config):
        url = config["url"]
        headers = config["headers"]
        if not url:
            return False, "URL not configured."
        
        # Ensure headers is a dictionary
        if not isinstance(headers, dict):
            try:
                import json
                headers = json.loads(str(headers))
            except:
                headers = {}
        
        # Default Content-Type if not provided
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        try:
            # For Supabase/Firebase, the body is usually a JSON object
            response = requests.post(url, json=data, headers=headers, timeout=10)
            response.raise_for_status()
            return True, f"Success: {response.status_code}"
        except Exception as e:
            self.logger.error(f"REST Export Error: {e}")
            return False, str(e)

    def _export_mysql(self, data, config):
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=config["mysql_host"],
                user=config["mysql_user"],
                password=config["mysql_pass"],
                database=config["mysql_db"]
            )
            cursor = conn.cursor()
            
            # Simple implementation: keys in 'data' must match columns in 'mysql_table'
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            sql = f"INSERT INTO {config['mysql_table']} ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, list(data.values()))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True, "Success"
        except ImportError:
            return False, "mysql-connector-python not installed."
        except Exception as e:
            self.logger.error(f"MySQL Export Error: {e}")
            return False, str(e)
