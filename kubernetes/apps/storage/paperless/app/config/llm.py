#!/usr/bin/env python
import random
import time
import re
from dateutil import parser
from datetime import datetime
import tempfile
import os
import json
import logging
from PIL import Image
import base64
import requests
import sys
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional, Dict, List, Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PAPERLESS_HOST = os.getenv(
    "PAPERLESS_HOST", "http://paperless.storage.svc.cluster.local:80/api"
)
PAPERLESS_API_KEY = os.getenv("PAPERLESS_APIKEY")
OPENAI_API_ENDPOINT = os.getenv("OPENAI_API_ENDPOINT", "https://ai.thekao.cloud")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Model — single env var; VISION_MODEL / TEXT_MODEL kept for backward compat
MODEL = os.getenv(
    "MODEL", os.getenv("VISION_MODEL", os.getenv("TEXT_MODEL", "default"))
)

MAX_RETURN_TOKENS = int(os.getenv("MAX_RETURN_TOKENS", 8192))
# Hard safety cap: ~100k tokens worth of characters. Virtually never hit for normal docs.
MAX_CONTENT_CHARS = int(os.getenv("MAX_CONTENT_CHARS", 400_000))
# Minimum characters per page to consider Tesseract OCR acceptable.
MINIMUM_CHARS_PER_PAGE = int(os.getenv("MINIMUM_CHARS_PER_PAGE", 100))

DEFAULT_TAGS = list(map(int, os.getenv("DEFAULT_TAGS", "111,112").split(",")))
LLM_PROCESSED_TAG = int(os.getenv("LLM_PROCESSED_TAG", 112))  # tag 112 = "LLM"
NEEDS_REVIEW_TAG_NAME = os.getenv("NEEDS_REVIEW_TAG_NAME", "AI: Needs Review")

ENABLE_VISION = os.getenv("ENABLE_VISION", "false").lower() == "true"
PAPERLESS_OCR_LANGUAGE = os.getenv("PAPERLESS_OCR_LANGUAGE", "eng")

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 8))
INITIAL_RETRY_WAIT = int(os.getenv("INITIAL_RETRY_WAIT", 5))

# Characters per chunk when cleaning Tesseract text through the LLM.
# ~6000 chars ≈ ~1500 tokens in, leaves headroom under 8192 output token limit.
TEXT_CLEAN_CHUNK_CHARS = int(os.getenv("TEXT_CLEAN_CHUNK_CHARS", 6000))


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def validate_config() -> bool:
    """Validate required configuration with detailed error messages."""
    missing = []
    if not PAPERLESS_API_KEY:
        missing.append("PAPERLESS_APIKEY")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if missing:
        logger.error(
            "Missing required environment variables:\n"
            f"- {', '.join(missing)}\n\n"
            "1. Paperless API: PAPERLESS_APIKEY, PAPERLESS_HOST\n"
            "2. LLM API:       OPENAI_API_KEY, OPENAI_API_ENDPOINT"
        )
        if __name__ == "__main__":
            sys.exit(1)
        return False

    if not PAPERLESS_HOST.startswith(("http://", "https://")):
        logger.error(
            f"Invalid PAPERLESS_HOST format: {PAPERLESS_HOST} — must start with http:// or https://"
        )
        if __name__ == "__main__":
            sys.exit(1)
        return False

    return True


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def encode_image(image_path: str) -> str:
    """Encode image file to base64 string."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        raise


def resize_image(image_path: str, max_length: int = 2048) -> Optional[str]:
    """Resize image so its longest side is at most max_length pixels."""
    try:
        with Image.open(image_path) as img:
            ratio = max_length / max(img.size)
            new_size = tuple(int(x * ratio) for x in img.size)
            img.resize(new_size, Image.Resampling.LANCZOS).save(image_path)
        return image_path
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return None


# ---------------------------------------------------------------------------
# PDF analysis
# ---------------------------------------------------------------------------


def pdf_needs_vision_ocr(pdf_path: str) -> bool:
    """Return True if any page of the PDF contains images, tables, or sparse text.

    A PDF that passes this check can be classified using the text already
    extracted by Paperless/Tesseract.  Any document with embedded images,
    detectable table structures, or too little text per page benefits from
    the vision model OCR path.
    """
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                if page.get_images():
                    return True
                try:
                    if page.find_tables().tables:
                        return True
                except Exception:
                    pass  # find_tables not available on all PyMuPDF builds
                if len(page.get_text("text").strip()) < MINIMUM_CHARS_PER_PAGE:
                    return True
        return False
    except Exception as e:
        logger.error(f"Error analysing PDF for vision requirement: {e}")
        return True  # Err on the side of using vision


# ---------------------------------------------------------------------------
# Paperless API helpers
# ---------------------------------------------------------------------------


def fetch_metadata_list(url: str) -> List[Dict[str, Any]]:
    """Fetch a paginated list resource from the Paperless API."""
    headers = {"Authorization": f"Token {PAPERLESS_API_KEY}"}
    all_data: List[Dict[str, Any]] = []

    while url:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", data) if isinstance(data, dict) else data
            all_data.extend(results)
            url = data.get("next") if isinstance(data, dict) else None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch metadata from {url}: {e}")
            break
        except ValueError as e:
            logger.error(f"Failed to parse JSON from {url}: {e}")
            break

    return all_data


def fetch_tags() -> List[Dict[str, Any]]:
    return fetch_metadata_list(f"{PAPERLESS_HOST}/tags/")


def fetch_correspondents() -> List[Dict[str, Any]]:
    return fetch_metadata_list(f"{PAPERLESS_HOST}/correspondents/")


def fetch_document_types() -> List[Dict[str, Any]]:
    return fetch_metadata_list(f"{PAPERLESS_HOST}/document_types/")


def download_document(
    document_id: int,
) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Download document metadata from Paperless."""
    url = f"{PAPERLESS_HOST}/documents/{document_id}/"
    headers = {"Authorization": f"Token {PAPERLESS_API_KEY}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("content_type", ""), data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download document {document_id}: {e}")
        return None, None
    except ValueError as e:
        logger.error(f"Failed to parse document JSON: {e}")
        return None, None


