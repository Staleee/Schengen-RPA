"""Italy Schengen visa form — the ops-provided fillable harmonised template
(assets/italy_fillable.pdf, Vers. 06/2024), AcroForm.

Replaces the coordinate overlay this country used to be filled with. The overlay only ever
covered 33 of the form's fields, and the ones it missed printed blank with nothing to indicate
it — §11, §19's phone, §20 entirely, §29, §31's phone and the declaration place/date. Named
fields also make the mapping checkable: the tests read each value back, which a coordinate
overlay cannot support (a tick drawn faithfully at a wrong coordinate looks identical to a
correct one, which is how Bulgaria's §33 mark ended up beside its box rather than inside it).

Two things about this template are unusual and shape the maps below.

**Every tick box is a one-character text input, not a checkbox** — `Sex_Female`,
`Civil_status_Single` and the rest are 8-10pt Text widgets sitting over a printed ☐. They take a
typed mark, so they go in ``mark_map`` rather than ``checkbox_map``.

**Most option groups carry only one option.** As shipped by ops the template had a field for
Female but none for Male, one for Single but none for the other five civil statuses, one for
Multiple entries but none for Single or Two, and one for Fingerprints-No but none for Yes. A box
is only marked when the answer is the one it states; any other answer leaves it blank and is
reported by ``multi_country_fill.report_missing_options``, because marking it regardless would
assert something untrue on a visa application.

§9 is now complete: ``Civil_status_Married``, ``_Divorced``, ``_Widow``, ``_Separated`` and
``_Registered_partnership`` were added to the template as one-character Text widgets over their
printed ☐, positioned by the same glyph-to-widget offset ``Civil_status_Single`` uses. The
remaining gaps still need a field added per missing option: Sex_Male, Single_entry, Two_entries,
Fingerprints_yes.

The old blank overlay template (italy_conslagos.pdf) and italy_overlay.json are no longer used
for Italy; the other overlay countries keep their own.
"""

from multi_country_fill import CountryConfig, register_country

# Logical body key -> text field name on the form.
TEXT_MAP = {
    "surname": "Surname",
    "surname_at_birth": "Surname_at_birth",
    "given_names": "First_names",
    "maid_date_of_birth": "Date_of_birth",
    "maid_place_of_birth": "Place_of_birth",
    "country_of_birth": "Country_of_birth",
    "nationality": "Current_nationality",
    "passport_number": "Travel_doc_number",
    "passport_issue_date": "Travel_doc_date_of_issue",
    "passport_expiry_date": "Travel_doc_valid_until",
    "passport_issuing_country": "Travel_doc_issued_by_country",
    "residence_number": "Residence_permit_number",
    "residence_valid_until": "Residence_permit_valid_until",
    "occupation": "Current_occupation",
    "employer_sponsor_address": "Employer_name_address_telephone",
    # §19 the applicant's own home address, email and telephone. applicant_address_email is
    # composed from maid_address + maid_email by multi_country_fill.
    "applicant_address_email": "Home_address_and_email",
    "maid_phone": "Telephone_number",
    "purpose_additional_info": "Additional_information_purpose",
    "destination_member_states_line": "Main_destination_member_state",
    "first_entry_member_state": "First_entry_member_state",
    "arrival_date": "Intended_date_of_arrival",
    "departure_date": "Intended_date_of_departure",
    "partner_name": "Inviting_person_name",
    "partner_address_email": "Inviting_person_address",
    "partner_phone": "Inviting_person_telephone",
    "place": "Declaration_place",
    "application_date": "Declaration_date",
    # §34 the person filling in the application — the client when they accompany the maid,
    # otherwise the companion.
    "person_filling_form_name": "Person_filling_form_name",
    "person_filling_form_address_email": "Person_filling_form_address_email",
    "person_filling_form_phone": "Person_filling_form_telephone",
}

# Tick boxes: one-character text inputs, marked only when the answer matches the printed option.
MARK_MAP = {
    "sex_female": "Sex_Female",
    "marital_status_single": "Civil_status_Single",
    "marital_status_married": "Civil_status_Married",
    "marital_status_divorced": "Civil_status_Divorced",
    "marital_status_widowed": "Civil_status_Widow",
    "marital_status_separated": "Civil_status_Separated",
    "marital_status_registered_union": "Civil_status_Registered_partnership",
    "travel_doc_ordinary_passport": "Travel_doc_ordinary_passport",
    "resident_outside_nationality_yes": "Residence_in_other_country_yes",
    "purpose_tourism": "Purpose_tourism",
    "entries_multiple": "Multiple_entries",
    "schengen_before_no": "Fingerprints_no",
    "costs_paid_by_sponsor_host": "Cost_paid_by_sponsor",
    "costs_sponsor_referred_in_field_30_or_31": "Sponsor_referred_field",
    "all_expenses_covered_during_stay": "Sponsor_means_all_expenses",
}

# §19 and §34 used to be force-emptied here, on the rule that ops leave them blank on the
# submitted form. Ops now want both stated, so they are mapped above instead.
#
# One half of §34 still cannot be filled: it asks for the person's HOME address, and pro-backend
# carries one only for the client. When a companion rather than the client accompanies the maid,
# multi_country_fill leaves the address out and prints the email alone — see the note there.
FORCE_EMPTY: tuple[str, ...] = ()

register_country(
    "italy",
    CountryConfig(
        template="italy_fillable.pdf",
        text_map=TEXT_MAP,
        checkbox_map={},
        mark_map=MARK_MAP,
        force_empty=FORCE_EMPTY,
        engine="acroform",
    ),
)
