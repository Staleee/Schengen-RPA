"""Shared fillable (AcroForm) harmonised Schengen form config.

The Italy / Bulgaria / Portugal / Greece templates the client provided are FLAT (no form
fields), so coordinate overlay produced messy, intersecting text. The EU harmonised form is
identical across Schengen countries, so we fill a genuine fillable harmonised template
(assets/harmonised_fillable.pdf) via AcroForm — clean output like Spain/Switzerland — and the
destination field carries the country.

Field names below are the exact AcroForm names in the fillable template (numeric suffixes
disambiguate the applicant block from the family-member block).
"""

from multi_country_fill import CountryConfig, register_country

TEMPLATE = "harmonised_fillable.pdf"

TEXT_MAP = {
    "surname": "Surname 1",
    "maid_surname_at_birth": "Surname at birth 1",
    "given_names": "First name(s) 1",
    "maid_date_of_birth": "Date of birth 1",
    "maid_place_of_birth": "Place of birth 1",
    "country_of_birth": "Country of birth 1",
    "nationality": "Current nationality 1",
    "maid_eid_number": "National identity number 1",
    "passport_number": "Number of trvel document 1",
    "passport_issue_date": "Date of issue 1",
    "passport_expiry_date": "Valid until 1",
    "passport_issuing_country": "Issued by (country) 1",
    "applicant_address_email": "Applicants home adress 1",
    "maid_phone": "Telephone no  1",
    "residence_number": "Rrsidence permit no 1",
    "residence_valid_until": "Rrsidence permit 3",
    "occupation": "Current occupation 1",
    "employer_sponsor_address": "Employer 1",
    "purpose_additional_info": "Additional information on purpose of stay 1",
    "destination_member_states_line": "Member State of main destination 1",
    "first_entry_member_state": "Member State of first entry 1",
    "arrival_date": "Intended date of arrival 1",
    "departure_date": "Intended date of departure 1",
    "partner_name": "Inviting persons 1",
    "partner_address_email": "Inviting persons address 1",
    "partner_phone": "Inviting persons telephone 1",
}

CHECKBOX_MAP = {
    "purpose_tourism": "Tourism",
}

# Radio groups: logical key -> (field name, on-state index). Indices mapped from widget positions.
RADIO_MAP = {
    "sex_male": ("Sex", "0"),
    "sex_female": ("Sex", "1"),
    "marital_status_single": ("Civil status", "0"),
    "marital_status_married": ("Civil status", "1"),
    "travel_doc_ordinary_passport": ("Type of travel document", "0"),
    "entries_one": ("Number of entries requested", "0"),
    "entries_two": ("Number of entries requested", "1"),
    "entries_multiple": ("Number of entries requested", "2"),
    "resident_outside_nationality_yes": ("Residence", "1"),
    "resident_outside_nationality_no": ("Residence", "0"),
    "schengen_before_yes": ("Fingerprints", "1"),
    "schengen_before_no": ("Fingerprints", "0"),
}


def register_harmonised(country: str) -> None:
    register_country(
        country,
        CountryConfig(
            template=TEMPLATE,
            text_map=TEXT_MAP,
            checkbox_map=CHECKBOX_MAP,
            engine="acroform",
            radio_map=RADIO_MAP,
        ),
    )
