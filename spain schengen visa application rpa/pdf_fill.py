"""
Fill the BLS Spain UAE Schengen visa application PDF (AcroForm).
Template: assets/schengen_visa_application_form_english.pdf

Field targets follow the verified mapping in FIELDS_TO_FILL.md (user + PDF catalog).
Optional overrides: my_pdf_mapping.json (see HOW_I_FIX_THE_MAPPING.md).
"""

import json
import re
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
    # §9 marital status. The form offers Single / Married / Registered union / Separated /
    # Divorced / Widow-er / Other, and HousemaidCivilStatus in the ERP is SINGLE, MARRIED,
    # DIVORCED or WIDOW — but only the first two were ever mapped, so a divorced or widowed
    # maid had nothing ticked at all.
    "marital_status_single": "ChkBox",
    "marital_status_married": "ChkBox-0",
    "marital_status_divorced": "ChkBox-1",
    "marital_status_widowed": "ChkBox-2",
    "marital_status_separated": "SeparadoaSeparated",
    "marital_status_registered_union": "Unión registrada",
    "civil_status_single": "ChkBox",
    "marital_married": "ChkBox-0",
    "travel_doc_ordinary_passport": "Pasaporte ordinarioOrdinary Passport",
    "purpose_tourism": "TurismoTourism",
    "purpose_business": "NegociosBusiness",
    "purpose_visiting_family": "Visita a familiares o amigosVisiting family or fri",
    "entries_one": "UnaOne entry",
    "entries_two": "DosTwo entries",
    "entries_multiple": "MúltiplesMultiple entries",
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

# Printed “19” (the applicant's own home address + email, and her phone number) — both boxes
# stay blank per ops. Note the phone here is the page-2 maid phone; the §31 host phone is the
# distinct `…-0` field above and is still filled.
FIELD_19_ADDRESS_EMAIL = "Texto18"
FIELD_19_PHONE = "Números de teléfonoTelephone numbers"

# Cleared unless caller passes them in `pdf_fields` (applied before pdf_fields merge).
FORCE_EMPTY_UNLESS_PDF_FIELDS: Tuple[str, ...] = (
    "Texto17",
    "Texto27",
    FIELD_32_COMPANY_LINE,
    FIELD_19_ADDRESS_EMAIL,
    FIELD_19_PHONE,
)

# Printed “20” (resident of a country other than the country of current nationality) is a RADIO
# group, not a checkbox: both widgets share one field name and each carries its own on-state, so
# writing "/On" did nothing and the field always printed blank. Selecting the group means finding
# the widget whose on-state identifies the answer. Matched on a distinguishing substring because
# the real on-states are long PDF-escaped names ("20#20Residente#20en#20un#20pa#C3#ADs…_SiYes…").
# logical key -> (field name, substring identifying the wanted widget's on-state)
RADIO_GROUPS: Dict[str, Tuple[str, str]] = {
    "resident_outside_nationality_yes": (
        "20 Residente en un país distinto del país de nacio",
        "siyes",
    ),
    "resident_outside_nationality_no": (
        "20 Residente en un país distinto del país de nacio",
        "nono",
    ),
}

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


# Printed field -> what has to be present for it to render at all. These come off the maid's
# profile, so when the profile is incomplete the box simply prints blank and the gap is only
# noticed once a consulate rejects the application. Reported instead of silently skipped; the
# values cannot be defaulted here (nobody should be inventing a marital status on a visa form).
REQUIRED_FOR_SUBMISSION: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("5 place of birth", ("maid_place_of_birth",)),
    ("8 sex", ("sex_male", "sex_female")),
    ("9 marital status", ("marital_status_single", "marital_status_married")),
    ("13 travel document number", ("passport_number",)),
    ("14 date of issue", ("passport_issue_date",)),
    ("15 valid until", ("passport_expiry_date",)),
    ("16 issued by", ("passport_issuing_country",)),
)


def missing_required_fields(structured: Dict[str, Any]) -> Tuple[str, ...]:
    """Printed fields that will come out blank because no source value arrived."""
    missing = []
    for label, keys in REQUIRED_FOR_SUBMISSION:
        if not any(_present(structured.get(k)) for k in keys):
            missing.append(label)
    return tuple(missing)


def _present(value: Any) -> bool:
    """A tick box counts as present only when actually on; a text box when non-blank."""
    if isinstance(value, bool):
        return value
    return bool(str(value).strip()) if value is not None else False


def _radio_selections(structured: Dict[str, Any]) -> Dict[str, str]:
    """field name -> on-state substring, for each radio group the body answers."""
    out: Dict[str, str] = {}
    for logical, (field_name, on_state) in RADIO_GROUPS.items():
        if _truthy(structured.get(logical)):
            out[field_name] = on_state
    return out


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


