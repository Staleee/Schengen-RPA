"""
Field translator - Maps English-friendly field names to VIDEX internal field IDs.
Also handles default values for fields that are commonly the same.
"""

from pathlib import Path
from typing import Any
import json

# English to German field ID mapping
ENGLISH_TO_GERMAN = {
    # Personal Details (maid_* prefix is primary)
    "maid_surname": "antragsteller.familienname",
    "maid_first_name": "antragsteller.vorname",
    "maid_date_of_birth": "antragsteller.geburtsdatum",
    "maid_place_of_birth": "antragsteller.geburtsort",
    "maid_country_of_birth": "antragsteller.geburtsland",
    "maid_gender": "antragsteller.geschlecht",
    "maid_sex": "antragsteller.geschlecht",
    "maid_marital_status": "antragsteller.familienstand",
    "maid_nationality": "antragsteller.staatsangehoerigkeitListe[0]",
    # Legacy aliases (backwards compatibility)
    "surname": "antragsteller.familienname",
    "family_name": "antragsteller.familienname",
    "birth_name": "antragsteller.geburtsname",
    "maiden_name": "antragsteller.geburtsname",
    "first_name": "antragsteller.vorname",
    "given_names": "antragsteller.vorname",
    "date_of_birth": "antragsteller.geburtsdatum",
    "birth_date": "antragsteller.geburtsdatum",
    "place_of_birth": "antragsteller.geburtsort",
    "birth_place": "antragsteller.geburtsort",
    "country_of_birth": "antragsteller.geburtsland",
    "birth_country": "antragsteller.geburtsland",
    "gender": "antragsteller.geschlecht",
    "sex": "antragsteller.geschlecht",
    "marital_status": "antragsteller.familienstand",
    "nationality": "antragsteller.staatsangehoerigkeitListe[0]",
    "current_nationality": "antragsteller.staatsangehoerigkeitListe[0]",
    "nationality_at_birth": "antragsteller.staatsangehoerigkeitBeiGeburtListe[0]",
    "birth_nationality": "antragsteller.staatsangehoerigkeitBeiGeburtListe[0]",
    # "We can exercise the right of freedom of movement" -> skip occupation/financial
    "freedom_of_movement": "rechtAufFreizuegigkeit",
    "we_can_exercise_freedom_of_movement": "rechtAufFreizuegigkeit",
    
    # Occupation (always Blue-collar worker per maids.cc)
    "occupation": "antragsteller.personendaten.berufdaten.berufAuswahl",
    "current_occupation": "antragsteller.personendaten.berufdaten.berufAuswahl",
    "profession": "antragsteller.personendaten.berufdaten.berufAuswahl",
    "employer": "antragsteller.personendaten.berufdaten.firmenname",
    "company_name": "antragsteller.personendaten.berufdaten.firmenname",
    "client_name": "antragsteller.personendaten.berufdaten.firmenname",
    "employer_street": "antragsteller.personendaten.berufdaten.strasse",
    "employer_house_number": "antragsteller.personendaten.berufdaten.hausnummer",
    "employer_address_extra": "antragsteller.personendaten.berufdaten.sonstigeAdressangaben",
    "employer_postal_code": "antragsteller.personendaten.berufdaten.plz",
    "employer_city": "antragsteller.personendaten.berufdaten.ort",
    "employer_country": "antragsteller.personendaten.berufdaten.land",
    
    # Home Address (maid_* prefix is primary)
    "maid_street": "antragsteller.personendaten.staendigeAnschrift.strasse",
    "maid_house_number": "antragsteller.personendaten.staendigeAnschrift.hausnummer",
    "maid_postal_code": "antragsteller.personendaten.staendigeAnschrift.plz",
    "maid_city": "antragsteller.personendaten.staendigeAnschrift.ort",
    "maid_country": "antragsteller.personendaten.staendigeAnschrift.land",
    # Legacy aliases
    "street": "antragsteller.personendaten.staendigeAnschrift.strasse",
    "home_street": "antragsteller.personendaten.staendigeAnschrift.strasse",
    "house_number": "antragsteller.personendaten.staendigeAnschrift.hausnummer",
    "home_house_number": "antragsteller.personendaten.staendigeAnschrift.hausnummer",
    "address_extra": "antragsteller.personendaten.staendigeAnschrift.sonstigeAdressangaben",
    "apartment": "antragsteller.personendaten.staendigeAnschrift.sonstigeAdressangaben",
    "postal_code": "antragsteller.personendaten.staendigeAnschrift.plz",
    "zip_code": "antragsteller.personendaten.staendigeAnschrift.plz",
    "city": "antragsteller.personendaten.staendigeAnschrift.ort",
    "home_city": "antragsteller.personendaten.staendigeAnschrift.ort",
    "country": "antragsteller.personendaten.staendigeAnschrift.land",
    "home_country": "antragsteller.personendaten.staendigeAnschrift.land",
    "phone": "antragsteller.personendaten.staendigeAnschrift.kontaktdaten.telefon",
    "telephone": "antragsteller.personendaten.staendigeAnschrift.kontaktdaten.telefon",
    "mobile": "antragsteller.personendaten.staendigeAnschrift.kontaktdaten.telefon",
    "maid_phone_number": "antragsteller.personendaten.staendigeAnschrift.kontaktdaten.telefon",
    "email": "antragsteller.personendaten.staendigeAnschrift.kontaktdaten.email",
    "maid_email": "antragsteller.personendaten.staendigeAnschrift.kontaktdaten.email",
    
    # Passport
    "passport_type": "antragsteller.pass.passArt",
    "passport_number": "antragsteller.pass.passnummer",
    "national_id": "antragsteller.nationaleIdentNr",
    "national_id_number": "antragsteller.nationaleIdentNr",
    "passport_issue_date": "antragsteller.pass.gueltigVon",
    "passport_valid_from": "antragsteller.pass.gueltigVon",
    "passport_expiry_date": "antragsteller.pass.gueltigBis",
    "passport_valid_until": "antragsteller.pass.gueltigBis",
    "passport_issuing_country": "antragsteller.pass.ausstellenderStaat",
    "passport_issued_by": "antragsteller.pass.ausgestelltVon",
    "passport_issuing_authority": "antragsteller.pass.ausgestelltVon",
    "passport_issue_place": "antragsteller.pass.ausgestelltIn",
    "passport_issued_in": "antragsteller.pass.ausgestelltIn",
    "date_of_issue": "antragsteller.pass.gueltigVon",
    "valid_until": "antragsteller.pass.gueltigBis",
    "issuing_state": "antragsteller.pass.ausstellenderStaat",
    
    # Travel Details
    "purpose_of_visit": "reisedaten.aufenthaltszweckListe[0]",
    "travel_purpose": "reisedaten.aufenthaltszweckListe[0]",
    "purpose_description": "reisedaten.angegebenerReisezweck",
    "additional_info": "reisedaten.weitereInformationen",
    "first_entry_country": "reisedaten.ersteinreiseStaat",
    "entry_country": "reisedaten.ersteinreiseStaat",
    "main_destination": "reisedaten.hauptzielListe[0]",
    "destination_country": "reisedaten.hauptzielListe[0]",
    # Single "destination" field that fills both first_entry_country and main_destination
    "destination": ["reisedaten.ersteinreiseStaat", "reisedaten.hauptzielListe[0]"],
    "number_of_entries": "visumdaten.anzahlEinreisen",
    "entries": "visumdaten.anzahlEinreisen",
    "arrival_date": "visumdaten.gueltigkeit.von",
    "departure_date": "visumdaten.gueltigkeit.bisGenau.value",
    "visa_start_date": "visumdaten.gueltigkeit.von",
    "travel_start_date": "visumdaten.gueltigkeit.von",
    "visa_end_date": "visumdaten.gueltigkeit.bisGenau.value",
    "travel_end_date": "visumdaten.gueltigkeit.bisGenau.value",
    
    # Reference/Inviting Person
    "reference_type": "referenz.referenzArt",
    "inviter_type": "referenz.referenzArt",
    # Client fields (renamed from inviter - the inviting person/sponsor)
    "client_surname": "referenz.ansprechpartner.familienname",
    "client_first_name": "referenz.ansprechpartner.vorname",
    "client_gender": "referenz.ansprechpartner.geschlecht",
    "client_date_of_birth": "referenz.ansprechpartner.geburtsdatum",
    "client_birth_place": "referenz.ansprechpartner.geburtsort",
    "householder_place_of_birth": "referenz.ansprechpartner.geburtsort",
    "reference_place_of_birth": "referenz.ansprechpartner.geburtsort",
    "client_nationality": "referenz.ansprechpartner.staatsangehoerigkeit",
    "client_street": "referenz.ansprechpartner.anschrift.strasse",
    "client_house_number": "referenz.ansprechpartner.anschrift.hausnummer",
    "client_postal_code": "referenz.ansprechpartner.anschrift.plz",
    "client_city": "referenz.ansprechpartner.anschrift.ort",
    "client_country": "referenz.ansprechpartner.anschrift.land",
    "client_phone": "referenz.ansprechpartner.kontaktdaten.telefon",
    "client_email": "referenz.ansprechpartner.kontaktdaten.email",
    # Hotel aliases for address fields
    "hotel_street": "referenz.ansprechpartner.anschrift.strasse",
    "hotel_house_number": "referenz.ansprechpartner.anschrift.hausnummer",
    "hotel_postal_code": "referenz.ansprechpartner.anschrift.plz",
    "hotel_city": "referenz.ansprechpartner.anschrift.ort",
    "hotel_country": "referenz.ansprechpartner.anschrift.land",
    "hotel_phone": "referenz.ansprechpartner.kontaktdaten.telefon",
    "hotel_email": "referenz.ansprechpartner.kontaktdaten.email",
    # Legacy inviter aliases (backwards compatibility)
    "inviter_surname": "referenz.ansprechpartner.familienname",
    "inviter_family_name": "referenz.ansprechpartner.familienname",
    "inviter_first_name": "referenz.ansprechpartner.vorname",
    "inviter_given_name": "referenz.ansprechpartner.vorname",
    "inviter_gender": "referenz.ansprechpartner.geschlecht",
    "inviter_date_of_birth": "referenz.ansprechpartner.geburtsdatum",
    "inviter_birth_date": "referenz.ansprechpartner.geburtsdatum",
    "inviter_birth_place": "referenz.ansprechpartner.geburtsort",
    "inviter_nationality": "referenz.ansprechpartner.staatsangehoerigkeit",
    "inviter_street": "referenz.ansprechpartner.anschrift.strasse",
    "inviter_house_number": "referenz.ansprechpartner.anschrift.hausnummer",
    "inviter_postal_code": "referenz.ansprechpartner.anschrift.plz",
    "inviter_city": "referenz.ansprechpartner.anschrift.ort",
    "inviter_country": "referenz.ansprechpartner.anschrift.land",
    "inviter_phone": "referenz.ansprechpartner.kontaktdaten.telefon",
    "inviter_email": "referenz.ansprechpartner.kontaktdaten.email",
    
    # Cost Coverage
    "applicant_pays": "reisedaten.reisekostenUebernahme.antragsteller",
    "self_funded": "reisedaten.reisekostenUebernahme.antragsteller",
    "third_party_pays": "reisedaten.reisekostenUebernahme.dritte",
    "sponsor_pays": "reisedaten.reisekostenUebernahme.dritte",
    "inviter_pays": "reisedaten.reisekostenUebernahme.einlader",
    "host_pays": "reisedaten.reisekostenUebernahme.einlader",
    "other_sponsor_pays": "reisedaten.reisekostenUebernahme.organisation",
    "organisation_pays": "reisedaten.reisekostenUebernahme.organisation",
    
    # Sponsor Section (for when other_sponsor_pays is used)
    "sponsor_type": "verpflichtungserklaerungsgeber.art",
    "sponsor_company_name": "verpflichtungserklaerungsgeber.firmenname",
    "sponsor_institution_name": "verpflichtungserklaerungsgeber.firmenname",
    "sponsor_surname": "verpflichtungserklaerungsgeber.ansprechpartner.familienname",
    "sponsor_first_name": "verpflichtungserklaerungsgeber.ansprechpartner.vorname",
    "sponsor_date_of_birth": "verpflichtungserklaerungsgeber.ansprechpartner.geburtsdatum",
    "sponsor_birth_place": "verpflichtungserklaerungsgeber.ansprechpartner.geburtsort",
    "sponsor_gender": "verpflichtungserklaerungsgeber.ansprechpartner.geschlecht",
    "sponsor_nationality": "verpflichtungserklaerungsgeber.ansprechpartner.staatsangehoerigkeit",
    "sponsor_street": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.strasse",
    "sponsor_house_number": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.hausnummer",
    "sponsor_postal_code": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.plz",
    "sponsor_city": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.ort",
    "sponsor_country": "verpflichtungserklaerungsgeber.ansprechpartner.anschrift.land",
    "sponsor_phone": "verpflichtungserklaerungsgeber.ansprechpartner.kontaktdaten.telefon",
    "sponsor_email": "verpflichtungserklaerungsgeber.ansprechpartner.kontaktdaten.email",
    
    # Means of Support
    "has_cash": "reisedaten.lebensunterhalt.bar",
    "cash": "reisedaten.lebensunterhalt.bar",
    "has_travellers_cheques": "reisedaten.lebensunterhalt.reiseschecks",
    "travellers_cheques": "reisedaten.lebensunterhalt.reiseschecks",
    "has_credit_cards": "reisedaten.lebensunterhalt.kreditkarten",
    "credit_cards": "reisedaten.lebensunterhalt.kreditkarten",
    "accommodation_prepaid": "reisedaten.lebensunterhalt.unterkunft",
    "prepaid_accommodation": "reisedaten.lebensunterhalt.unterkunft",
    "all_expenses_covered": "reisedaten.lebensunterhalt.vollstaendigeKostenuebernahme",
    "transport_prepaid": "reisedaten.lebensunterhalt.befoerderung",
    "prepaid_transport": "reisedaten.lebensunterhalt.befoerderung",
    "other_means": "reisedaten.lebensunterhalt.sonstiges",
    "other_means_specify": "reisedaten.lebensunterhalt.sonstigesAngabe",
    
    # Biometrics – "Have your fingerprints been taken before?" (in request body)
    "fingerprints_taken_before": "antragsteller.biometrie.fingerabdrueckeErfassungsDatum_vorhanden",
    "fingerprints_collected": "antragsteller.biometrie.fingerabdrueckeErfassungsDatum_vorhanden",
    "has_fingerprints": "antragsteller.biometrie.fingerabdrueckeErfassungsDatum_vorhanden",
    "fingerprint_date": "antragsteller.biometrie.fingerabdrueckeErfassungsDatum",
    "fingerprints_date": "antragsteller.biometrie.fingerabdrueckeErfassungsDatum",
    "biometric_date": "antragsteller.biometrie.fingerabdrueckeErfassungsDatum",
    
    # EU Free Movement
    "eu_family_member": "rechtAufFreizuegigkeit",
    "right_of_free_movement": "rechtAufFreizuegigkeit",
    
    # Residence in other country (checkbox) + Details on right to reside (exact IDs from VIDEX)
    "has_residence_permit": "antragsteller.aufenthaltsberechtigung",
    "residence_permit": "antragsteller.aufenthaltsberechtigung",
    "residence_in_other_country": "antragsteller.aufenthaltsberechtigung",
    "rvisa_type": "antragsteller.aufenthaltsberechtigung.artDerRueckkehrberechtigung",
    "residence_permit_type": "antragsteller.aufenthaltsberechtigung.artDerRueckkehrberechtigung",
    "authorisation_type": "antragsteller.aufenthaltsberechtigung.artDerRueckkehrberechtigung",
    "rvisa_number": "antragsteller.aufenthaltsberechtigung.rueckkehrDokumentNr",
    "residence_permit_number": "antragsteller.aufenthaltsberechtigung.rueckkehrDokumentNr",
    "rvisa_expiration_date": "antragsteller.aufenthaltsberechtigung.rueckkehrGueltigBis",
    "residence_permit_valid_until": "antragsteller.aufenthaltsberechtigung.rueckkehrGueltigBis",

    # Previous Visa
    "previous_visa_number": "reisedaten.letzteVisumStickernummer",
    "last_visa_sticker": "reisedaten.letzteVisumStickernummer",
    
    # Entry Permit (for transit)
    "entry_permit_number": "antragsteller.einreisegenehmigung.einreisegenehmigungsNr",
    "entry_permit_issued_by": "antragsteller.einreisegenehmigung.ausgestelltVon",
    "entry_permit_valid_from": "antragsteller.einreisegenehmigung.gueltigVon",
    "entry_permit_valid_until": "antragsteller.einreisegenehmigung.gueltigBis",
    "entry_permit_type": "antragsteller.einreisegenehmigung.artDerEinreisegenehmigungAuswahl",
    "final_destination_country": "antragsteller.einreisegenehmigung.endzielStaat",
    
    # Inviter alternative spellings
    "inviter_surname_alt": "referenz.ansprechpartner.abweichendeSchreibweiseNachname",
    "inviter_first_name_alt": "referenz.ansprechpartner.abweichendeSchreibweiseVorname",
    "inviter_other_names": "referenz.ansprechpartner.andereNamen",
    "inviter_previous_names": "referenz.ansprechpartner.fruehereNamen",
}

