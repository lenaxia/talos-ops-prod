#!/usr/bin/env python
import unittest
from unittest.mock import patch, MagicMock, call
import tempfile
import os
import requests
import json
import base64
from datetime import datetime
from PIL import Image
import fitz

from llm import (
    encode_image,
    pdf_needs_vision_ocr,
    fetch_metadata_list,
    download_document,
    resize_image,
    ocr_document,
    classify_document,
    extract_classification_data,
    update_document_content,
    process_pdf_document,
    process_image_document,
    create_correspondent,
    create_tag,
    get_or_create_tag,
    add_document_note,
    sanitize_title,
    clean_text_with_llm,
    main,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

MOCK_TAGS = [
    {"id": 1, "name": "Invoice"},
    {"id": 2, "name": "Receipt"},
    {"id": 111, "name": "ChatGPT"},
    {"id": 112, "name": "LLM"},
]
MOCK_CORRESPONDENTS = [{"id": 1, "name": "ACME Corp"}]
MOCK_DOCUMENT_TYPES = [{"id": 1, "name": "Financial"}]

VALID_CLASSIFICATION_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "creation_date": "2023-01-01",
                        "title": "ACME Invoice January 2023",
                        "correspondent": "ACME Corp",
                        "correspondent_is_new": False,
                        "tags": ["Invoice"],
                        "new_tags": [],
                        "document_type": "Financial",
                        "summary": "An invoice from ACME Corp for January 2023 totalling $500.",
                        "reasoning": "Correspondent matched ACME Corp; document is a financial invoice.",
                    }
                )
            }
        }
    ]
}


def _make_response(status_code: int, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    if json_data is not None:
        r.json.return_value = json_data
    r.text = text
    if status_code >= 400:
        r.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{status_code} Error"
        )
    else:
        r.raise_for_status.return_value = None
    return r


# ---------------------------------------------------------------------------
# encode_image
# ---------------------------------------------------------------------------


class TestEncodeImage(unittest.TestCase):
    def setUp(self):
        self.test_image_path = "test_image.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(self.test_image_path)

    def tearDown(self):
        if os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)

    def test_encode_image_success(self):
        result = encode_image(self.test_image_path)
        self.assertIsInstance(result, str)
        # Should be valid base64
        base64.b64decode(result)

    def test_encode_image_missing_file(self):
        with self.assertRaises(Exception):
            encode_image("nonexistent.jpg")


# ---------------------------------------------------------------------------
# pdf_needs_vision_ocr  (replaces is_pdf_image_only)
# ---------------------------------------------------------------------------


class TestPdfNeedsVisionOcr(unittest.TestCase):
    def _make_page(self, text="", has_images=False, has_tables=False):
        page = MagicMock()
        page.get_text.return_value = text
        page.get_images.return_value = [MagicMock()] if has_images else []
        tables_mock = MagicMock()
        tables_mock.tables = [MagicMock()] if has_tables else []
        page.find_tables.return_value = tables_mock
        return page

    @patch("fitz.open")
    def test_image_only_pdf_needs_vision(self, mock_fitz):
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        mock_doc.__iter__.return_value = [self._make_page(text="")]
        mock_fitz.return_value = mock_doc
        self.assertTrue(pdf_needs_vision_ocr("dummy.pdf"))

    @patch("fitz.open")
    def test_pdf_with_embedded_images_needs_vision(self, mock_fitz):
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        mock_doc.__iter__.return_value = [
            self._make_page(text="Some text " * 20, has_images=True)
        ]
        mock_fitz.return_value = mock_doc
        self.assertTrue(pdf_needs_vision_ocr("dummy.pdf"))

    @patch("fitz.open")
    def test_pdf_with_tables_needs_vision(self, mock_fitz):
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        mock_doc.__iter__.return_value = [
            self._make_page(text="Some text " * 20, has_tables=True)
        ]
        mock_fitz.return_value = mock_doc
        self.assertTrue(pdf_needs_vision_ocr("dummy.pdf"))

    @patch("fitz.open")
    def test_plain_text_pdf_does_not_need_vision(self, mock_fitz):
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        mock_doc.__iter__.return_value = [
            self._make_page(text="Normal text content " * 20)
        ]
        mock_fitz.return_value = mock_doc
        self.assertFalse(pdf_needs_vision_ocr("dummy.pdf"))

    @patch("fitz.open")
    def test_sparse_text_needs_vision(self, mock_fitz):
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        # Text shorter than MINIMUM_CHARS_PER_PAGE (100)
        mock_doc.__iter__.return_value = [self._make_page(text="hi")]
        mock_fitz.return_value = mock_doc
        self.assertTrue(pdf_needs_vision_ocr("dummy.pdf"))

    @patch("fitz.open")
    def test_exception_returns_true(self, mock_fitz):
        mock_fitz.side_effect = Exception("corrupt pdf")
        self.assertTrue(pdf_needs_vision_ocr("dummy.pdf"))


# ---------------------------------------------------------------------------
# fetch_metadata_list
# ---------------------------------------------------------------------------


