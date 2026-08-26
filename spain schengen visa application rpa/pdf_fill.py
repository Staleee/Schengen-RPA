"""
Fill the BLS Spain UAE Schengen visa application PDF (AcroForm).
Template: assets/schengen_visa_application_form_english.pdf

Field targets follow the verified mapping in FIELDS_TO_FILL.md (user + PDF catalog).
Optional overrides: my_pdf_mapping.json (see HOW_I_FIX_THE_MAPPING.md).
"""

import json
import warnings
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pypdf import PdfReader, PdfWriter

DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "assets" / "schengen_visa_application_form_english.pdf"
MY_PDF_MAPPING_PATH = Path(__file__).resolve().parent / "my_pdf_mapping.json"

# Named PDF fields (exact strings from PDF_FIELD_CATALOG.json)
STRUCTURED_FIELD_MAP: Dict[str, str] = {
    "surname_line_1": "1 ApellidosSumames",
    "surname_at_birth": "2 Apellidos de nacimiento apellidos anterioresSuma",
    "given_names_line_3": "3 NombresFirst names Given names",
    "national_id_number": "11 Número de documento nacional de identidad si pr",
    "phone": "Números de teléfonoTelephone numbers",
    "residence_permit_details": "SiYes Permiso de residencia o documento equivalent",
    "residence_number": "nnumber",
    "residence_valid_until": "válido hasta el valid until",
    "purpose_additional_info": "24 Información adicional sobre el motivo de la est",
    "first_entry_member_state": "26 Estado miembro de primera entradaMember State o",
    "occupation": "21 Profesión actual Current occupation",
    "other_specify": "otro especifiquese",
    "place_and_date": "Lugar y fechaPlace and date",
}

# Texto* boxes (user-verified layout)
TEXTO_FIELD_MAP: Dict[str, str] = {
    "maid_date_of_birth": "Texto1",
    "maid_place_of_birth": "Texto2",
    "country_of_birth": "Texto3",
    "nationality_line_top": "Texto4",
    "nationality_line_bottom": "Texto5",
    "passport_number": "Texto10",
    "passport_issue_date": "Texto11",
    "passport_expiry_date": "Texto12",
    "passport_issuing_country": "Texto13",
    "maid_address_email_combined": "Texto18",
    "employer_block_text": "Texto19",
    "destination_member_state_line": "Texto21",
    "arrival_date": "Texto22",
    "departure_date": "Texto23",
    # §31 host/travel: upper = client name + hotel; lower = client email + hotel
    "host_upper_name_hotel_stacked": "Texto25",
    "host_lower_email_hotel_stacked": "Texto26",
    # §34 costs / sponsor: name, then address + client email below
    "sponsor_section_client_name": "Texto31",
    "sponsor_section_address_email_stacked": "Texto32",
}

CHECKBOX_ALIASES: Dict[str, str] = {
    "sex_male": "VarónMale",
    "sex_female": "MujerFemale",
    "marital_status_single": "ChkBox",
    "marital_status_married": "ChkBox-0",
    "civil_status_single": "ChkBox",
    "marital_married": "ChkBox-0",
    "travel_doc_ordinary_passport": "Pasaporte ordinarioOrdinary Passport",
    "purpose_tourism": "TurismoTourism",
    "purpose_business": "NegociosBusiness",
    "purpose_visiting_family": "Visita a familiares o amigosVisiting family or fri",
    "entries_one": "UnaOne entry",
    "entries_two": "DosTwo entries",
    "entries_multiple": "MúltiplesMultiple entries",
    "resident_outside_nationality_yes": "20 Residente en un país distinto del país de nacio",
    "all_expenses_covered_during_stay": "Todos los gastos de estancia están cubiertosAll ex",
    "costs_paid_by_sponsor_host": "por un patrocinador anfitrión empresa u organizaci",
    # §33 sub-option under "by a sponsor" — the host is the one already named in §30/§31.
    "costs_sponsor_referred_in_field_30_or_31": "indicado en las casillas 30 031",
    "schengen_before_yes": "SÍyes",
    "schengen_before_no": "NOno",
}

# Section 31 host phone (page 3) — distinct from maid phone on page 2
HOST_TRAVEL_PHONE_PDF = "Números de teléfonoTelephone numbers-0"
SPONSOR_PHONE_PDF = "Número de teléfono  Phone number"

# Printed “32” (company name/address) — leave blank per ops; not the same as generic `Texto32`.
FIELD_32_COMPANY_LINE = "32 Nombre y dirección de la empresa u organización"

# Cleared unless caller passes them in `pdf_fields` (applied before pdf_fields merge).
FORCE_EMPTY_UNLESS_PDF_FIELDS: Tuple[str, ...] = (
    "Texto17",
    "Texto27",
    FIELD_32_COMPANY_LINE,
)

# Page-1 footer repeats of §1 / §3 — ops leave blank (not a second copy of surname/given names).
FOOTER_NAME_FIELDS_ALWAYS_BLANK: Tuple[str, ...] = (
    "ApellidosSumamefamily name",
    "NombresFirst names Given names",
)


