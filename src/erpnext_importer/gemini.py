"""
Google Gemini AI Client für intelligentes Feld-Mapping
"""

import json
import time
import logging
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Conditional requests import
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class GeminiAPI:
    """Google Gemini API Client für intelligentes Feld-Mapping"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-2.5-flash"
        self.last_error = ""

    def _make_request(self, prompt: str, retries: int = 2) -> Optional[str]:
        """Sendet Anfrage an Gemini API mit Retry-Logik"""
        if not REQUESTS_AVAILABLE:
            return None

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "topK": 1,
                "topP": 0.8,
                "maxOutputTokens": 2048,
            }
        }

        for attempt in range(retries + 1):
            try:
                response = requests.post(url, json=payload, timeout=60)

                # Rate Limit Handling
                if response.status_code == 429:
                    self.last_error = "Rate Limit erreicht - bitte kurz warten"
                    if attempt < retries:
                        wait_time = (attempt + 1) * 5  # 5s, 10s
                        logger.warning(f"Rate limit, warte {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error("Rate limit nach allen Retries")
                        return None

                response.raise_for_status()
                data = response.json()

                # Extrahiere Text aus Antwort
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        self.last_error = ""
                        return parts[0].get("text", "")

                self.last_error = "Keine Antwort von API"
                return None

            except requests.exceptions.HTTPError as e:
                self.last_error = f"HTTP Fehler: {e.response.status_code}"
                logger.error(f"Gemini API HTTP Error: {e}")
                if attempt < retries and e.response.status_code >= 500:
                    time.sleep(2)
                    continue
                return None
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Gemini API Error: {e}")
                return None

        return None

    def test_connection(self) -> Tuple[bool, str]:
        """Testet die API-Verbindung"""
        result = self._make_request("Antworte nur mit: OK", retries=0)
        if result:
            return True, f"Verbunden ({self.model})"
        return False, self.last_error or "Verbindung fehlgeschlagen"

    def smart_map_fields(self, source_columns: List[str],
                         target_fields: Dict[str, Dict],
                         sample_data: List[Dict] = None) -> Dict[str, str]:
        """
        Mappt Quellspalten intelligent auf Zielfelder mittels AI.

        Args:
            source_columns: Liste der Spalten aus der Quelldatei
            target_fields: Dictionary der ERPNext-Zielfelder
            sample_data: Optionale Beispieldaten für bessere Erkennung
            
        Returns:
            Dict[source_column, target_field]
        """
        # Erstelle Beschreibung der Zielfelder
        target_descriptions = []
        for field_key, field_info in target_fields.items():
            label = field_info.get("label", field_key)
            field_type = field_info.get("type", "Text")
            required = "PFLICHT" if field_info.get("required") else ""
            custom = "CUSTOM" if field_info.get("custom") else ""
            target_descriptions.append(f"- {field_key}: {label} ({field_type}) {required} {custom}".strip())

        target_list = "\n".join(target_descriptions)

        # Erstelle Beschreibung der Quellspalten mit Beispieldaten
        source_descriptions = []
        for col in source_columns:
            sample_values = []
            if sample_data:
                for row in sample_data[:3]:
                    val = row.get(col, "")
                    if val:
                        sample_values.append(str(val)[:50])

            sample_str = f" (Beispiele: {', '.join(sample_values)})" if sample_values else ""
            source_descriptions.append(f"- {col}{sample_str}")

        source_list = "\n".join(source_descriptions)

        prompt = f"""Du bist ein Experte für Daten-Mapping in ERP-Systemen.

AUFGABE: Ordne die Quellspalten den passenden ERPNext-Zielfeldern zu.

QUELLSPALTEN (aus CSV/Import-Datei):
{source_list}

ZIELFELDER (ERPNext):
{target_list}

REGELN:
1. Jede Quellspalte kann nur EINEM Zielfeld zugeordnet werden
2. Nicht alle Quellspalten müssen zugeordnet werden
3. Achte auf semantische Ähnlichkeit, nicht nur auf Namen
4. Berücksichtige die Beispieldaten für bessere Zuordnung
5. CUSTOM-Felder sind benutzerdefinierte Felder - ordne diese auch zu wenn passend
6. Typische Mappings:
   - Artikelnummer/SKU/Art-Nr -> item_code
   - Bezeichnung/Name/Titel -> item_name
   - EAN/GTIN/Barcode -> gtin
   - Preis/VK/Netto -> standard_rate
   - Kategorie/Warengruppe -> item_group
   - Beschreibung/Text -> description
   - Gewicht -> weight_per_unit
   - Hersteller/Marke/Brand -> brand

ANTWORT-FORMAT (NUR JSON, keine Erklärung):
{{"quellspalte1": "zielfeld1", "quellspalte2": "zielfeld2"}}

Wenn keine passende Zuordnung möglich ist, die Spalte weglassen.
Antworte NUR mit dem JSON-Objekt, nichts anderes."""

        result = self._make_request(prompt)

        if not result:
            return {}

        # Parse JSON aus Antwort
        try:
            # Bereinige Antwort (manchmal kommt Markdown)
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1])
            if result.startswith("json"):
                result = result[4:]

            mapping = json.loads(result.strip())

            # Validiere Mapping
            valid_targets = set(target_fields.keys())
            validated_mapping = {}
            for source, target in mapping.items():
                if source in source_columns and target in valid_targets:
                    validated_mapping[source] = target

            return validated_mapping

        except json.JSONDecodeError as e:
            logger.error(f"Gemini JSON Parse Error: {e}")
            logger.error(f"Response was: {result}")
            return {}