def _fill_with_fitz(
    template: Path, updates: Dict[str, str], radio_on: Optional[Dict[str, str]] = None
) -> bytes:
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
        if _drop_duplicate_widgets(doc):
            # Removing annotations leaves the remaining ones unbound, even on a fresh widgets()
            # call, so the document is round-tripped to get clean state before filling.
            data = doc.tobytes()
            doc.close()
            doc = fitz.open(stream=data, filetype="pdf")
        # Drawing on a page invalidates that page's other Annot objects, so ticks are collected
        # here as (page index, rect) and drawn once every widget has been written.
        marks: list = []
        for i in range(len(doc)):
            # Iterated lazily on purpose: updating one widget unbinds the others in a snapshot.
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
                    if is_on:
                        marks.append((i, fitz.Rect(w.rect)))
                else:
                    w.field_value = str(val)
                    w.update()
        marks.extend(_select_radios(doc, radio_on or {}))
        for page_index, rect in marks:
            _draw_selected_mark(doc[page_index], rect)
        return doc.tobytes()
    finally:
        doc.close()


def _select_radios(doc, radio_on: Dict[str, str]) -> list:
    """Turn on the widget of each radio group whose on-state matches the wanted answer.

    A radio group's widgets all share one field name, so it cannot be set by name like a
    checkbox — each widget carries its own on-state and setting that state selects it. The
    on-state comes back PDF-name-escaped (``#20`` = space, ``#C3#AD`` = í), so it is decoded
    before matching the substring from RADIO_GROUPS. Returns the rects to mark, for the caller to
    draw once all widgets have been written.
    """
    if not radio_on:
        return []
    import fitz

    def decode(name: str) -> str:
        return re.sub(r"#([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), name or "")

    marks = []
    for index, page in enumerate(doc):
        for w in page.widgets() or []:
            if w.field_type != fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
                continue
            wanted = radio_on.get(w.field_name)
            if wanted and wanted.lower() in decode(w.on_state()).lower():
                w.field_value = w.on_state()
                w.update()
                marks.append((index, fitz.Rect(w.rect)))
    return marks


def _drop_duplicate_widgets(doc) -> int:
    """Remove redundant widgets stacked on top of one another.

    Nine text fields on page 3 of this template carry two widget annotations 0.5pt apart. All the
    widgets of one AcroForm field show that field's single value, so each of those printed its
    value twice, overlapping — the §31 host phone, the §34 sponsor phone and the sponsor name all
    came out doubled at two different auto-sizes, looking like a printing fault on a submitted
    application. It cannot be fixed by blanking one of them: there is only one value behind both.

    Only widgets of the same field that actually sit on top of each other are dropped, so a field
    legitimately repeated elsewhere on the form is left alone.
    """
    removed = 0
    for page in doc:
        # Deleting an annotation unbinds the page's other Annot objects, so the page is rescanned
        # after each removal rather than deleting from a snapshot.
        while True:
            target = None
            kept: Dict[str, list] = {}
            for index, widget in enumerate(page.widgets() or []):
                name = widget.field_name
                if not name:
                    continue
                rect = widget.rect
                for other in kept.get(name, []):
                    overlap = (rect & other).get_area()
                    smaller = min(rect.get_area(), other.get_area())
                    if smaller > 0 and overlap > 0.5 * smaller:
                        target = index
                        break
                if target is not None:
                    break
                kept.setdefault(name, []).append(rect)
            if target is None:
                break
            for index, widget in enumerate(page.widgets() or []):
                if index == target:
                    page.delete_widget(widget)
                    removed += 1
                    break
    return removed


def _draw_selected_mark(page, rect) -> None:
    """Draw a cross in a ticked box, on top of whatever appearance the widget carries.

    The template's widgets do not agree on what "ticked" looks like: some draw a full cross,
    others a small centred dot barely a fifth the size. §20 and §9 were both reported as unticked
    when the fields were in fact set, because a dot on a printed application reads as a speck.
    Drawing the mark into the page itself makes every tick identical and unmistakable, and makes
    it independent of whether the reader's viewer regenerates form appearances at all.
    """
    inset = min(rect.width, rect.height) * 0.22
    box = (rect.x0 + inset, rect.y0 + inset, rect.x1 - inset, rect.y1 - inset)
    width = max(0.6, min(rect.width, rect.height) * 0.1)
    page.draw_line((box[0], box[1]), (box[2], box[3]), color=(0, 0, 0), width=width)
    page.draw_line((box[0], box[3]), (box[2], box[1]), color=(0, 0, 0), width=width)


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

    missing = missing_required_fields(data)
    if missing:
        print(f"[spain] !! these printed fields have no source value and will be blank: {list(missing)}")

    try:
        return _fill_with_fitz(path, updates, _radio_selections(data))
    except ImportError:
        warnings.warn("pymupdf not installed; using pypdf (fewer fields may appear). pip install pymupdf", stacklevel=2)
        return _fill_with_pypdf(path, updates)
