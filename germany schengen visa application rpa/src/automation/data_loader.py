"""
Data Loader - Loads and validates applicant data from JSON files.
"""

import json
from pathlib import Path
from typing import Any, Optional
from rich.console import Console
from rich.table import Table

console = Console()


class DataValidationError(Exception):
    """Raised when applicant data validation fails."""
    pass


def load_applicant_data(data_path: Path) -> dict[str, Any]:
    """
    Load applicant data from a JSON file.
    
    Args:
        data_path: Path to the applicant data JSON file
    
    Returns:
        Dictionary containing the applicant data
    
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file is not valid JSON
    """
    if not data_path.exists():
        raise FileNotFoundError(f"Applicant data file not found: {data_path}")
    
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    console.print(f"[green]Loaded applicant data from {data_path}[/green]")
    return data


def flatten_applicant_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Flatten nested applicant data to a simple field_id -> value mapping.
    
    Handles both flat format and nested page format.
    
    Args:
        data: The loaded applicant data (possibly nested)
    
    Returns:
        Flat dictionary mapping field IDs to values
    """
    flat_data = {}
    
    # Check if it's the nested page format
    if "pages" in data:
        for page_key, page_data in data["pages"].items():
            if isinstance(page_data, dict) and "fields" in page_data:
                for field_id, field_info in page_data["fields"].items():
                    if isinstance(field_info, dict) and "value" in field_info:
                        flat_data[field_id] = field_info["value"]
                    else:
                        flat_data[field_id] = field_info
    else:
        # Already flat format - filter out comment keys
        for key, value in data.items():
            if not key.startswith("_"):
                flat_data[key] = value
    
    return flat_data


def validate_required_fields(
    data: dict[str, Any],
    schema_path: Optional[Path] = None,
    required_fields: Optional[list[str]] = None
) -> tuple[bool, list[str]]:
    """
    Validate that all required fields have values.
    
    Args:
        data: Flat applicant data dictionary
        schema_path: Path to the schema file (to get required fields)
        required_fields: List of required field IDs (alternative to schema)
    
    Returns:
        Tuple of (is_valid, list of missing required fields)
    """
    if required_fields is None and schema_path:
        required_fields = _get_required_fields_from_schema(schema_path)
    
    if required_fields is None:
        console.print("[yellow]Warning: No required fields specified, skipping validation[/yellow]")
        return True, []
    
    missing = []
    for field_id in required_fields:
        value = data.get(field_id)
        if value is None or value == "" or (isinstance(value, bool) and value is False):
            # For checkboxes, False might be valid, but for text fields empty is not
            if not isinstance(value, bool):
                missing.append(field_id)
    
    return len(missing) == 0, missing


def _get_required_fields_from_schema(schema_path: Path) -> list[str]:
    """Extract required field IDs from the schema file."""
    if not schema_path.exists():
        return []
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)
    
    required = []
    for page in schema.get("form_pages", []):
        for field in page.get("fields", []):
            if field.get("required", False):
                required.append(field.get("id"))
    
    return required


def display_data_summary(data: dict[str, Any], schema_path: Optional[Path] = None) -> None:
    """
    Display a summary of the applicant data.
    
    Args:
        data: Flat applicant data dictionary
        schema_path: Optional path to schema for field labels
    """
    # Load labels from schema if available
    labels = {}
    if schema_path and schema_path.exists():
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        for page in schema.get("form_pages", []):
            for field in page.get("fields", []):
                labels[field.get("id")] = field.get("label", field.get("id"))
    
    table = Table(title="Applicant Data Summary")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="yellow")
    
    filled_count = 0
    empty_count = 0
    
    for field_id, value in data.items():
        label = labels.get(field_id, field_id)
        
        # Truncate long values
        display_value = str(value)
        if len(display_value) > 50:
            display_value = display_value[:47] + "..."
        
        if value is None or value == "":
            status = "Empty"
            empty_count += 1
        else:
            status = "Filled"
            filled_count += 1
        
        table.add_row(label[:40], display_value, status)
    
    console.print(table)
    console.print(f"\n[bold]Summary:[/bold] {filled_count} filled, {empty_count} empty")


def merge_data_with_defaults(
    user_data: dict[str, Any],
    template_path: Path
) -> dict[str, Any]:
    """
    Merge user data with template defaults.
    
    Args:
        user_data: User-provided data
        template_path: Path to the template file
    
    Returns:
        Merged data dictionary
    """
    if not template_path.exists():
        return user_data
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template = json.load(f)
    
    template_flat = flatten_applicant_data(template)
    
    # User data takes precedence
    merged = {**template_flat, **user_data}
    
    return merged


class ApplicantDataLoader:
    """
    High-level class for loading and managing applicant data.
    Supports English field names and default values.
    """
    
    def __init__(
        self,
        data_path: Path,
        schema_path: Optional[Path] = None,
        defaults_path: Optional[Path] = None,
        use_english: bool = True
    ):
        self.data_path = data_path
        self.schema_path = schema_path
        self.defaults_path = defaults_path
        self.use_english = use_english
        self.raw_data: dict = {}
        self.flat_data: dict = {}
        self._loaded = False
        self._translator = None
        
        # Initialize translator if using English
        if use_english:
            from .field_translator import FieldTranslator
            self._translator = FieldTranslator(defaults_path)
    
    def load(self) -> "ApplicantDataLoader":
        """Load the applicant data, translating English names if needed."""
        self.raw_data = load_applicant_data(self.data_path)
        
        # Flatten first
        flat_raw = flatten_applicant_data(self.raw_data)
        
        # Auto-generate client_name from client_first_name + client_surname if not provided
        if "client_name" not in flat_raw or not flat_raw["client_name"]:
            first = flat_raw.get("client_first_name", "") or flat_raw.get("inviter_first_name", "")
            surname = flat_raw.get("client_surname", "") or flat_raw.get("inviter_surname", "")
            if first and surname:
                flat_raw["client_name"] = f"{first} {surname}"
        # Applicant address (Contact Data) = client address when not provided (same as API)
        for addr_key, client_key in [
            ("street", "client_street"), ("house_number", "client_house_number"),
            ("postal_code", "client_postal_code"), ("city", "client_city"), ("country", "client_country"),
            ("email", "client_email"), ("phone", "client_phone"),
        ]:
            if (not flat_raw.get(addr_key) or not str(flat_raw.get(addr_key, "")).strip()) and flat_raw.get(client_key):
                val = flat_raw[client_key]
                if addr_key == "phone" and val and str(val).strip().startswith("+"):
                    val = str(val).strip()[1:].strip()
                flat_raw[addr_key] = val
        # Occupation address = client address (maid works at client's house)
        for emp_key, client_key in [
            ("employer_street", "client_street"), ("employer_house_number", "client_house_number"),
            ("employer_postal_code", "client_postal_code"), ("employer_city", "client_city"),
            ("employer_country", "client_country"),
        ]:
            if (not flat_raw.get(emp_key) or not str(flat_raw.get(emp_key, "")).strip()) and flat_raw.get(client_key):
                flat_raw[emp_key] = flat_raw[client_key]
        # Name at birth (geburtsname) = same as family name when not provided
        family_name = flat_raw.get("maid_surname") or flat_raw.get("surname") or flat_raw.get("family_name")
        if family_name and not flat_raw.get("birth_name") and not flat_raw.get("maiden_name"):
            flat_raw["birth_name"] = family_name

        # Do NOT auto-fill other_means_specify / "Other (please specify)" – only fill when user sends it
        # Translate if using English mode
        if self._translator:
            self.flat_data = self._translator.translate_data(flat_raw)
        else:
            self.flat_data = flat_raw
        
        # Auto-populate sponsor fields from employer fields (Section 22) if other_sponsor_pays is used
        # (do this after translation so defaults are applied)
        self._copy_inviter_to_sponsor_translated(self.flat_data)
        
        self._loaded = True
        return self
    
    def _build_employer_info(self, data: dict[str, Any]) -> str:
        """Build employer info string for 'other means specify' field."""
        parts = []
        
        # Employer/client name
        employer = data.get("client_name", "") or data.get("employer", "")
        if employer:
            parts.append(employer)
        
        # Address
        address_parts = []
        street = data.get("employer_street", "")
        house_num = data.get("employer_house_number", "")
        if street:
            addr = street
            if house_num:
                addr += f" {house_num}"
            address_parts.append(addr)
        
        postal = data.get("employer_postal_code", "")
        city = data.get("employer_city", "")
        if postal or city:
            address_parts.append(f"{postal} {city}".strip())
        
        country = data.get("employer_country", "")
        if country:
            address_parts.append(country)
        
        if address_parts:
            parts.append(", ".join(address_parts))
        
        # Phone
        phone = data.get("phone", "")
        if phone:
            parts.append(f"Tel: {phone}")
        
        return ", ".join(parts) if parts else ""
    
    def _copy_client_to_sponsor(self, data: dict[str, Any]) -> None:
        """Copy client fields to sponsor fields if other_sponsor_pays is used."""
        # Only copy if other_sponsor_pays is set
        if not data.get("other_sponsor_pays", False):
            return
        
        # Copy client data to sponsor (Person type)
        # Check client_* first, fall back to inviter_* for backwards compatibility
        client_to_sponsor = {
            ("client_surname", "inviter_surname"): "sponsor_surname",
            ("client_first_name", "inviter_first_name"): "sponsor_first_name",
            ("client_gender", "inviter_gender"): "sponsor_gender",
            ("client_date_of_birth", "inviter_date_of_birth"): "sponsor_date_of_birth",
            ("client_birth_place", "inviter_birth_place"): "sponsor_birth_place",
            ("client_nationality", "inviter_nationality"): "sponsor_nationality",
            ("hotel_street", "client_street", "inviter_street"): "sponsor_street",
            ("hotel_house_number", "client_house_number", "inviter_house_number"): "sponsor_house_number",
            ("hotel_postal_code", "client_postal_code", "inviter_postal_code"): "sponsor_postal_code",
            ("hotel_city", "client_city", "inviter_city"): "sponsor_city",
            ("hotel_country", "client_country", "inviter_country"): "sponsor_country",
            ("hotel_phone", "client_phone", "inviter_phone"): "sponsor_phone",
            ("hotel_email", "client_email", "inviter_email"): "sponsor_email",
        }
        
        for source_fields, sponsor_field in client_to_sponsor.items():
            # Only copy if sponsor field is not already provided
            if sponsor_field not in data or not data[sponsor_field]:
                # Try each source field in order until one has a value
                value = ""
                for field in source_fields:
                    value = data.get(field, "")
                    if value:
                        break
                if value:
                    data[sponsor_field] = value
        
        # Set default sponsor type to "Person"
        if "sponsor_type" not in data or not data["sponsor_type"]:
            data["sponsor_type"] = "Person"
    
    def _copy_inviter_to_sponsor_translated(self, data: dict[str, Any]) -> None:
        """Copy inviter fields to sponsor fields (using translated German field names)."""
        # Only copy if other_sponsor_pays (organisation) is set
        if not data.get("reisedaten.reisekostenUebernahme.organisation", False):
            return
        
        # Copy inviter data to sponsor (Person type)
        inviter_to_sponsor = {
            "referenz.ansprechpartner.familienname": "verpflichtungserklaerungsgeber.ansprechpartner.familienname",
            "referenz.ansprechpartner.vorname": "verpflichtungserklaerungsgeber.ansprechpartner.vorname",
            "referenz.ansprechpartner.geschlecht": "verpflichtungserklaerungsgeber.ansprechpartner.geschlecht",
            "referenz.ansprechpartner.geburtsdatum": "verpflichtungserklaerungsgeber.ansprechpartner.geburtsdatum",
            "referenz.ansprechpartner.geburtsort": "verpflichtungserklaerungsgeber.ansprechpartner.geburtsort",
            "referenz.ansprechpartner.staatsangehoerigkeit": "verpflichtungserklaerungsgeber.ansprechpartner.staatsangehoerigkeit",
            "referenz.ansprechpartner.anschrift.strasse": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.strasse",
            "referenz.ansprechpartner.anschrift.hausnummer": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.hausnummer",
            "referenz.ansprechpartner.anschrift.plz": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.plz",
            "referenz.ansprechpartner.anschrift.ort": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.ort",
            "referenz.ansprechpartner.anschrift.land": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.land",
            "referenz.ansprechpartner.kontaktdaten.telefon": "verpflichtungserklaerungsgeber.ansprechpartner.kontaktdaten.telefon",
            "referenz.ansprechpartner.kontaktdaten.email": "verpflichtungserklaerungsgeber.ansprechpartner.kontaktdaten.email",
        }
        
        for inviter_field, sponsor_field in inviter_to_sponsor.items():
            if sponsor_field not in data or not data[sponsor_field]:
                inviter_value = data.get(inviter_field, "")
                if inviter_value:
                    data[sponsor_field] = inviter_value
        
        # Set sponsor type to "Person"
        if "verpflichtungserklaerungsgeber.art" not in data or not data["verpflichtungserklaerungsgeber.art"]:
            data["verpflichtungserklaerungsgeber.art"] = "Person"
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate the loaded data."""
        if not self._loaded:
            self.load()
        return validate_required_fields(self.flat_data, self.schema_path)
    
    def get_value(self, field_id: str, default: Any = None) -> Any:
        """Get a field value."""
        if not self._loaded:
            self.load()
        return self.flat_data.get(field_id, default)
    
    def get_all_values(self) -> dict[str, Any]:
        """Get all field values as a flat dictionary."""
        if not self._loaded:
            self.load()
        return self.flat_data.copy()
    
    def display_summary(self) -> None:
        """Display a summary of the data."""
        if not self._loaded:
            self.load()
        display_data_summary(self.flat_data, self.schema_path)


if __name__ == "__main__":
    # Test
    base_path = Path(__file__).parent.parent.parent
    data_path = base_path / "output" / "applicant_template.json"
    schema_path = base_path / "output" / "fields_schema.json"
    
    if data_path.exists():
        loader = ApplicantDataLoader(data_path, schema_path)
        loader.load()
        loader.display_summary()
        
        is_valid, missing = loader.validate()
        if not is_valid:
            console.print(f"[red]Missing required fields: {missing}[/red]")
    else:
        console.print("[yellow]No applicant data file found.[/yellow]")

