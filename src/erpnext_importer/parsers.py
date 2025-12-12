"""
Datei-Parser für CSV und BMECat XML
"""

import csv
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class CSVParser:
    """Parser für CSV-Dateien"""
    
    def __init__(self, delimiter: str = ";", encoding: str = "utf-8"):
        self.delimiter = delimiter
        self.encoding = encoding
        self.data: List[Dict] = []
        self.columns: List[str] = []
    
    def parse(self, file_path: str) -> Tuple[List[Dict], List[str]]:
        """
        Parst eine CSV-Datei.
        
        Args:
            file_path: Pfad zur CSV-Datei
            
        Returns:
            Tuple von (Daten als Liste von Dicts, Spaltennamen)
        """
        try:
            with open(file_path, 'r', encoding=self.encoding, errors='replace') as f:
                reader = csv.DictReader(f, delimiter=self.delimiter)
                self.columns = reader.fieldnames or []
                self.data = list(reader)
            
            logger.info(f"CSV geparst: {len(self.data)} Zeilen, {len(self.columns)} Spalten")
            return self.data, self.columns
            
        except Exception as e:
            logger.error(f"CSV Parse Error: {e}")
            raise
    
    def get_sample_data(self, rows: int = 5) -> List[Dict]:
        """Gibt Beispieldaten zurück"""
        return self.data[:rows]


class BMECatParser:
    """Parser für BMECat XML Format"""
    
    def __init__(self):
        self.products: List[Dict] = []
        self.categories: List[Dict] = []
    
    def parse(self, file_path: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Parst BMECat XML Datei.
        
        Args:
            file_path: Pfad zur XML-Datei
            
        Returns:
            Tuple von (Produkte, Kategorien)
        """
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        ns = self._detect_namespace(root)
        self.products = []
        self.categories = []
        
        # Produkte parsen
        for article in root.iter():
            if article.tag.endswith('ARTICLE'):
                product = self._parse_article(article, ns)
                if product:
                    self.products.append(product)
        
        logger.info(f"BMECat geparst: {len(self.products)} Produkte")
        return self.products, self.categories
    
    def _detect_namespace(self, root) -> str:
        """Erkennt den XML-Namespace"""
        tag = root.tag
        if '{' in tag:
            return tag[tag.find('{'):tag.find('}')+1]
        return ''
    
    def _get_text(self, element, path: str, ns: str, default: str = "") -> str:
        """Extrahiert Text aus einem XML-Element"""
        if element is None:
            return default
        
        # Suche mit und ohne Namespace
        for search_path in [f'{ns}{path}', path, f'.//{ns}{path}', f'.//{path}']:
            el = element.find(search_path)
            if el is not None and el.text:
                return el.text.strip()
        return default
    
    def _parse_article(self, article, ns: str) -> Optional[Dict]:
        """Parst einen einzelnen Artikel aus BMECat"""
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
            logger.error(f"BMECat Article Parse Error: {e}")
            return None
    
    def get_columns(self) -> List[str]:
        """Gibt die verfügbaren Spalten zurück"""
        if self.products:
            return list(self.products[0].keys())
        return []
    
    def get_sample_data(self, rows: int = 5) -> List[Dict]:
        """Gibt Beispieldaten zurück"""
        return self.products[:rows]


def detect_file_type(file_path: str) -> str:
    """
    Erkennt den Dateityp basierend auf der Endung.
    
    Args:
        file_path: Pfad zur Datei
        
    Returns:
        Dateityp ("csv", "xml", "unknown")
    """
    import os
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in (".csv", ".tsv", ".txt"):
        return "csv"
    elif ext in (".xml",):
        return "xml"
    else:
        return "unknown"


def parse_file(file_path: str, delimiter: str = ";", 
               encoding: str = "utf-8") -> Tuple[List[Dict], List[str]]:
    """
    Universelle Parse-Funktion die den richtigen Parser wählt.
    
    Args:
        file_path: Pfad zur Datei
        delimiter: CSV-Trennzeichen
        encoding: Datei-Encoding
        
    Returns:
        Tuple von (Daten, Spalten)
    """
    file_type = detect_file_type(file_path)
    
    if file_type == "csv":
        parser = CSVParser(delimiter=delimiter, encoding=encoding)
        return parser.parse(file_path)
    elif file_type == "xml":
        parser = BMECatParser()
        products, _ = parser.parse(file_path)
        columns = parser.get_columns()
        return products, columns
    else:
        raise ValueError(f"Unbekannter Dateityp: {file_path}")