def _load_effective_maps() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    structured = dict(STRUCTURED_FIELD_MAP)
    texto = dict(TEXTO_FIELD_MAP)
    checkbox = dict(CHECKBOX_ALIASES)
    if MY_PDF_MAPPING_PATH.is_file():
        try:
            data = json.loads(MY_PDF_MAPPING_PATH.read_text(encoding="utf-8"))
            if isinstance(data.get("structured"), dict):
                structured.update({str(k): str(v) for k, v in data["structured"].items()})
            if isinstance(data.get("texto"), dict):
                texto.update({str(k): str(v) for k, v in data["texto"].items()})
            if isinstance(data.get("checkbox"), dict):
                checkbox.update({str(k): str(v) for k, v in data["checkbox"].items()})
        except json.JSONDecodeError as e:
            warnings.warn(f"Ignoring my_pdf_mapping.json (invalid JSON): {e}", stacklevel=2)
        except (OSError, TypeError) as e:
            warnings.warn(f"Ignoring my_pdf_mapping.json: {e}", stacklevel=2)
    return structured, texto, checkbox


def _truthy(v: Any) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _build_updates(structured: Dict[str, Any], pdf_fields: Optional[Dict[str, str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    smap, tmap, cmap = _load_effective_maps()

    for key, pdf_name in smap.items():
        if key not in structured:
            continue
        val = structured[key]
        if val is None:
            continue
        out[pdf_name] = str(val).strip()

    for key, pdf_name in tmap.items():
        if key not in structured:
            continue
        val = structured[key]
        if val is None:
            continue
        out[pdf_name] = str(val).strip()

    for alias, pdf_name in cmap.items():
        if alias not in structured:
            continue
        out[pdf_name] = "/On" if _truthy(structured[alias]) else "/Off"

    if structured.get("host_travel_phone"):
        out[HOST_TRAVEL_PHONE_PDF] = str(structured["host_travel_phone"]).strip()
    if structured.get("sponsor_client_phone_line"):
        out[SPONSOR_PHONE_PDF] = str(structured["sponsor_client_phone_line"]).strip()

    for fn in FORCE_EMPTY_UNLESS_PDF_FIELDS:
        out[fn] = ""

    if pdf_fields:
        for k, v in pdf_fields.items():
            if v is None:
                continue
            out[str(k).strip()] = str(v).strip()

    for fn in FOOTER_NAME_FIELDS_ALWAYS_BLANK:
        out[fn] = ""

    return out


def _fill_with_fitz(template: Path, updates: Dict[str, str]) -> bytes:
    """Apply AcroForm values with PyMuPDF (more reliable than pypdf on this BLS PDF)."""
    import fitz

    from pdf_field_resolve import collect_field_names_from_pdf, resolve_updates

    path_str = str(template)
    canonical = collect_field_names_from_pdf(path_str)
    resolved = resolve_updates(updates, canonical)

    doc = fitz.open(path_str)
    try:
        # Single appearance pass (helps some viewers); duplicate AcroForm widgets are handled below
        try:
            doc.need_appearances = True
        except (AttributeError, RuntimeError):
            pass
        cb = fitz.PDF_WIDGET_TYPE_CHECKBOX
        text_field_seen: set[str] = set()
        for i in range(len(doc)):
            for w in doc[i].widgets() or []:
                fn = w.field_name
                if not fn or fn not in resolved:
                    continue
                val = resolved[fn]
                if w.field_type == cb:
                    sval = str(val).strip()
                    is_on = sval in ("/On", "/Yes", "Yes", "on", "On", "true", "True", "1")
                    w.field_value = is_on
                    w.update()
                else:
                    # BLS template often has two widgets sharing the same field name; updating both
                    # can draw overlapping text. Only the first text widget per name gets the value.
                    if fn in text_field_seen:
                        w.field_value = ""
                        w.update()
                        continue
                    text_field_seen.add(fn)
                    w.field_value = str(val)
                    w.update()
        return doc.tobytes()
    finally:
        doc.close()


def _fill_with_pypdf(template: Path, updates: Dict[str, str]) -> bytes:
    from pdf_field_resolve import collect_field_names_from_pdf, resolve_updates

    canonical = collect_field_names_from_pdf(str(template))
    resolved = resolve_updates(updates, canonical)
    reader = PdfReader(str(template), strict=False)
    writer = PdfWriter()
    writer.append(reader)
    if resolved:
        for page in writer.pages:
            writer.update_page_form_field_values(page, resolved, auto_regenerate=True)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def fill_spain_schengen_pdf(
    structured: Dict[str, Any],
    pdf_fields: Optional[Dict[str, str]] = None,
    template_path: Optional[Path] = None,
    merge_business_rules: bool = True,
) -> bytes:
    data = structured
    if merge_business_rules:
        from spain_merge import merge_spain_schengen_body

        data = merge_spain_schengen_body(structured)

    path = template_path or DEFAULT_TEMPLATE
    if not path.exists():
        raise FileNotFoundError(f"PDF template not found: {path}")

    updates = _build_updates(data, pdf_fields)

    try:
        return _fill_with_fitz(path, updates)
    except ImportError:
        warnings.warn("pymupdf not installed; using pypdf (fewer fields may appear). pip install pymupdf", stacklevel=2)
        return _fill_with_pypdf(path, updates)
