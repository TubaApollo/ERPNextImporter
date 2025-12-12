# ERPNext Produkt-Importer v2 🚀

Ein mächtiges Import-Tool für ERPNext mit intelligenter Feld-Erkennung, Custom Fields Support und AI-Mapping.

## ✨ Features

### 📥 Datenimport
- **CSV-Import** mit konfigurierbarem Trennzeichen und Encoding (inkl. UTF-8 BOM)
- **BMECat XML** Support
- Datenvorschau vor dem Import
- **Dry-Run Modus** zum Testen
- **Batch-Verarbeitung** für große Imports

### 🗺️ Flexibles Feld-Mapping
- **Auto-Mapping**: Erkennt Spalten automatisch nach JTL-Ameise-Konventionen
- **AI Smart-Mapping**: Nutze Google Gemini für intelligente Feld-Erkennung
- **✨ Custom Fields**: Lädt automatisch benutzerdefinierte Felder von ERPNext
- Transformationen: Trim, Uppercase, Lowercase, Number, Boolean, HTML-Strip
- Standardwerte für leere Felder
- Vorlagen speichern & laden

### 🔧 ERPNext-Integration
- **Custom Fields automatisch erkennen** - Lädt alle benutzerdefinierten Felder direkt von ERPNext
- **Intelligente UOM-Konvertierung** (Stück, kg, Liter, etc.)
- **Konfigurierbarer Steuersatz** für Brutto/Netto-Umrechnung
- **Kategorie-Hierarchie** - Erstellt automatisch verschachtelte Kategorien
- Verbesserte Fehlerbehandlung mit hilfreichen Tipps

### 🖼️ Bilder-Verwaltung
- **Massenupload** von Produktbildern
- Bilder **ersetzen** oder **löschen**
- Flexible Zuordnung (Artikelnummer, Prefix, Bindestrich)
- Mehrere Bilder pro Artikel (ART123-1.jpg, ART123-2.jpg)

### ⚡ Import-Modi
- **Nur Anlegen**: Überspringt existierende
- **Nur Aktualisieren**: Ändert nur vorhandene
- **Anlegen & Aktualisieren**: Kompletter Sync

## 🚀 Installation