class TestFetchMetadataList(unittest.TestCase):
    @patch("requests.get")
    def test_single_page_success(self, mock_get):
        mock_get.return_value = _make_response(
            200, {"results": MOCK_TAGS, "next": None}
        )
        result = fetch_metadata_list("http://test/api/tags/")
        self.assertEqual(len(result), len(MOCK_TAGS))

    @patch("requests.get")
    def test_pagination(self, mock_get):
        mock_get.side_effect = [
            _make_response(
                200, {"results": MOCK_TAGS[:2], "next": "http://test/api/tags/?page=2"}
            ),
            _make_response(200, {"results": MOCK_TAGS[2:], "next": None}),
        ]
        result = fetch_metadata_list("http://test/api/tags/")
        self.assertEqual(len(result), len(MOCK_TAGS))

    @patch("requests.get")
    def test_http_error_returns_empty(self, mock_get):
        mock_get.return_value = _make_response(500)
        result = fetch_metadata_list("http://test/api/tags/")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# download_document
# ---------------------------------------------------------------------------


class TestDownloadDocument(unittest.TestCase):
    @patch("requests.get")
    def test_success(self, mock_get):
        mock_get.return_value = _make_response(
            200,
            {"content_type": "application/pdf", "content": "PDF content", "tags": []},
        )
        content_type, metadata = download_document(123)
        self.assertEqual(content_type, "application/pdf")
        self.assertEqual(metadata["content"], "PDF content")

    @patch("requests.get")
    def test_http_error(self, mock_get):
        mock_get.return_value = _make_response(404)
        content_type, metadata = download_document(123)
        self.assertIsNone(content_type)
        self.assertIsNone(metadata)

    @patch("requests.get")
    def test_json_decode_error(self, mock_get):
        r = MagicMock()
        r.status_code = 200
        r.raise_for_status.return_value = None
        r.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_get.return_value = r
        content_type, metadata = download_document(123)
        self.assertIsNone(content_type)
        self.assertIsNone(metadata)


# ---------------------------------------------------------------------------
# resize_image
# ---------------------------------------------------------------------------


class TestResizeImage(unittest.TestCase):
    @patch("PIL.Image.open")
    def test_resize_large_image(self, mock_open):
        mock_img = MagicMock()
        mock_img.size = (3000, 4000)
        mock_img.resize.return_value = mock_img
        mock_open.return_value.__enter__.return_value = mock_img

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            result = resize_image(tmp.name)
            self.assertEqual(result, tmp.name)
            mock_img.resize.assert_called_once()
            new_w, new_h = mock_img.resize.call_args[0][0]
            self.assertLessEqual(max(new_w, new_h), 2048)


# ---------------------------------------------------------------------------
# sanitize_title
# ---------------------------------------------------------------------------


class TestSanitizeTitle(unittest.TestCase):
    def test_strips_quotes(self):
        from llm import sanitize_title

        self.assertEqual(sanitize_title('"Hello World"'), "Hello World")

    def test_strips_leading_trailing_whitespace(self):
        from llm import sanitize_title

        self.assertEqual(sanitize_title("  Invoice  "), "Invoice")

    def test_removes_slashes(self):
        from llm import sanitize_title

        self.assertEqual(sanitize_title("foo/bar\\baz"), "foo bar baz")

    def test_truncates_to_128_chars(self):
        from llm import sanitize_title

        long_title = "A" * 200
        result = sanitize_title(long_title)
        self.assertLessEqual(len(result), 128)

    def test_strips_trailing_punctuation(self):
        from llm import sanitize_title

        self.assertEqual(sanitize_title("Invoice."), "Invoice")

    def test_empty_string(self):
        from llm import sanitize_title

        self.assertEqual(sanitize_title(""), "")

    def test_normal_title_unchanged(self):
        from llm import sanitize_title

        self.assertEqual(
            sanitize_title("Chase Statement Jan 2024"), "Chase Statement Jan 2024"
        )


# ---------------------------------------------------------------------------
# create_correspondent
# ---------------------------------------------------------------------------


