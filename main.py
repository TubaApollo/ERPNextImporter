#!/usr/bin/env python3
"""
ERPNext Produkt-Importer (JTL-Ameise Style) v2
==============================================
Vollständige Flet-GUI für ERPNext Produktimport und -export.

Features:
- CSV und BMECat XML Import
- Flexibles Feld-Mapping mit Auto-Zuordnung
- Vorlagen speichern/laden
- Dry Run Modus
- Bilder hochladen/aktualisieren/löschen
- Varianten/Attribute Import
- Progress-Tracking mit Log

Export-Features:
- Artikel-Export mit Feldauswahl
- Kategorien-Export
- Preislisten-Export
- Lagerbestand-Export
- CSV/TSV/JSON Formate
- Filter nach Artikelgruppe, Marke, etc.
"""

import flet as ft
from flet import (
    Page, Text, ElevatedButton, FilePicker, FilePickerResultEvent,
    Column, Row, Container, DataTable, DataColumn, DataRow, DataCell,
    Dropdown, dropdown, TextField, Checkbox, ProgressBar, Divider,
    Tab, Tabs, ListView, Card, AlertDialog, TextButton, SnackBar,
    Switch, RadioGroup, Radio, ScrollMode, MainAxisAlignment,
    CrossAxisAlignment, FontWeight, border, margin, padding,
    ThemeMode, ButtonStyle, BorderSide
)
from flet import Icons, Colors  # Neue Flet-Version
import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
import threading
import time
import mimetypes
import hashlib
import logging

