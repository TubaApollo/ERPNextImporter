"""
ERPNext Feld-Definitionen und Auto-Mapping-Regeln
"""

from typing import Dict

# ==================== ERPNext FELDER ====================

ERPNEXT_ITEM_FIELDS: Dict[str, Dict] = {
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

ERPNEXT_ITEM_GROUP_FIELDS: Dict[str, Dict] = {
    "item_group_name": {"label": "Kategoriename*", "type": "Data", "required": True},
    "parent_item_group": {"label": "Oberkategorie", "type": "Link"},
    "description": {"label": "Beschreibung", "type": "Text"},
    "seo_title": {"label": "SEO Title", "type": "Data"},
    "seo_meta_description": {"label": "SEO Meta Description", "type": "Small Text"},
    "seo_keywords": {"label": "SEO Keywords", "type": "Data"},
}

ERPNEXT_ATTRIBUTE_FIELDS: Dict[str, Dict] = {
    "attribute_name": {"label": "Attribut-Name*", "type": "Data", "required": True},
    "attribute_values": {"label": "Attributwerte (kommagetrennt)", "type": "Data"},
    "numeric_values": {"label": "Numerische Werte", "type": "Check"},
    "from_range": {"label": "Von (Bereich)", "type": "Float"},
    "to_range": {"label": "Bis (Bereich)", "type": "Float"},
    "increment": {"label": "Schrittweite", "type": "Float"},
}

ERPNEXT_VARIANT_FIELDS: Dict[str, Dict] = {
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

# Export-Felder für Artikel
EXPORT_ITEM_FIELDS: Dict[str, str] = {
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
EXPORT_ATTRIBUTE_FIELDS: Dict[str, str] = {
    "name": "Attribut-Name",
    "attribute_name": "Attribut-Bezeichnung",
    "numeric_values": "Numerische Werte",
    "from_range": "Von (Bereich)",
    "to_range": "Bis (Bereich)",
    "increment": "Schrittweite",
    "attribute_values": "Attributwerte",
}

# ==================== AUTO-MAPPING REGELN ====================

AUTO_MAPPING_RULES: Dict[str, str] = {
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

# ==================== UOM MAPPING ====================

UOM_MAPPING: Dict[str, str] = {
    "stück": "Stk",
    "stk": "Stk",
    "stck": "Stk",
    "pcs": "Stk",
    "piece": "Stk",
    "pieces": "Stk",
    "kg": "Kg",
    "kilogramm": "Kg",
    "kilo": "Kg",
    "g": "Gramm",
    "gramm": "Gramm",
    "gram": "Gramm",
    "l": "Liter",
    "liter": "Liter",
    "litre": "Liter",
    "ml": "Milliliter",
    "milliliter": "Milliliter",
    "m": "Meter",
    "meter": "Meter",
    "cm": "Zentimeter",
    "zentimeter": "Zentimeter",
    "mm": "Millimeter",
    "millimeter": "Millimeter",
    "set": "Set",
    "paar": "Paar",
    "pair": "Paar",
    "box": "Box",
    "karton": "Karton",
    "palette": "Palette",
}


def get_target_fields(import_type: str, custom_fields: Dict[str, Dict] = None) -> Dict[str, Dict]:
    """
    Gibt die Zielfelder basierend auf Import-Typ zurück.
    
    Args:
        import_type: Der Import-Typ (artikel, kategorien, attribute, varianten)
        custom_fields: Optionale Custom Fields zum Hinzufügen
        
    Returns:
        Dictionary mit Feldname -> Feldinformationen
    """
    if import_type == "kategorien":
        fields = dict(ERPNEXT_ITEM_GROUP_FIELDS)
    elif import_type == "attribute":
        fields = dict(ERPNEXT_ATTRIBUTE_FIELDS)
    elif import_type == "varianten":
        fields = dict(ERPNEXT_VARIANT_FIELDS)
    else:  # artikel, preise
        fields = dict(ERPNEXT_ITEM_FIELDS)
    
    if custom_fields:
        fields.update(custom_fields)
    
    return fields
