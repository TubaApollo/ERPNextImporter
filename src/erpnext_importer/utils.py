"""
Hilfsfunktionen für den ERPNext Importer
"""

from typing import Any, Optional


def parse_number(value: Any, allow_empty: bool = True) -> Optional[float]:
    """
    Parst einen Wert zu einer Zahl (float).
    Unterstützt deutsche Zahlenformate (Komma als Dezimaltrennzeichen).
    
    Args:
        value: Der zu parsende Wert
        allow_empty: Wenn True, gibt None für leere Werte zurück
        
    Returns:
        float oder None
    """
    if value is None or value == "":
        return None if allow_empty else 0.0
    
    try:
        # Bereits eine Zahl
        if isinstance(value, (int, float)):
            return float(value)
        
        # String-Verarbeitung
        str_val = str(value).strip()
        if not str_val:
            return None if allow_empty else 0.0
        
        # Entferne Tausender-Trennzeichen (Punkt oder Leerzeichen)
        # und ersetze Komma durch Punkt für Dezimal
        str_val = str_val.replace(" ", "")
        
        # Deutsche Notation: 1.234,56 -> 1234.56
        if "," in str_val and "." in str_val:
            # Punkt ist Tausender-Trennzeichen
            str_val = str_val.replace(".", "").replace(",", ".")
        elif "," in str_val:
            # Nur Komma -> Dezimaltrennzeichen
            str_val = str_val.replace(",", ".")
        
        return float(str_val)
    except (ValueError, TypeError):
        return None if allow_empty else 0.0


def brutto_to_netto(brutto: float, tax_rate: float = 19.0) -> float:
    """
    Konvertiert Brutto zu Netto mit gegebenem Steuersatz.
    
    Args:
        brutto: Brutto-Betrag
        tax_rate: Steuersatz in Prozent (Standard: 19.0)
        
    Returns:
        Netto-Betrag (gerundet auf 2 Dezimalstellen)
    """
    if brutto is None or brutto == 0:
        return 0.0
    tax_divisor = 1 + (tax_rate / 100)
    return round(brutto / tax_divisor, 2)


def netto_to_brutto(netto: float, tax_rate: float = 19.0) -> float:
    """
    Konvertiert Netto zu Brutto mit gegebenem Steuersatz.
    
    Args:
        netto: Netto-Betrag
        tax_rate: Steuersatz in Prozent (Standard: 19.0)
        
    Returns:
        Brutto-Betrag (gerundet auf 2 Dezimalstellen)
    """
    if netto is None or netto == 0:
        return 0.0
    tax_multiplier = 1 + (tax_rate / 100)
    return round(netto * tax_multiplier, 2)


def clean_string(value: Any, strip: bool = True, 
                 max_length: int = None) -> str:
    """
    Bereinigt einen String-Wert.
    
    Args:
        value: Der zu bereinigende Wert
        strip: Whitespace entfernen
        max_length: Maximale Länge (optional)
        
    Returns:
        Bereinigter String
    """
    if value is None:
        return ""
    
    result = str(value)
    
    if strip:
        result = result.strip()
    
    if max_length and len(result) > max_length:
        result = result[:max_length]
    
    return result


def is_valid_barcode(barcode: str) -> bool:
    """
    Prüft ob ein Barcode gültig ist (EAN-8, EAN-13, UPC-A).
    
    Args:
        barcode: Der zu prüfende Barcode
        
    Returns:
        True wenn gültig
    """
    if not barcode:
        return False
    
    barcode = str(barcode).strip()
    
    # Nur Ziffern erlaubt
    if not barcode.isdigit():
        return False
    
    # Mindestlänge 8 (EAN-8)
    if len(barcode) < 8:
        return False
    
    # Bekannte ungültige Barcodes (Platzhalter/Test-Barcodes)
    if barcode in INVALID_BARCODES:
        return False
    
    return True


# Bekannte ungültige/Test-Barcodes (können erweitert werden)
INVALID_BARCODES = frozenset([
    "0",
    "00000000",
    "0000000000000",
    "4017980000000",  # Häufiger Platzhalter-Barcode
])


def detect_barcode_type(barcode: str) -> str:
    """
    Erkennt den Barcode-Typ basierend auf der Länge.
    
    Args:
        barcode: Der Barcode
        
    Returns:
        Barcode-Typ ("EAN", "UPC-A", "ISBN", etc.)
    """
    if not barcode:
        return "EAN"
    
    length = len(str(barcode).strip())
    
    if length == 13:
        # Prüfe auf ISBN (beginnt mit 978 oder 979)
        if barcode.startswith(("978", "979")):
            return "ISBN"
        return "EAN"
    elif length == 12:
        return "UPC-A"
    elif length == 8:
        return "EAN-8"
    else:
        return "EAN"