# Reverse mapping for reference
GERMAN_TO_ENGLISH = {v: k for k, v in ENGLISH_TO_GERMAN.items() if not isinstance(v, list)}


class FieldTranslator:
    """Translates English-friendly field names to VIDEX internal IDs and applies defaults."""
    
    def __init__(self, defaults_path: Path = None):
        self.defaults = {}
        if defaults_path and defaults_path.exists():
            self.load_defaults(defaults_path)
    
    def translate_field_name(self, name: str) -> str:
        """Translate an English field name to German internal ID."""
        # If already a German ID (contains dots), return as-is
        if '.' in name and name not in ENGLISH_TO_GERMAN:
            return name
        
        # Look up in mapping (case-insensitive)
        name_lower = name.lower().replace(' ', '_').replace('-', '_')
        return ENGLISH_TO_GERMAN.get(name_lower, name)
    
    def translate_data(self, english_data: dict[str, Any]) -> dict[str, Any]:
        """
        Translate a dictionary with English field names to German internal IDs.
        Also applies default values.
        """
        # Start with defaults
        result = dict(self.defaults)
        
        # Translate and merge user data (user data overrides defaults)
        for key, value in english_data.items():
            if key.startswith('_'):  # Skip metadata keys like _instructions
                continue
            german_key = ENGLISH_TO_GERMAN.get(key)
            
            # Handle multi-field mapping (one English field -> multiple German fields)
            if isinstance(german_key, list):
                for gk in german_key:
                    result[gk] = value
            else:
                result[self.translate_field_name(key)] = value
        
        return result
    
    def set_defaults(self, defaults: dict[str, Any]):
        """Set default values (in English or German field names)."""
        for key, value in defaults.items():
            german_key = self.translate_field_name(key)
            self.defaults[german_key] = value
    
    def save_defaults(self, path: Path):
        """Save defaults to a JSON file."""
        with open(path, 'w') as f:
            json.dump(self.defaults, f, indent=2)
    
    def load_defaults(self, path: Path):
        """Load defaults from a JSON file and translate to German field IDs."""
        if path.exists():
            with open(path) as f:
                raw_defaults = json.load(f)
            
            # Translate English field names to German IDs
            self.defaults = {}
            for key, value in raw_defaults.items():
                if key.startswith('_'):  # Skip metadata
                    continue
                german_key = self.translate_field_name(key)
                self.defaults[german_key] = value


