# Tests

Runs the service in Docker and drives it over HTTP with static payloads, so what is tested is
the deployed artifact — same image, same `/fill-pdf` — rather than the fill functions in
isolation. Every case also writes the generated PDF plus a cropped PNG of the region under test
into `tests/output/`, so the result can be reviewed by eye and not only asserted.

```bash
docker compose -f tests/docker-compose.yml up --build --abort-on-container-exit --exit-code-from tests
```

Exit code is non-zero if any check fails. Against an already-running service:

```bash
RPA_BASE_URL=http://localhost:8090 python tests/verify_field33.py
```

## verify_field33.py

Field 33, "Cost of travelling and living during the applicant's stay is covered". For the
maids.cc flow all three of its boxes belong ticked — the client sponsors the trip and is the host
already named in §30/§31. Covers Spain/harmonised, Switzerland, Italy, Greece, Bulgaria and
Portugal, and checks that an explicit `false` from the caller still wins over the default.

The templates need three different checks, which is most of why this exists:

| Template | Field 33 is | Checked by |
|---|---|---|
| Spain / harmonised, Switzerland | AcroForm checkbox | reading the widget value back |
| Switzerland "referred to in field 30 or 31" | a one-character **text** input (`undefined`) | reading a non-empty typed mark |
| Italy, Greece, Bulgaria, Portugal | two crossing vector lines drawn onto a flat PDF | finding drawn segments inside the mapped box |

For the overlay templates there is a second check: the mapped tick box must land on the empty-box
glyph printed in the blank template. Without it a tick drawn faithfully into a *misplaced* box
still reads as "checked" — which is exactly how Bulgaria's "referred to in field 30 or 31" tick
came to sit beside its box instead of inside it, caught by looking at the PNG, not by the
assertion. Italy's boxes are vector squares with no glyph to compare against, so that check
reports as skipped there.