# Conditional requests import
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Gemini API
GEMINI_AVAILABLE = REQUESTS_AVAILABLE  # Uses requests


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

        Returns: Dict[source_column, target_field]
        """
        # Erstelle Beschreibung der Zielfelder
        target_descriptions = []
        for field_key, field_info in target_fields.items():
            label = field_info.get("label", field_key)
            field_type = field_info.get("type", "Text")
            required = "PFLICHT" if field_info.get("required") else ""
            target_descriptions.append(f"- {field_key}: {label} ({field_type}) {required}")

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
5. Typische Mappings:
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


# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== DATENMODELLE ====================

@dataclass
class ERPNextConfig:
    """ERPNext API Konfiguration"""
    base_url: str = "https://erp.example.com"
    api_key: str = ""
    api_secret: str = ""
    company: str = "Kreckler GmbH"
    default_warehouse: str = "Lager - KG"
    default_price_list: str = "Standard-Verkauf"
    default_item_group: str = "Alle Artikelgruppen"
    # Gemini AI
    gemini_api_key: str = ""

    @property
    def auth_header(self) -> Dict[str, str]:
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }


@dataclass
class FieldMapping:
    """Einzelne Feld-Zuordnung"""
    source_column: str
    target_field: str
    transform: str = "none"
    default_value: str = ""


@dataclass
class ImportTemplate:
    """Import-Vorlage"""
    name: str
    import_type: str
    file_format: str
    mappings: List[FieldMapping] = field(default_factory=list)
    csv_delimiter: str = ";"
    csv_encoding: str = "utf-8"
    skip_first_row: bool = True
    created_at: str = ""
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "import_type": self.import_type,
            "file_format": self.file_format,
            "mappings": [asdict(m) for m in self.mappings],
            "csv_delimiter": self.csv_delimiter,
            "csv_encoding": self.csv_encoding,
            "skip_first_row": self.skip_first_row,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ImportTemplate":
        mappings = [FieldMapping(**m) for m in data.get("mappings", [])]
        return cls(
            name=data.get("name", ""),
            import_type=data.get("import_type", "artikel"),
            file_format=data.get("file_format", "csv"),
            mappings=mappings,
            csv_delimiter=data.get("csv_delimiter", ";"),
            csv_encoding=data.get("csv_encoding", "utf-8"),
            skip_first_row=data.get("skip_first_row", True),
            created_at=data.get("created_at", "")
        )


@dataclass
class JTLArtikel:
    """JTL Artikel Datenstruktur"""
    artikelnummer: str
    artikelname: str = ""
    kurzbeschreibung: str = ""
    beschreibung: str = ""
    gtin: str = ""
    han: str = ""
    vater_artikel_id: str = ""
    netto_vk: float = 0.0
    brutto_vk: float = 0.0
    steuersatz: float = 19.0
    hersteller: str = ""
    kategorie_pfad: List[str] = field(default_factory=list)
    ist_vaterartikel: bool = False
    artikel_aktiv: bool = True
    # SEO
    titel_tag: str = ""
    meta_description: str = ""
    meta_keywords: str = ""
    url_pfad: str = ""
    lieferstatus: str = ""
    # Maße
    laenge: float = 0.0
    breite: float = 0.0
    hoehe: float = 0.0
    versandgewicht: float = 0.0
    # Varianten
    varianten_attribut: str = ""


@dataclass
class JTLKategorie:
    """JTL Kategorie Datenstruktur"""
    name: str
    pfad: str = ""
    url_pfad: str = ""
    beschreibung: str = ""
    titel_tag: str = ""
    meta_description: str = ""
    meta_keywords: str = ""


# ==================== ERPNext FELDER ====================

ERPNEXT_ITEM_FIELDS = {
    # Stammdaten
    "item_code": {"label": "Artikelnummer*", "type": "Data", "required": True},
    "item_name": {"label": "Artikelname*", "type": "Data", "required": True},
    "item_group": {"label": "Artikelgruppe", "type": "Link"},
    # Kategorie-Hierarchie-Felder (für mehrstufige Kategorien)
    "category_level_1": {"label": "Kategorie Ebene 1", "type": "Data", "hierarchy": True},
    "category_level_2": {"label": "Kategorie Ebene 2", "type": "Data", "hierarchy": True},
    "category_level_3": {"label": "Kategorie Ebene 3", "type": "Data", "hierarchy": True},
    "category_level_4": {"label": "Kategorie Ebene 4", "type": "Data", "hierarchy": True},
    "category_path": {"label": "Kategoriepfad (z.B. A > B > C)", "type": "Data", "hierarchy": True},
    "description": {"label": "Beschreibung", "type": "Text Editor"},
    "description_html": {"label": "Beschreibung (HTML)", "type": "Text Editor"},
    "stock_uom": {"label": "Lagereinheit", "type": "Link", "default": "Stk"},
    "is_stock_item": {"label": "Lagerartikel", "type": "Check"},
    "disabled": {"label": "Deaktiviert", "type": "Check"},
    # Preise
    "standard_rate": {"label": "Standardpreis (Netto)", "type": "Currency"},
    "standard_rate_brutto": {"label": "VK Brutto", "type": "Currency", "transform": "brutto_to_netto"},
    "valuation_rate": {"label": "Einkaufspreis", "type": "Currency"},
    # Barcodes/EAN
    "gtin": {"label": "GTIN/EAN", "type": "Data"},
    "barcode": {"label": "Barcode (für Barcode-Tabelle)", "type": "Data", "special": "barcode"},
    # Hersteller
    "manufacturer_part_no": {"label": "Herstellerartikelnr.", "type": "Data"},
    "brand": {"label": "Marke/Hersteller", "type": "Link"},
    "manufacturer": {"label": "Hersteller", "type": "Link"},
    # Maße & Gewicht
    "weight_per_unit": {"label": "Gewicht (kg)", "type": "Float"},
    "item_length": {"label": "Länge (cm)", "type": "Float"},
    "item_width": {"label": "Breite (cm)", "type": "Float"},
    "item_height": {"label": "Höhe (cm)", "type": "Float"},
    # Zoll & Herkunft
    "country_of_origin": {"label": "Herkunftsland", "type": "Link"},
    "customs_tariff_number": {"label": "Zolltarifnummer", "type": "Data"},
    # SEO
    "seo_title": {"label": "SEO Titel", "type": "Data"},
    "seo_meta_description": {"label": "SEO Meta-Beschreibung", "type": "Small Text"},
    "seo_keywords": {"label": "SEO Keywords", "type": "Data"},
    "seo_url_slug": {"label": "SEO URL Slug", "type": "Data"},
    # Lieferzeit & Webshop
    "delivery_time": {"label": "Lieferzeit", "type": "Data"},
    "show_in_website": {"label": "Im Webshop anzeigen", "type": "Check"},
    # Varianten
    "has_variants": {"label": "Hat Varianten", "type": "Check"},
    "variant_of": {"label": "Variante von", "type": "Link"},
    # JTL Custom Fields (jattr_*)
    "jattr_farbe": {"label": "Attribut: Farbe", "type": "Data", "jattr": True},
    "jattr_material": {"label": "Attribut: Material", "type": "Data", "jattr": True},
    "jattr_groesse": {"label": "Attribut: Größe", "type": "Data", "jattr": True},
    "jattr_regalsystem": {"label": "Attribut: Regalsystem", "type": "Data", "jattr": True},
    "jattr_fachlast": {"label": "Attribut: Fachlast", "type": "Data", "jattr": True},
    "jattr_feldlast": {"label": "Attribut: Feldlast", "type": "Data", "jattr": True},
    "jattr_gesamtbreite_mm": {"label": "Attribut: Gesamtbreite (mm)", "type": "Data", "jattr": True},
    "jattr_gesamthoehe_mm": {"label": "Attribut: Gesamthöhe (mm)", "type": "Data", "jattr": True},
    "jattr_bauweise": {"label": "Attribut: Bauweise", "type": "Data", "jattr": True},
    "jattr_bodentyp": {"label": "Attribut: Bodentyp", "type": "Data", "jattr": True},
    "jattr_anzahl_boeden": {"label": "Attribut: Anzahl Böden", "type": "Data", "jattr": True},
    # Dynamische JTL-Attribute (werden bei Import automatisch erkannt)
    "jattr_custom": {"label": "Dynamisches JTL-Attribut", "type": "Data", "jattr": True, "dynamic": True},
}

ERPNEXT_ITEM_GROUP_FIELDS = {
    "item_group_name": {"label": "Kategoriename*", "type": "Data", "required": True},
    "parent_item_group": {"label": "Oberkategorie", "type": "Link"},
    "description": {"label": "Beschreibung", "type": "Text"},
    "seo_title": {"label": "SEO Title", "type": "Data"},
    "seo_meta_description": {"label": "SEO Meta Description", "type": "Small Text"},
    "seo_keywords": {"label": "SEO Keywords", "type": "Data"},
}

# Felder für Attribut-Import
ERPNEXT_ATTRIBUTE_FIELDS = {
    "attribute_name": {"label": "Attribut-Name*", "type": "Data", "required": True},
    "attribute_values": {"label": "Attributwerte (kommagetrennt)", "type": "Data"},
    "numeric_values": {"label": "Numerische Werte", "type": "Check"},
    "from_range": {"label": "Von (Bereich)", "type": "Float"},
    "to_range": {"label": "Bis (Bereich)", "type": "Float"},
    "increment": {"label": "Schrittweite", "type": "Float"},
}

# Felder für Varianten-Import
ERPNEXT_VARIANT_FIELDS = {
    "item_code": {"label": "Varianten-Artikelnr.*", "type": "Data", "required": True},
    "variant_of": {"label": "Vorlagenartikel*", "type": "Link", "required": True},
    "item_name": {"label": "Variantenname", "type": "Data"},
    "attribute_color": {"label": "Attribut: Farbe", "type": "Data"},
    "attribute_size": {"label": "Attribut: Größe", "type": "Data"},
    "attribute_material": {"label": "Attribut: Material", "type": "Data"},
    "attribute_1": {"label": "Attribut 1 (Name:Wert)", "type": "Data"},
    "attribute_2": {"label": "Attribut 2 (Name:Wert)", "type": "Data"},
    "attribute_3": {"label": "Attribut 3 (Name:Wert)", "type": "Data"},
    "standard_rate": {"label": "Preis", "type": "Currency"},
    "gtin": {"label": "GTIN/EAN", "type": "Data"},
}

# Auto-Mapping Regeln (JTL-Ameise kompatibel)
AUTO_MAPPING_RULES = {
    # ==================== ARTIKEL STAMMDATEN ====================
    "artikelnummer": "item_code",
    "artikelname": "item_name",
    "artikel-nr": "item_code",
    "artikel-name": "item_name",
    "sku": "item_code",
    "name": "item_name",
    "bezeichnung": "item_name",
    "produktname": "item_name",
    # Beschreibungen
    "beschreibung": "description",
    "beschreibung (html)": "description",
    "kurzbeschreibung": "description",
    "langbeschreibung": "description",
    "artikelbeschreibung": "description",
    # Aktiv-Status
    "aktiv": "disabled",  # Wird invertiert beim Import
    "artikel aktiv": "disabled",
    "deaktiviert": "disabled",

    # ==================== PREISE ====================
    "preis": "standard_rate",
    "vk netto": "standard_rate",
    "vk_netto": "standard_rate",
    "netto_vk": "standard_rate",
    "netto-vk": "standard_rate",
    "verkaufspreis": "standard_rate",
    "verkaufspreis netto": "standard_rate",
    "vk brutto": "standard_rate_brutto",
    "vk_brutto": "standard_rate_brutto",
    "brutto_vk": "standard_rate_brutto",
    "verkaufspreis brutto": "standard_rate_brutto",
    "ek netto": "valuation_rate",
    "ek_netto": "valuation_rate",
    "einkaufspreis": "valuation_rate",
    "einkaufspreis netto": "valuation_rate",

    # ==================== EAN/GTIN/BARCODE ====================
    "ean": "barcode",
    "ean/gtin": "barcode",
    "gtin": "barcode",
    "barcode": "barcode",
    "upc": "barcode",
    "isbn": "barcode",

    # ==================== HERSTELLER ====================
    "han": "manufacturer_part_no",
    "herstellerartikelnummer": "manufacturer_part_no",
    "hersteller-artikelnummer": "manufacturer_part_no",
    "hersteller artikelnummer": "manufacturer_part_no",
    "hersteller": "brand",
    "marke": "brand",
    "brand": "brand",
    "manufacturer": "brand",

    # ==================== GEWICHT & MAßE ====================
    "gewicht": "weight_per_unit",
    "artikelgewicht": "weight_per_unit",
    "versandgewicht": "weight_per_unit",
    "gewicht (kg)": "weight_per_unit",
    "laenge": "item_length",
    "länge": "item_length",
    "länge (cm)": "item_length",
    "breite": "item_width",
    "breite (cm)": "item_width",
    "hoehe": "item_height",
    "höhe": "item_height",
    "höhe (cm)": "item_height",

    # ==================== KATEGORIEN (JTL-Hierarchie) ====================
    "warengruppe": "item_group",
    "kategorie": "item_group",
    "artikelgruppe": "item_group",
    # Kategorie-Hierarchie Auto-Mapping (JTL-Ameise Format)
    "kategorie ebene 1": "category_level_1",
    "kategorie ebene 2": "category_level_2",
    "kategorie ebene 3": "category_level_3",
    "kategorie ebene 4": "category_level_4",
    "kategorie (ebene 1)": "category_level_1",
    "kategorie (ebene 2)": "category_level_2",
    "kategorie (ebene 3)": "category_level_3",
    "kategorie (ebene 4)": "category_level_4",
    "kategorie_ebene_1": "category_level_1",
    "kategorie_ebene_2": "category_level_2",
    "kategorie_ebene_3": "category_level_3",
    "kategorie_ebene_4": "category_level_4",
    "category level 1": "category_level_1",
    "category level 2": "category_level_2",
    "category level 3": "category_level_3",
    "category level 4": "category_level_4",
    "kategoriepfad": "category_path",
    "kategorie_pfad": "category_path",
    "category_path": "category_path",
    "hauptkategorie": "category_level_1",
    "unterkategorie": "category_level_2",

    # ==================== ZOLL & HERKUNFT ====================
    "herkunftsland": "country_of_origin",
    "ursprungsland": "country_of_origin",
    "taric": "customs_tariff_number",
    "taric-code": "customs_tariff_number",
    "zolltarifnummer": "customs_tariff_number",
    "zolltarif": "customs_tariff_number",

    # ==================== SEO (JTL-Ameise Format) ====================
    "seo titel": "seo_title",
    "seo-titel": "seo_title",
    "titel_tag": "seo_title",
    "titel-tag (seo)": "seo_title",
    "seo_title": "seo_title",
    "meta_title": "seo_title",
    "meta title": "seo_title",
    "seo beschreibung": "seo_meta_description",
    "seo-beschreibung": "seo_meta_description",
    "meta_description": "seo_meta_description",
    "meta description": "seo_meta_description",
    "meta-description (seo)": "seo_meta_description",
    "seo_description": "seo_meta_description",
    "seo keywords": "seo_keywords",
    "seo-keywords": "seo_keywords",
    "meta_keywords": "seo_keywords",
    "meta keywords": "seo_keywords",
    "meta-keywords (seo)": "seo_keywords",
    "suchbegriffe": "seo_keywords",
    "url pfad": "seo_url_slug",
    "url-pfad": "seo_url_slug",
    "url_pfad": "seo_url_slug",
    "url_slug": "seo_url_slug",
    "seo url": "seo_url_slug",

    # ==================== LIEFERZEIT ====================
    "lieferstatus": "delivery_time",
    "lieferzeit": "delivery_time",
    "lieferzeit text": "delivery_time",

    # ==================== JTL ATTRIBUTE (jattr_*) ====================
    "farbe": "jattr_farbe",
    "material": "jattr_material",
    "größe": "jattr_groesse",
    "groesse": "jattr_groesse",
    "regalsystem": "jattr_regalsystem",
    "fachlast": "jattr_fachlast",
    "feldlast": "jattr_feldlast",
    "gesamtbreite": "jattr_gesamtbreite_mm",
    "gesamtbreite (mm)": "jattr_gesamtbreite_mm",
    "gesamthöhe": "jattr_gesamthoehe_mm",
    "gesamthöhe (mm)": "jattr_gesamthoehe_mm",
    "bauweise": "jattr_bauweise",
    "bodentyp": "jattr_bodentyp",
    "anzahl böden": "jattr_anzahl_boeden",
    "anzahl boeden": "jattr_anzahl_boeden",

    # ==================== VARIANTEN ====================
    "ist vaterartikel": "has_variants",
    "vaterartikel": "has_variants",
    "identifizierungsspalte vaterartikel": "variant_of",
    "variante von": "variant_of",

    # ==================== LAGER ====================
    "lagerbestand": "opening_stock",
    "bestand": "opening_stock",
    "verfügbar": "opening_stock",

    # ==================== KATEGORIEN (Item Group Import) ====================
    "kategoriename": "item_group_name",
    "oberkategorie": "parent_item_group",
}


# ==================== BMECat PARSER ====================

class BMECatParser:
    """Parser für BMECat XML Format"""
    
    def __init__(self):
        self.products = []
        self.categories = []
    
    def parse(self, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """Parst BMECat XML"""
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        ns = self._detect_namespace(root)
        self.products = []
        self.categories = []
        
        # Produkte
        for article in root.iter():
            if article.tag.endswith('ARTICLE'):
                product = self._parse_article(article, ns)
                if product:
                    self.products.append(product)
        
        return self.products, self.categories
    
    def _detect_namespace(self, root) -> str:
        tag = root.tag
        if '{' in tag:
            return tag[tag.find('{'):tag.find('}')+1]
        return ''
    
    def _get_text(self, element, path: str, ns: str, default: str = "") -> str:
        if element is None:
            return default
        
        # Suche mit und ohne Namespace
        for search_path in [f'{ns}{path}', path, f'.//{ns}{path}', f'.//{path}']:
            el = element.find(search_path)
            if el is not None and el.text:
                return el.text.strip()
        return default
    
    def _parse_article(self, article, ns: str) -> Optional[Dict]:
        try:
            # Suche nach Details-Elementen
            details = None
            prices = None
            
            for child in article:
                if child.tag.endswith('ARTICLE_DETAILS'):
                    details = child
                elif child.tag.endswith('ARTICLE_PRICE_DETAILS'):
                    prices = child
            
            supplier_aid = self._get_text(article, 'SUPPLIER_AID', ns)
            
            product = {
                "artikelnummer": supplier_aid,
                "artikelname": self._get_text(details, 'DESCRIPTION_SHORT', ns) if details else "",
                "beschreibung": self._get_text(details, 'DESCRIPTION_LONG', ns) if details else "",
                "ean": self._get_text(details, 'EAN', ns) if details else "",
                "han": self._get_text(details, 'MANUFACTURER_AID', ns) if details else "",
                "hersteller": self._get_text(details, 'MANUFACTURER_NAME', ns) if details else "",
            }
            
            # Preise
            if prices:
                for price_el in prices:
                    if price_el.tag.endswith('ARTICLE_PRICE'):
                        product["preis"] = self._get_text(price_el, 'PRICE_AMOUNT', ns)
                        break
            
            return product if product.get("artikelnummer") else None
            
        except Exception as e:
            logger.error(f"BMECat Parse Error: {e}")
            return None
    
    def get_columns(self) -> List[str]:
        if self.products:
            return list(self.products[0].keys())
        return []


# ==================== ERPNext API CLIENT ====================

class ERPNextAPI:
    """ERPNext REST API Client - Vollständige Implementation"""
    
    def __init__(self, config: ERPNextConfig):
        self.config = config
        self.session = self._create_session() if REQUESTS_AVAILABLE else None
        self._item_cache: Dict[str, str] = {}
        self._item_group_cache: Dict[str, str] = {}
        self._attribute_cache: Dict[str, bool] = {}
    
    def _create_session(self):
        if not REQUESTS_AVAILABLE:
            return None
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(self.config.auth_header)
        return session
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Führt API-Request aus"""
        if not self.session:
            raise Exception("requests library not available")
        
        url = f"{self.config.base_url}/api/resource/{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, params=data, timeout=30)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=30)
            elif method == "PUT":
                response = self.session.put(url, json=data, timeout=30)
            elif method == "DELETE":
                response = self.session.delete(url, timeout=30)
            else:
                raise ValueError(f"Unknown HTTP method: {method}")
            
            response.raise_for_status()
            return response.json() if response.text else {}
            
        except Exception as e:
            logger.error(f"API Error {method} {endpoint}: {e}")
            raise
    
    def _call_method(self, method_name: str, data: Optional[Dict] = None,
                     files: Optional[Dict] = None) -> Dict:
        """Ruft Frappe-Methode auf"""
        if not self.session:
            raise Exception("requests library not available")
        
        url = f"{self.config.base_url}/api/method/{method_name}"
        
        try:
            if files:
                headers = {"Authorization": self.config.auth_header["Authorization"]}
                response = self.session.post(url, data=data, files=files, headers=headers, timeout=60)
            else:
                response = self.session.post(url, json=data, timeout=30)
            
            response.raise_for_status()
            return response.json() if response.text else {}
        except Exception as e:
            logger.error(f"Method Error {method_name}: {e}")
            raise
    
    def test_connection(self) -> Tuple[bool, str]:
        """Testet API-Verbindung"""
        if not REQUESTS_AVAILABLE:
            return False, "requests library not installed"
        
        try:
            url = f"{self.config.base_url}/api/method/frappe.auth.get_logged_user"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return True, f"Verbunden als: {data.get('message', 'OK')}"
            return False, f"Status {response.status_code}"
        except Exception as e:
            return False, str(e)
    
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
            # Pflichtfelder sicherstellen
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
            
            # GTIN als Barcode
            if "gtin" in data and data["gtin"]:
                gtin = data.pop("gtin")
                if gtin and gtin != "4017980000000":
                    data["barcodes"] = [{
                        "barcode": gtin,
                        "barcode_type": "EAN" if len(str(gtin)) == 13 else "UPC-A"
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
            # Nicht-aktualisierbare Felder entfernen
            data.pop("item_code", None)
            data.pop("doctype", None)
            data.pop("gtin", None)  # Barcodes separat
            
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

            # Prüfen ob existiert
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
        """
        Erstellt Kategorie-Hierarchie und gibt die unterste Kategorie zurück.

        Args:
            levels: Liste der Kategorie-Ebenen von oben nach unten
                    z.B. ["Elektronik", "Computer", "Laptops"]
            log_callback: Optional callback für Log-Ausgaben

        Returns:
            Name der untersten (tiefsten) Kategorie für item_group
        """
        if not levels:
            return self.config.default_item_group

        # Leere Einträge filtern
        levels = [l.strip() for l in levels if l and l.strip()]
        if not levels:
            return self.config.default_item_group

        parent = self.config.default_item_group
        last_category = parent

        for level_name in levels:
            # Prüfen ob Kategorie existiert
            existing = self.get_item_group(level_name)

            if existing:
                # Kategorie existiert bereits
                last_category = level_name
                parent = level_name
                if log_callback:
                    log_callback(f"Kategorie existiert: {level_name}")
            else:
                # Kategorie erstellen mit parent_item_group
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
                    # Bei Fehler trotzdem versuchen fortzufahren
                    break

        return last_category

    def parse_category_path(self, path: str, separator: str = ">") -> List[str]:
        """
        Parst einen Kategorie-Pfad-String in einzelne Ebenen.

        Args:
            path: z.B. "Elektronik > Computer > Laptops" oder "Elektronik/Computer/Laptops"
            separator: Trennzeichen (Standard: ">")

        Returns:
            Liste der Ebenen: ["Elektronik", "Computer", "Laptops"]
        """
        if not path:
            return []

        # Verschiedene Trennzeichen unterstützen
        for sep in [" > ", " -> ", " >> ", " / ", "/", ">", "|"]:
            if sep in path:
                return [p.strip() for p in path.split(sep) if p.strip()]

        # Kein Trennzeichen gefunden - einzelne Kategorie
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
            # Hole alle Attachments
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
            
            # Bild-Feld leeren
            self._make_request("PUT", f"Item/{item_code}", {"image": ""})
            
            return True, f"{deleted} Anhänge gelöscht"
        except Exception as e:
            return False, str(e)
    
    # ==================== ITEM ATTRIBUTES (Varianten) ====================
    
    def get_or_create_attribute(self, name: str, values: List[str] = None) -> Tuple[bool, str]:
        """Erstellt oder aktualisiert Item Attribute"""
        try:
            # Prüfen ob existiert
            try:
                result = self._make_request("GET", f"Item Attribute/{name}")
                if result.get("data"):
                    # Werte hinzufügen falls nötig
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
            
            # Neu erstellen
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

            # Vollständige Daten holen wenn nötig
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

    def export_item_prices(self, price_list: str = None, limit: int = 0) -> List[Dict]:
        """Exportiert Preise"""
        try:
            fields = ["name", "item_code", "item_name", "price_list",
                     "price_list_rate", "currency", "valid_from", "valid_upto"]
            params = {
                "fields": json.dumps(fields),
                "limit_page_length": limit if limit > 0 else 0
            }

            if price_list:
                params["filters"] = json.dumps([["price_list", "=", price_list]])

            result = self._make_request("GET", "Item Price", params)
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Export Prices Error: {e}")
            return []

    def export_stock_levels(self, warehouse: str = None, limit: int = 0) -> List[Dict]:
        """Exportiert Lagerbestände"""
        try:
            fields = ["name", "item_code", "warehouse", "actual_qty",
                     "reserved_qty", "projected_qty", "valuation_rate"]
            params = {
                "fields": json.dumps(fields),
                "limit_page_length": limit if limit > 0 else 0
            }

            if warehouse:
                params["filters"] = json.dumps([["warehouse", "=", warehouse]])

            result = self._make_request("GET", "Bin", params)
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Export Stock Error: {e}")
            return []

    def export_attributes(self, limit: int = 0) -> List[Dict]:
        """Exportiert Item Attributes"""
        try:
            fields = ["name", "attribute_name", "numeric_values",
                     "from_range", "to_range", "increment"]
            params = {
                "fields": json.dumps(fields),
                "limit_page_length": limit if limit > 0 else 0
            }

            result = self._make_request("GET", "Item Attribute", params)
            attributes = result.get("data", [])

            # Hole Attributwerte für jedes Attribut
            for attr in attributes:
                try:
                    full_data = self._make_request("GET", f"Item Attribute/{attr['name']}")
                    attr_data = full_data.get("data", {})
                    # Extrahiere Attributwerte
                    values = attr_data.get("item_attribute_values", [])
                    attr["attribute_values"] = ", ".join([v.get("attribute_value", "") for v in values])
                except:
                    attr["attribute_values"] = ""

            return attributes
        except Exception as e:
            logger.error(f"Export Attributes Error: {e}")
            return []

    # ==================== ATTRIBUT & VARIANTEN IMPORT ====================

    def create_attribute(self, attribute_name: str, values: List[str] = None,
                        numeric: bool = False, from_range: float = None,
                        to_range: float = None, increment: float = None) -> Tuple[bool, str]:
        """Erstellt ein Item Attribute"""
        try:
            data = {
                "attribute_name": attribute_name,
                "numeric_values": 1 if numeric else 0,
            }

            if numeric and from_range is not None:
                data["from_range"] = from_range
                data["to_range"] = to_range or 100
                data["increment"] = increment or 1
            elif values:
                data["item_attribute_values"] = [
                    {"attribute_value": v.strip(), "abbr": v.strip()[:3].upper()}
                    for v in values if v.strip()
                ]

            self._make_request("POST", "Item Attribute", data)
            return True, f"Attribut '{attribute_name}' erstellt"
        except Exception as e:
            # Prüfe ob bereits existiert
            if "DuplicateEntryError" in str(e) or "already exists" in str(e).lower():
                return True, f"Attribut '{attribute_name}' existiert bereits"
            return False, str(e)

    def add_attribute_value(self, attribute_name: str, value: str) -> Tuple[bool, str]:
        """Fügt einen Wert zu einem bestehenden Attribut hinzu"""
        try:
            # Hole aktuelle Werte
            result = self._make_request("GET", f"Item Attribute/{attribute_name}")
            attr_data = result.get("data", {})
            current_values = attr_data.get("item_attribute_values", [])

            # Prüfe ob Wert bereits existiert
            existing = [v.get("attribute_value", "").lower() for v in current_values]
            if value.lower() in existing:
                return True, f"Wert '{value}' existiert bereits"

            # Füge neuen Wert hinzu
            current_values.append({
                "attribute_value": value,
                "abbr": value[:3].upper()
            })

            self._make_request("PUT", f"Item Attribute/{attribute_name}", {
                "item_attribute_values": current_values
            })
            return True, f"Wert '{value}' zu '{attribute_name}' hinzugefügt"
        except Exception as e:
            return False, str(e)

    def create_variant(self, template_item: str, variant_code: str,
                      attributes: Dict[str, str], item_name: str = None,
                      additional_data: Dict = None) -> Tuple[bool, str]:
        """Erstellt eine Artikelvariante"""
        try:
            # Prüfe ob Template existiert und has_variants=1 hat
            template = self._make_request("GET", f"Item/{template_item}")
            template_data = template.get("data", {})

            if not template_data.get("has_variants"):
                return False, f"Artikel '{template_item}' ist keine Variantenvorlage"

            # Varianten-Daten
            data = {
                "item_code": variant_code,
                "variant_of": template_item,
                "item_name": item_name or f"{template_data.get('item_name', '')} - {' / '.join(attributes.values())}",
                "attributes": [
                    {"attribute": attr_name, "attribute_value": attr_value}
                    for attr_name, attr_value in attributes.items()
                ]
            }

            if additional_data:
                data.update(additional_data)

            self._make_request("POST", "Item", data)
            return True, f"Variante '{variant_code}' erstellt"
        except Exception as e:
            if "DuplicateEntryError" in str(e):
                return True, f"Variante '{variant_code}' existiert bereits"
            return False, str(e)

    def setup_template_attributes(self, item_code: str, attribute_names: List[str]) -> Tuple[bool, str]:
        """Fügt Attribute zu einem Vorlagenartikel hinzu"""
        try:
            # Hole aktuellen Artikel
            result = self._make_request("GET", f"Item/{item_code}")
            item_data = result.get("data", {})

            # Setze has_variants und Attribute
            update_data = {
                "has_variants": 1,
                "attributes": [{"attribute": attr} for attr in attribute_names]
            }

            self._make_request("PUT", f"Item/{item_code}", update_data)
            return True, f"Attribute zu '{item_code}' hinzugefügt"
        except Exception as e:
            return False, str(e)

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


# ==================== EXPORT FELDER ====================

EXPORT_ITEM_FIELDS = {
    # Stammdaten
    "item_code": "Artikelnummer",
    "item_name": "Artikelname",
    "item_group": "Artikelgruppe",
    "description": "Beschreibung",
    "stock_uom": "Lagereinheit",
    "is_stock_item": "Lagerartikel",
    "standard_rate": "Standardpreis",
    "valuation_rate": "Einkaufspreis",
    "brand": "Marke/Hersteller",
    "manufacturer_part_no": "Herstellerartikelnr.",
    "gtin": "GTIN/EAN",
    # Maße & Gewicht
    "weight_per_unit": "Gewicht (kg)",
    "weight_uom": "Gewichtseinheit",
    "item_length": "Länge (cm)",
    "item_width": "Breite (cm)",
    "item_height": "Höhe (cm)",
    # Zoll & Herkunft
    "country_of_origin": "Herkunftsland",
    "customs_tariff_number": "Zolltarifnummer",
    # SEO Felder
    "seo_title": "SEO Title",
    "seo_meta_description": "SEO Meta Description",
    "seo_keywords": "SEO Keywords",
    "seo_url_slug": "SEO URL Slug",
    # Webshop
    "delivery_time": "Lieferzeit",
    "website_item_name": "Webshop-Name",
    "web_long_description": "Webshop Langbeschreibung",
    "show_in_website": "Im Webshop anzeigen",
    # Varianten & Attribute
    "has_variants": "Hat Varianten",
    "variant_of": "Variante von",
    "variant_based_on": "Varianten basiert auf",
    "attributes": "Attribute (JSON)",
    # Status
    "is_sales_item": "Verkaufsartikel",
    "is_purchase_item": "Einkaufsartikel",
    "disabled": "Deaktiviert",
    "image": "Bild-URL",
    "creation": "Erstellt am",
    "modified": "Geändert am",
}

# Export-Felder für Attribute
EXPORT_ATTRIBUTE_FIELDS = {
    "name": "Attribut-Name",
    "attribute_name": "Attribut-Bezeichnung",
    "numeric_values": "Numerische Werte",
    "from_range": "Von (Bereich)",
    "to_range": "Bis (Bereich)",
    "increment": "Schrittweite",
    "item_attribute_values": "Attributwerte (JSON)",
}


# ==================== HAUPTANWENDUNG ====================

class ERPNextImporterApp:
    """Haupt-Anwendungsklasse"""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.config = ERPNextConfig()
        self.api: Optional[ERPNextAPI] = None
        self.gemini: Optional[GeminiAPI] = None
        self.current_template: Optional[ImportTemplate] = None

        # Daten
        self.source_file: Optional[str] = None
        self.source_data: List[Dict] = []
        self.source_columns: List[str] = []
        self.field_mappings: Dict[str, FieldMapping] = {}
        
        # Image folder
        self.image_folder: Optional[str] = None
        self.image_files: List[str] = []
        
        # File Pickers
        self.file_picker = FilePicker(on_result=self.on_file_picked)
        self.image_folder_picker = FilePicker(on_result=self.on_image_folder_picked)
        self.template_picker = FilePicker(on_result=self.on_template_loaded)
        
        self.page.overlay.extend([
            self.file_picker,
            self.image_folder_picker,
            self.template_picker
        ])
        
        # Log
        self.log_entries: List[str] = []
        
        # Import State
        self.is_importing = False
        
        # Setup
        self.setup_page()
        self.build_ui()
        self.load_config()
        # Initial update nach UI-Aufbau
        try:
            self.page.update()
        except:
            pass
    
    def setup_page(self):
        """Konfiguriert die Seite"""
        self.page.title = "ERPNext Produkt-Importer"
        self.page.theme_mode = ThemeMode.DARK
        self.page.padding = 20
        self.page.scroll = ScrollMode.AUTO
        self.page.window.width = 1400
        self.page.window.height = 900
    
    def build_ui(self):
        """Baut die UI"""
        
        # Header
        header = Container(
            content=Row([
                ft.Icon(Icons.INVENTORY_2, size=40, color=Colors.BLUE_400),
                Column([
                    Text("ERPNext Produkt-Importer", size=28, weight=FontWeight.BOLD),
                    Text("Import & Export wie JTL-Ameise", size=14, color=Colors.GREY_400)
                ], spacing=0),
                Container(expand=True),
                self._build_connection_status(),
            ], alignment=MainAxisAlignment.START),
            margin=margin.only(bottom=20)
        )
        
        # Tabs
        self.tabs = Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                Tab(
                    text="Datenimport",
                    icon=Icons.DOWNLOAD,
                    content=self._build_import_tab()
                ),
                Tab(
                    text="Datenexport",
                    icon=Icons.UPLOAD,
                    content=self._build_export_tab()
                ),
                Tab(
                    text="Feld-Mapping",
                    icon=Icons.SWAP_HORIZ,
                    content=self._build_mapping_tab()
                ),
                Tab(
                    text="Bilder",
                    icon=Icons.IMAGE,
                    content=self._build_images_tab()
                ),
                Tab(
                    text="Einstellungen",
                    icon=Icons.SETTINGS,
                    content=self._build_settings_tab()
                ),
                Tab(
                    text="Protokoll",
                    icon=Icons.LIST_ALT,
                    content=self._build_log_tab()
                ),
            ],
            expand=True,
        )
        
        self.page.add(header, self.tabs)
    
    def _build_connection_status(self) -> Container:
        """Verbindungsstatus"""
        self.connection_icon = ft.Icon(Icons.CIRCLE, size=12, color=Colors.GREY_600)
        self.connection_text = Text("Nicht verbunden", size=12, color=Colors.GREY_400)
        self.connect_button = ElevatedButton(
            "Verbinden",
            icon=Icons.LINK,
            on_click=self.test_connection
        )
        return Row([
            Row([self.connection_icon, self.connection_text], spacing=5),
            self.connect_button
        ], spacing=10)
    
    def _build_import_tab(self) -> Container:
        """Import-Tab"""
        
        # Dateiauswahl
        self.file_path_text = Text("Keine Datei ausgewählt", italic=True, color=Colors.GREY_500)
        self.file_info_text = Text("", size=12)
        
        file_section = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.FOLDER_OPEN, size=20, color=Colors.BLUE_400),
                        Text("Quelldatei", size=18, weight=FontWeight.BOLD),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Row([
                        ElevatedButton(
                            "CSV auswählen",
                            icon=Icons.TABLE_CHART,
                            on_click=lambda _: self.file_picker.pick_files(
                                allowed_extensions=["csv", "txt"],
                                dialog_title="CSV-Datei auswählen"
                            )
                        ),
                        ElevatedButton(
                            "BMECat XML",
                            icon=Icons.CODE,
                            on_click=lambda _: self.file_picker.pick_files(
                                allowed_extensions=["xml"],
                                dialog_title="BMECat XML auswählen"
                            )
                        ),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    self.file_path_text,
                    self.file_info_text,
                ]),
                padding=20
            )
        )
        
        # CSV Optionen
        self.csv_delimiter = Dropdown(
            label="Trennzeichen",
            value=";",
            options=[
                dropdown.Option(";", "Semikolon (;)"),
                dropdown.Option(",", "Komma (,)"),
                dropdown.Option("\t", "Tab"),
                dropdown.Option("|", "Pipe (|)"),
            ],
            width=200,
            on_change=self.reload_file
        )
        
        self.csv_encoding = Dropdown(
            label="Zeichensatz",
            value="utf-8-sig",
            options=[
                dropdown.Option("utf-8-sig", "UTF-8 (BOM)"),
                dropdown.Option("utf-8", "UTF-8"),
                dropdown.Option("cp1252", "Windows-1252"),
                dropdown.Option("iso-8859-1", "ISO-8859-1"),
            ],
            width=200,
            on_change=self.reload_file
        )
        
        self.skip_header = Checkbox(label="Erste Zeile ist Überschrift", value=True)
        
        csv_options = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.TUNE, size=20, color=Colors.BLUE_400),
                        Text("CSV-Optionen", size=18, weight=FontWeight.BOLD),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Row([
                        self.csv_delimiter,
                        self.csv_encoding,
                        self.skip_header,
                    ], spacing=20),
                ]),
                padding=20
            )
        )
        
        # Import-Typ
        self.import_type = RadioGroup(
            content=Column([
                Row([
                    Radio(value="artikel", label="Artikel"),
                    Radio(value="kategorien", label="Kategorien"),
                    Radio(value="preise", label="Nur Preise"),
                ]),
                Row([
                    Radio(value="attribute", label="Attribute"),
                    Radio(value="varianten", label="Varianten"),
                ]),
            ], spacing=5),
            value="artikel",
            on_change=self.on_import_type_changed
        )
        
        # Import-Modus
        self.import_mode = RadioGroup(
            content=Row([
                Radio(value="create", label="Nur neue anlegen"),
                Radio(value="update", label="Nur aktualisieren"),
                Radio(value="upsert", label="Anlegen & Aktualisieren"),
            ]),
            value="upsert"
        )
        
        self.dry_run = Switch(label="Dry Run (nur simulieren)", value=False)
        
        import_options = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.SETTINGS_INPUT_COMPONENT, size=20, color=Colors.BLUE_400),
                        Text("Import-Optionen", size=18, weight=FontWeight.BOLD),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Text("Import-Typ:", weight=FontWeight.BOLD),
                    self.import_type,
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Text("Import-Modus:", weight=FontWeight.BOLD),
                    self.import_mode,
                    Divider(height=10, color=Colors.TRANSPARENT),
                    self.dry_run,
                ]),
                padding=20
            )
        )
        
        # Vorlagen
        template_section = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.BOOKMARK, size=20, color=Colors.BLUE_400),
                        Text("Vorlagen", size=18, weight=FontWeight.BOLD),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Row([
                        ElevatedButton(
                            "Vorlage laden",
                            icon=Icons.FOLDER_OPEN,
                            on_click=lambda _: self.template_picker.pick_files(
                                allowed_extensions=["json"],
                                dialog_title="Vorlage laden"
                            )
                        ),
                        ElevatedButton(
                            "Vorlage speichern",
                            icon=Icons.SAVE,
                            on_click=self.save_template
                        ),
                    ], spacing=10),
                ]),
                padding=20
            )
        )
        
        # Vorschau
        self.preview_table = DataTable(
            columns=[DataColumn(Text("Keine Datei ausgewählt"))],
            rows=[],
            border=border.all(1, Colors.GREY_700),
            heading_row_color=Colors.BLUE_GREY_900,
            heading_row_height=40,
            data_row_min_height=35,
            column_spacing=15,
            horizontal_lines=border.BorderSide(1, Colors.GREY_800),
            show_checkbox_column=False,
        )

        self.preview_column_info = Text("", size=11, color=Colors.GREY_500)

        preview_section = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.PREVIEW, size=20, color=Colors.BLUE_400),
                        Text("Datenvorschau", size=18, weight=FontWeight.BOLD),
                        Container(expand=True),
                        self.preview_column_info,
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Container(
                        content=Row(
                            controls=[self.preview_table],
                            scroll=ScrollMode.ALWAYS,
                        ),
                        height=280,
                        border=border.all(1, Colors.GREY_700),
                        border_radius=5,
                    ),
                ]),
                padding=20,
            )
        )
        
        # Start-Button
        self.start_button = ElevatedButton(
            "Import starten",
            icon=Icons.PLAY_ARROW,
            style=ButtonStyle(
                color=Colors.WHITE,
                bgcolor=Colors.GREEN_700,
                padding=20,
            ),
            on_click=self.start_import,
            disabled=True,
        )
        
        self.progress_bar = ProgressBar(width=600, value=0, visible=False)
        self.progress_text = Text("", size=14)
        
        action_section = Container(
            content=Column([
                Row([
                    self.start_button,
                    Container(expand=True),
                    Column([
                        self.progress_bar,
                        self.progress_text,
                    ], horizontal_alignment=CrossAxisAlignment.END)
                ]),
            ]),
            margin=margin.only(top=20)
        )
        
        return Container(
            content=Column([
                Row([file_section, csv_options], spacing=20),
                Row([import_options, template_section], spacing=20),
                preview_section,
                action_section,
            ], scroll=ScrollMode.AUTO),
            padding=20
        )

    def _build_export_tab(self) -> Container:
        """Export-Tab - wie JTL-Ameise Export"""

        # Export-Typ Auswahl
        self.export_type = RadioGroup(
            content=Column([
                Row([
                    Radio(value="artikel", label="Artikel"),
                    Radio(value="kategorien", label="Kategorien"),
                    Radio(value="preise", label="Preise"),
                ]),
                Row([
                    Radio(value="bestand", label="Lagerbestand"),
                    Radio(value="attribute", label="Attribute"),
                ]),
            ], spacing=5),
            value="artikel",
            on_change=self.on_export_type_changed
        )

        export_type_section = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.INVENTORY_2, size=20, color=Colors.BLUE_400),
                        Text("Export-Typ", size=18, weight=FontWeight.BOLD),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    self.export_type,
                ]),
                padding=20
            )
        )

        # Feldauswahl für Export
        self.export_field_checkboxes = Column(spacing=5)
        self._build_export_field_checkboxes()

        field_section = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.CHECKLIST, size=20, color=Colors.BLUE_400),
                        Text("Felder auswählen", size=18, weight=FontWeight.BOLD),
                        Container(expand=True),
                        ElevatedButton(
                            "Alle",
                            icon=Icons.SELECT_ALL,
                            on_click=self.select_all_export_fields
                        ),
                        ElevatedButton(
                            "Keine",
                            icon=Icons.DESELECT,
                            on_click=self.deselect_all_export_fields
                        ),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Container(
                        content=self.export_field_checkboxes,
                        height=200,
                        border=border.all(1, Colors.GREY_700),
                        border_radius=10,
                        padding=10,
                    ),
                ]),
                padding=20
            )
        )

        # Filter
        self.export_filter_item_code = TextField(
            label="Artikelnummer enthält",
            hint_text="z.B. ART",
            width=200
        )
        self.export_filter_item_name = TextField(
            label="Artikelname enthält",
            hint_text="z.B. Schraube",
            width=200
        )
        self.export_filter_item_group = Dropdown(
            label="Artikelgruppe",
            options=[dropdown.Option("", "-- Alle --")],
            value="",
            width=250
        )
        self.export_filter_brand = TextField(
            label="Marke/Hersteller",
            hint_text="z.B. Bosch",
            width=200
        )
        self.export_limit = TextField(
            label="Max. Anzahl",
            hint_text="0 = alle",
            value="0",
            width=120
        )

        # Preisliste (für Preisexport)
        self.export_price_list = Dropdown(
            label="Preisliste",
            options=[dropdown.Option("", "-- Alle --")],
            value="",
            width=250
        )

        # Lager (für Bestandsexport)
        self.export_warehouse = Dropdown(
            label="Lager",
            options=[dropdown.Option("", "-- Alle --")],
            value="",
            width=250
        )

        filter_section = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.FILTER_LIST, size=20, color=Colors.BLUE_400),
                        Text("Filter", size=18, weight=FontWeight.BOLD),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Row([
                        self.export_filter_item_code,
                        self.export_filter_item_name,
                        self.export_filter_item_group,
                    ], spacing=15),
                    Row([
                        self.export_filter_brand,
                        self.export_price_list,
                        self.export_warehouse,
                        self.export_limit,
                    ], spacing=15),
                ]),
                padding=20
            )
        )

        # Export-Format
        self.export_format = RadioGroup(
            content=Row([
                Radio(value="csv", label="CSV (Semikolon)"),
                Radio(value="csv_comma", label="CSV (Komma)"),
                Radio(value="tsv", label="TSV (Tab)"),
                Radio(value="json", label="JSON"),
            ]),
            value="csv"
        )

        self.export_encoding = Dropdown(
            label="Zeichensatz",
            value="utf-8-sig",
            options=[
                dropdown.Option("utf-8-sig", "UTF-8 (mit BOM, Excel-kompatibel)"),
                dropdown.Option("utf-8", "UTF-8"),
                dropdown.Option("cp1252", "Windows-1252"),
                dropdown.Option("iso-8859-1", "ISO-8859-1"),
            ],
            width=300
        )

        format_section = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.SAVE_ALT, size=20, color=Colors.BLUE_400),
                        Text("Export-Format", size=18, weight=FontWeight.BOLD),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    self.export_format,
                    self.export_encoding,
                ]),
                padding=20
            )
        )

        # Vorschau
        self.export_preview_table = DataTable(
            columns=[DataColumn(Text("Klicke 'Vorschau laden' für Datenvorschau"))],
            rows=[],
            border=border.all(1, Colors.GREY_700),
            heading_row_color=Colors.BLUE_GREY_900,
            heading_row_height=40,
            data_row_min_height=35,
            column_spacing=15,
            horizontal_lines=border.BorderSide(1, Colors.GREY_800),
        )

        self.export_preview_info = Text("", size=11, color=Colors.GREY_500)

        preview_section = Card(
            content=Container(
                content=Column([
                    Row([
                        ft.Icon(Icons.PREVIEW, size=20, color=Colors.BLUE_400),
                        Text("Vorschau", size=18, weight=FontWeight.BOLD),
                        Container(expand=True),
                        self.export_preview_info,
                        ElevatedButton(
                            "Vorschau laden",
                            icon=Icons.REFRESH,
                            on_click=self.load_export_preview
                        ),
                    ], spacing=10),
                    Divider(height=10, color=Colors.TRANSPARENT),
                    Container(
                        content=Row(
                            controls=[self.export_preview_table],
                            scroll=ScrollMode.ALWAYS,
                        ),
                        height=220,
                        border=border.all(1, Colors.GREY_700),
                        border_radius=5,
                    ),
                ]),
                padding=20,
            )
        )

        # Export Button
        self.export_button = ElevatedButton(
            "Export starten",
            icon=Icons.FILE_DOWNLOAD,
            style=ButtonStyle(
                color=Colors.WHITE,
                bgcolor=Colors.BLUE_700,
                padding=20,
            ),
            on_click=self.start_export,
        )

        self.export_progress = ProgressBar(width=500, value=0, visible=False)
        self.export_status = Text("", size=14)

        action_section = Container(
            content=Row([
                self.export_button,
                Column([
                    self.export_progress,
                    self.export_status,
                ], horizontal_alignment=CrossAxisAlignment.END)
            ], spacing=20),
            margin=margin.only(top=20)
        )

        return Container(
            content=Column([
                Row([export_type_section, format_section], spacing=20),
                Row([field_section, filter_section], spacing=20),
                preview_section,
                action_section,
            ], scroll=ScrollMode.AUTO),
            padding=20
        )

    def _build_export_field_checkboxes(self):
        """Erstellt Checkboxen für Export-Felder"""
        self.export_fields_selected: Dict[str, Checkbox] = {}
        self.export_field_checkboxes.controls.clear()

        # Standard-Felder für Artikel
        default_selected = {"item_code", "item_name", "item_group", "standard_rate"}

        row_controls = []
        for field_key, field_label in EXPORT_ITEM_FIELDS.items():
            cb = Checkbox(
                label=field_label,
                value=field_key in default_selected,
            )
            self.export_fields_selected[field_key] = cb
            row_controls.append(Container(content=cb, width=200))

            if len(row_controls) == 3:
                self.export_field_checkboxes.controls.append(
                    Row(row_controls, spacing=10)
                )
                row_controls = []

        if row_controls:
            self.export_field_checkboxes.controls.append(
                Row(row_controls, spacing=10)
            )

    def on_export_type_changed(self, e):
        """Export-Typ geändert"""
        export_type = self.export_type.value

        # Filter-Felder ein/ausblenden
        self.export_price_list.visible = export_type == "preise"
        self.export_warehouse.visible = export_type == "bestand"
        self.export_filter_item_code.visible = export_type in ["artikel", "preise", "bestand"]
        self.export_filter_item_name.visible = export_type == "artikel"
        self.export_filter_item_group.visible = export_type in ["artikel", "kategorien"]
        self.export_filter_brand.visible = export_type == "artikel"

        # Feldauswahl nur für Artikel sichtbar
        if hasattr(self, 'export_field_checkboxes'):
            self.export_field_checkboxes.visible = export_type == "artikel"

        try:
            self.page.update()
        except:
            pass

    def select_all_export_fields(self, e=None):
        """Alle Export-Felder auswählen"""
        for cb in self.export_fields_selected.values():
            cb.value = True
        self.page.update()

    def deselect_all_export_fields(self, e=None):
        """Alle Export-Felder abwählen"""
        for cb in self.export_fields_selected.values():
            cb.value = False
        self.page.update()

    def load_export_preview(self, e=None):
        """Lädt Vorschau der Export-Daten"""
        if not self.api:
            self.log("Keine API-Verbindung!", error=True)
            return

        self.log("Lade Export-Vorschau...")
        export_type = self.export_type.value

        try:
            if export_type == "artikel":
                # Ausgewählte Felder
                fields = ["name"] + [k for k, cb in self.export_fields_selected.items() if cb.value]

                # Filter
                filters = {}
                if self.export_filter_item_code.value:
                    filters["item_code"] = self.export_filter_item_code.value
                if self.export_filter_item_name.value:
                    filters["item_name"] = self.export_filter_item_name.value
                if self.export_filter_item_group.value:
                    filters["item_group"] = self.export_filter_item_group.value

                data = self.api.export_items(fields, filters, limit=10)

            elif export_type == "kategorien":
                data = self.api.export_item_groups(limit=10)

            elif export_type == "preise":
                price_list = self.export_price_list.value or None
                data = self.api.export_item_prices(price_list, limit=10)

            elif export_type == "bestand":
                warehouse = self.export_warehouse.value or None
                data = self.api.export_stock_levels(warehouse, limit=10)

            elif export_type == "attribute":
                data = self.api.export_attributes(limit=10)

            else:
                data = []

            self._update_export_preview(data)
            self.log(f"Vorschau geladen: {len(data)} Datensätze")

        except Exception as ex:
            self.log(f"Fehler beim Laden der Vorschau: {ex}", error=True)

        self.page.update()

    def _update_export_preview(self, data: List[Dict]):
        """Aktualisiert die Export-Vorschau-Tabelle - alle Spalten mit Scroll"""
        if not data:
            self.export_preview_table.columns = [DataColumn(Text("Keine Daten"))]
            self.export_preview_table.rows = []
            if hasattr(self, 'export_preview_info'):
                self.export_preview_info.value = ""
            return

        # Alle Spalten aus erstem Datensatz
        columns = list(data[0].keys())

        # Info-Text aktualisieren
        if hasattr(self, 'export_preview_info'):
            self.export_preview_info.value = f"{len(columns)} Spalten | {len(data)} Datensätze"

        # Spalten erstellen
        self.export_preview_table.columns = []
        for col in columns:
            display_name = col if len(col) <= 18 else col[:16] + "..."
            self.export_preview_table.columns.append(
                DataColumn(
                    Text(display_name, weight=FontWeight.BOLD, size=10, color=Colors.BLUE_200)
                )
            )

        rows = []
        for row_data in data[:10]:
            cells = []
            for col in columns:
                value = str(row_data.get(col, ""))
                display_value = value if len(value) <= 30 else value[:27] + "..."
                cells.append(DataCell(Text(display_value, size=9)))
            rows.append(DataRow(cells=cells))

        self.export_preview_table.rows = rows

    def start_export(self, e=None):
        """Startet den Export"""
        if not self.api:
            self.log("Keine API-Verbindung!", error=True)
            return

        self.export_button.disabled = True
        self.export_progress.visible = True
        self.export_progress.value = None  # Indeterminate
        self.export_status.value = "Exportiere..."
        self.page.update()

        thread = threading.Thread(target=self._run_export)
        thread.start()

    def _run_export(self):
        """Export-Thread"""
        export_type = self.export_type.value
        export_format = self.export_format.value
        encoding = self.export_encoding.value

        try:
            limit = int(self.export_limit.value or "0")
        except:
            limit = 0

        self.log(f"=== Export gestartet: {export_type} ===")

        try:
            # Daten holen
            def progress_callback(current, total):
                self.export_status.value = f"Lade {current}/{total}..."
                try:
                    self.page.update()
                except:
                    pass

            if export_type == "artikel":
                fields = ["name"] + [k for k, cb in self.export_fields_selected.items() if cb.value]
                filters = {}
                if self.export_filter_item_code.value:
                    filters["item_code"] = self.export_filter_item_code.value
                if self.export_filter_item_name.value:
                    filters["item_name"] = self.export_filter_item_name.value
                if self.export_filter_item_group.value:
                    filters["item_group"] = self.export_filter_item_group.value

                data = self.api.export_items(fields, filters, limit, progress_callback)

            elif export_type == "kategorien":
                data = self.api.export_item_groups(limit=limit)

            elif export_type == "preise":
                price_list = self.export_price_list.value or None
                data = self.api.export_item_prices(price_list, limit)

            elif export_type == "bestand":
                warehouse = self.export_warehouse.value or None
                data = self.api.export_stock_levels(warehouse, limit)

            elif export_type == "attribute":
                data = self.api.export_attributes(limit)

            else:
                data = []

            if not data:
                self.log("Keine Daten zum Exportieren!", error=True)
                self._finish_export()
                return

            # Dateiname
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if export_format == "json":
                filename = f"export_{export_type}_{timestamp}.json"
            else:
                filename = f"export_{export_type}_{timestamp}.csv"

            filepath = os.path.join("exports", filename)
            os.makedirs("exports", exist_ok=True)

            # Exportieren
            if export_format == "json":
                with open(filepath, 'w', encoding=encoding) as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            else:
                # CSV
                if export_format == "csv":
                    delimiter = ";"
                elif export_format == "csv_comma":
                    delimiter = ","
                else:  # tsv
                    delimiter = "\t"

                with open(filepath, 'w', encoding=encoding, newline='') as f:
                    if data:
                        # Alle Schlüssel sammeln
                        all_keys = set()
                        for row in data:
                            all_keys.update(row.keys())
                        fieldnames = sorted(all_keys)

                        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
                        writer.writeheader()

                        for row in data:
                            # Werte bereinigen
                            clean_row = {}
                            for k, v in row.items():
                                if isinstance(v, (list, dict)):
                                    clean_row[k] = json.dumps(v, ensure_ascii=False)
                                else:
                                    clean_row[k] = v
                            writer.writerow(clean_row)

            self.log(f"Export erfolgreich: {filepath}")
            self.log(f"Exportiert: {len(data)} Datensätze")

            self.export_status.value = f"Exportiert: {len(data)} Datensätze -> {filename}"

        except Exception as ex:
            self.log(f"Export-Fehler: {ex}", error=True)
            self.export_status.value = f"Fehler: {ex}"

        self._finish_export()

    def _finish_export(self):
        """Beendet Export"""
        self.export_button.disabled = False
        self.export_progress.visible = False
        try:
            self.page.update()
        except:
            pass

    def _build_mapping_tab(self) -> Container:
        """Mapping-Tab"""

        self.mapping_list = ListView(
            expand=True,
            spacing=5,
            padding=10,
        )

        auto_map_btn = ElevatedButton(
            "Auto-Mapping",
            icon=Icons.AUTO_FIX_HIGH,
            on_click=self.auto_map_fields,
            tooltip="Regelbasiertes Mapping nach Spaltennamen"
        )

        self.ai_map_btn = ElevatedButton(
            "AI Smart-Mapping",
            icon=Icons.AUTO_AWESOME,
            on_click=self.ai_smart_map_fields,
            tooltip="Intelligentes Mapping mit Gemini AI",
            style=ButtonStyle(
                bgcolor=Colors.PURPLE_700,
                color=Colors.WHITE,
            )
        )

        self.ai_mapping_status = Text("", size=12, color=Colors.GREY_400)

        clear_btn = ElevatedButton(
            "Alle löschen",
            icon=Icons.CLEAR_ALL,
            on_click=self.clear_mappings
        )

        return Container(
            content=Column([
                Row([
                    ft.Icon(Icons.SWAP_HORIZ, size=24, color=Colors.BLUE_400),
                    Text("Feld-Zuordnung", size=24, weight=FontWeight.BOLD),
                    Container(expand=True),
                    auto_map_btn,
                    self.ai_map_btn,
                    clear_btn,
                ], spacing=10),
                Divider(height=10),
                Row([
                    Text(
                        "Ordne die Spalten aus deiner Quelldatei den ERPNext-Feldern zu. "
                        "Felder mit * sind Pflichtfelder.",
                        size=14,
                        color=Colors.GREY_400
                    ),
                    Container(expand=True),
                    self.ai_mapping_status,
                ]),
                Divider(height=10, color=Colors.TRANSPARENT),
                Container(
                    content=self.mapping_list,
                    expand=True,
                    border=border.all(1, Colors.GREY_700),
                    border_radius=10,
                ),
            ]),
            padding=20,
            expand=True
        )

    def _build_images_tab(self) -> Container:
        """Bilder-Tab"""
        
        self.image_folder_text = Text("Kein Ordner ausgewählt", italic=True)
        self.image_file_list = ListView(expand=True, spacing=5)
        self.image_count_text = Text("", size=12)
        
        self.image_mode = RadioGroup(
            content=Column([
                Radio(value="upload", label="Bilder hochladen (neue hinzufügen)"),
                Radio(value="replace", label="Bilder ersetzen (alte löschen, neue hochladen)"),
                Radio(value="delete", label="Nur Bilder löschen"),
            ]),
            value="upload"
        )
        
        self.image_match_mode = Dropdown(
            label="Dateiname-Zuordnung",
            value="jtl_format",
            options=[
                dropdown.Option("jtl_format", "JTL-Format: artikelnummer-1.jpg, artikelnummer-2.jpg"),
                dropdown.Option("artikelnummer", "Artikelnummer = Dateiname (exakt)"),
                dropdown.Option("artikelnummer_prefix", "Artikelnummer als Prefix (ART123_1.jpg)"),
                dropdown.Option("artikelnummer_dash", "Artikelnummer-Nummer (ART123-1.jpg)"),
            ],
            width=450
        )
        
        self.image_progress = ProgressBar(width=500, value=0, visible=False)
        self.image_status = Text("", size=14)
        
        return Container(
            content=Column([
                Row([
                    ft.Icon(Icons.IMAGE, size=24, color=Colors.BLUE_400),
                    Text("Bilder-Import", size=24, weight=FontWeight.BOLD),
                ], spacing=10),
                Divider(height=20),

                Card(
                    content=Container(
                        content=Column([
                            Row([
                                ft.Icon(Icons.FOLDER, size=18, color=Colors.AMBER_400),
                                Text("Bildordner auswählen", weight=FontWeight.BOLD),
                            ], spacing=8),
                            Row([
                                ElevatedButton(
                                    "Ordner wählen",
                                    icon=Icons.FOLDER_OPEN,
                                    on_click=lambda _: self.image_folder_picker.get_directory_path(
                                        dialog_title="Bildordner auswählen"
                                    )
                                ),
                                self.image_folder_text,
                            ], spacing=15),
                            self.image_count_text,
                        ]),
                        padding=20
                    )
                ),

                Row([
                    Card(
                        content=Container(
                            content=Column([
                                Row([
                                    ft.Icon(Icons.SETTINGS, size=16, color=Colors.BLUE_400),
                                    Text("Modus", weight=FontWeight.BOLD),
                                ], spacing=8),
                                self.image_mode,
                            ]),
                            padding=20
                        ),
                        expand=True
                    ),
                    Card(
                        content=Container(
                            content=Column([
                                Row([
                                    ft.Icon(Icons.LINK, size=16, color=Colors.BLUE_400),
                                    Text("Zuordnung", weight=FontWeight.BOLD),
                                ], spacing=8),
                                self.image_match_mode,
                                Divider(height=10, color=Colors.TRANSPARENT),
                                Text(
                                    "Tipp: Benenne Bilder nach Artikelnummer.\n"
                                    "Mehrere Bilder: ART123-1.jpg, ART123-2.jpg",
                                    size=12, color=Colors.GREY_500
                                ),
                            ]),
                            padding=20
                        ),
                        expand=True
                    ),
                ], spacing=20),

                Row([
                    ft.Icon(Icons.PHOTO_LIBRARY, size=16, color=Colors.BLUE_400),
                    Text("Gefundene Bilder:", weight=FontWeight.BOLD),
                ], spacing=8),
                Container(
                    content=self.image_file_list,
                    height=200,
                    border=border.all(1, Colors.GREY_700),
                    border_radius=10,
                ),

                Row([
                    ElevatedButton(
                        "Bilder-Import starten",
                        icon=Icons.CLOUD_UPLOAD,
                        style=ButtonStyle(bgcolor=Colors.BLUE_700, color=Colors.WHITE),
                        on_click=self.start_image_import
                    ),
                    Column([
                        self.image_progress,
                        self.image_status,
                    ])
                ], spacing=20),
            ]),
            padding=20
        )
    
    def _build_settings_tab(self) -> Container:
        """Einstellungen-Tab"""
        
        self.setting_url = TextField(
            label="ERPNext URL",
            hint_text="https://erp.example.com",
            value=self.config.base_url,
            width=400
        )
        
        self.setting_api_key = TextField(
            label="API Key",
            value=self.config.api_key,
            width=400
        )
        
        self.setting_api_secret = TextField(
            label="API Secret",
            password=True,
            can_reveal_password=True,
            value=self.config.api_secret,
            width=400
        )
        
        self.setting_company = TextField(
            label="Firma",
            value=self.config.company,
            width=400
        )
        
        self.setting_warehouse = TextField(
            label="Standard-Lager",
            value=self.config.default_warehouse,
            width=400
        )
        
        self.setting_price_list = TextField(
            label="Standard-Preisliste",
            value=self.config.default_price_list,
            width=400
        )
        
        self.setting_item_group = TextField(
            label="Standard-Artikelgruppe",
            value=self.config.default_item_group,
            width=400
        )

        # Gemini AI Settings
        self.setting_gemini_api_key = TextField(
            label="Gemini API Key",
            hint_text="AIza...",
            password=True,
            can_reveal_password=True,
            value=self.config.gemini_api_key,
            width=400
        )

        self.gemini_status_icon = ft.Icon(Icons.CIRCLE, size=12, color=Colors.GREY_600)
        self.gemini_status_text = Text("Nicht konfiguriert", size=12, color=Colors.GREY_400)

        return Container(
            content=Column([
                Row([
                    ft.Icon(Icons.SETTINGS, size=24, color=Colors.BLUE_400),
                    Text("Einstellungen", size=24, weight=FontWeight.BOLD),
                ], spacing=10),
                Divider(height=20),

                Row([
                    # ERPNext Card
                    Card(
                        content=Container(
                            content=Column([
                                Row([
                                    ft.Icon(Icons.LINK, size=18, color=Colors.GREEN_400),
                                    Text("ERPNext API", weight=FontWeight.BOLD, size=16),
                                ], spacing=8),
                                Divider(height=10, color=Colors.TRANSPARENT),
                                self.setting_url,
                                self.setting_api_key,
                                self.setting_api_secret,
                                Divider(height=15),
                                Text("Standard-Werte", weight=FontWeight.BOLD, size=14),
                                self.setting_company,
                                self.setting_warehouse,
                                self.setting_price_list,
                                self.setting_item_group,
                                Divider(height=15),
                                Row([
                                    ElevatedButton(
                                        "Speichern",
                                        icon=Icons.SAVE,
                                        on_click=self.save_config
                                    ),
                                    ElevatedButton(
                                        "Verbindung testen",
                                        icon=Icons.SYNC,
                                        on_click=self.test_connection
                                    ),
                                ], spacing=10)
                            ], spacing=8),
                            padding=20
                        ),
                        expand=True
                    ),

                    # Gemini AI Card
                    Card(
                        content=Container(
                            content=Column([
                                Row([
                                    ft.Icon(Icons.AUTO_AWESOME, color=Colors.PURPLE_400),
                                    Text("Gemini AI", weight=FontWeight.BOLD, size=16),
                                ], spacing=10),
                                Divider(height=10, color=Colors.TRANSPARENT),
                                Text(
                                    "Nutze Google Gemini AI für intelligentes\n"
                                    "Feld-Mapping. Die AI erkennt automatisch\n"
                                    "welche Spalten zu welchen ERPNext-Feldern\n"
                                    "gehören - auch bei unterschiedlichen Namen.",
                                    size=12,
                                    color=Colors.GREY_400
                                ),
                                Divider(height=15),
                                self.setting_gemini_api_key,
                                Divider(height=10, color=Colors.TRANSPARENT),
                                Text(
                                    "API Key erstellen:\n"
                                    "https://aistudio.google.com/apikey",
                                    size=11,
                                    color=Colors.BLUE_300,
                                    selectable=True
                                ),
                                Divider(height=15),
                                Row([
                                    ElevatedButton(
                                        "Testen",
                                        icon=Icons.SCIENCE,
                                        on_click=self.test_gemini_connection
                                    ),
                                    Row([self.gemini_status_icon, self.gemini_status_text], spacing=5),
                                ], spacing=15),
                            ], spacing=8),
                            padding=20,
                            width=350
                        ),
                    ),
                ], spacing=20, alignment=MainAxisAlignment.START),
            ], scroll=ScrollMode.AUTO),
            padding=20
        )
    
    def _build_log_tab(self) -> Container:
        """Log-Tab"""
        
        self.log_list = ListView(
            expand=True,
            spacing=2,
            padding=10,
            auto_scroll=True
        )
        
        return Container(
            content=Column([
                Row([
                    ft.Icon(Icons.LIST_ALT, size=24, color=Colors.BLUE_400),
                    Text("Import-Protokoll", size=24, weight=FontWeight.BOLD),
                    Container(expand=True),
                    ElevatedButton(
                        "Leeren",
                        icon=Icons.DELETE,
                        on_click=self.clear_log
                    ),
                    ElevatedButton(
                        "Exportieren",
                        icon=Icons.DOWNLOAD,
                        on_click=self.export_log
                    ),
                ], spacing=10),
                Divider(height=10),
                Container(
                    content=self.log_list,
                    expand=True,
                    border=border.all(1, Colors.GREY_700),
                    border_radius=10,
                    bgcolor=Colors.GREY_900,
                ),
            ]),
            padding=20,
            expand=True
        )
    
    # ==================== EVENT HANDLER ====================
    
    def on_file_picked(self, e: FilePickerResultEvent):
        """Datei ausgewählt"""
        if not e.files:
            return
        
        file = e.files[0]
        self.source_file = file.path
        self.file_path_text.value = file.name
        self.file_path_text.color = Colors.WHITE
        self.file_path_text.italic = False
        
        self.log(f"Datei geladen: {file.name}")
        self.parse_source_file()
        self.page.update()
    
    def parse_source_file(self):
        """Parst Quelldatei"""
        if not self.source_file:
            return
        
        try:
            ext = os.path.splitext(self.source_file)[1].lower()
            
            if ext == ".xml":
                parser = BMECatParser()
                self.source_data, _ = parser.parse(self.source_file)
                self.source_columns = parser.get_columns() if self.source_data else []
                self.file_info_text.value = f"BMECat: {len(self.source_data)} Produkte"
            else:
                delimiter = self.csv_delimiter.value
                encoding = self.csv_encoding.value
                
                with open(self.source_file, 'r', encoding=encoding, errors='replace') as f:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    self.source_columns = reader.fieldnames or []
                    self.source_data = list(reader)
                
                self.file_info_text.value = f"CSV: {len(self.source_data)} Zeilen, {len(self.source_columns)} Spalten"
            
            self.log(f"Geparst: {len(self.source_data)} Datensätze, {len(self.source_columns)} Spalten")
            
            self.update_preview_table()
            self.update_mapping_list()
            self.start_button.disabled = False
            
        except Exception as e:
            self.log(f"FEHLER beim Parsen: {e}", error=True)
            self.file_info_text.value = f"Fehler: {e}"
            self.file_info_text.color = Colors.RED_400
        
        self.page.update()
    
    def reload_file(self, e=None):
        """Lädt Datei neu"""
        if self.source_file:
            self.parse_source_file()
    
    def update_preview_table(self):
        """Aktualisiert Vorschau - zeigt alle Spalten mit horizontalem Scroll"""
        if not self.source_columns:
            return

        # Alle Spalten anzeigen
        display_cols = self.source_columns
        total_cols = len(self.source_columns)
        total_rows = len(self.source_data)

        # Info-Text aktualisieren
        if hasattr(self, 'preview_column_info'):
            self.preview_column_info.value = f"{total_cols} Spalten | {total_rows} Zeilen (zeige max. 15)"

        # Spalten erstellen
        self.preview_table.columns = []
        for col in display_cols:
            # Kürze lange Spaltennamen
            display_name = col if len(col) <= 20 else col[:18] + "..."
            self.preview_table.columns.append(
                DataColumn(
                    Text(display_name, weight=FontWeight.BOLD, size=10, color=Colors.BLUE_200),
                )
            )

        rows = []
        for row_data in self.source_data[:15]:
            cells = []
            for col in display_cols:
                value = str(row_data.get(col, ""))
                # Kürze lange Werte
                display_value = value if len(value) <= 35 else value[:32] + "..."
                cells.append(DataCell(Text(display_value, size=9)))
            rows.append(DataRow(cells=cells))

        self.preview_table.rows = rows
    
    def update_mapping_list(self):
        """Aktualisiert Mapping-Liste"""
        self.mapping_list.controls.clear()
        self.mapping_dropdowns: Dict[str, Dropdown] = {}  # Speichere Dropdown-Referenzen

        import_type = self.import_type.value

        # Wähle Zielfelder basierend auf Import-Typ
        if import_type == "kategorien":
            target_fields = ERPNEXT_ITEM_GROUP_FIELDS
        elif import_type == "attribute":
            target_fields = ERPNEXT_ATTRIBUTE_FIELDS
        elif import_type == "varianten":
            target_fields = ERPNEXT_VARIANT_FIELDS
        else:  # artikel, preise
            target_fields = ERPNEXT_ITEM_FIELDS

        for col in self.source_columns:
            row = self._create_mapping_row(col, target_fields)
            self.mapping_list.controls.append(row)

        self.page.update()

    def on_import_type_changed(self, e=None):
        """Import-Typ geändert - aktualisiere Mapping"""
        if self.source_columns:
            self.field_mappings.clear()
            self.update_mapping_list()
            self.log(f"Import-Typ geändert auf: {self.import_type.value}")
    
    def _create_mapping_row(self, source_col: str, target_fields: Dict) -> Container:
        """Erstellt Mapping-Zeile"""
        
        target_options = [dropdown.Option("", "-- Nicht importieren --")]
        for field_key, field_info in target_fields.items():
            label = field_info["label"]
            target_options.append(dropdown.Option(field_key, label))
        
        # Auto-Mapping
        auto_target = ""
        col_lower = source_col.lower().replace(" ", "_").replace("-", "_")
        col_normalized = re.sub(r'[^a-z0-9_]', '', col_lower)
        
        # Direkte Suche
        if col_lower in AUTO_MAPPING_RULES:
            auto_target = AUTO_MAPPING_RULES[col_lower]
        elif col_normalized in AUTO_MAPPING_RULES:
            auto_target = AUTO_MAPPING_RULES[col_normalized]
        else:
            # Fuzzy-Suche
            for rule_key, rule_target in AUTO_MAPPING_RULES.items():
                if rule_key in col_lower or col_lower in rule_key:
                    auto_target = rule_target
                    break
        
        # Mapping speichern wenn auto-zugeordnet
        if auto_target:
            self.field_mappings[source_col] = FieldMapping(
                source_column=source_col,
                target_field=auto_target
            )
        
        target_dropdown = Dropdown(
            options=target_options,
            value=auto_target,
            width=250,
            dense=True,
            on_change=lambda e, col=source_col: self.on_mapping_changed(col, e.control.value)
        )

        # Dropdown-Referenz speichern für Duplikat-Prüfung
        self.mapping_dropdowns[source_col] = target_dropdown
        
        transform_dropdown = Dropdown(
            options=[
                dropdown.Option("none", "Keine"),
                dropdown.Option("trim", "Whitespace entfernen"),
                dropdown.Option("uppercase", "GROSSBUCHSTABEN"),
                dropdown.Option("lowercase", "kleinbuchstaben"),
                dropdown.Option("number", "Als Zahl"),
                dropdown.Option("bool", "Als Boolean"),
                dropdown.Option("html_strip", "HTML entfernen"),
            ],
            value="none",
            width=180,
            dense=True,
            on_change=lambda e, col=source_col: self.on_transform_changed(col, e.control.value)
        )
        
        default_field = TextField(
            hint_text="Standardwert",
            width=150,
            dense=True,
            on_change=lambda e, col=source_col: self.on_default_changed(col, e.control.value)
        )
        
        sample = ""
        if self.source_data:
            sample = str(self.source_data[0].get(source_col, ""))[:35]
        
        return Container(
            content=Row([
                Container(
                    content=Text(source_col, weight=FontWeight.BOLD, size=12),
                    width=200,
                    bgcolor=Colors.BLUE_GREY_800,
                    padding=10,
                    border_radius=5
                ),
                ft.Icon(Icons.ARROW_FORWARD, color=Colors.GREY_600, size=20),
                target_dropdown,
                transform_dropdown,
                default_field,
                Container(
                    content=Text(sample, size=10, color=Colors.GREY_500, italic=True),
                    width=150
                ),
            ], spacing=10),
            padding=5
        )
    
    def on_mapping_changed(self, source_col: str, target_field: str):
        """Mapping geändert - verhindert Duplikate"""
        if target_field:
            # Prüfe ob dieses Zielfeld bereits von einer anderen Spalte verwendet wird
            for other_col, mapping in list(self.field_mappings.items()):
                if other_col != source_col and mapping.target_field == target_field:
                    # Entferne das alte Mapping und setze Dropdown zurück
                    del self.field_mappings[other_col]
                    if hasattr(self, 'mapping_dropdowns') and other_col in self.mapping_dropdowns:
                        self.mapping_dropdowns[other_col].value = ""
                    self.log(f"Feld '{target_field}' war bereits vergeben - altes Mapping entfernt")

            # Setze neues Mapping
            if source_col not in self.field_mappings:
                self.field_mappings[source_col] = FieldMapping(source_column=source_col, target_field=target_field)
            else:
                self.field_mappings[source_col].target_field = target_field
        elif source_col in self.field_mappings:
            del self.field_mappings[source_col]

        # UI aktualisieren
        try:
            self.page.update()
        except:
            pass
    
    def on_transform_changed(self, source_col: str, transform: str):
        """Transform geändert"""
        if source_col in self.field_mappings:
            self.field_mappings[source_col].transform = transform
    
    def on_default_changed(self, source_col: str, default_value: str):
        """Standardwert geändert"""
        if source_col in self.field_mappings:
            self.field_mappings[source_col].default_value = default_value
    
    def auto_map_fields(self, e=None):
        """Auto-Mapping - ohne Duplikate"""
        mapped_count = 0
        used_targets = set()  # Verhindert Duplikate

        for i, control in enumerate(self.mapping_list.controls):
            row = control.content
            source_text = row.controls[0].content.value
            dropdown_ctrl = row.controls[2]

            col_lower = source_text.lower().replace(" ", "_").replace("-", "_")
            col_normalized = re.sub(r'[^a-z0-9_]', '', col_lower)

            target = ""
            if col_lower in AUTO_MAPPING_RULES:
                target = AUTO_MAPPING_RULES[col_lower]
            elif col_normalized in AUTO_MAPPING_RULES:
                target = AUTO_MAPPING_RULES[col_normalized]
            else:
                for rule_key, rule_target in AUTO_MAPPING_RULES.items():
                    if rule_key in col_lower:
                        target = rule_target
                        break

            # Nur zuordnen wenn Zielfeld noch nicht verwendet
            if target and target not in used_targets:
                dropdown_ctrl.value = target
                self.field_mappings[source_text] = FieldMapping(
                    source_column=source_text,
                    target_field=target
                )
                used_targets.add(target)
                mapped_count += 1

        self.log(f"Auto-Mapping: {mapped_count} Felder zugeordnet")
        self.page.update()
    
    def clear_mappings(self, e=None):
        """Löscht alle Mappings"""
        self.field_mappings.clear()
        for control in self.mapping_list.controls:
            row = control.content
            dropdown_ctrl = row.controls[2]
            dropdown_ctrl.value = ""
        self.log("Alle Mappings gelöscht")
        self.page.update()

    def ai_smart_map_fields(self, e=None):
        """AI-basiertes Smart-Mapping mit Gemini"""
        if not self.source_columns:
            self.log("Keine Quelldatei geladen!", error=True)
            return

        if not self.gemini:
            self.log("Gemini AI nicht konfiguriert! Bitte API Key in Einstellungen hinterlegen.", error=True)
            self.ai_mapping_status.value = "Kein API Key"
            self.ai_mapping_status.color = Colors.RED_400
            self.page.update()
            return

        # UI Feedback
        self.ai_map_btn.disabled = True
        self.ai_mapping_status.value = "AI analysiert Spalten..."
        self.ai_mapping_status.color = Colors.PURPLE_400
        self.page.update()

        # In separatem Thread ausführen
        thread = threading.Thread(target=self._run_ai_mapping)
        thread.start()

    def _run_ai_mapping(self):
        """Führt AI-Mapping in separatem Thread aus"""
        try:
            import_type = self.import_type.value
            target_fields = ERPNEXT_ITEM_FIELDS if import_type in ["artikel", "preise"] else ERPNEXT_ITEM_GROUP_FIELDS

            # Sample-Daten für bessere Erkennung
            sample_data = self.source_data[:5] if self.source_data else None

            self.log("Starte Gemini AI Smart-Mapping...")

            # AI Mapping anfordern
            ai_mappings = self.gemini.smart_map_fields(
                self.source_columns,
                target_fields,
                sample_data
            )

            if not ai_mappings:
                self.log("AI konnte keine Mappings ermitteln", error=True)
                self.ai_mapping_status.value = "Keine Mappings gefunden"
                self.ai_mapping_status.color = Colors.ORANGE_400
                self._finish_ai_mapping()
                return

            # Mappings in UI übernehmen - ohne Duplikate
            mapped_count = 0
            used_targets = set()  # Verhindert Duplikate

            for control in self.mapping_list.controls:
                row = control.content
                source_text = row.controls[0].content.value
                dropdown_ctrl = row.controls[2]

                if source_text in ai_mappings:
                    target = ai_mappings[source_text]
                    # Nur zuordnen wenn Zielfeld noch nicht verwendet
                    if target not in used_targets:
                        dropdown_ctrl.value = target
                        self.field_mappings[source_text] = FieldMapping(
                            source_column=source_text,
                            target_field=target
                        )
                        used_targets.add(target)
                        mapped_count += 1

            self.log(f"AI Smart-Mapping: {mapped_count} Felder intelligent zugeordnet (keine Duplikate)")
            self.ai_mapping_status.value = f"{mapped_count} Felder gemappt"
            self.ai_mapping_status.color = Colors.GREEN_400

        except Exception as ex:
            self.log(f"AI Mapping Fehler: {ex}", error=True)
            self.ai_mapping_status.value = "Fehler"
            self.ai_mapping_status.color = Colors.RED_400

        self._finish_ai_mapping()

    def _finish_ai_mapping(self):
        """Beendet AI-Mapping"""
        self.ai_map_btn.disabled = False
        try:
            self.page.update()
        except:
            pass

    def on_image_folder_picked(self, e: FilePickerResultEvent):
        """Bildordner ausgewählt"""
        if not e.path:
            return
        
        self.image_folder = e.path
        self.image_folder_text.value = e.path
        self.image_folder_text.italic = False
        
        self.image_file_list.controls.clear()
        
        extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        self.image_files = []
        
        for f in os.listdir(e.path):
            if os.path.splitext(f)[1].lower() in extensions:
                self.image_files.append(f)
        
        for img in sorted(self.image_files)[:100]:
            self.image_file_list.controls.append(
                Row([
                    ft.Icon(Icons.IMAGE, size=16, color=Colors.BLUE_400),
                    Text(img, size=12),
                ], spacing=10)
            )
        
        self.image_count_text.value = f"{len(self.image_files)} Bilder gefunden"
        self.log(f"Bildordner: {len(self.image_files)} Bilder gefunden")
        self.page.update()
    
    def on_template_loaded(self, e: FilePickerResultEvent):
        """Vorlage geladen"""
        if not e.files:
            return
        
        try:
            with open(e.files[0].path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.current_template = ImportTemplate.from_dict(data)
            
            self.csv_delimiter.value = self.current_template.csv_delimiter
            self.csv_encoding.value = self.current_template.csv_encoding
            self.skip_header.value = self.current_template.skip_first_row
            self.import_type.value = self.current_template.import_type
            
            self.field_mappings.clear()
            for mapping in self.current_template.mappings:
                self.field_mappings[mapping.source_column] = mapping
            
            self.log(f"Vorlage geladen: {self.current_template.name}")
            
            if self.source_file:
                self.reload_file()
            
        except Exception as ex:
            self.log(f"Fehler beim Laden: {ex}", error=True)
        
        self.page.update()
    
    def save_template(self, e=None):
        """Vorlage speichern"""
        
        def do_save(e):
            name = template_name.value or "Meine Vorlage"
            
            template = ImportTemplate(
                name=name,
                import_type=self.import_type.value,
                file_format="csv",
                mappings=list(self.field_mappings.values()),
                csv_delimiter=self.csv_delimiter.value,
                csv_encoding=self.csv_encoding.value,
                skip_first_row=self.skip_header.value,
                created_at=datetime.now().isoformat()
            )
            
            filename = f"template_{name.lower().replace(' ', '_')}.json"
            filepath = os.path.join("templates", filename)
            os.makedirs("templates", exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.log(f"Vorlage gespeichert: {filepath}")
            self.page.close(dlg)
            self.page.update()
        
        template_name = TextField(label="Vorlagenname", value="Meine Vorlage")
        
        dlg = AlertDialog(
            modal=True,
            title=Text("Vorlage speichern"),
            content=Column([
                template_name,
                Text(f"Mappings: {len(self.field_mappings)}", size=12),
            ], tight=True),
            actions=[
                TextButton("Abbrechen", on_click=lambda e: self.page.close(dlg)),
                ElevatedButton("Speichern", on_click=do_save),
            ],
        )
        
        self.page.open(dlg)
    
    # ==================== IMPORT ====================
    
    def start_import(self, e=None):
        """Startet Import"""
        if not self.source_data:
            self.log("Keine Daten!", error=True)
            return
        
        if not self.field_mappings:
            self.log("Keine Mappings!", error=True)
            return
        
        # Pflichtfelder prüfen
        import_type = self.import_type.value
        if import_type in ["artikel", "preise"]:
            required = {"item_code"}
        else:
            required = {"item_group_name"}
        
        mapped_targets = {m.target_field for m in self.field_mappings.values()}
        missing = required - mapped_targets
        
        if missing:
            self.log(f"Pflichtfelder fehlen: {missing}", error=True)
            return
        
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.start_button.disabled = True
        self.is_importing = True
        
        dry_run = self.dry_run.value
        self.log(f"=== Import gestartet ({'DRY RUN' if dry_run else 'LIVE'}) ===")
        
        thread = threading.Thread(target=self._run_import, args=(dry_run,))
        thread.start()
    
    def _run_import(self, dry_run: bool):
        """Import-Thread"""
        total = len(self.source_data)
        success = 0
        errors = 0
        skipped = 0
        
        mode = self.import_mode.value
        import_type = self.import_type.value
        
        for i, row in enumerate(self.source_data):
            try:
                # Daten transformieren
                item_data = {}
                for source_col, mapping in self.field_mappings.items():
                    value = row.get(source_col, "") or mapping.default_value
                    
                    # Transformation
                    if mapping.transform == "trim":
                        value = str(value).strip()
                    elif mapping.transform == "uppercase":
                        value = str(value).upper()
                    elif mapping.transform == "lowercase":
                        value = str(value).lower()
                    elif mapping.transform == "number":
                        try:
                            value = float(str(value).replace(",", ".").replace(" ", ""))
                        except:
                            value = 0.0
                    elif mapping.transform == "bool":
                        value = str(value).lower() in ("1", "true", "ja", "yes", "y")
                    elif mapping.transform == "html_strip":
                        value = re.sub(r'<[^>]+>', '', str(value))
                    
                    if value:
                        item_data[mapping.target_field] = value

                # ==================== JTL-SPEZIFISCHE FELDVERARBEITUNG ====================

                # VK Brutto -> standard_rate (Netto konvertieren, 19% MwSt)
                if "standard_rate_brutto" in item_data:
                    brutto = item_data.pop("standard_rate_brutto")
                    try:
                        brutto_val = float(str(brutto).replace(",", ".").replace(" ", ""))
                        # Brutto zu Netto (19% MwSt)
                        netto = round(brutto_val / 1.19, 2)
                        item_data["standard_rate"] = netto
                    except:
                        pass

                # Barcode/EAN -> gtin (wird in create_item in barcodes-Tabelle konvertiert)
                if "barcode" in item_data:
                    barcode = item_data.pop("barcode")
                    if barcode and str(barcode).strip():
                        # Leere oder ungültige Barcodes filtern
                        barcode_str = str(barcode).strip()
                        if len(barcode_str) >= 8 and barcode_str not in ("0", ""):
                            item_data["gtin"] = barcode_str

                # Aktiv-Status invertieren (JTL: aktiv=1 -> ERPNext: disabled=0)
                if "disabled" in item_data:
                    aktiv = item_data["disabled"]
                    if isinstance(aktiv, str):
                        # Wenn "aktiv" gemappt wurde, invertieren
                        is_aktiv = aktiv.lower() in ("1", "true", "ja", "yes", "y", "aktiv")
                        item_data["disabled"] = 0 if is_aktiv else 1
                    elif isinstance(aktiv, bool):
                        item_data["disabled"] = 0 if aktiv else 1

                # description_html -> description (Alias)
                if "description_html" in item_data and "description" not in item_data:
                    item_data["description"] = item_data.pop("description_html")
                elif "description_html" in item_data:
                    item_data.pop("description_html")

                identifier = item_data.get("item_code") or item_data.get("item_group_name", f"Row {i+1}")

                # Kategorie-Hierarchie verarbeiten (für Artikel-Import)
                if import_type in ["artikel", "preise"]:
                    category_levels = []

                    # Prüfen auf category_level_1, category_level_2, etc.
                    for level in range(1, 5):
                        level_key = f"category_level_{level}"
                        if level_key in item_data:
                            category_levels.append(item_data.pop(level_key))

                    # Prüfen auf category_path (z.B. "Elektronik > Computer > Laptops")
                    if "category_path" in item_data:
                        path = item_data.pop("category_path")
                        if path and self.api:
                            parsed_levels = self.api.parse_category_path(path)
                            if parsed_levels:
                                category_levels = parsed_levels

                    # Wenn Kategorie-Hierarchie vorhanden, erstellen und item_group setzen
                    if category_levels and self.api and not dry_run:
                        final_category = self.api.ensure_category_hierarchy(
                            category_levels,
                            log_callback=self.log
                        )
                        item_data["item_group"] = final_category
                    elif category_levels and dry_run:
                        self.log(f"[DRY] Kategorie-Hierarchie: {' > '.join(category_levels)}")
                        # Bei Dry-Run die unterste Kategorie als item_group setzen
                        item_data["item_group"] = category_levels[-1]

                if dry_run:
                    self.log(f"[DRY] {identifier}: {list(item_data.keys())}")
                    success += 1
                else:
                    if self.api:
                        if import_type in ["artikel", "preise"]:
                            existing = self.api.get_item(item_data.get("item_code", ""))

                            if existing and mode == "create":
                                skipped += 1
                            elif not existing and mode == "update":
                                skipped += 1
                            elif existing:
                                ok, msg = self.api.update_item(item_data["item_code"], item_data)
                                if ok:
                                    success += 1
                                else:
                                    errors += 1
                                    self.log(f"Fehler {identifier}: {msg}", error=True)
                            else:
                                ok, msg = self.api.create_item(item_data)
                                if ok:
                                    success += 1
                                    # Preis erstellen
                                    if "standard_rate" in item_data:
                                        self.api.create_item_price(
                                            item_data["item_code"],
                                            item_data["standard_rate"]
                                        )
                                else:
                                    errors += 1
                                    self.log(f"Fehler {identifier}: {msg}", error=True)

                        elif import_type == "kategorien":
                            ok, msg = self.api.create_item_group(item_data)
                            if ok:
                                success += 1
                            else:
                                errors += 1
                                self.log(f"Fehler {identifier}: {msg}", error=True)

                        elif import_type == "attribute":
                            # Attribut-Import
                            attr_name = item_data.get("attribute_name", "")
                            if not attr_name:
                                errors += 1
                                self.log(f"Zeile {i+1}: Kein Attribut-Name", error=True)
                                continue

                            values_str = item_data.get("attribute_values", "")
                            values = [v.strip() for v in values_str.split(",") if v.strip()] if values_str else []

                            numeric = item_data.get("numeric_values", False)
                            if isinstance(numeric, str):
                                numeric = numeric.lower() in ("1", "true", "ja", "yes")

                            ok, msg = self.api.create_attribute(
                                attr_name,
                                values=values,
                                numeric=numeric,
                                from_range=item_data.get("from_range"),
                                to_range=item_data.get("to_range"),
                                increment=item_data.get("increment")
                            )
                            if ok:
                                success += 1
                                self.log(f"Attribut: {msg}")
                            else:
                                errors += 1
                                self.log(f"Fehler Attribut {attr_name}: {msg}", error=True)

                        elif import_type == "varianten":
                            # Varianten-Import
                            variant_code = item_data.get("item_code", "")
                            template = item_data.get("variant_of", "")

                            if not variant_code or not template:
                                errors += 1
                                self.log(f"Zeile {i+1}: Varianten-Code oder Vorlage fehlt", error=True)
                                continue

                            # Sammle Attribute
                            attributes = {}
                            # Standard-Attribute
                            if item_data.get("attribute_color"):
                                attributes["Farbe"] = item_data["attribute_color"]
                            if item_data.get("attribute_size"):
                                attributes["Größe"] = item_data["attribute_size"]
                            if item_data.get("attribute_material"):
                                attributes["Material"] = item_data["attribute_material"]

                            # Dynamische Attribute (Name:Wert Format)
                            for key in ["attribute_1", "attribute_2", "attribute_3"]:
                                if item_data.get(key) and ":" in str(item_data[key]):
                                    parts = str(item_data[key]).split(":", 1)
                                    attributes[parts[0].strip()] = parts[1].strip()

                            if not attributes:
                                errors += 1
                                self.log(f"Zeile {i+1}: Keine Attribute für Variante", error=True)
                                continue

                            # Zusätzliche Daten
                            extra_data = {}
                            if item_data.get("standard_rate"):
                                extra_data["standard_rate"] = item_data["standard_rate"]
                            if item_data.get("gtin"):
                                extra_data["gtin"] = item_data["gtin"]

                            ok, msg = self.api.create_variant(
                                template,
                                variant_code,
                                attributes,
                                item_data.get("item_name"),
                                extra_data
                            )
                            if ok:
                                success += 1
                                self.log(f"Variante: {msg}")
                            else:
                                errors += 1
                                self.log(f"Fehler Variante {variant_code}: {msg}", error=True)
                    else:
                        self.log(f"[NO API] {identifier}")
                        success += 1
                
                # Progress
                progress = (i + 1) / total
                self.progress_bar.value = progress
                self.progress_text.value = f"{i + 1}/{total} ({int(progress * 100)}%)"
                self.page.update()
                
            except Exception as ex:
                errors += 1
                self.log(f"Fehler Zeile {i+1}: {ex}", error=True)
        
        self.log(f"=== Import abgeschlossen ===")
        self.log(f"✓ Erfolgreich: {success} | ✗ Fehler: {errors} | ⊘ Übersprungen: {skipped}")
        
        self.progress_bar.visible = False
        self.start_button.disabled = False
        self.is_importing = False
        self.page.update()
    
    def start_image_import(self, e=None):
        """Startet Bilder-Import"""
        if not self.image_folder or not self.image_files:
            self.log("Kein Bildordner oder keine Bilder!", error=True)
            return
        
        if not self.api:
            self.log("Keine API-Verbindung!", error=True)
            return
        
        self.image_progress.visible = True
        self.image_progress.value = 0
        
        thread = threading.Thread(target=self._run_image_import)
        thread.start()
    
    def _run_image_import(self):
        """Bilder-Import Thread"""
        mode = self.image_mode.value
        match_mode = self.image_match_mode.value
        
        total = len(self.image_files)
        success = 0
        errors = 0
        
        self.log(f"=== Bilder-Import gestartet ({mode}) ===")
        
        # Gruppiere Bilder nach Artikelnummer
        article_images: Dict[str, List[str]] = {}

        for img_file in self.image_files:
            basename = os.path.splitext(img_file)[0]

            if match_mode == "artikelnummer":
                # Exakter Match: Dateiname = Artikelnummer
                article_nr = basename
            elif match_mode == "artikelnummer_prefix":
                # ART123_1.jpg -> ART123
                article_nr = basename.rsplit("_", 1)[0]
            elif match_mode == "jtl_format":
                # JTL-Format: 0130287-300S10000-1.jpg -> 0130287-300S10000
                # Das letzte -N ist die Bildnummer
                parts = basename.rsplit("-", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    article_nr = parts[0]
                else:
                    # Fallback: Gesamter Dateiname
                    article_nr = basename
            else:
                # artikelnummer_dash: ART123-1.jpg -> ART123
                article_nr = basename.rsplit("-", 1)[0]

            if article_nr not in article_images:
                article_images[article_nr] = []
            article_images[article_nr].append(img_file)
        
        processed = 0
        for article_nr, images in article_images.items():
            try:
                # Prüfe ob Artikel existiert
                if not self.api.get_item(article_nr):
                    self.log(f"Artikel nicht gefunden: {article_nr}", error=True)
                    errors += len(images)
                    processed += len(images)
                    continue
                
                # Bei replace: Erst alte löschen
                if mode == "replace":
                    self.api.delete_item_attachments(article_nr)
                elif mode == "delete":
                    ok, msg = self.api.delete_item_attachments(article_nr)
                    if ok:
                        success += 1
                    processed += 1
                    continue
                
                # Bilder hochladen
                images_sorted = sorted(images)
                for idx, img_file in enumerate(images_sorted):
                    img_path = os.path.join(self.image_folder, img_file)
                    
                    if idx == 0:
                        # Erstes Bild als Hauptbild
                        ok, msg = self.api.set_item_image(article_nr, img_path)
                    else:
                        # Weitere als Attachments
                        ok, msg = self.api.attach_file(article_nr, img_path)
                    
                    if ok:
                        success += 1
                    else:
                        errors += 1
                        self.log(f"Fehler {img_file}: {msg}", error=True)
                    
                    processed += 1
                    
                    # Progress
                    progress = processed / total
                    self.image_progress.value = progress
                    self.image_status.value = f"{processed}/{total}"
                    self.page.update()
                    
            except Exception as ex:
                errors += len(images)
                processed += len(images)
                self.log(f"Fehler {article_nr}: {ex}", error=True)
        
        self.log(f"=== Bilder-Import abgeschlossen ===")
        self.log(f"✓ Erfolgreich: {success} | ✗ Fehler: {errors}")
        
        self.image_progress.visible = False
        self.image_status.value = "Fertig!"
        self.page.update()
    
    # ==================== CONFIG ====================
    
    def load_config(self):
        """Lädt Config"""
        config_path = "erpnext_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                self.config = ERPNextConfig(**data)
                self.update_settings_ui()
                self.log("Konfiguration geladen")
            except Exception as e:
                self.log(f"Config-Fehler: {e}", error=True)
    
    def save_config(self, e=None):
        """Speichert Config"""
        self.config.base_url = self.setting_url.value
        self.config.api_key = self.setting_api_key.value
        self.config.api_secret = self.setting_api_secret.value
        self.config.company = self.setting_company.value
        self.config.default_warehouse = self.setting_warehouse.value
        self.config.default_price_list = self.setting_price_list.value
        self.config.default_item_group = self.setting_item_group.value
        self.config.gemini_api_key = self.setting_gemini_api_key.value

        config_data = {
            "base_url": self.config.base_url,
            "api_key": self.config.api_key,
            "api_secret": self.config.api_secret,
            "company": self.config.company,
            "default_warehouse": self.config.default_warehouse,
            "default_price_list": self.config.default_price_list,
            "default_item_group": self.config.default_item_group,
            "gemini_api_key": self.config.gemini_api_key,
        }

        with open("erpnext_config.json", 'w') as f:
            json.dump(config_data, f, indent=2)

        # Gemini API initialisieren wenn Key vorhanden
        if self.config.gemini_api_key:
            self.gemini = GeminiAPI(self.config.gemini_api_key)

        self.log("Konfiguration gespeichert")
        self.page.snack_bar = SnackBar(Text("Konfiguration gespeichert!"))
        self.page.snack_bar.open = True
        self.page.update()

    def update_settings_ui(self):
        """Aktualisiert Settings UI"""
        # Prüfe ob UI-Elemente existieren
        if not hasattr(self, 'setting_url'):
            return

        self.setting_url.value = self.config.base_url
        self.setting_api_key.value = self.config.api_key
        self.setting_api_secret.value = self.config.api_secret
        self.setting_company.value = self.config.company
        self.setting_warehouse.value = self.config.default_warehouse
        self.setting_price_list.value = self.config.default_price_list
        self.setting_item_group.value = self.config.default_item_group

        if hasattr(self, 'setting_gemini_api_key'):
            self.setting_gemini_api_key.value = self.config.gemini_api_key

        # Gemini API initialisieren wenn Key vorhanden
        if self.config.gemini_api_key:
            self.gemini = GeminiAPI(self.config.gemini_api_key)

    def test_gemini_connection(self, e=None):
        """Testet Gemini API Verbindung"""
        api_key = self.setting_gemini_api_key.value
        if not api_key:
            self.gemini_status_icon.color = Colors.RED_400
            self.gemini_status_text.value = "Kein API Key"
            self.gemini_status_text.color = Colors.RED_400
            self.page.update()
            return

        self.gemini_status_text.value = "Teste..."
        self.page.update()

        self.gemini = GeminiAPI(api_key)
        success, msg = self.gemini.test_connection()

        if success:
            self.gemini_status_icon.color = Colors.GREEN_400
            self.gemini_status_text.value = "Verbunden"
            self.gemini_status_text.color = Colors.GREEN_400
            self.log("Gemini API verbunden")
            # Speichere den Key
            self.config.gemini_api_key = api_key
            self.save_config()
        else:
            self.gemini_status_icon.color = Colors.RED_400
            self.gemini_status_text.value = "Fehler"
            self.gemini_status_text.color = Colors.RED_400
            self.log(f"Gemini Fehler: {msg}", error=True)
            self.gemini = None

        self.page.update()
    
    def test_connection(self, e=None):
        """Testet Verbindung"""
        self.save_config()
        self.api = ERPNextAPI(self.config)
        
        success, msg = self.api.test_connection()
        
        if success:
            self.connection_icon.color = Colors.GREEN_400
            self.connection_text.value = msg
            self.connection_text.color = Colors.GREEN_400
            self.log(f"Verbindung OK: {msg}")
        else:
            self.connection_icon.color = Colors.RED_400
            self.connection_text.value = "Fehler"
            self.connection_text.color = Colors.RED_400
            self.log(f"Verbindungsfehler: {msg}", error=True)
        
        self.page.update()
    
    # ==================== LOGGING ====================

    def log(self, message: str, error: bool = False):
        """Log-Eintrag"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = Colors.RED_400 if error else Colors.GREY_300
        icon = Icons.ERROR if error else Icons.INFO_OUTLINE
        icon_color = Colors.RED_400 if error else Colors.BLUE_400

        entry = f"[{timestamp}] {message}"
        self.log_entries.append(entry)

        self.log_list.controls.append(
            Row([
                ft.Icon(icon, size=14, color=icon_color),
                Text(entry, size=12, color=color, selectable=True, expand=True),
            ], spacing=8)
        )

        if len(self.log_list.controls) > 500:
            self.log_list.controls.pop(0)

        # Auto-update wenn nicht im Import - mit Fehlerbehandlung
        if not self.is_importing:
            try:
                self.page.update()
            except:
                pass
    
    def clear_log(self, e=None):
        """Leert Log"""
        self.log_entries.clear()
        self.log_list.controls.clear()
        self.page.update()
    
    def export_log(self, e=None):
        """Exportiert Log"""
        filename = f"import_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join("logs", filename)
        os.makedirs("logs", exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(self.log_entries))
        
        self.log(f"Log exportiert: {filepath}")


def main(page: ft.Page):
    # Warte bis Page bereit ist
    page.on_error = lambda e: print(f"Page error: {e.data}")
    app = ERPNextImporterApp(page)
    page.update()


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)