def create_english_template() -> dict[str, Any]:
    """Create a template with English field names for easy filling."""
    return {
        "_instructions": "Fill in the values below. All field names are in English.",
        
        # Personal Details
        "surname": "",
        "first_name": "",
        "birth_name": "",  # Maiden name if applicable
        "date_of_birth": "",  # Format: DD.MM.YYYY
        "place_of_birth": "",
        "country_of_birth": "",
        "gender": "",  # Male / Female
        "marital_status": "",  # Single / Married / Divorced / Widowed
        "nationality": "",
        "nationality_at_birth": "",
        
        # Occupation
        "occupation": "",  # e.g., White-collar worker, Self-employed, Student
        "employer": "",
        "employer_street": "",
        "employer_house_number": "",
        "employer_postal_code": "",
        "employer_city": "",
        "employer_country": "",
        
        # Home Address
        "street": "",
        "house_number": "",
        "apartment": "",  # Optional
        "postal_code": "",
        "city": "",
        "country": "",
        "phone": "",
        "email": "",
        
        # Passport
        "passport_type": "Ordinary passport",
        "passport_number": "",
        "national_id": "",
        "passport_issue_date": "",  # DD.MM.YYYY
        "passport_expiry_date": "",  # DD.MM.YYYY
        "passport_issuing_country": "",
        "passport_issued_by": "",
        "passport_issue_place": "",
        
        # Travel Details
        "purpose_of_visit": "",  # Tourism / Business / Visit family or friends
        "purpose_description": "",
        "additional_info": "",
        "destination": "Germany",
        "number_of_entries": "Single entry",  # Single entry / Two entries / Multiple entries
        "visa_start_date": "",  # DD.MM.YYYY
        "visa_end_date": "",  # DD.MM.YYYY
        
        # Inviting Person (if applicable)
        "reference_type": "Inviting person",
        "inviter_surname": "",
        "inviter_first_name": "",
        "inviter_gender": "",
        "inviter_date_of_birth": "",
        "inviter_birth_place": "",
        "inviter_nationality": "",
        "inviter_street": "",
        "inviter_house_number": "",
        "inviter_postal_code": "",
        "inviter_city": "",
        "inviter_country": "",
        "inviter_phone": "",
        "inviter_email": "",
        
        # Cost Coverage
        "applicant_pays": True,
        "third_party_pays": False,
        "inviter_pays": False,
        
        # Means of Support
        "cash": True,
        "credit_cards": True,
        "accommodation_prepaid": True,
        "transport_prepaid": True,
    }


if __name__ == "__main__":
    # Generate English template
    template = create_english_template()
    output_path = Path(__file__).parent.parent.parent / "output" / "english_template.json"
    with open(output_path, 'w') as f:
        json.dump(template, f, indent=2)
    print(f"English template saved to: {output_path}")

