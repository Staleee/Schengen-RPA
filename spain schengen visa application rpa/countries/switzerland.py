"""Switzerland Schengen visa form (assets/switzerland_schengen_form.pdf).

Real AcroForm PDF — field names below are the exact widget names extracted from the
template (see switzerland_fields.json). Filled via the shared AcroForm engine.
"""

from multi_country_fill import CountryConfig, register_country

TEXT_MAP = {
    "surname": "1 Surname Family name  Nom nom de famille",
    "given_names": "3 First names Given names  Prénoms Noms usuels",
    "maid_date_of_birth": "4 Date of birth daymonthyear  Date de naissance jourmois année",
    # Field 5 (place), 6 (country of birth) and 7 (current nationality) are three separate widgets;
    # 6 and 7 carry generic names (Text1 / Text2). Keep them split so nothing clips into one cell.
    "maid_place_of_birth": "5 Place of birth  Lieu de naissance 6 Country of birth  Pays de naissance",
    "country_of_birth": "Text1",
    "nationality": "Text2",
    "passport_number": "13 Number of travel docu ment  Numéro du document de voyage",
    "passport_issue_date": "14 Date of issue  Date de délivrance",
    "passport_expiry_date": "15 Valid until  Date dexpiration",
    "passport_issuing_country": "16 Issued by Country  Délivré par pays",
    "applicant_address_email": "19 Applicants home address and email address  Adresse du domicile et adresse électronique du demandeur",
    "maid_phone": "Telephone no  Numéro de téléphone",
    # §20 home-country residence permit — the No/Yes checkboxes are in CHECKBOX_MAP; the permit
    # number and validity are the two unlabelled text widgets on that line (Text8 = "No. / N°",
    # Text9 = "Valid until"). Field 11 (national ID) is deliberately NOT mapped and force-emptied.
    "residence_number": "Text8",
    "residence_valid_until": "Text9",
    "occupation": "21 Current occupation  Profession actuelle",
    "employer_sponsor_address": "22 Employer and employers address and telephone number For students name and address of educational establishment  Nom adresse et numéro de telephone de lemployeur Pour les étudiants address de létablissment denseignement",
    "purpose_additional_info": "24 Additional information on purpose of stay  Informations complémentaires sur lobjet du voyage",
    "destination_member_states_line": "25 Member State of main destination and other Member States of destination if applicable  État membre de destination principale et autres États membres de destination le cas échéant",
    # §26 Member State of first entry (widget carries the wrapped French label as its name).
    "first_entry_member_state": "État membre de destination principale et autres États",
    # Arrival and departure are two separate boxes: the long-named widget is the arrival box, and
    # Text11 (to its right) is the departure box — do NOT collapse them into one combined value.
    "arrival_date": "Intended dates of the journey  Date prévue pour le séjour Intended date of arrival of the first intended stay in the Schengen area  Date darrivée prévue pour le premier séjour envisagé dans lespace Schengen Intended date of departure from the Schengen area after the first intended stay  Date de départ prévue de lespace Schengen après le premier séjour envisagé",
    "departure_date": "Text11",
    "partner_name": "30 Surname and first name of the inviting persons in the Member States If not applicable name of hotels or temporary accommodations in the Member States  Nom et prénom de la ou des personnes qui invitent dans lÉtat membre ou les États membres A défaut nom dun ou des hôtels ou lieux dhébergement temporaires dans lÉtat membre ou les États membres",
    "partner_address_email": "Address and email address of inviting personshotelstemporary accommodations  Adresse et adresse électronique de la ou des personnes qui invitentde lhôtel ou des hôtelsdu ou des lieux dhébergement temporaire",
    "partner_phone": "Telephone no  Numéro de téléphone_2",
    # §33 person filling in the application (client when they accompany, else the companion).
    "person_filling_form_name": "33 Surname and first name of the person filling in the application form if different from the applicant  Nom et prénom de la personne qui remplit le formulaire de demande si elle nest pas le demandeur",
    "person_filling_form_address_email": "Address and email address of the person filling in the application form  Adresse et adresse électronique de la personne qui remplit le formulaire de demande",
    "person_filling_form_phone": "Telephone No  Numéro de téléphone",
    # §33 "referred to in field 30 or 31". This template builds that tick box as a
    # one-character text input named `undefined` (its "other (please specify)" twin is
    # `undefined_2`), not a checkbox — so it takes a typed mark, not an on/off state.
    "costs_sponsor_referred_mark": "undefined",
    "place_and_date": "Place and date  Lieu et date",
}

CHECKBOX_MAP = {
    "sex_male": "Male  Masculin",
    "sex_female": "Female  Féminin",
    "marital_status_single": "Single",
    "marital_status_married": "Married",
    "marital_status_divorced": "Divorced",
    "marital_status_widowed": "Widower",
    "marital_status_separated": "Separated",
    "marital_status_registered_union": "Registered Partnership",
    "travel_doc_ordinary_passport": "Ordinary passport  Passeport ordinaire",
    "purpose_tourism": "Tourism  Tourisme",
    "entries_one": "Single entry  une entrée",
    "entries_two": "Two entries  deux entrées",
    "entries_multiple": "Multiple entries  entrées multiples",
    "resident_outside_nationality_yes": "Yes Residence permit or equivalent  Oui Autorisation de séjour ou équivalent",
    "resident_outside_nationality_no": "No  Non",
    # §29 previous Schengen visa — the No/Yes pair on page 4 (the "_2" No disambiguates it from
    # the §20 residence "No" on page 3).
    "schengen_before_yes": "Yes  Oui",
    "schengen_before_no": "No  Non_2",
    "all_expenses_covered_during_stay": "All expenses covered during the stay",
    # §33 costs: the sponsor box was never mapped, so it stayed blank on every Swiss form.
    # (This template has no "referred to in field 30 or 31" box — that one is harmonised-only.)
    "costs_paid_by_sponsor_host": "by a sponsor host company organisation please specify",
}

# §11 national identity number must remain completely blank for domestic-worker applications;
# force-empty it so nothing (stale sample or stray payload) can populate it.
FORCE_EMPTY = ("11 National identity number where applicable  Numéro national didentité le cas échéant",)

register_country(
    "switzerland",
    CountryConfig(
        template="switzerland_schengen_form.pdf",
        text_map=TEXT_MAP,
        checkbox_map=CHECKBOX_MAP,
        force_empty=FORCE_EMPTY,
    ),
)