class TestCreateCorrespondent(unittest.TestCase):
    @patch("requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = _make_response(201, {"id": 99, "name": "New Corp"})
        result = create_correspondent("New Corp")
        self.assertEqual(result, 99)
        posted = mock_post.call_args[1]["json"]
        self.assertEqual(posted["name"], "New Corp")

    @patch("requests.post")
    def test_http_error_returns_none(self, mock_post):
        mock_post.return_value = _make_response(400)
        result = create_correspondent("New Corp")
        self.assertIsNone(result)

    @patch("requests.post")
    def test_request_exception_returns_none(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("timeout")
        result = create_correspondent("New Corp")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# create_tag
# ---------------------------------------------------------------------------


class TestCreateTag(unittest.TestCase):
    @patch("requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = _make_response(201, {"id": 55, "name": "NewTag"})
        result = create_tag("NewTag")
        self.assertEqual(result, 55)
        posted = mock_post.call_args[1]["json"]
        self.assertEqual(posted["name"], "NewTag")

    @patch("requests.post")
    def test_http_error_returns_none(self, mock_post):
        mock_post.return_value = _make_response(400)
        result = create_tag("NewTag")
        self.assertIsNone(result)

    @patch("requests.post")
    def test_request_exception_returns_none(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("timeout")
        result = create_tag("NewTag")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_or_create_tag
# ---------------------------------------------------------------------------


class TestGetOrCreateTag(unittest.TestCase):
    def test_returns_existing_id_exact_match(self):
        result = get_or_create_tag("Invoice", MOCK_TAGS)
        self.assertEqual(result, 1)

    def test_case_insensitive_match(self):
        result = get_or_create_tag("invoice", MOCK_TAGS)
        self.assertEqual(result, 1)

    @patch("llm.create_tag")
    def test_creates_when_not_found(self, mock_create):
        mock_create.return_value = 77
        result = get_or_create_tag("BrandNewTag", MOCK_TAGS)
        self.assertEqual(result, 77)
        mock_create.assert_called_once_with("BrandNewTag")

    @patch("llm.create_tag")
    def test_returns_none_when_create_fails(self, mock_create):
        mock_create.return_value = None
        result = get_or_create_tag("BrandNewTag", MOCK_TAGS)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# add_document_note
# ---------------------------------------------------------------------------


class TestAddDocumentNote(unittest.TestCase):
    @patch("requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = _make_response(200, {"id": 1})
        result = add_document_note(123, "This is a summary.")
        self.assertTrue(result)
        posted = mock_post.call_args[1]["json"]
        self.assertIn("note", posted)
        self.assertEqual(posted["note"], "This is a summary.")

    @patch("requests.post")
    def test_http_error_returns_false(self, mock_post):
        mock_post.return_value = _make_response(400)
        result = add_document_note(123, "Summary.")
        self.assertFalse(result)

    @patch("requests.post")
    def test_request_exception_returns_false(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("timeout")
        result = add_document_note(123, "Summary.")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# ocr_document
# ---------------------------------------------------------------------------


class TestOcrDocument(unittest.TestCase):
    def setUp(self):
        self.test_image_path = "test_ocr_image.png"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(self.test_image_path)

    def tearDown(self):
        if os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)

    @patch("requests.post")
    @patch("llm.encode_image")
    @patch("llm.resize_image")
    def test_success(self, mock_resize, mock_encode, mock_post):
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        mock_post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "Extracted text"}}]}
        )
        result = ocr_document(self.test_image_path)
        self.assertEqual(result["choices"][0]["message"]["content"], "Extracted text")

    @patch("requests.post")
    @patch("llm.encode_image")
    @patch("llm.resize_image")
    def test_previous_context_included_in_payload(
        self, mock_resize, mock_encode, mock_post
    ):
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        mock_post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "Page 2 text"}}]}
        )
        ocr_document(self.test_image_path, previous_context="Page 1 text")
        payload = mock_post.call_args[1]["json"]
        user_content = payload["messages"][1]["content"]
        text_parts = [p["text"] for p in user_content if p.get("type") == "text"]
        self.assertTrue(
            any("Page 1 text" in t for t in text_parts),
            "previous_context should appear in OCR prompt",
        )

    @patch("requests.post")
    @patch("llm.encode_image")
    @patch("llm.resize_image")
    def test_tesseract_hint_included_in_payload(
        self, mock_resize, mock_encode, mock_post
    ):
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        mock_post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "Clean text"}}]}
        )
        ocr_document(self.test_image_path, tesseract_hint="BuyerÕs raw text")
        payload = mock_post.call_args[1]["json"]
        user_content = payload["messages"][1]["content"]
        text_parts = [p["text"] for p in user_content if p.get("type") == "text"]
        self.assertTrue(
            any("BuyerÕs raw text" in t for t in text_parts),
            "tesseract_hint should appear in OCR prompt",
        )

    @patch("requests.post")
    @patch("llm.encode_image")
    @patch("llm.resize_image")
    def test_empty_tesseract_hint_not_included(
        self, mock_resize, mock_encode, mock_post
    ):
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        mock_post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "text"}}]}
        )
        ocr_document(self.test_image_path, tesseract_hint="")
        payload = mock_post.call_args[1]["json"]
        user_content = payload["messages"][1]["content"]
        text_parts = [p["text"] for p in user_content if p.get("type") == "text"]
        self.assertFalse(
            any("structural hint" in t for t in text_parts),
            "empty tesseract_hint should not add hint block to prompt",
        )

    @patch("requests.post")
    @patch("llm.encode_image")
    @patch("llm.resize_image")
    def test_no_bnf_grammar_in_prompt(self, mock_resize, mock_encode, mock_post):
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        mock_post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "text"}}]}
        )
        ocr_document(self.test_image_path)
        payload = mock_post.call_args[1]["json"]
        all_text = json.dumps(payload)
        self.assertNotIn("BNF", all_text)
        self.assertNotIn("bnf_grammar", all_text)
        self.assertNotIn("creation_date", all_text)

    @patch("requests.post")
    @patch("llm.encode_image")
    @patch("llm.resize_image")
    @patch("time.sleep", return_value=None)
    def test_rate_limit_retries_then_succeeds(
        self, mock_sleep, mock_resize, mock_encode, mock_post
    ):
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        rate_limit = MagicMock()
        rate_limit.status_code = 429
        rate_limit.headers = {"Retry-After": "1"}
        success = _make_response(200, {"choices": [{"message": {"content": "text"}}]})
        mock_post.side_effect = [rate_limit, success]
        result = ocr_document(self.test_image_path)
        self.assertIsNotNone(result)
        mock_sleep.assert_called_once()

    @patch("requests.post")
    @patch("llm.encode_image")
    @patch("llm.resize_image")
    @patch("time.sleep", return_value=None)
    def test_rate_limit_exceeds_max_retries(
        self, mock_sleep, mock_resize, mock_encode, mock_post
    ):
        import llm

        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        rate_limit = MagicMock()
        rate_limit.status_code = 429
        rate_limit.headers = {"Retry-After": "1"}
        mock_post.side_effect = [rate_limit] * (llm.MAX_RETRIES + 1)
        result = ocr_document(self.test_image_path)
        self.assertIsNone(result)
        self.assertEqual(mock_sleep.call_count, llm.MAX_RETRIES)

    @patch("requests.post")
    @patch("llm.encode_image")
    @patch("llm.resize_image")
    def test_debug_mode_makes_real_api_call(self, mock_resize, mock_encode, mock_post):
        """Debug mode makes a real LLM call — no canned response."""
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        mock_post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "Real OCR text"}}]}
        )
        result = ocr_document(self.test_image_path, debug=True)
        mock_post.assert_called_once()
        self.assertEqual(result["choices"][0]["message"]["content"], "Real OCR text")


