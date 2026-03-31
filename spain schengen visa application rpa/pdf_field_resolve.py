"""
Map intended PDF field names (code / handwritten typos) → actual AcroForm names in the file.

Uses: exact match → manual typo table → accent-insensitive match → fuzzy match (difflib).
"""

from __future__ import annotations

import difflib
import unicodedata
from typing import Dict, Iterable, List, Set, Tuple

# Normalized typo / shorthand → exact name in bundled BLS PDF (when different)
_MANUAL: Dict[str, str] = {
    # User "ApellidosSurnames" etc.
    "apellidossurnames": "1 ApellidosSumames",
    "apellidosdesnacimientoapellidosanteriore": "2 Apellidos de nacimiento apellidos anterioresSuma",
    "apellidosdenacimientoapellidosanterioressuma": "2 Apellidos de nacimiento apellidos anterioresSuma",
    "nombresfirstnamesgivennames": "3 NombresFirst names Given names",
    "passaporteordinarioordinarypassport": "Pasaporte ordinarioOrdinary Passport",
    "turisomotourism": "TurismoTourism",
    "informacionadicionalsobreelmotivodel": "24 Información adicional sobre el motivo de la est",
    "estadomiembrodeprimeraetradamemberst": "26 Estado miembro de primera entradaMember State o",
    "estadomiembrodeprimeraentradamemberstateo": "26 Estado miembro de primera entradaMember State o",
    "multiplesmultipleentries": "MúltiplesMultiple entries",
    "nono": "NOno",
    "siyes": "SÍyes",
    "validohaslaelvaliduntil": "válido hasta el valid until",
    "validohastaelvaliduntil": "válido hasta el valid until",
    "residenteunpaisdistintodelpaisdenacio": "20 Residente en un país distinto del país de nacio",
    "residenteenunpaisdistintodelpaisdenacio": "20 Residente en un país distinto del país de nacio",
    "numerosdetelefonotelephonenumbers0": "Números de teléfonoTelephone numbers-0",
    "numerosdetelephonotelephonenumbers": "Números de teléfonoTelephone numbers",
    "numerodetelefonophonenumber": "Número de teléfono  Phone number",
    "profesionactualcurrentoccupation": "21 Profesión actual Current occupation",
    "todoslosgastosdeestanciaestancubiertosa": "Todos los gastos de estancia están cubiertosAll ex",
    "lugaryfechaplaceanddate": "Lugar y fechaPlace and date",
    "varonmale": "VarónMale",
    "chkbox": "ChkBox",
    "chkbox0": "ChkBox-0",
    "unaoneentry": "UnaOne entry",
    "dostwoentries": "DosTwo entries",
    "porunpatrocinadoranfitrionempresauorganizaci": "por un patrocinador anfitrión empresa u organizaci",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return "".join(c.lower() if c.isalnum() else "" for c in s)


def _build_norm_index(canonical_names: Iterable[str]) -> Tuple[Set[str], Dict[str, str]]:
    actual: Set[str] = set()
    norm_to_actual: Dict[str, str] = {}
    for name in canonical_names:
        if not name:
            continue
        actual.add(name)
        n = _norm(name)
        norm_to_actual.setdefault(n, name)
    return actual, norm_to_actual


def collect_field_names_from_pdf(path: str) -> List[str]:
    try:
        import fitz

        doc = fitz.open(path)
        names: List[str] = []
        for i in range(len(doc)):
            for w in doc[i].widgets() or []:
                if w.field_name:
                    names.append(w.field_name)
        doc.close()
        return names
    except ImportError:
        from pypdf import PdfReader

        r = PdfReader(path, strict=False)
        return [str(k) for k in (r.get_fields() or {}).keys()]


def resolve_updates(
    updates: Dict[str, str],
    canonical_names: Iterable[str],
    fuzzy_cutoff: float = 0.72,
) -> Dict[str, str]:
    """
    Return a new dict with keys rewritten to names that exist in canonical_names.
    Values unchanged. Unknown keys are dropped if no match (optional log).
    """
    actual, norm_to_actual = _build_norm_index(canonical_names)
    norm_keys_sorted = sorted(norm_to_actual.keys(), key=len, reverse=True)

    out: Dict[str, str] = {}
    dropped: List[str] = []

    for key, val in updates.items():
        resolved = resolve_one_field_name(key, actual, norm_to_actual, norm_keys_sorted, fuzzy_cutoff)
        if resolved in actual:
            out[resolved] = val
        elif key in actual:
            out[key] = val
        else:
            dropped.append(key)

    if dropped:
        import warnings

        warnings.warn(
            "PDF field names not found in template (skipped): " + ", ".join(dropped[:12])
            + ("..." if len(dropped) > 12 else ""),
            stacklevel=2,
        )

    return out


def resolve_one_field_name(
    desired: str,
    actual: Set[str],
    norm_to_actual: Dict[str, str],
    norm_keys_sorted: List[str],
    fuzzy_cutoff: float,
) -> str:
    if desired in actual:
        return desired

    nd = _norm(desired)
    if nd in _MANUAL:
        cand = _MANUAL[nd]
        if cand in actual:
            return cand

    if nd in norm_to_actual:
        return norm_to_actual[nd]

    m = difflib.get_close_matches(nd, norm_keys_sorted, n=1, cutoff=fuzzy_cutoff)
    if m:
        return norm_to_actual[m[0]]

    return desired