```bash
# Windows - Doppelklick auf:
start.bat

# Oder manuell:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## ⚙️ Konfiguration

`erpnext_config.json`:
```json
{
  "base_url": "https://erp.example.com",
  "api_key": "DEIN_API_KEY",
  "api_secret": "DEIN_API_SECRET",
  "company": "Meine Firma GmbH",
  "default_warehouse": "Lager - MF",
  "default_price_list": "Standard-Verkauf",
  "default_item_group": "Alle Artikelgruppen",
  "gemini_api_key": "AIza...",
  "default_tax_rate": 19.0,
  "batch_size": 50,
  "request_timeout": 30
}
```

### Neue Einstellungen

| Einstellung | Beschreibung | Standard |
|-------------|--------------|----------|
| `default_tax_rate` | MwSt-Satz für Brutto→Netto | 19.0 |
| `batch_size` | Datensätze pro Batch | 50 |
| `request_timeout` | API-Timeout in Sekunden | 30 |
| `gemini_api_key` | Google Gemini AI Key | - |

## 📖 Verwendung

### 1. Verbinden
- Einstellungen → API-Daten eingeben → "Verbindung testen"

### 2. Custom Fields laden (NEU!)
- Tab "Feld-Mapping" → "Custom Fields laden" klicken
- Alle benutzerdefinierten Felder von ERPNext werden automatisch geladen
- Custom Fields werden mit ✨ markiert

### 3. Datei laden
- "CSV auswählen" oder "BMECat XML"
- CSV-Optionen anpassen (Trennzeichen, Encoding)

### 4. Felder zuordnen
- Tab "Feld-Mapping" → "Auto-Mapping" oder "AI Smart-Mapping"
- Manuelle Anpassungen vornehmen

### 5. Import starten
- Import-Modus wählen
- Optional: "Dry Run" aktivieren
- "Import starten"

## 🤖 AI Smart-Mapping (Gemini)

Mit Google Gemini AI kann der Importer intelligente Feld-Zuordnungen vornehmen:

1. **API Key holen**: https://aistudio.google.com/apikey
2. In Einstellungen eintragen
3. Bei "Feld-Mapping" auf "AI Smart-Mapping" klicken

Die AI analysiert:
- Spaltennamen und Muster
- Beispieldaten aus der CSV
- ERPNext-Felddefinitionen (inkl. Custom Fields!)

## ✨ Custom Fields

Der Importer erkennt automatisch alle Custom Fields die in ERPNext für:
- **Item** (Artikel)
- **Item Group** (Kategorien)

definiert wurden.

### So funktioniert's:
1. Verbindung zu ERPNext herstellen
2. "Custom Fields laden" klicken
3. Custom Fields erscheinen in der Mapping-Dropdown mit ✨-Markierung

## 🔄 Auto-Mapping

Folgende Spalten werden automatisch erkannt:

| Spalte | ERPNext-Feld |
|------------|--------------|
| Artikelnummer | item_code |
| Artikelname | item_name |
| Beschreibung | description |
| Netto-VK / VK Netto | standard_rate |
| Brutto-VK / VK Brutto | standard_rate (mit Umrechnung) |
| GTIN / EAN | barcode (in Barcode-Tabelle) |
| HAN | manufacturer_part_no |
| Hersteller / Marke | brand |
| Kategorie Ebene 1-4 | category_level_1-4 (Hierarchie) |
| Kategoriepfad | category_path (z.B. "A > B > C") |
| Titel-Tag (SEO) | seo_title |
| Meta-Description (SEO) | seo_meta_description |
| URL-Pfad | seo_url_slug |
| Länge/Breite/Höhe | item_length/width/height |
| Gewicht | weight_per_unit |

### Kategorie-Hierarchie

Der Importer unterstützt automatische Erstellung von verschachtelten Kategorien:

**Option 1: Separate Spalten**
```csv
Kategorie Ebene 1;Kategorie Ebene 2;Kategorie Ebene 3
Elektronik;Computer;Laptops
```

**Option 2: Kategoriepfad**
```csv
Kategoriepfad
Elektronik > Computer > Laptops
```

## 🖼️ Bilder-Import

### Dateinamen-Konventionen

**Modus "Artikelnummer = Dateiname":**
```
ART123.jpg → Artikel ART123
```

**Modus "Artikelnummer als Prefix":**
```
ART123_1.jpg → Artikel ART123 (Bild 1)
ART123_2.jpg → Artikel ART123 (Bild 2)
```

**Modus "Artikelnummer-Nummer" (JTL-Format):**
```
ART123-1.jpg → Artikel ART123 (Bild 1)
ART123-2.jpg → Artikel ART123 (Bild 2)
```

Das erste Bild (sortiert) wird als Hauptbild gesetzt.

## 📁 Projektstruktur

```
erpnext_importer_v2/
├── main.py              # Hauptanwendung
├── requirements.txt     # Python-Dependencies
├── start.bat           # Windows-Starter
├── erpnext_config.json # API-Konfiguration
├── templates/          # Gespeicherte Vorlagen
└── logs/              # Export-Logs
```

## 🐛 Troubleshooting

### "requests library not available"
```bash
pip install requests
```

### "Verbindung fehlgeschlagen"
- URL mit https:// prüfen
- API Key/Secret korrekt?
- Benutzer hat API-Berechtigung?
- Timeout in Einstellungen erhöhen

### "Pflichtfelder fehlen"
- item_code muss zugeordnet sein
- Bei Kategorien: item_group_name

### "Custom Fields werden nicht geladen"
- Erst "Verbindung testen" erfolgreich durchführen
- API-Benutzer braucht Leserecht für "Custom Field" DocType

### Import ist langsam
- Batch-Größe in Einstellungen reduzieren (20-30)
- Timeout erhöhen
- Dry-Run erst testen

## 📋 Lizenz

MIT License