# ---------------------------------------------------------------------------
# classify_document
# ---------------------------------------------------------------------------


class TestClassifyDocument(unittest.TestCase):
    @patch("requests.post")
    def test_success_with_all_fields(self, mock_post):
        mock_post.return_value = _make_response(200, VALID_CLASSIFICATION_RESPONSE)
        result = classify_document(
            ocr_text="Invoice from ACME Corp",
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
        )
        self.assertIsNotNone(result)

    @patch("requests.post")
    def test_filename_hint_included_in_payload(self, mock_post):
        mock_post.return_value = _make_response(200, VALID_CLASSIFICATION_RESPONSE)
        classify_document(
            ocr_text="Some text",
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            filename="Chase_Statement_2024-03.pdf",
        )
        payload = mock_post.call_args[1]["json"]
        all_text = json.dumps(payload)
        self.assertIn("Chase_Statement_2024-03.pdf", all_text)

    @patch("requests.post")
    def test_system_message_present(self, mock_post):
        mock_post.return_value = _make_response(200, VALID_CLASSIFICATION_RESPONSE)
        classify_document(
            ocr_text="Some text",
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
        )
        payload = mock_post.call_args[1]["json"]
        roles = [m["role"] for m in payload["messages"]]
        self.assertIn("system", roles)

    @patch("requests.post")
    def test_no_image_path_parameter(self, mock_post):
        """classify_document should not accept or send image data"""
        mock_post.return_value = _make_response(200, VALID_CLASSIFICATION_RESPONSE)
        # Should work without image_path - it's been removed from the signature
        result = classify_document(
            ocr_text="Some text",
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
        )
        self.assertIsNotNone(result)
        payload = mock_post.call_args[1]["json"]
        all_content = json.dumps(payload)
        self.assertNotIn("image_url", all_content)

    @patch("requests.post")
    def test_json_object_response_format(self, mock_post):
        mock_post.return_value = _make_response(200, VALID_CLASSIFICATION_RESPONSE)
        classify_document(
            ocr_text="Some text",
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
        )
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload.get("response_format"), {"type": "json_object"})

    @patch("requests.post")
    def test_missing_ocr_text_returns_none(self, mock_post):
        result = classify_document(
            ocr_text="",
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
        )
        self.assertIsNone(result)
        mock_post.assert_not_called()

    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_rate_limit_retries(self, mock_sleep, mock_post):
        import llm

        rate_limit = MagicMock()
        rate_limit.status_code = 429
        rate_limit.headers = {"Retry-After": "1"}
        success = _make_response(200, VALID_CLASSIFICATION_RESPONSE)
        mock_post.side_effect = [rate_limit, success]
        result = classify_document(
            ocr_text="Some text",
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
        )
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# extract_classification_data
# ---------------------------------------------------------------------------


class TestExtractClassificationData(unittest.TestCase):
    def test_valid_full_response(self):
        result = extract_classification_data(VALID_CLASSIFICATION_RESPONSE)
        self.assertEqual(result["title"], "ACME Invoice January 2023")
        self.assertEqual(result["correspondent"], "ACME Corp")
        self.assertFalse(result["correspondent_is_new"])
        self.assertEqual(result["tags"], ["Invoice"])
        self.assertEqual(result["new_tags"], [])
        self.assertEqual(result["document_type"], "Financial")
        self.assertIn("summary", result)
        self.assertIn("reasoning", result)

    def test_missing_fields_get_safe_defaults(self):
        minimal = {"choices": [{"message": {"content": json.dumps({"title": "Test"})}}]}
        result = extract_classification_data(minimal)
        self.assertEqual(result["title"], "Test")
        self.assertEqual(result["creation_date"], "")
        self.assertEqual(result["correspondent"], "")
        self.assertFalse(result["correspondent_is_new"])
        self.assertEqual(result["tags"], [])
        self.assertEqual(result["new_tags"], [])
        self.assertEqual(result["document_type"], "")
        self.assertEqual(result["summary"], "")
        self.assertEqual(result["reasoning"], "")

    def test_invalid_json_returns_empty_defaults(self):
        bad = {"choices": [{"message": {"content": "not json"}}]}
        result = extract_classification_data(bad)
        self.assertEqual(result["title"], "")
        self.assertFalse(result["correspondent_is_new"])
        self.assertEqual(result["tags"], [])
        self.assertEqual(result["new_tags"], [])

    def test_correspondent_is_new_defaults_to_false(self):
        data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "Test",
                                "correspondent": "Someone New",
                                # correspondent_is_new intentionally absent
                            }
                        )
                    }
                }
            ]
        }
        result = extract_classification_data(data)
        self.assertFalse(result["correspondent_is_new"])


