# ERPNext Produkt-Importer v2 🚀

Ein mächtiges Import-Tool für ERPNext.

## ✨ Features

### 📥 Datenimport
- **CSV-Import** mit konfigurierbarem Trennzeichen und Encoding (inkl. UTF-8 BOM)
- **BMECat XML** Support
- Datenvorschau vor dem Import
- **Dry-Run Modus** zum Testen

### 🗺️ Flexibles Feld-Mapping
- **Auto-Mapping**: Erkennt Spalten automatisch
- Transformationen: Trim, Uppercase, Lowercase, Number, Boolean, HTML-Strip
- Standardwerte für leere Felder
- Vorlagen speichern & laden

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
  "base_url": "https://erp.kreckler.shop",
  "api_key": "DEIN_API_KEY",
  "api_secret": "DEIN_API_SECRET",
  "company": "Kreckler GmbH",
  "default_warehouse": "Lager - KG",
  "default_price_list": "Standard-Verkauf",
  "default_item_group": "Alle Artikelgruppen"
}
```

## 📖 Verwendung

### 1. Verbinden
- Einstellungen → API-Daten eingeben → "Verbindung testen"

### 2. Datei laden
- "CSV auswählen" oder "BMECat XML"
- CSV-Optionen anpassen (Trennzeichen, Encoding)

### 3. Felder zuordnen
- Tab "Feld-Mapping" → "Auto-Mapping" klicken
- Manuelle Anpassungen vornehmen

### 4. Import starten
- Import-Modus wählen
- Optional: "Dry Run" aktivieren
- "Import starten"

## 🔄 Auto-Mapping

Folgende Spalten werden automatisch erkannt:

| Spalte | ERPNext-Feld |
|------------|--------------|
| Artikelnummer | item_code |
| Artikelname | item_name |
| Beschreibung | description |
| Netto-VK | standard_rate |
| GTIN | gtin (→ Barcode) |
| HAN | manufacturer_part_no |
| Hersteller | brand |
| Titel-Tag (SEO) | seo_title |
| Meta-Description (SEO) | seo_meta_description |
| URL-Pfad | seo_url_slug |
| Länge/Breite/Höhe | item_length/width/height |
| ... | ... |

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

**Modus "Artikelnummer-Nummer":**
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

### Encoding-Probleme
- Probiere "UTF-8 (BOM)" für JTL-Exporte
- Oder "Windows-1252" für ältere Dateien

### "Pflichtfelder fehlen"
- item_code muss zugeordnet sein
- Bei Kategorien: item_group_name


