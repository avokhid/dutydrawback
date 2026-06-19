"""
Live API integration for 7501 extraction.

THIS FILE IS NOT TESTED IN THE BUILD ENVIRONMENT. It has no API key and no real
PDF to run against, so unlike schema.py / validation.py / calculation.py (which
have passing tests), this is runnable-but-unverified code. Treat it as a correct
starting point you must test against a real document and the current API.

It ties the existing pieces together into the thin end-to-end path:
    PDF -> [API extraction] -> Entry7501 -> [validation] -> findings
            (this file)         schema       validation

Two things you MUST confirm against the live docs at docs.claude.com before
relying on this, because they shift over time and I won't guess at them:

  1. The current model id (e.g. the latest Claude model string).
  2. The exact structured-output / strict tool-use syntax for binding a response
     to a Pydantic/JSON schema. The pattern below uses tool-use with the schema
     as the tool's input_schema, which is the stable approach, but parameter
     names and the structured-output convenience API may have changed.

Install: pip install anthropic pydantic
Set:     export ANTHROPIC_API_KEY=...
"""

from __future__ import annotations

import json
import os
from typing import Any

from schema import Entry7501
from extraction import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from validation import validate_entry


# Confirm/replace from docs.claude.com — do not assume this is current.
MODEL_ID = "claude-opus-4-8"


# A 7501 doesn't always arrive as a clean PDF — people photograph or scan the
# form, so the front door has to accept images too. Claude reads these natively,
# but the upload media type and the content-block kind differ: PDFs go in a
# `document` block, images in an `image` block. Map by extension so the same
# extraction path handles either.
_IMAGE_MEDIA = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp",
}


def _media_type_for(filename: str) -> str:
    return _IMAGE_MEDIA.get(os.path.splitext(filename)[1].lower(), "application/pdf")


def _content_block_for(filename: str, file_id: str) -> dict[str, Any]:
    """Image files need an `image` block; everything else is treated as a PDF
    `document` block. Both reference the uploaded file by id."""
    kind = "image" if os.path.splitext(filename)[1].lower() in _IMAGE_MEDIA else "document"
    return {"type": kind, "source": {"type": "file", "file_id": file_id}}


def _schema_as_tool() -> dict[str, Any]:
    """
    Expose the Entry7501 schema as a tool so the model is forced to return data
    in exactly that shape (strict tool use). Pydantic emits a JSON schema we can
    hand straight to the API as the tool's input_schema.
    """
    return {
        "name": "record_7501",
        "description": "Record the extracted CBP 7501 entry summary fields.",
        "input_schema": Entry7501.model_json_schema(),
    }


def extract_7501_from_bytes(
    pdf_bytes: bytes, filename: str = "upload.pdf"
) -> Entry7501:
    """Upload document bytes via the Files API and extract into Entry7501.

    Accepts a PDF or an image (photo/scan) of a 7501 — the media type and the
    content-block kind are chosen from the filename extension.
    """
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("pip install anthropic") from e

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("set ANTHROPIC_API_KEY")

    client = anthropic.Anthropic()

    uploaded = client.beta.files.upload(
        file=(filename, pdf_bytes, _media_type_for(filename))
    )

    tool = _schema_as_tool()

    message = client.beta.messages.create(
        model=MODEL_ID,
        max_tokens=4096,
        betas=["files-api-2025-04-14"],  # confirm current beta tag
        system=SYSTEM_PROMPT,
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_7501"},
        messages=[
            {
                "role": "user",
                "content": [
                    _content_block_for(filename, uploaded.id),
                    {"type": "text", "text": USER_PROMPT_TEMPLATE},
                ],
            }
        ],
    )

    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "record_7501":
            return Entry7501.model_validate(block.input)

    raise RuntimeError(
        "model did not return a record_7501 tool_use block; "
        f"got types: {[getattr(b, 'type', '?') for b in message.content]}"
    )


def extract_7501_from_pdf(pdf_path: str) -> Entry7501:
    """
    Upload a 7501 PDF, extract it via the API into a validated Entry7501.

    Raises if the model's output does not satisfy the schema — that failure is
    desirable: a malformed extraction should stop here, loudly, not flow
    downstream into a duty calculation.
    """
    with open(pdf_path, "rb") as f:
        return extract_7501_from_bytes(f.read(), filename=os.path.basename(pdf_path))


def extract_and_validate(pdf_path: str, claim_date=None):
    """The thin end-to-end path: extract, then run the deterministic checks."""
    entry = extract_7501_from_pdf(pdf_path)
    result = validate_entry(entry, claim_date=claim_date)
    return entry, result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python3 api_extract.py path/to/7501.pdf")
        raise SystemExit(1)
    entry, result = extract_and_validate(sys.argv[1])
    print(json.dumps(entry.model_dump(mode="json"), indent=2, default=str))
    print("\n--- validation ---")
    if result.ok and not result.findings:
        print("clean: all fields auto-pass")
    else:
        for fnd in result.findings:
            print(f"  {fnd}")
