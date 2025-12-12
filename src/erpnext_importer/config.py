"""
Konfiguration und Datenmodelle für den ERPNext Importer
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional


@dataclass
class ERPNextConfig:
    """ERPNext API Konfiguration"""
    base_url: str = "https://erp.example.com"
    api_key: str = ""
    api_secret: str = ""
    company: str = "Meine Firma GmbH"
    default_warehouse: str = "Lager - MF"
    default_price_list: str = "Standard-Verkauf"
    default_item_group: str = "Alle Artikelgruppen"
    # Gemini AI
    gemini_api_key: str = ""
    # Import Settings
    default_tax_rate: float = 19.0  # MwSt-Satz für Brutto/Netto-Konvertierung
    batch_size: int = 50  # Anzahl der Datensätze pro Batch
    request_timeout: int = 30  # Timeout in Sekunden
    max_retries: int = 3  # Maximale Anzahl Wiederholungen bei Fehlern

    @property
    def auth_header(self) -> Dict[str, str]:
        """Gibt die Authentifizierungs-Header zurück"""
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validiert die Konfiguration und gibt Fehler zurück.
        
        Returns:
            Tuple von (ist_valide, Liste von Fehlermeldungen)
        """
        errors = []
        
        if not self.base_url or self.base_url == "https://erp.example.com":
            errors.append("ERPNext URL muss konfiguriert werden")
        elif not self.base_url.startswith(("http://", "https://")):
            errors.append("ERPNext URL muss mit http:// oder https:// beginnen")
        
        if not self.api_key:
            errors.append("API Key fehlt")
        
        if not self.api_secret:
            errors.append("API Secret fehlt")
            
        if self.default_tax_rate < 0 or self.default_tax_rate > 100:
            errors.append("Steuersatz muss zwischen 0 und 100 liegen")
            
        return len(errors) == 0, errors
    
    def to_dict(self) -> dict:
        """Konvertiert die Konfiguration zu einem Dictionary"""
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "company": self.company,
            "default_warehouse": self.default_warehouse,
            "default_price_list": self.default_price_list,
            "default_item_group": self.default_item_group,
            "gemini_api_key": self.gemini_api_key,
            "default_tax_rate": self.default_tax_rate,
            "batch_size": self.batch_size,
            "request_timeout": self.request_timeout,
            "max_retries": self.max_retries,
        }


@dataclass
class FieldMapping:
    """Einzelne Feld-Zuordnung zwischen Quelle und ERPNext"""
    source_column: str
    target_field: str
    transform: str = "none"
    default_value: str = ""


@dataclass
class ImportTemplate:
    """Import-Vorlage für wiederverwendbare Mappings"""
    name: str
    import_type: str
    file_format: str
    mappings: List[FieldMapping] = field(default_factory=list)
    csv_delimiter: str = ";"
    csv_encoding: str = "utf-8"
    skip_first_row: bool = True
    created_at: str = ""
    
    def to_dict(self) -> dict:
        """Konvertiert die Vorlage zu einem Dictionary"""
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
        """Erstellt eine Vorlage aus einem Dictionary"""
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
class ImportResult:
    """Ergebnis eines Import-Vorgangs"""
    total: int = 0
    success: int = 0
    errors: int = 0
    skipped: int = 0
    error_messages: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Berechnet die Erfolgsrate in Prozent"""
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100
    
    def add_error(self, message: str):
        """Fügt eine Fehlermeldung hinzu"""
        self.errors += 1
        self.error_messages.append(message)
    
    def add_success(self):
        """Zählt einen Erfolg"""
        self.success += 1
    
    def add_skip(self):
        """Zählt einen übersprungenen Datensatz"""
        self.skipped += 1
