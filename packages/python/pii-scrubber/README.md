# pii-scrubber

Opportunistic, regex-based helpers for redacting **PII-shaped** substrings from plain text and JSON-like dicts.

## WARNING

This library uses heuristics (compiled regular expressions and light checks such as Luhn for card-shaped spans). It is **not** a complete or authoritative PII detector. Expect **false positives** and **false negatives**. Treat it as **defense in depth** (logging pipelines, support tooling, LLM prompts) — **not** as your primary privacy or compliance control.

## Install

```bash
pip install ./packages/python/pii-scrubber
```

## Usage

```python
from pii_scrubber import ScrubMode, scrub, scrub_dict

text = "Reach me at user@example.com or 212-555-0199; SSN 078-05-1120"
result = scrub(text)
print(result.text)
print(result.replacements_by_mode)
print(result.total_replacements)

only_ssn = scrub(text, modes=[ScrubMode.SSN])

payload = {"email": "user@example.com", "count": 3, "nested": {"phone": "(415) 555-2671"}}
print(scrub_dict(payload))
```

Running `scrub` twice on its own output should make **no further replacements** (tokens like `[REDACTED:EMAIL]` are not matched by the built-in patterns).

## Modes

| Mode           | What it targets (high level)                         |
|----------------|------------------------------------------------------|
| `SSN`          | `###-##-####` hyphenated SSN-shaped tokens           |
| `EIN`          | `##-#######` EIN-shaped tokens (excludes `12-3456789`) |
| `EMAIL`        | Common email shapes                                  |
| `PHONE_US`     | US phone numbers with common separators              |
| `CREDIT_CARD`  | Card-shaped groups / digit runs passing Luhn         |
| `IP_ADDRESS`   | IPv4 dotted quads with valid octets                  |
| `BANK_ACCOUNT` | Long digit runs typical of account numbers           |
| `JWT`          | Three-part JWT-shaped blobs                          |
| `API_KEY`      | OpenAI-style `sk` dash-prefixed keys, GitHub classic PATs (`gh` + `p_` prefix), AWS access key ids (`AK` + `IA` + 16 A–Z/0–9), Stripe publishable keys (`pk` + `_` + …), `api` + `_key=` forms, and colon-labeled secret assignments (Slack `xox` star-suffixed tokens omitted in-repo to satisfy push scanners) |

## Development

```bash
cd packages/python/pii-scrubber
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]" ruff mypy
ruff check src tests
mypy src
pytest
```
