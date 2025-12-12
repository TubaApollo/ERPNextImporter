"""
ERPNext Importer Package
========================

Ein modulares Import-Tool für ERPNext mit:
- CSV und BMECat XML Import
- Flexibles Feld-Mapping mit AI-Unterstützung
- Custom Fields Support
- Bilder-Verwaltung
"""

__version__ = "2.1.0"
__author__ = "ERPNext Importer Team"

from .config import ERPNextConfig, FieldMapping, ImportTemplate
from .api import ERPNextAPI, ERPNextAPIError
from .gemini import GeminiAPI
from .utils import parse_number, brutto_to_netto, netto_to_brutto

__all__ = [
    "ERPNextConfig",
    "FieldMapping", 
    "ImportTemplate",
    "ERPNextAPI",
    "ERPNextAPIError",
    "GeminiAPI",
    "parse_number",
    "brutto_to_netto",
    "netto_to_brutto",
]