# ---------------------------------------------------------------------------
# update_document_content
# ---------------------------------------------------------------------------


class TestUpdateDocumentContent(unittest.TestCase):
    def _make_classification(self, overrides=None):
        data = {
            "creation_date": "2023-01-01",
            "title": "Test Document",
            "correspondent": "ACME Corp",
            "correspondent_is_new": False,
            "tags": ["Invoice"],
            "new_tags": [],
            "document_type": "Financial",
            "summary": "A test invoice.",
            "reasoning": "Matched ACME Corp.",
        }
        if overrides:
            data.update(overrides)
        return {"choices": [{"message": {"content": json.dumps(data)}}]}

    @patch("llm.add_document_note")
    @patch("requests.patch")
    def test_successful_update_calls_note(self, mock_patch, mock_note):
        mock_patch.return_value = _make_response(200, {})
        mock_note.return_value = True
        result = update_document_content(
            document_id=123,
            ocr_text="content",
            classification_result=self._make_classification(),
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            needs_review_tag_id=None,
        )
        self.assertTrue(result)
        mock_note.assert_called_once_with(123, "A test invoice.")

    @patch("llm.add_document_note")
    @patch("requests.patch")
    def test_no_note_when_summary_empty(self, mock_patch, mock_note):
        mock_patch.return_value = _make_response(200, {})
        result = update_document_content(
            document_id=123,
            ocr_text="content",
            classification_result=self._make_classification({"summary": ""}),
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            needs_review_tag_id=None,
        )
        self.assertTrue(result)
        mock_note.assert_not_called()

    @patch("llm.add_document_note")
    @patch("llm.create_correspondent")
    @patch("requests.patch")
    def test_creates_new_correspondent_and_adds_review_tag(
        self, mock_patch, mock_create_corr, mock_note
    ):
        mock_patch.return_value = _make_response(200, {})
        mock_create_corr.return_value = 88
        mock_note.return_value = True
        result = update_document_content(
            document_id=123,
            ocr_text="content",
            classification_result=self._make_classification(
                {
                    "correspondent": "Brand New Corp",
                    "correspondent_is_new": True,
                }
            ),
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            needs_review_tag_id=99,
        )
        self.assertTrue(result)
        mock_create_corr.assert_called_once_with("Brand New Corp")
        # Review tag should be in the PATCH payload
        patch_payload = mock_patch.call_args[1]["json"]
        self.assertIn(99, patch_payload["tags"])
        self.assertEqual(patch_payload["correspondent"], 88)

    @patch("llm.add_document_note")
    @patch("llm.create_tag")
    @patch("requests.patch")
    def test_creates_new_tags_and_adds_review_tag(
        self, mock_patch, mock_create_tag, mock_note
    ):
        mock_patch.return_value = _make_response(200, {})
        mock_create_tag.return_value = 66
        mock_note.return_value = True
        result = update_document_content(
            document_id=123,
            ocr_text="content",
            classification_result=self._make_classification(
                {"new_tags": ["BrandNewTag"]}
            ),
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            needs_review_tag_id=99,
        )
        self.assertTrue(result)
        mock_create_tag.assert_called_once_with("BrandNewTag")
        patch_payload = mock_patch.call_args[1]["json"]
        self.assertIn(66, patch_payload["tags"])
        self.assertIn(99, patch_payload["tags"])

    @patch("llm.add_document_note")
    @patch("requests.patch")
    def test_default_tags_always_present(self, mock_patch, mock_note):
        mock_patch.return_value = _make_response(200, {})
        mock_note.return_value = True
        update_document_content(
            document_id=123,
            ocr_text="content",
            classification_result=self._make_classification({"tags": []}),
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            needs_review_tag_id=None,
        )
        patch_payload = mock_patch.call_args[1]["json"]
        self.assertIn(111, patch_payload["tags"])
        self.assertIn(112, patch_payload["tags"])

    @patch("llm.add_document_note")
    @patch("requests.patch")
    def test_title_is_sanitized(self, mock_patch, mock_note):
        mock_patch.return_value = _make_response(200, {})
        mock_note.return_value = True
        update_document_content(
            document_id=123,
            ocr_text="content",
            classification_result=self._make_classification(
                {"title": '"Dirty/Title."'}
            ),
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            needs_review_tag_id=None,
        )
        patch_payload = mock_patch.call_args[1]["json"]
        self.assertNotIn('"', patch_payload["title"])
        self.assertNotIn("/", patch_payload["title"])

    @patch("llm.add_document_note")
    @patch("requests.patch")
    def test_no_refusal_guard_on_content(self, mock_patch, mock_note):
        """The old 'i can't assist' guard should be gone — all content is stored."""
        mock_patch.return_value = _make_response(200, {})
        mock_note.return_value = True
        refusal_text = "I can't assist with that request. I'm sorry."
        update_document_content(
            document_id=123,
            ocr_text=refusal_text,
            classification_result=self._make_classification(),
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            needs_review_tag_id=None,
        )
        patch_payload = mock_patch.call_args[1]["json"]
        # content should be stored regardless
        self.assertEqual(patch_payload.get("content"), refusal_text)

    @patch("requests.patch")
    def test_patch_failure_returns_false(self, mock_patch):
        mock_patch.return_value = _make_response(500)
        result = update_document_content(
            document_id=123,
            ocr_text="content",
            classification_result=self._make_classification(),
            tags=MOCK_TAGS,
            correspondents=MOCK_CORRESPONDENTS,
            document_types=MOCK_DOCUMENT_TYPES,
            needs_review_tag_id=None,
        )
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# process_pdf_document  (rolling context)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# clean_text_with_llm
# ---------------------------------------------------------------------------