def create_correspondent(name: str) -> Optional[int]:
    """Create a new correspondent in Paperless and return its ID."""
    url = f"{PAPERLESS_HOST}/correspondents/"
    headers = {
        "Authorization": f"Token {PAPERLESS_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, headers=headers, json={"name": name})
        response.raise_for_status()
        return response.json()["id"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create correspondent '{name}': {e}")
        return None


def create_tag(name: str) -> Optional[int]:
    """Create a new tag in Paperless and return its ID."""
    url = f"{PAPERLESS_HOST}/tags/"
    headers = {
        "Authorization": f"Token {PAPERLESS_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, headers=headers, json={"name": name})
        response.raise_for_status()
        return response.json()["id"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create tag '{name}': {e}")
        return None


def get_or_create_tag(name: str, existing_tags: List[Dict[str, Any]]) -> Optional[int]:
    """Return the ID of a tag by name, creating it if it doesn't exist."""
    for tag in existing_tags:
        if tag["name"].lower() == name.lower():
            return tag["id"]
    logger.info(f"Tag '{name}' not found — creating it")
    return create_tag(name)


def add_document_note(document_id: int, note: str) -> bool:
    """Append a note to a document via the Paperless notes API."""
    url = f"{PAPERLESS_HOST}/documents/{document_id}/notes/"
    headers = {
        "Authorization": f"Token {PAPERLESS_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, headers=headers, json={"note": note})
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to add note to document {document_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Title sanitisation
# ---------------------------------------------------------------------------


def sanitize_title(title: str) -> str:
    """Clean a title string for safe storage in Paperless."""
    if not title:
        return ""
    # Replace slashes and backslashes with spaces
    title = title.replace("/", " ").replace("\\", " ")
    # Remove surrounding and embedded straight/smart quotes
    title = (
        title.replace('"', "")
        .replace("'", "")
        .replace("\u201c", "")
        .replace("\u201d", "")
    )
    # Collapse multiple spaces
    title = re.sub(r"\s+", " ", title).strip()
    # Strip trailing punctuation
    title = title.rstrip(".,;:!?")
    # Enforce max length
    return title[:128]


# ---------------------------------------------------------------------------
# LLM helpers — shared retry/backoff
# ---------------------------------------------------------------------------


def _retry_wait(current_wait: float) -> float:
    """Sleep with jitter then return next wait duration."""
    jittered = current_wait + random.uniform(0, 1)
    time.sleep(jittered)
    return min(current_wait * 2, 60)


def _llm_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }


# ---------------------------------------------------------------------------
# OCR — vision model, one page at a time with rolling context
# ---------------------------------------------------------------------------


def ocr_document(
    image_path: str,
    previous_context: str = "",
    tesseract_hint: str = "",
    debug: bool = False,
) -> Optional[Dict[str, Any]]:
    """Perform OCR on a single page image using the vision model.

    Args:
        image_path:       Path to the page image.
        previous_context: Text extracted from all preceding pages (rolling context).
        tesseract_hint:   Raw Tesseract text for this page. Passed alongside the
                          image so the model can use it as a structural scaffold
                          even when the encoding is garbled.
        debug:            If True, make real LLM call but caller will skip Paperless writes.

    Returns:
        OpenAI-style chat completion dict, or None on failure.
    """
    retry_wait = float(INITIAL_RETRY_WAIT)

    for attempt in range(MAX_RETRIES + 1):
        try:
            resized = resize_image(image_path)
            if not resized:
                logger.error("Failed to resize image for OCR")
                return None

            base64_image = encode_image(resized)

            context_block = ""
            if previous_context:
                trimmed = previous_context[-MAX_CONTENT_CHARS:]
                context_block = (
                    "The following text was extracted from previous pages of this "
                    "document for context:\n\n"
                    f"{trimmed}\n\n"
                    "---\n\n"
                )

            hint_block = ""
            if tesseract_hint and tesseract_hint.strip():
                hint_block = (
                    "The following is a raw Tesseract OCR pass of this page. "
                    "It may contain encoding artefacts, garbled characters, or "
                    "misaligned columns, but use it as a structural hint for what "
                    "text is present and where:\n\n"
                    f"{tesseract_hint.strip()}\n\n"
                    "---\n\n"
                )

            user_text = (
                f"{context_block}"
                f"{hint_block}"
                "Extract all text from this page image exactly as it appears. "
                "Preserve table structure using spacing where meaningful. "
                "Fix any encoding artefacts you can identify from the image. "
                "Output only the extracted text, nothing else."
            )

            payload = {
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an OCR assistant. Extract text from document "
                            "images faithfully and completely."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    },
                ],
                "max_tokens": MAX_RETURN_TOKENS,
            }

            response = requests.post(
                f"{OPENAI_API_ENDPOINT}/v1/chat/completions",
                headers=_llm_headers(),
                json=payload,
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                if attempt < MAX_RETRIES:
                    retry_after = int(response.headers.get("Retry-After", retry_wait))
                    retry_wait = max(float(retry_after), retry_wait)
                    logger.warning(
                        f"OCR rate limited — retry {attempt + 1}/{MAX_RETRIES} in {retry_wait:.1f}s"
                    )
                    retry_wait = _retry_wait(retry_wait)
                    continue

            logger.error(
                f"OCR request failed ({response.status_code}): {response.text}"
            )
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"OCR request error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES:
                retry_wait = _retry_wait(retry_wait)
            continue
        except Exception as e:
            logger.error(f"Unexpected OCR error: {e}")
            return None

    logger.error(f"OCR failed after {MAX_RETRIES} retries")
    return None


# ---------------------------------------------------------------------------
# Classification — text model, new schema
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = (
    "You are a document classification assistant for a personal document management "
    "system. Analyse document text and metadata to assign accurate, consistent "
    "classifications. Return only valid JSON — no markdown, no code fences."
)

_CLASSIFY_SCHEMA = """{
  "creation_date":       "YYYY-MM-DD or empty string if unknown",
  "title":               "concise human-readable title, no quotes or special chars, max 100 chars",
  "correspondent":       "exact name from EXISTING CORRESPONDENTS list, or empty string",
  "correspondent_is_new": false,
  "tags":                ["exact names from EXISTING TAGS list"],
  "new_tags":            ["only if NO existing tag covers this concept — prefer existing tags"],
  "document_type":       "exact name from EXISTING DOCUMENT TYPES list, or empty string",
  "summary":             "2-4 sentences describing the document and any key figures or dates",
  "reasoning":           "one sentence explaining correspondent and document_type choices"
}"""

_CLASSIFY_INSTRUCTIONS = """INSTRUCTIONS:
- Use ONLY the exact names from the provided lists unless creating new entities.
- correspondent: pick the single best match or leave as empty string.
- correspondent_is_new: set to true ONLY when you are certain this is a real,
  identifiable entity (company, government agency, named individual) clearly named
  in the document AND not represented in the existing list. If in any doubt, leave
  correspondent as empty string and set correspondent_is_new to false.
- tags: pick zero or more existing tags that apply. Do not invent new ones here.
- new_tags: only add entries here when NO existing tag covers this concept. Strongly
  prefer existing tags. Leave as empty array when in doubt.
- document_type: pick the single best match or leave as empty string.
- creation_date: use the document's own date, not today's date.
- title: concise and descriptive, avoid redundant words like "Document" or "File".
- summary: plain English, 2-4 sentences, mention key amounts/dates if present.
- reasoning: brief internal note for logging — one sentence only."""


def classify_document(
    ocr_text: str,
    tags: List[Dict[str, Any]],
    correspondents: List[Dict[str, Any]],
    document_types: List[Dict[str, Any]],
    filename: str = "",
    language: str = "eng",
    debug: bool = False,
) -> Optional[Dict[str, Any]]:
    """Classify a document using the text model.

    Args:
        ocr_text:       Full extracted text of the document.
        tags:           All existing Paperless tags.
        correspondents: All existing Paperless correspondents.
        document_types: All existing Paperless document types.
        filename:       Original filename hint (optional).
        language:       Document language hint (optional).
        debug:          Return sample response without API call.

    Returns:
        OpenAI-style chat completion dict, or None on failure.
    """
    if not ocr_text or not ocr_text.strip():
        logger.error("classify_document: empty ocr_text — skipping")
        return None

    tags_str = ", ".join(f"'{t['name']}'" for t in tags)
    correspondents_str = ", ".join(f"'{c['name']}'" for c in correspondents)
    doc_types_str = ", ".join(f"'{d['name']}'" for d in document_types)

    # Build the user prompt
    hint_lines = []
    if filename:
        hint_lines.append(f"Original filename: {filename}")
    if language and language.lower() != "eng":
        hint_lines.append(f"Document language: {language}")
    hints = ("\n".join(hint_lines) + "\n\n") if hint_lines else ""

    # Apply hard safety cap on content
    truncated_text = ocr_text[:MAX_CONTENT_CHARS]
    if len(ocr_text) > MAX_CONTENT_CHARS:
        logger.warning(
            f"Document text truncated from {len(ocr_text)} to {MAX_CONTENT_CHARS} chars"
        )

    user_prompt = (
        f"{hints}"
        f"Classify this document. Return a JSON object matching EXACTLY this schema:\n"
        f"{_CLASSIFY_SCHEMA}\n\n"
        f"{_CLASSIFY_INSTRUCTIONS}\n\n"
        f"EXISTING TAGS:           {tags_str}\n"
        f"EXISTING CORRESPONDENTS: {correspondents_str}\n"
        f"EXISTING DOCUMENT TYPES: {doc_types_str}\n\n"
        f"DOCUMENT TEXT:\n{truncated_text}"
    )

    retry_wait = float(INITIAL_RETRY_WAIT)

    for attempt in range(MAX_RETRIES + 1):
        try:
            payload = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": _CLASSIFY_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": MAX_RETURN_TOKENS,
                "response_format": {"type": "json_object"},
            }

            response = requests.post(
                f"{OPENAI_API_ENDPOINT}/v1/chat/completions",
                headers=_llm_headers(),
                json=payload,
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", retry_wait))
                retry_wait = max(float(retry_after), retry_wait)
                logger.warning(
                    f"Classification rate limited — retry {attempt + 1}/{MAX_RETRIES} "
                    f"in {retry_wait:.1f}s"
                )
                retry_wait = _retry_wait(retry_wait)
                continue

            logger.error(
                f"Classification failed ({response.status_code}): {response.text}"
            )
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Classification request error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES:
                retry_wait = _retry_wait(retry_wait)
            continue

    logger.error(f"Classification failed after {MAX_RETRIES} retries")
    return None


# ---------------------------------------------------------------------------
# Extract classification data from LLM response
# ---------------------------------------------------------------------------

_EMPTY_CLASSIFICATION: Dict[str, Any] = {
    "creation_date": "",
    "title": "",
    "correspondent": "",
    "correspondent_is_new": False,
    "tags": [],
    "new_tags": [],
    "document_type": "",
    "summary": "",
    "reasoning": "",
}


def extract_classification_data(
    classification_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract and validate classification data from an LLM API response."""
    defaults = dict(_EMPTY_CLASSIFICATION)
    try:
        content = classification_result["choices"][0]["message"]["content"]
        data = json.loads(content)

        # Merge with defaults so all keys are always present
        for key, default in defaults.items():
            if key not in data:
                data[key] = default

        # Type coercions for safety
        data["correspondent_is_new"] = bool(data.get("correspondent_is_new", False))
        data["tags"] = list(data.get("tags", []))
        data["new_tags"] = list(data.get("new_tags", []))

        return data

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Failed to extract classification data: {e}")
        return defaults


# ---------------------------------------------------------------------------
# Update document in Paperless
# ---------------------------------------------------------------------------


def update_document_content(
    document_id: int,
    ocr_text: str,
    classification_result: Dict[str, Any],
    tags: List[Dict[str, Any]],
    correspondents: List[Dict[str, Any]],
    document_types: List[Dict[str, Any]],
    needs_review_tag_id: Optional[int] = None,
) -> bool:
    """Update a Paperless document with classification results.

    Creates new correspondents/tags when the LLM flags them, attaches a
    'needs review' tag when new entities are created, writes a summary note,
    and PATCHes the document metadata.
    """
    data = extract_classification_data(classification_result)
    needs_review = False

    # --- Resolve tag IDs --------------------------------------------------
    tag_ids: List[int] = []
    for tag_name in data["tags"]:
        tag_id = next((t["id"] for t in tags if t["name"] == tag_name), None)
        if tag_id:
            tag_ids.append(tag_id)

    # Create new tags if the LLM flagged any
    for new_tag_name in data.get("new_tags", []):
        new_id = create_tag(new_tag_name)
        if new_id:
            tag_ids.append(new_id)
            needs_review = True
            logger.info(f"Created new tag '{new_tag_name}' (id={new_id})")

    # Always apply DEFAULT_TAGS
    for dt in DEFAULT_TAGS:
        if dt not in tag_ids:
            tag_ids.append(dt)

    # --- Resolve correspondent ID -----------------------------------------
    correspondent_id: Optional[int] = None
    if data["correspondent"]:
        correspondent_id = next(
            (c["id"] for c in correspondents if c["name"] == data["correspondent"]),
            None,
        )

        if correspondent_id is None and data["correspondent_is_new"]:
            correspondent_id = create_correspondent(data["correspondent"])
            if correspondent_id:
                needs_review = True
                logger.info(
                    f"Created new correspondent '{data['correspondent']}' "
                    f"(id={correspondent_id})"
                )

    # --- Attach needs-review tag ------------------------------------------
    if needs_review and needs_review_tag_id and needs_review_tag_id not in tag_ids:
        tag_ids.append(needs_review_tag_id)

    # --- Resolve document type ID -----------------------------------------
    document_type_id: Optional[int] = None
    if data["document_type"]:
        document_type_id = next(
            (d["id"] for d in document_types if d["name"] == data["document_type"]),
            None,
        )

    # --- Parse creation date ----------------------------------------------
    iso_date = ""
    if data.get("creation_date"):
        try:
            parsed = parser.parse(data["creation_date"])
            iso_date = parsed.strftime("%Y-%m-%dT00:00:00Z")
        except (ValueError, OverflowError) as e:
            logger.error(f"Invalid creation_date '{data['creation_date']}': {e}")

    # --- Build PATCH payload ----------------------------------------------
    title = sanitize_title(data.get("title", ""))

    payload: Dict[str, Any] = {
        "tags": tag_ids,
        "content": ocr_text,
    }
    if title:
        payload["title"] = title
    if iso_date:
        payload["created"] = iso_date
    if correspondent_id is not None:
        payload["correspondent"] = correspondent_id
    if document_type_id is not None:
        payload["document_type"] = document_type_id

    # --- PATCH ------------------------------------------------------------
    url = f"{PAPERLESS_HOST}/documents/{document_id}/"
    headers = {
        "Authorization": f"Token {PAPERLESS_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to update document {document_id}: {e}")
        return False

    logger.info(
        f"Classification: title={title!r}, correspondent={data['correspondent']!r}, "
        f"tags={data['tags']}, doc_type={data['document_type']!r}"
    )
    logger.debug(f"Reasoning: {data.get('reasoning', '')}")

    # --- Store summary as note --------------------------------------------
    summary = data.get("summary", "").strip()
    if summary:
        add_document_note(document_id, summary)

    logger.info(f"Successfully updated document {document_id}")
    return True


# ---------------------------------------------------------------------------
# PDF OCR — rolling context page loop
# ---------------------------------------------------------------------------


def process_pdf_document(
    pdf_path: str,
    document_id: int,
    tags: List[Dict[str, Any]],
    correspondents: List[Dict[str, Any]],
    document_types: List[Dict[str, Any]],
    debug: bool = False,
) -> Optional[str]:
    """Run vision OCR over every page of a PDF with rolling context.

    For each page, the raw Tesseract text (extracted locally via PyMuPDF) is
    passed alongside the page image as a structural hint for the vision model.

    Returns the aggregated OCR text for all pages, or None if vision is
    disabled or processing fails.
    """
    if not ENABLE_VISION:
        logger.warning("Vision processing disabled — skipping PDF OCR")
        return None

    aggregated: List[str] = []

    try:
        with fitz.open(pdf_path) as doc:
            page_count = len(doc)
            for page_number in range(page_count):
                page = doc.load_page(page_number)
                pix = page.get_pixmap()

                # Extract Tesseract text for this page as a hint
                tesseract_hint = page.get_text("text")

                with tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False
                ) as img_file:
                    img_path = img_file.name

                try:
                    pix.save(img_path)
                    previous_context = "\n\n".join(aggregated)
                    ocr_result = ocr_document(
                        img_path,
                        previous_context=previous_context,
                        tesseract_hint=tesseract_hint,
                        debug=debug,
                    )
                    if ocr_result:
                        page_text = ocr_result["choices"][0]["message"]["content"]
                        aggregated.append(page_text)
                        logger.info(
                            f"OCR page {page_number + 1}/{page_count} "
                            f"({len(page_text)} chars)"
                        )
                    else:
                        logger.warning(
                            f"OCR returned nothing for page {page_number + 1}"
                        )
                finally:
                    try:
                        os.unlink(img_path)
                    except OSError as e:
                        logger.warning(f"Could not delete temp image {img_path}: {e}")

    except Exception as e:
        logger.error(f"Error during PDF OCR: {e}")
        raise

    return "\n\n".join(aggregated) if aggregated else None


# ---------------------------------------------------------------------------
# Image document OCR
# ---------------------------------------------------------------------------


def process_image_document(
    file_content: bytes,
    document_id: int,
    tags: List[Dict[str, Any]],
    correspondents: List[Dict[str, Any]],
    document_types: List[Dict[str, Any]],
    debug: bool = False,
) -> Optional[str]:
    """Run vision OCR on a JPEG/PNG document.

    Returns extracted text string, or None if vision is disabled or fails.
    """
    if not ENABLE_VISION:
        logger.warning("Vision processing disabled — skipping image OCR")
        return None

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
        try:
            tmp.write(file_content)
            tmp.flush()
            ocr_result = ocr_document(tmp_path, debug=debug)
            if not ocr_result:
                logger.error("OCR processing failed for image document")
                return None
            return ocr_result["choices"][0]["message"]["content"]
        finally:
            try:
                os.unlink(tmp_path)
            except OSError as e:
                logger.warning(f"Could not delete temp file {tmp_path}: {e}")


# ---------------------------------------------------------------------------
# Tesseract text cleaning
# ---------------------------------------------------------------------------

_CLEAN_SYSTEM = (
    "You are a document text cleaning assistant. "
    "You receive raw OCR text extracted from a PDF by Tesseract OCR. "
    "Clean and reformat it into well-structured plain text:\n"
    "- Fix encoding artefacts (e.g. Õ → apostrophe, Ò/Ó → straight quotes)\n"
    "- Remove blank form field underscores (______) and empty label lines\n"
    "- Reconstruct logical structure: numbered items, checkboxes (use ☑/☐), paragraphs\n"
    "- Preserve all factual content exactly — do NOT add, remove, or paraphrase anything\n"
    "Output only the cleaned text, nothing else."
)


def clean_text_with_llm(text: str) -> str:
    """Clean Tesseract OCR text through the LLM in chunks.

    Splits the text into chunks of TEXT_CLEAN_CHUNK_CHARS, cleans each
    independently, then joins the results. Returns the original text if
    cleaning fails for any chunk.
    """
    if not text or not text.strip():
        return text

    chunks = [
        text[i : i + TEXT_CLEAN_CHUNK_CHARS]
        for i in range(0, len(text), TEXT_CLEAN_CHUNK_CHARS)
    ]
    total = len(chunks)
    logger.info(
        f"Cleaning Tesseract text in {total} chunk(s) of ~{TEXT_CLEAN_CHUNK_CHARS} chars"
    )

    cleaned_chunks: List[str] = []

    for idx, chunk in enumerate(chunks):
        retry_wait = float(INITIAL_RETRY_WAIT)
        success = False

        for attempt in range(MAX_RETRIES + 1):
            try:
                payload = {
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": _CLEAN_SYSTEM},
                        {
                            "role": "user",
                            "content": (
                                f"Chunk {idx + 1} of {total}. Clean this OCR text:\n\n{chunk}"
                            ),
                        },
                    ],
                    "max_tokens": MAX_RETURN_TOKENS,
                }

                response = requests.post(
                    f"{OPENAI_API_ENDPOINT}/v1/chat/completions",
                    headers=_llm_headers(),
                    json=payload,
                )

                if response.status_code == 200:
                    cleaned = response.json()["choices"][0]["message"]["content"]
                    cleaned_chunks.append(cleaned)
                    logger.info(
                        f"Cleaned chunk {idx + 1}/{total}: "
                        f"{len(chunk)} → {len(cleaned)} chars"
                    )
                    success = True
                    break

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", retry_wait))
                    retry_wait = max(float(retry_after), retry_wait)
                    logger.warning(
                        f"Rate limited on chunk {idx + 1} — retry {attempt + 1}/{MAX_RETRIES}"
                    )
                    retry_wait = _retry_wait(retry_wait)
                    continue

                logger.error(
                    f"Text cleaning failed for chunk {idx + 1} "
                    f"({response.status_code}): {response.text[:200]}"
                )
                break

            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Request error on chunk {idx + 1} (attempt {attempt + 1}): {e}"
                )
                if attempt < MAX_RETRIES:
                    retry_wait = _retry_wait(retry_wait)
                continue

        if not success:
            logger.warning(
                f"Chunk {idx + 1}/{total} cleaning failed — "
                "falling back to original text for entire document"
            )
            return text

    return "\n\n".join(cleaned_chunks)


# ---------------------------------------------------------------------------
# Document type handlers
# ---------------------------------------------------------------------------


def _handle_pdf(
    pdf_path: str,
    doc_id: int,
    tags: list,
    correspondents: list,
    doc_types: list,
    metadata: dict,
    filename: str,
    needs_review_tag_id: Optional[int],
    debug: bool,
) -> None:
    """Process a PDF document.

    If ENABLE_VISION is true, always use vision OCR (rolling context, page by page)
    for the best possible content quality.  Otherwise fall back to Tesseract text and
    clean it through the LLM in chunks.
    """
    if ENABLE_VISION:
        logger.info("Vision enabled — running LLM OCR on all PDF pages")
        text_content = process_pdf_document(
            pdf_path, doc_id, tags, correspondents, doc_types, debug
        )
        if not text_content:
            logger.warning(
                "Vision OCR produced no text — falling back to Tesseract content"
            )
            raw = metadata.get("content", "")
            text_content = (
                raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
            )
    else:
        logger.info("Vision disabled — cleaning Tesseract text through LLM")
        raw = metadata.get("content", "")
        raw_text = (
            raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        )
        text_content = clean_text_with_llm(raw_text) if not debug else raw_text

    if not text_content or not text_content.strip():
        logger.error("No text content available — aborting classification")
        return

    result = classify_document(
        ocr_text=text_content,
        tags=tags,
        correspondents=correspondents,
        document_types=doc_types,
        filename=filename,
        language=PAPERLESS_OCR_LANGUAGE,
        debug=debug,
    )
    if result:
        if debug:
            logger.info("DEBUG MODE — skipping Paperless write")
            data = extract_classification_data(result)
            logger.info(
                f"Would write: title={data.get('title')!r}, correspondent={data.get('correspondent')!r}, "
                f"tags={data.get('tags')}, new_tags={data.get('new_tags')}, "
                f"doc_type={data.get('document_type')!r}, summary={data.get('summary')!r}"
            )
        else:
            update_document_content(
                doc_id,
                text_content,
                result,
                tags,
                correspondents,
                doc_types,
                needs_review_tag_id=needs_review_tag_id,
            )


def _handle_image(
    image_data: bytes,
    doc_id: int,
    tags: list,
    correspondents: list,
    doc_types: list,
    filename: str,
    needs_review_tag_id: Optional[int],
    debug: bool,
) -> None:
    """Process a JPEG/PNG document."""
    if not ENABLE_VISION:
        logger.warning("Vision processing disabled — skipping image document")
        return

    logger.info("Processing image document via vision OCR")
    text_content = process_image_document(
        image_data, doc_id, tags, correspondents, doc_types, debug
    )
    if not text_content:
        return

    result = classify_document(
        ocr_text=text_content,
        tags=tags,
        correspondents=correspondents,
        document_types=doc_types,
        filename=filename,
        language=PAPERLESS_OCR_LANGUAGE,
        debug=debug,
    )
    if result:
        if debug:
            logger.info("DEBUG MODE — skipping Paperless write")
            data = extract_classification_data(result)
            logger.info(
                f"Would write: title={data.get('title')!r}, correspondent={data.get('correspondent')!r}, "
                f"tags={data.get('tags')}, new_tags={data.get('new_tags')}, "
                f"doc_type={data.get('document_type')!r}, summary={data.get('summary')!r}"
            )
        else:
            update_document_content(
                doc_id,
                text_content,
                result,
                tags,
                correspondents,
                doc_types,
                needs_review_tag_id=needs_review_tag_id,
            )


def _handle_text(
    metadata: dict,
    doc_id: int,
    tags: list,
    correspondents: list,
    doc_types: list,
    filename: str,
    needs_review_tag_id: Optional[int],
    debug: bool,
) -> None:
    """Process a plain-text document, cleaning Tesseract output through the LLM."""
    logger.info("Processing text document")
    raw = metadata.get("content", "")
    raw_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    text_content = clean_text_with_llm(raw_text) if not debug else raw_text

    result = classify_document(
        ocr_text=text_content,
        tags=tags,
        correspondents=correspondents,
        document_types=doc_types,
        filename=filename,
        language=PAPERLESS_OCR_LANGUAGE,
        debug=debug,
    )
    if result:
        if debug:
            logger.info("DEBUG MODE — skipping Paperless write")
            data = extract_classification_data(result)
            logger.info(
                f"Would write: title={data.get('title')!r}, correspondent={data.get('correspondent')!r}, "
                f"tags={data.get('tags')}, new_tags={data.get('new_tags')}, "
                f"doc_type={data.get('document_type')!r}, summary={data.get('summary')!r}"
            )
        else:
            update_document_content(
                doc_id,
                text_content,
                result,
                tags,
                correspondents,
                doc_types,
                needs_review_tag_id=needs_review_tag_id,
            )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main(document_id: int, debug: bool = False) -> None:
    """Main document processing pipeline.

    In debug mode, LLM calls return canned responses and NO writes are made
    to Paperless — the pipeline is fully read-only.
    """
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.info("Running in debug mode — Paperless writes are DISABLED")

    try:
        # 1. Fetch metadata
        logger.info("Fetching Paperless metadata…")
        tags = fetch_tags()
        correspondents = fetch_correspondents()
        document_types = fetch_document_types()

        # 2. Download document
        logger.info(f"Downloading document {document_id}…")
        content_type, doc_metadata = download_document(document_id)
        if not doc_metadata:
            logger.error("Failed to download document metadata — aborting")
            return

        # 3. Idempotency check — skip if LLM tag already applied (not in debug)
        existing_tags = doc_metadata.get("tags", [])
        if not debug and LLM_PROCESSED_TAG in existing_tags:
            logger.info(
                f"Document {document_id} already processed by LLM "
                f"(tag {LLM_PROCESSED_TAG} present) — skipping"
            )
            return

        # 4. Resolve / create the "needs review" tag once per run (read-only in debug)
        needs_review_tag_id = (
            next(
                (
                    t["id"]
                    for t in tags
                    if t["name"].lower() == NEEDS_REVIEW_TAG_NAME.lower()
                ),
                None,
            )
            if debug
            else get_or_create_tag(NEEDS_REVIEW_TAG_NAME, tags)
        )

        # 5. Extract filename hint
        filename = doc_metadata.get("original_filename", "")

        # 6. Prepare raw content bytes
        raw_content = doc_metadata.get("content", b"")
        file_content = (
            raw_content
            if isinstance(raw_content, bytes)
            else raw_content.encode("utf-8")
        )

        # 7. Dispatch by content type
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            try:
                tmp.write(file_content)
                tmp.flush()

                if content_type == "application/pdf":
                    _handle_pdf(
                        tmp_path,
                        document_id,
                        tags,
                        correspondents,
                        document_types,
                        doc_metadata,
                        filename,
                        needs_review_tag_id,
                        debug,
                    )
                elif content_type in ("image/jpeg", "image/png"):
                    _handle_image(
                        file_content,
                        document_id,
                        tags,
                        correspondents,
                        document_types,
                        filename,
                        needs_review_tag_id,
                        debug,
                    )
                else:
                    _handle_text(
                        doc_metadata,
                        document_id,
                        tags,
                        correspondents,
                        document_types,
                        filename,
                        needs_review_tag_id,
                        debug,
                    )

            except Exception as e:
                logger.error(f"Document processing failed: {e}")
                raise
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError as e:
                    logger.warning(f"Could not delete temp file: {e}")

    except Exception as e:
        logger.error(f"Fatal error in document pipeline: {e}")
        raise

    logger.info(f"Document {document_id} processing completed successfully")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        if not validate_config():
            sys.exit(1)

        document_id_raw = None
        if len(sys.argv) > 1:
            document_id_raw = sys.argv[1]
        else:
            document_id_raw = os.getenv("DOCUMENT_ID")

        if not document_id_raw:
            logger.error(
                "No document ID provided.\n"
                "Usage:  ./llm.py <document_id>\n"
                "Or set: DOCUMENT_ID environment variable\n\n"
                "When run from Paperless-NGX as a post-consume script "
                "the document ID is passed automatically as the first argument."
            )
            sys.exit(1)

        debug_flag = "--debug" in sys.argv
        main(int(document_id_raw), debug_flag)

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)
