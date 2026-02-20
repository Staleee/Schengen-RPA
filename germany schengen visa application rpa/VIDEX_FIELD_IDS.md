# VIDEX form – field IDs (single source of truth)

Exact IDs from the live form. Use these in field_translator and form_filler.

---

## Personal details – Applicant's personal data

| Label | Field ID |
|-------|----------|
| Family name | antragsteller.familienname |
| First name(s) | antragsteller.vorname |
| Date of birth (dd.mm.yyyy) | antragsteller.geburtsdatum |
| Place of birth | antragsteller.geburtsort |
| Country of birth | antragsteller.geburtsland |
| Sex | antragsteller.geschlecht |
| Marital status | antragsteller.familienstand |
| Current nationality | antragsteller.staatsangehoerigkeitListe[0] |

---

## Occupation

| Label | Field ID |
|-------|----------|
| Current occupation | antragsteller.personendaten.berufdaten.berufAuswahl |
| Company name and telephone number | antragsteller.personendaten.berufdaten.firmenname |
| Street | antragsteller.personendaten.berufdaten.strasse |
| House number | antragsteller.personendaten.berufdaten.hausnummer |
| Postal code | antragsteller.personendaten.berufdaten.plz |
| Town/city | antragsteller.personendaten.berufdaten.ort |
| Country | antragsteller.personendaten.berufdaten.land |

---

## Contact data – Applicant's address

| Label | Field ID |
|-------|----------|
| Street | antragsteller.personendaten.berufdaten.strasse |
| House number | antragsteller.personendaten.staendigeAnschrift.hausnummer |
| Postal code | antragsteller.personendaten.berufdaten.plz |
| Town/city | antragsteller.personendaten.berufdaten.ort |
| Country | antragsteller.personendaten.berufdaten.land |
| Is your residence in a country other than that of your current nationality? (checkbox) | antragsteller.aufenthaltsberechtigung |

### Details on the applicant's right to reside in place of residence

| Label | Field ID |
|-------|----------|
| Type of authorisation to return/residence permit | antragsteller.aufenthaltsberechtigung.artDerRueckkehrberechtigung |
| Number of authorisation to return/residence permit | antragsteller.aufenthaltsberechtigung.rueckkehrDokumentNr |
| Valid until | antragsteller.aufenthaltsberechtigung.rueckkehrGueltigBis |

---

## Documents – Identification papers and travel documents

| Label | Field ID |
|-------|----------|
| Type of travel document | antragsteller.pass.passArt |
| Travel document number | antragsteller.pass.passnummer |
| Date of issue | antragsteller.pass.gueltigVon |
| Valid until | antragsteller.pass.gueltigBis |
| Issuing state | antragsteller.pass.ausstellenderStaat |
| Issued by | antragsteller.pass.ausgestelltVon |

---

## Biometric data

| Label | Field ID |
|-------|----------|
| Have your fingerprints been collected previously for the purpose of applying for a Schengen visa? | antragsteller.biometrie.fingerabdrueckeErfassungsDatum_vorhanden |
| Date (dd.mm.yyyy), if known | antragsteller.biometrie.fingerabdrueckeErfassungsDatum |

---

## Travel data

| Label | Field ID |
|-------|----------|
| Purpose of the journey | reisedaten.aufenthaltszweckListe[0] |
| Member State of first entry | reisedaten.ersteinreiseStaat |
| Main travel destination | reisedaten.hauptzielListe[0] |
| Number of entries requested | visumdaten.anzahlEinreisen |
| Intended date of arrival for the first intended stay in the Schengen area | visumdaten.gueltigkeit.von |
| Intended date of departure from the Schengen area after the first intended stay | visumdaten.gueltigkeit.bisGenau.value |

---

## Reference – Inviting person

| Label | Field ID |
|-------|----------|
| Type of reference | referenz.referenzArt |
| Family name | referenz.ansprechpartner.familienname |
| First name(s) | referenz.ansprechpartner.vorname |
| Sex | referenz.ansprechpartner.geschlecht |
| Date of birth | referenz.ansprechpartner.geburtsdatum |
| Place of birth | referenz.ansprechpartner.geburtsort |
| Nationality | referenz.ansprechpartner.staatsangehoerigkeit |
| Street | referenz.ansprechpartner.anschrift.strasse |
| House number | referenz.ansprechpartner.anschrift.hausnummer |
| Postal code | referenz.ansprechpartner.anschrift.plz |
| Town/city | referenz.ansprechpartner.anschrift.ort |
| Country | referenz.ansprechpartner.anschrift.land |
| Telephone/mobile number | referenz.ansprechpartner.kontaktdaten.telefon |
| Email | referenz.ansprechpartner.kontaktdaten.email |

---

## Assumption of costs

| What we check | Field ID(s) |
|---------------|-------------|
| Travel and living costs – a third party | reisedaten.reisekostenUebernahme.dritte |
| Travel and living costs – the inviting person | reisedaten.reisekostenUebernahme.einlader |
| Means of support – all expenses covered | reisedaten.lebensunterhalt.vollstaendigeKostenuebernahme |
