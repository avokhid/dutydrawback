"""
Extraction prompt for the CBP 7501 entry summary.

This is the "prompting reliably per document type" piece. The prompt is kept
in code (not buried in an API call) so it can be version-controlled, diffed,
and tuned against a labeled test set — the prompt is as much a tuned artifact
as any model weight.

Design choices that matter for reliability:

  - Strict structured output. Pair this prompt with the API's strict tool-use /
    structured-output mode bound to the Entry7501 schema, so the model can only
    return schema-shaped JSON. This eliminates the whole class of "quantity came
    back as the string '2'" errors before they reach validation.

  - Demand provenance. Every value must carry page + bounding box. This is what
    powers the grounding check (does the cited region actually contain the
    value?) and lets the reviewer UI show the proof inline instead of making a
    human open the PDF.

  - Forbid guessing. The model is told to mark a field null rather than invent
    a plausible value. A null is cheap to catch and route to review; a confident
    hallucination is the expensive failure mode. We would rather miss a value
    than fabricate one.

  - No arithmetic. The model transcribes; it does not compute. We do not ask it
    to "calculate the total" — the deterministic layer does that, and the
    model's total is only useful as an independent reading to reconcile against.

  - Structured files bypass this entirely. If the 7501 data arrives as a clean
    CSV/Excel export from a broker system, parse it deterministically. This
    prompt is for the PDF / scanned path only.
"""

SYSTEM_PROMPT = """\
You are a precise data-extraction component in a customs duty-drawback system.
You read CBP Form 7501 entry summaries and transcribe their contents into a
strict schema. You are a transcriber, not an analyst.

Rules you must follow exactly:

1. Transcribe only what is printed. Never compute, infer, or "clean up" values.
   If the form prints a value, copy it verbatim. If a field is absent or
   illegible, return null for that field. Do NOT guess a plausible value.

2. Do not perform arithmetic. Do not sum lines, do not derive totals, do not
   reconcile anything. Report header totals exactly as printed, separately from
   the line items. A downstream system checks the math.

3. For every value you return, record where you read it: the 1-based page
   number and, when available, the bounding-box region. If you cannot point to
   where a value came from on the page, return null for it rather than reporting
   an ungrounded value.

4. Transcribe numbers without reformatting. Keep the digits exactly as shown.
   Do not add or remove decimal places, thousands separators, or currency
   symbols beyond what the schema requires (plain decimal numbers).

5. HTS classification codes: report the digits as printed. Do not pad, truncate,
   or correct them. If the code looks malformed, transcribe what you see and let
   validation flag it.

6. One line item per printed line on the entry. Preserve the line numbering from
   the form. Do not merge or split lines.

When you are uncertain about a character (e.g. an 8 vs a 0 on a faxed scan),
prefer null over a coin-flip guess, and note the uncertainty in the field's
confidence if the schema allows it.
"""

USER_PROMPT_TEMPLATE = """\
Extract the CBP 7501 entry summary in the attached document into the required
schema. Follow every rule in your instructions. Remember: transcribe, do not
compute; record provenance for every value; return null rather than guessing.

Return only the structured data.
"""


def extract_live(pdf_bytes: bytes, filename: str = "upload.pdf") -> "Entry7501":
    """
    Live extraction via Anthropic Claude API.

    Delegates to api_extract.extract_7501_from_bytes. Requires ANTHROPIC_API_KEY.
    """
    from api_extract import extract_7501_from_bytes

    return extract_7501_from_bytes(pdf_bytes, filename=filename)


def build_messages(pdf_file_id: str) -> list[dict]:
    """
    Assemble the Messages API payload for extraction.

    `pdf_file_id` is a Files API id for the uploaded 7501 PDF (preferred over
    re-sending base64 each call). Bind the response to the Entry7501 schema via
    the API's structured-output / strict tool-use feature when you make the
    actual call — that binding, not this function, is what guarantees the shape.

    Model id and the exact structured-output parameter are intentionally not
    hardcoded here: take the current model string and the current
    structured-output syntax from the live docs at docs.claude.com when wiring
    this to the real API, since those shift over time.
    """
    return [
        {
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "file", "file_id": pdf_file_id}},
                {"type": "text", "text": USER_PROMPT_TEMPLATE},
            ],
        }
    ]
