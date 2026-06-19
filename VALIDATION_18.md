# Live-extraction validation — how to run it

This answers the system's #1 unknown: **does extraction hold up on real, messy
7501s?** It can only run in YOUR environment, because it needs a live API key and
real documents — exactly the assumption being tested. Nothing upstream of this
has touched a real document.

## Run

```bash
export ANTHROPIC_API_KEY=...
pip install anthropic pydantic --break-system-packages
python3 validate_extraction.py /path/to/folder_of_7501_pdfs
python3 validate_extraction.py one_7501.pdf --json results.json
```

## What you get — a per-document scorecard

- **PASS** — extracted cleanly and passed every deterministic check.
- **NEEDS-REVIEW** — extracted, but tripped a validation gate/warning or had a
  high null rate. The safety net worked; it also means extraction misread or was
  unsure about something. Inspect the findings.
- **FAIL** — the model couldn't return valid structured data at all.

Plus aggregates: extraction success rate, average **null rate** (how often the
model said "I'm not sure" — the early-warning signal for shaky extraction),
and average latency (your cost/latency picture).

## How to read it

- High PASS share on a representative document mix (including faxes, scans, odd
  vendor formats) = extraction is reliable enough to build on.
- Lots of NEEDS-REVIEW with line-math/total gates = the model is misreading
  numbers; tighten the prompt, or route hard docs through the verification
  signals (grounding/sampling) before trusting them.
- High null rate or FAILs = extraction needs hardening before launch.

## Before relying on api_extract.py

Confirm the current model id and the structured-output / Files-API syntax against
docs.claude.com — those shift, and `api_extract.py` flags exactly where. The
harness logic itself (scoring, null-counting, verdicts) is unit-tested; the live
extraction inside it is what you're validating.

## Building a realistic (messy) test set

A validation run on pristine PDFs gives a rosy scorecard that lies — extraction
only breaks on the long tail. If you're short on messy real documents, manufacture
them from clean samples:

```bash
pip install pypdfium2 pillow img2pdf --break-system-packages
python3 degrade_pdf.py clean_7501.pdf --out messy_variants
# produces messy_variants/clean_7501__{fax,scan,photo,lowres,rotate}.pdf
python3 validate_extraction.py messy_variants
```

Each variant simulates a real failure mode: `fax` (1-bit, low DPI), `scan`
(grayscale, blur + noise), `photo` (skew + uneven lighting), `lowres`
(downscaled), `rotate` (a few degrees off). The interesting signal is the
*difference* — clean passes, fax/photo fail — which tells you exactly which
conditions need prompt-hardening or document-type handling. Real messy documents
are still better than synthetic ones; this is for when you don't have enough.

Use only on documents you're authorized to use.