class TestCleanTextWithLlm(unittest.TestCase):
    DIRTY = (
        "Form 21 ©Copyright 2024\n"
        "BuyerÕs Initials ______________________________\n"
        "SellerÒs offer ___________\n"
        "8. Default: (check only one) \n"
        "✔ Forfeiture of Earnest Money;  SellerÕs Election of Remedies\n"
    )
    CLEAN = "Form 21 cleaned text"

    @patch("requests.post")
    def test_single_chunk_success(self, mock_post):
        mock_post.return_value = _make_response(
            200, {"choices": [{"message": {"content": self.CLEAN}}]}
        )
        result = clean_text_with_llm(self.DIRTY)
        self.assertEqual(result, self.CLEAN)
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        system_role = payload["messages"][0]["role"]
        self.assertEqual(system_role, "system")

    @patch("requests.post")
    def test_multi_chunk_joined_with_double_newline(self, mock_post):
        """Text longer than TEXT_CLEAN_CHUNK_CHARS is split and results joined."""
        import llm

        chunk_size = llm.TEXT_CLEAN_CHUNK_CHARS
        long_text = "word " * (chunk_size // 5 * 3)  # ~3 chunks worth

        mock_post.return_value = _make_response(
            200, {"choices": [{"message": {"content": "cleaned chunk"}}]}
        )
        result = clean_text_with_llm(long_text)
        expected_chunks = -(-len(long_text) // chunk_size)  # ceiling division
        self.assertEqual(mock_post.call_count, expected_chunks)
        self.assertEqual(result.count("cleaned chunk"), expected_chunks)
        self.assertIn("\n\n", result)

    @patch("requests.post")
    def test_returns_original_on_chunk_failure(self, mock_post):
        """If any chunk fails, return original text unchanged."""
        success = _make_response(
            200, {"choices": [{"message": {"content": "cleaned"}}]}
        )
        failure = _make_response(500, text="Server error")
        mock_post.side_effect = [success, failure]

        import llm

        chunk_size = llm.TEXT_CLEAN_CHUNK_CHARS
        long_text = "word " * (chunk_size // 5 * 3)  # forces at least 2 chunks

        result = clean_text_with_llm(long_text)
        self.assertEqual(result, long_text)

    @patch("requests.post")
    def test_empty_string_returns_immediately(self, mock_post):
        result = clean_text_with_llm("")
        self.assertEqual(result, "")
        mock_post.assert_not_called()

    @patch("requests.post")
    def test_whitespace_only_returns_immediately(self, mock_post):
        result = clean_text_with_llm("   \n\n  ")
        mock_post.assert_not_called()

    @patch("requests.post")
    @patch("time.sleep", return_value=None)
    def test_rate_limit_retries_then_succeeds(self, mock_sleep, mock_post):
        rate_limit = MagicMock()
        rate_limit.status_code = 429
        rate_limit.headers = {"Retry-After": "1"}
        success = _make_response(
            200, {"choices": [{"message": {"content": "cleaned"}}]}
        )
        mock_post.side_effect = [rate_limit, success]
        result = clean_text_with_llm("some dirty text")
        self.assertEqual(result, "cleaned")
        mock_sleep.assert_called_once()


class TestProcessPdfDocument(unittest.TestCase):
    @patch("llm.ocr_document")
    @patch("fitz.open")
    def test_rolling_context_passed_between_pages(self, mock_fitz, mock_ocr):
        """Each page after the first should receive previous pages' text as context."""
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__len__.return_value = 2
        mock_doc.load_page.side_effect = [mock_page, mock_page]

        mock_fitz.return_value = mock_doc

        mock_ocr.side_effect = [
            {"choices": [{"message": {"content": "Page one text"}}]},
            {"choices": [{"message": {"content": "Page two text"}}]},
        ]

        with patch("llm.ENABLE_VISION", True):
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                result = process_pdf_document(
                    pdf_path=f.name,
                    document_id=123,
                    tags=MOCK_TAGS,
                    correspondents=MOCK_CORRESPONDENTS,
                    document_types=MOCK_DOCUMENT_TYPES,
                )

        self.assertEqual(mock_ocr.call_count, 2)
        # Second call should include page 1 text as context
        second_call_kwargs = mock_ocr.call_args_list[1][1]
        self.assertIn("previous_context", second_call_kwargs)
        self.assertIn("Page one text", second_call_kwargs["previous_context"])

    @patch("llm.ocr_document")
    @patch("fitz.open")
    def test_tesseract_hint_passed_per_page(self, mock_fitz, mock_ocr):
        """Each page's Tesseract text should be passed as tesseract_hint."""
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix
        mock_page.get_text.return_value = "Raw tesseract page text"
        mock_doc.__len__.return_value = 1
        mock_doc.load_page.return_value = mock_page
        mock_fitz.return_value = mock_doc

        mock_ocr.return_value = {"choices": [{"message": {"content": "Clean text"}}]}

        with patch("llm.ENABLE_VISION", True):
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                process_pdf_document(
                    pdf_path=f.name,
                    document_id=123,
                    tags=MOCK_TAGS,
                    correspondents=MOCK_CORRESPONDENTS,
                    document_types=MOCK_DOCUMENT_TYPES,
                )

        call_kwargs = mock_ocr.call_args_list[0][1]
        self.assertIn("tesseract_hint", call_kwargs)
        self.assertEqual(call_kwargs["tesseract_hint"], "Raw tesseract page text")

    @patch("llm.ocr_document")
    @patch("fitz.open")
    def test_returns_aggregated_text(self, mock_fitz, mock_ocr):
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = False
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__len__.return_value = 2
        mock_doc.load_page.side_effect = [mock_page, mock_page]
        mock_fitz.return_value = mock_doc

        mock_ocr.side_effect = [
            {"choices": [{"message": {"content": "Page one text"}}]},
            {"choices": [{"message": {"content": "Page two text"}}]},
        ]

        with patch("llm.ENABLE_VISION", True):
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                result = process_pdf_document(
                    pdf_path=f.name,
                    document_id=123,
                    tags=MOCK_TAGS,
                    correspondents=MOCK_CORRESPONDENTS,
                    document_types=MOCK_DOCUMENT_TYPES,
                )

        self.assertIsNotNone(result)
        self.assertIn("Page one text", result)
        self.assertIn("Page two text", result)

    @patch("llm.ocr_document")
    @patch("fitz.open")
    def test_vision_disabled_returns_none(self, mock_fitz, mock_ocr):
        with patch("llm.ENABLE_VISION", False):
            result = process_pdf_document(
                pdf_path="dummy.pdf",
                document_id=123,
                tags=MOCK_TAGS,
                correspondents=MOCK_CORRESPONDENTS,
                document_types=MOCK_DOCUMENT_TYPES,
            )
        self.assertIsNone(result)
        mock_ocr.assert_not_called()


# ---------------------------------------------------------------------------
# process_image_document
# ---------------------------------------------------------------------------


class TestProcessImageDocument(unittest.TestCase):
    @patch("llm.ocr_document")
    def test_returns_ocr_text(self, mock_ocr):
        mock_ocr.return_value = {"choices": [{"message": {"content": "Image text"}}]}
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            img = Image.new("RGB", (100, 100), color="green")
            img.save(tmp.name)
            with patch("llm.ENABLE_VISION", True):
                result = process_image_document(
                    file_content=open(tmp.name, "rb").read(),
                    document_id=123,
                    tags=MOCK_TAGS,
                    correspondents=MOCK_CORRESPONDENTS,
                    document_types=MOCK_DOCUMENT_TYPES,
                )
        self.assertEqual(result, "Image text")

    @patch("llm.ocr_document")
    def test_vision_disabled_returns_none(self, mock_ocr):
        with patch("llm.ENABLE_VISION", False):
            result = process_image_document(
                file_content=b"fake",
                document_id=123,
                tags=MOCK_TAGS,
                correspondents=MOCK_CORRESPONDENTS,
                document_types=MOCK_DOCUMENT_TYPES,
            )
        self.assertIsNone(result)
        mock_ocr.assert_not_called()


# ---------------------------------------------------------------------------
# main — idempotency
# ---------------------------------------------------------------------------


class TestMainIdempotency(unittest.TestCase):
    @patch("llm.classify_document")
    @patch("llm.fetch_document_types")
    @patch("llm.fetch_correspondents")
    @patch("llm.fetch_tags")
    @patch("llm.download_document")
    def test_skips_processing_when_llm_tag_present(
        self, mock_download, mock_tags, mock_corr, mock_dt, mock_classify
    ):
        """If tag 112 (LLM) already on document, skip all processing."""
        mock_download.return_value = (
            "application/pdf",
            {"content": "text content", "tags": [112], "original_filename": "doc.pdf"},
        )
        mock_tags.return_value = MOCK_TAGS
        mock_corr.return_value = MOCK_CORRESPONDENTS
        mock_dt.return_value = MOCK_DOCUMENT_TYPES

        main(123)

        mock_classify.assert_not_called()

    @patch("llm.update_document_content")
    @patch("llm.classify_document")
    @patch("llm.clean_text_with_llm")
    @patch("llm.get_or_create_tag")
    @patch("llm.pdf_needs_vision_ocr")
    @patch("llm.fetch_document_types")
    @patch("llm.fetch_correspondents")
    @patch("llm.fetch_tags")
    @patch("llm.download_document")
    def test_processes_when_llm_tag_absent(
        self,
        mock_download,
        mock_tags,
        mock_corr,
        mock_dt,
        mock_needs_vision,
        mock_get_tag,
        mock_clean,
        mock_classify,
        mock_update,
    ):
        """If tag 112 not present, processing should proceed."""
        mock_download.return_value = (
            "application/pdf",
            {
                "content": "text content " * 50,
                "tags": [111],  # ChatGPT tag but NOT LLM tag
                "original_filename": "doc.pdf",
            },
        )
        mock_tags.return_value = MOCK_TAGS
        mock_corr.return_value = MOCK_CORRESPONDENTS
        mock_dt.return_value = MOCK_DOCUMENT_TYPES
        mock_needs_vision.return_value = False
        mock_get_tag.return_value = 98
        mock_clean.side_effect = lambda t: t  # pass-through
        mock_classify.return_value = VALID_CLASSIFICATION_RESPONSE
        mock_update.return_value = True

        main(123)

        mock_classify.assert_called_once()


# ---------------------------------------------------------------------------
# main — debug mode does not write to Paperless
# ---------------------------------------------------------------------------


class TestMainDebugMode(unittest.TestCase):
    @patch("llm.update_document_content")
    @patch("llm.classify_document")
    @patch("llm.get_or_create_tag")
    @patch("llm.pdf_needs_vision_ocr")
    @patch("llm.fetch_document_types")
    @patch("llm.fetch_correspondents")
    @patch("llm.fetch_tags")
    @patch("llm.download_document")
    def test_debug_skips_paperless_writes(
        self,
        mock_download,
        mock_tags,
        mock_corr,
        mock_dt,
        mock_needs_vision,
        mock_get_tag,
        mock_classify,
        mock_update,
    ):
        """In debug mode, classify is called but update_document_content is never called."""
        mock_download.return_value = (
            "application/pdf",
            {
                "content": "text content " * 50,
                "tags": [],
                "original_filename": "doc.pdf",
            },
        )
        mock_tags.return_value = MOCK_TAGS
        mock_corr.return_value = MOCK_CORRESPONDENTS
        mock_dt.return_value = MOCK_DOCUMENT_TYPES
        mock_needs_vision.return_value = False
        mock_get_tag.return_value = 98
        mock_classify.return_value = VALID_CLASSIFICATION_RESPONSE

        main(123, debug=True)

        mock_classify.assert_called_once()
        mock_update.assert_not_called()

    @patch("llm.classify_document")
    @patch("llm.get_or_create_tag")
    @patch("llm.pdf_needs_vision_ocr")
    @patch("llm.fetch_document_types")
    @patch("llm.fetch_correspondents")
    @patch("llm.fetch_tags")
    @patch("llm.download_document")
    def test_debug_does_not_skip_on_llm_tag(
        self,
        mock_download,
        mock_tags,
        mock_corr,
        mock_dt,
        mock_needs_vision,
        mock_get_tag,
        mock_classify,
    ):
        """In debug mode, idempotency check is skipped so we always process."""
        mock_download.return_value = (
            "application/pdf",
            {
                "content": "text content " * 50,
                "tags": [112],
                "original_filename": "doc.pdf",
            },
        )
        mock_tags.return_value = MOCK_TAGS
        mock_corr.return_value = MOCK_CORRESPONDENTS
        mock_dt.return_value = MOCK_DOCUMENT_TYPES
        mock_needs_vision.return_value = False
        mock_get_tag.return_value = 98
        mock_classify.return_value = VALID_CLASSIFICATION_RESPONSE

        main(123, debug=True)

        # Should still classify even though LLM tag is present
        mock_classify.assert_called_once()


# ---------------------------------------------------------------------------
# main — filename and language passthrough
# ---------------------------------------------------------------------------


class TestMainFilenamePassthrough(unittest.TestCase):
    @patch("llm.update_document_content")
    @patch("llm.classify_document")
    @patch("llm.clean_text_with_llm")
    @patch("llm.get_or_create_tag")
    @patch("llm.pdf_needs_vision_ocr")
    @patch("llm.fetch_document_types")
    @patch("llm.fetch_correspondents")
    @patch("llm.fetch_tags")
    @patch("llm.download_document")
    def test_filename_passed_to_classify(
        self,
        mock_download,
        mock_tags,
        mock_corr,
        mock_dt,
        mock_needs_vision,
        mock_get_tag,
        mock_clean,
        mock_classify,
        mock_update,
    ):
        mock_download.return_value = (
            "application/pdf",
            {
                "content": "text content " * 50,
                "tags": [],
                "original_filename": "Chase_2024_03.pdf",
            },
        )
        mock_tags.return_value = MOCK_TAGS
        mock_corr.return_value = MOCK_CORRESPONDENTS
        mock_dt.return_value = MOCK_DOCUMENT_TYPES
        mock_needs_vision.return_value = False
        mock_get_tag.return_value = 98
        mock_clean.side_effect = lambda t: t  # pass-through
        mock_classify.return_value = VALID_CLASSIFICATION_RESPONSE
        mock_update.return_value = True

        main(123)

        call_kwargs = mock_classify.call_args[1]
        self.assertEqual(call_kwargs.get("filename"), "Chase_2024_03.pdf")


if __name__ == "__main__":
    unittest.main()
