"""
ERPNext REST API Client mit verbesserter Fehlerbehandlung
"""

import json
import time
import logging
import os
import mimetypes
from typing import Optional, Dict, List, Tuple, Any

from .config import ERPNextConfig
from .fields import ERPNEXT_ITEM_FIELDS, UOM_MAPPING
from .utils import is_valid_barcode, detect_barcode_type

logger = logging.getLogger(__name__)

# Conditional requests import
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class ERPNextAPIError(Exception):
    """Spezifische Fehlerklasse für ERPNext API Fehler mit benutzerfreundlichen Meldungen"""
    
    def __init__(self, message: str, original_error: Exception = None, 
                 error_code: str = None, suggestion: str = None):
        self.message = message
        self.original_error = original_error
        self.error_code = error_code
        self.suggestion = suggestion
        super().__init__(self.get_full_message())
    
    def get_full_message(self) -> str:
        parts = [self.message]
        if self.error_code:
            parts.append(f"[{self.error_code}]")
        if self.suggestion:
            parts.append(f"Tipp: {self.suggestion}")
        return " | ".join(parts)


class ERPNextAPI:
    """ERPNext REST API Client - Vollständige Implementation mit verbesserter Fehlerbehandlung"""
    
    def __init__(self, config: ERPNextConfig):
        self.config = config
        self.session = self._create_session() if REQUESTS_AVAILABLE else None
        self._item_cache: Dict[str, str] = {}
        self._item_group_cache: Dict[str, str] = {}
        self._attribute_cache: Dict[str, bool] = {}
        self._uom_cache: Dict[str, str] = {}
        self._connection_healthy = False
        self._last_health_check = 0
    
    def _create_session(self):
        if not REQUESTS_AVAILABLE:
            return None
        session = requests.Session()
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(self.config.auth_header)
        return session
    
    def _parse_error_response(self, response) -> str:
        """Extrahiert benutzerfreundliche Fehlermeldung aus API-Antwort"""
        try:
            error_data = response.json()
            if "message" in error_data:
                return error_data["message"]
            if "_server_messages" in error_data:
                messages = json.loads(error_data["_server_messages"])
                if messages:
                    msg = json.loads(messages[0])
                    return msg.get("message", str(messages[0]))
            if "exc_type" in error_data:
                exc_type = error_data["exc_type"]
                if exc_type == "DuplicateEntryError":
                    return "Datensatz existiert bereits"
                elif exc_type == "ValidationError":
                    return "Validierungsfehler - prüfen Sie die Pflichtfelder"
                elif exc_type == "LinkValidationError":
                    return "Verknüpfter Datensatz nicht gefunden (z.B. Kategorie, Hersteller)"
                return f"ERPNext Fehler: {exc_type}"
        except:
            pass
        return f"HTTP {response.status_code}: {response.reason}"
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Führt API-Request aus mit verbesserter Fehlerbehandlung"""
        if not self.session:
            raise ERPNextAPIError(
                "HTTP-Bibliothek nicht verfügbar",
                suggestion="Installieren Sie requests: pip install requests"
            )
        
        url = f"{self.config.base_url}/api/resource/{endpoint}"
        timeout = self.config.request_timeout
        
        try:
            if method == "GET":
                response = self.session.get(url, params=data, timeout=timeout)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=timeout)
            elif method == "PUT":
                response = self.session.put(url, json=data, timeout=timeout)
            elif method == "DELETE":
                response = self.session.delete(url, timeout=timeout)
            else:
                raise ValueError(f"Unbekannte HTTP-Methode: {method}")
            
            if response.status_code >= 400:
                error_msg = self._parse_error_response(response)
                suggestion = None
                if response.status_code == 401:
                    suggestion = "Prüfen Sie API Key und Secret in den Einstellungen"
                elif response.status_code == 403:
                    suggestion = "Der API-Benutzer hat keine Berechtigung für diese Aktion"
                elif response.status_code == 404:
                    suggestion = "Der Datensatz oder Endpunkt existiert nicht"
                elif response.status_code == 417:
                    suggestion = "Pflichtfeld fehlt oder Validierung fehlgeschlagen"
                
                raise ERPNextAPIError(error_msg, error_code=str(response.status_code), suggestion=suggestion)
            
            return response.json() if response.text else {}
            
        except requests.exceptions.Timeout:
            raise ERPNextAPIError(
                "Zeitüberschreitung bei der Verbindung",
                suggestion=f"Server nicht erreichbar oder zu langsam (Timeout: {timeout}s)"
            )
        except requests.exceptions.ConnectionError as e:
            raise ERPNextAPIError(
                "Verbindung zu ERPNext fehlgeschlagen",
                original_error=e,
                suggestion="Prüfen Sie die URL und Ihre Internetverbindung"
            )
        except ERPNextAPIError:
            raise
        except Exception as e:
            logger.error(f"API Error {method} {endpoint}: {e}")
            raise ERPNextAPIError(f"Unerwarteter Fehler: {str(e)}", original_error=e)
    
    def _call_method(self, method_name: str, data: Optional[Dict] = None,
                     files: Optional[Dict] = None) -> Dict:
        """Ruft Frappe-Methode auf mit verbesserter Fehlerbehandlung"""
        if not self.session:
            raise ERPNextAPIError("HTTP-Bibliothek nicht verfügbar")
        
        url = f"{self.config.base_url}/api/method/{method_name}"
        
        try:
            if files:
                headers = {"Authorization": self.config.auth_header["Authorization"]}
                response = self.session.post(url, data=data, files=files, 
                                            headers=headers, timeout=60)
            else:
                response = self.session.post(url, json=data, 
                                            timeout=self.config.request_timeout)
            
            if response.status_code >= 400:
                error_msg = self._parse_error_response(response)
                raise ERPNextAPIError(error_msg, error_code=str(response.status_code))
            
            return response.json() if response.text else {}
        except ERPNextAPIError:
            raise
        except Exception as e:
            logger.error(f"Method Error {method_name}: {e}")
            raise ERPNextAPIError(f"Methodenaufruf fehlgeschlagen: {str(e)}", original_error=e)
    
    def test_connection(self) -> Tuple[bool, str]:
        """Testet API-Verbindung mit detaillierten Fehlermeldungen"""
        if not REQUESTS_AVAILABLE:
            return False, "requests library nicht installiert. Führen Sie aus: pip install requests"
        
        valid, errors = self.config.validate()
        if not valid:
            return False, f"Konfigurationsfehler: {'; '.join(errors)}"
        
        try:
            url = f"{self.config.base_url}/api/method/frappe.auth.get_logged_user"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                user = data.get('message', 'OK')
                self._connection_healthy = True
                self._last_health_check = time.time()
                return True, f"Verbunden als: {user}"
            elif response.status_code == 401:
                return False, "Authentifizierung fehlgeschlagen - prüfen Sie API Key/Secret"
            elif response.status_code == 403:
                return False, "Zugriff verweigert - API-Benutzer hat keine Berechtigung"
            else:
                error_msg = self._parse_error_response(response)
                return False, f"Verbindungsfehler: {error_msg}"
                
        except requests.exceptions.Timeout:
            return False, f"Zeitüberschreitung - Server {self.config.base_url} antwortet nicht"
        except requests.exceptions.ConnectionError:
            return False, f"Verbindung zu {self.config.base_url} fehlgeschlagen - URL prüfen"
        except Exception as e:
            return False, f"Unerwarteter Fehler: {str(e)}"
    
    def is_healthy(self) -> bool:
        """Prüft ob die Verbindung noch gesund ist (mit Cache)"""
        if time.time() - self._last_health_check > 300:
            success, _ = self.test_connection()
            return success
        return self._connection_healthy
    
    def normalize_uom(self, uom: str) -> str:
        """Normalisiert UOM-Eingabe auf ERPNext-Standard"""
        if not uom:
            return "Stk"
        
        uom_lower = uom.lower().strip()
        if uom_lower in self._uom_cache:
            return self._uom_cache[uom_lower]
        
        if uom_lower in UOM_MAPPING:
            result = UOM_MAPPING[uom_lower]
            self._uom_cache[uom_lower] = result
            return result
        
        return uom

    # ==================== CUSTOM FIELDS ====================
    
    def get_custom_fields(self, doctype: str = "Item") -> List[Dict]:
        """Holt alle Custom Fields für einen Doctype von ERPNext."""
        try:
            params = {
                "fields": '["fieldname", "label", "fieldtype", "options", "reqd", "description", "default"]',
                "filters": json.dumps([["dt", "=", doctype]]),
                "limit_page_length": 0
            }
            result = self._make_request("GET", "Custom Field", params)
            custom_fields = result.get("data", [])
            logger.info(f"Gefunden: {len(custom_fields)} Custom Fields für {doctype}")
            return custom_fields
        except Exception as e:
            logger.warning(f"Konnte Custom Fields für {doctype} nicht laden: {e}")
            return []
    
    def get_all_item_fields(self, include_custom: bool = True) -> Dict[str, Dict]:
        """Holt alle verfügbaren Felder für Item (Standard + Custom)."""
        all_fields = dict(ERPNEXT_ITEM_FIELDS)
        
        if include_custom and self.is_healthy():
            custom_fields = self.get_custom_fields("Item")
            
            for cf in custom_fields:
                fieldname = cf.get("fieldname", "")
                if not fieldname:
                    continue
                
                fieldtype = cf.get("fieldtype", "Data")
                ui_type = "Data"
                if fieldtype in ["Text", "Text Editor", "Small Text", "Long Text"]:
                    ui_type = "Text"
                elif fieldtype in ["Int", "Float", "Currency", "Percent"]:
                    ui_type = fieldtype
                elif fieldtype == "Check":
                    ui_type = "Check"
                elif fieldtype == "Link":
                    ui_type = "Link"
                elif fieldtype == "Select":
                    ui_type = "Select"
                
                all_fields[fieldname] = {
                    "label": f"✨ {cf.get('label', fieldname)}",
                    "type": ui_type,
                    "required": cf.get("reqd", 0) == 1,
                    "custom": True,
                    "description": cf.get("description", ""),
                    "default": cf.get("default", ""),
                    "options": cf.get("options", ""),
                }
        
        return all_fields

    # ==================== ITEM METHODS ====================
    
    def get_item(self, item_code: str) -> Optional[Dict]:
        """Holt Item nach Code"""
        if item_code in self._item_cache:
            return {"name": self._item_cache[item_code]}
        try:
            result = self._make_request("GET", f"Item/{item_code}")
            if result.get("data"):
                self._item_cache[item_code] = result["data"]["name"]
            return result.get("data")
        except:
            return None
    
    def create_item(self, data: Dict) -> Tuple[bool, str]:
        """Erstellt neuen Artikel"""
        try:
            if "item_code" not in data:
                return False, "item_code fehlt"
            if "item_name" not in data:
                data["item_name"] = data["item_code"]
            if "item_group" not in data:
                data["item_group"] = self.config.default_item_group
            if "stock_uom" not in data:
                data["stock_uom"] = "Stk"
            
            data["doctype"] = "Item"
            data["is_sales_item"] = 1
            data["is_purchase_item"] = 1
            
            if "gtin" in data and data["gtin"]:
                gtin = data.pop("gtin")
                if gtin and is_valid_barcode(str(gtin)):
                    data["barcodes"] = [{
                        "barcode": gtin,
                        "barcode_type": detect_barcode_type(str(gtin))
                    }]
            
            result = self._make_request("POST", "Item", data)
            name = result.get("data", {}).get("name", data["item_code"])
            self._item_cache[data["item_code"]] = name
            return True, f"Erstellt: {name}"
        except Exception as e:
            return False, str(e)
    
    def update_item(self, item_code: str, data: Dict) -> Tuple[bool, str]:
        """Aktualisiert Artikel"""
        try:
            data.pop("item_code", None)
            data.pop("doctype", None)
            data.pop("gtin", None)
            
            self._make_request("PUT", f"Item/{item_code}", data)
            return True, f"Aktualisiert: {item_code}"
        except Exception as e:
            return False, str(e)
    
    def delete_item(self, item_code: str) -> Tuple[bool, str]:
        """Löscht Artikel"""
        try:
            self._make_request("DELETE", f"Item/{item_code}")
            self._item_cache.pop(item_code, None)
            return True, f"Gelöscht: {item_code}"
        except Exception as e:
            return False, str(e)

    # ==================== ITEM GROUP METHODS ====================
    
    def get_item_group(self, name: str) -> Optional[Dict]:
        """Holt Item Group"""
        if name in self._item_group_cache:
            return {"name": self._item_group_cache[name]}
        try:
            result = self._make_request("GET", f"Item Group/{name}")
            if result.get("data"):
                self._item_group_cache[name] = result["data"]["name"]
            return result.get("data")
        except:
            return None
    
    def create_item_group(self, data: Dict) -> Tuple[bool, str]:
        """Erstellt Kategorie"""
        try:
            name = data.get("item_group_name", "")
            if self.get_item_group(name):
                return True, f"Existiert bereits: {name}"

            data["doctype"] = "Item Group"
            data["is_group"] = 1
            if "parent_item_group" not in data:
                data["parent_item_group"] = self.config.default_item_group

            result = self._make_request("POST", "Item Group", data)
            created_name = result.get("data", {}).get("name", name)
            self._item_group_cache[name] = created_name
            return True, f"Erstellt: {created_name}"
        except Exception as e:
            return False, str(e)

    def ensure_category_hierarchy(self, levels: List[str], log_callback=None) -> str:
        """Erstellt Kategorie-Hierarchie und gibt die unterste Kategorie zurück."""
        if not levels:
            return self.config.default_item_group

        levels = [l.strip() for l in levels if l and l.strip()]
        if not levels:
            return self.config.default_item_group

        parent = self.config.default_item_group
        last_category = parent

        for level_name in levels:
            existing = self.get_item_group(level_name)

            if existing:
                last_category = level_name
                parent = level_name
                if log_callback:
                    log_callback(f"Kategorie existiert: {level_name}")
            else:
                data = {
                    "item_group_name": level_name,
                    "parent_item_group": parent
                }
                success, msg = self.create_item_group(data)
                if success:
                    last_category = level_name
                    parent = level_name
                    if log_callback:
                        log_callback(f"Kategorie erstellt: {level_name} (unter {data['parent_item_group']})")
                else:
                    if log_callback:
                        log_callback(f"FEHLER: Kategorie {level_name} konnte nicht erstellt werden: {msg}")
                    break

        return last_category

    def parse_category_path(self, path: str, separator: str = ">") -> List[str]:
        """Parst einen Kategorie-Pfad-String in einzelne Ebenen."""
        if not path:
            return []

        for sep in [" > ", " -> ", " >> ", " / ", "/", ">", "|"]:
            if sep in path:
                return [p.strip() for p in path.split(sep) if p.strip()]

        return [path.strip()] if path.strip() else []

    # ==================== FILE UPLOAD ====================
    
    def upload_file(self, file_path: str, doctype: str = None,
                    docname: str = None, is_private: bool = False) -> Optional[str]:
        """Lädt Datei hoch"""
        if not os.path.exists(file_path):
            return None
        
        filename = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
        data = {
            "is_private": 1 if is_private else 0,
            "folder": "Home/Attachments"
        }
        
        if doctype and docname:
            data["doctype"] = doctype
            data["docname"] = docname
            data["attached_to_doctype"] = doctype
            data["attached_to_name"] = docname
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f, mime_type)}
                result = self._call_method("upload_file", data=data, files=files)
            
            file_url = result.get("message", {}).get("file_url", "")
            return file_url
        except Exception as e:
            logger.error(f"Upload Error: {e}")
            return None
    
    def set_item_image(self, item_code: str, image_path: str) -> Tuple[bool, str]:
        """Setzt Hauptbild für Item"""
        file_url = self.upload_file(image_path, "Item", item_code)
        
        if file_url:
            try:
                self._make_request("PUT", f"Item/{item_code}", {"image": file_url})
                return True, f"Bild gesetzt: {file_url}"
            except Exception as e:
                return False, str(e)
        return False, "Upload fehlgeschlagen"
    
    def attach_file(self, item_code: str, file_path: str) -> Tuple[bool, str]:
        """Hängt Datei an Item an"""
        file_url = self.upload_file(file_path, "Item", item_code)
        if file_url:
            return True, f"Angehängt: {file_url}"
        return False, "Upload fehlgeschlagen"
    
    def delete_item_attachments(self, item_code: str) -> Tuple[bool, str]:
        """Löscht alle Anhänge eines Items"""
        try:
            url = f"{self.config.base_url}/api/resource/File"
            params = {
                "filters": json.dumps([
                    ["attached_to_doctype", "=", "Item"],
                    ["attached_to_name", "=", item_code]
                ]),
                "limit_page_length": 0
            }
            response = self.session.get(url, params=params, timeout=30)
            files = response.json().get("data", [])
            
            deleted = 0
            for f in files:
                try:
                    self._make_request("DELETE", f"File/{f['name']}")
                    deleted += 1
                except:
                    pass
            
            self._make_request("PUT", f"Item/{item_code}", {"image": ""})
            
            return True, f"{deleted} Anhänge gelöscht"
        except Exception as e:
            return False, str(e)

    # ==================== ITEM ATTRIBUTES ====================
    
    def get_or_create_attribute(self, name: str, values: List[str] = None) -> Tuple[bool, str]:
        """Erstellt oder aktualisiert Item Attribute"""
        try:
            try:
                result = self._make_request("GET", f"Item Attribute/{name}")
                if result.get("data"):
                    if values:
                        existing = [v.get("attribute_value") for v in 
                                   result["data"].get("item_attribute_values", [])]
                        new_values = [v for v in values if v not in existing]
                        
                        if new_values:
                            current = result["data"].get("item_attribute_values", [])
                            for val in new_values:
                                abbr = val[:3].upper() if len(val) >= 3 else val.upper()
                                current.append({"attribute_value": val, "abbr": abbr})
                            self._make_request("PUT", f"Item Attribute/{name}", {
                                "item_attribute_values": current
                            })
                    return True, f"Attribut existiert: {name}"
            except:
                pass
            
            data = {
                "doctype": "Item Attribute",
                "attribute_name": name,
                "item_attribute_values": []
            }
            
            if values:
                for val in values:
                    abbr = val[:3].upper() if len(val) >= 3 else val.upper()
                    data["item_attribute_values"].append({
                        "attribute_value": val,
                        "abbr": abbr
                    })
            
            self._make_request("POST", "Item Attribute", data)
            return True, f"Attribut erstellt: {name}"
        except Exception as e:
            return False, str(e)
    
    def create_item_price(self, item_code: str, price: float) -> Tuple[bool, str]:
        """Erstellt Item-Preis"""
        try:
            data = {
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": self.config.default_price_list,
                "price_list_rate": price,
                "currency": "EUR",
                "selling": 1
            }
            self._make_request("POST", "Item Price", data)
            return True, f"Preis erstellt: {price} EUR"
        except Exception as e:
            return False, str(e)
    
    def get_all_items(self, limit: int = 0) -> List[Dict]:
        """Holt alle Items"""
        try:
            params = {"fields": '["name","item_name","item_group"]'}
            if limit > 0:
                params["limit_page_length"] = limit
            else:
                params["limit_page_length"] = 0

            result = self._make_request("GET", "Item", params)
            return result.get("data", [])
        except:
            return []

    # ==================== EXPORT METHODS ====================

    def export_items(self, fields: List[str], filters: Dict = None,
                     limit: int = 0, callback=None) -> List[Dict]:
        """Exportiert Artikel mit ausgewählten Feldern"""
        try:
            params = {
                "fields": json.dumps(fields),
                "limit_page_length": limit if limit > 0 else 0
            }

            if filters:
                filter_list = []
                for key, value in filters.items():
                    if value:
                        filter_list.append([key, "like", f"%{value}%"])
                if filter_list:
                    params["filters"] = json.dumps(filter_list)

            result = self._make_request("GET", "Item", params)
            items = result.get("data", [])

            full_items = []
            for i, item in enumerate(items):
                try:
                    full_data = self._make_request("GET", f"Item/{item['name']}")
                    full_items.append(full_data.get("data", item))
                    if callback:
                        callback(i + 1, len(items))
                except:
                    full_items.append(item)

            return full_items
        except Exception as e:
            logger.error(f"Export Error: {e}")
            return []

    def export_item_groups(self, fields: List[str] = None, limit: int = 0) -> List[Dict]:
        """Exportiert Kategorien"""
        try:
            default_fields = ["name", "item_group_name", "parent_item_group",
                            "is_group", "description"]
            params = {
                "fields": json.dumps(fields or default_fields),
                "limit_page_length": limit if limit > 0 else 0
            }

            result = self._make_request("GET", "Item Group", params)
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Export Item Groups Error: {e}")
            return []

    def get_price_lists(self) -> List[str]:
        """Holt verfügbare Preislisten"""
        try:
            params = {
                "fields": '["name"]',
                "filters": '[["enabled", "=", 1]]',
                "limit_page_length": 0
            }
            result = self._make_request("GET", "Price List", params)
            return [p["name"] for p in result.get("data", [])]
        except:
            return ["Standard-Verkauf", "Standard-Einkauf"]

    def get_warehouses(self) -> List[str]:
        """Holt verfügbare Lager"""
        try:
            params = {
                "fields": '["name"]',
                "filters": '[["is_group", "=", 0]]',
                "limit_page_length": 0
            }
            result = self._make_request("GET", "Warehouse", params)
            return [w["name"] for w in result.get("data", [])]
        except:
            return []

    def get_item_groups_list(self) -> List[str]:
        """Holt verfügbare Artikelgruppen"""
        try:
            params = {
                "fields": '["name"]',
                "limit_page_length": 0
            }
            result = self._make_request("GET", "Item Group", params)
            return [g["name"] for g in result.get("data", [])]
        except:
            return ["Alle Artikelgruppen"]
