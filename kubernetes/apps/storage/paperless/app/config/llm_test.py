#!/usr/bin/env python
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import requests
import json
import base64
from datetime import datetime
from PIL import Image
import fitz
import numpy as np

# Import the functions from your script (adjust import path as needed)
from llm import (
    encode_image,
    is_pdf_image_only,
    fetch_metadata_list,
    download_document,
    resize_image,
    ocr_document,
    classify_document,
    extract_classification_data,
    update_document_content,
    process_pdf_document,
    process_image_document,
    main
)

class TestDocumentProcessor(unittest.TestCase):
    def setUp(self):
        # Common test data
        self.test_image_path = "test_image.png"
        self.test_pdf_path = "test_document.pdf"
        self.document_id = 123
        self.mock_tags = [{"id": 1, "name": "Invoice"}, {"id": 2, "name": "Receipt"}]
        self.mock_correspondents = [{"id": 1, "name": "ACME Corp"}]
        self.mock_document_types = [{"id": 1, "name": "Financial"}]
        self.default_tags = [111, 112]
        
        # Create a test image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(self.test_image_path)
        
        # Create a test PDF
        doc = fitz.open()
        page = doc.new_page()
        doc.save(self.test_pdf_path)
        doc.close()

    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

    def test_encode_image(self):
        # Test successful encoding
        result = encode_image(self.test_image_path)
        self.assertIsInstance(result, str)
        
        # Test with non-existent file
        with self.assertRaises(Exception):
            encode_image("nonexistent.jpg")

    @patch('fitz.open')
    def test_is_pdf_image_only(self, mock_fitz):
        # Mock a PDF with text
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Some text"
        mock_doc.__iter__.return_value = [mock_page]
        mock_fitz.return_value = mock_doc
        
        self.assertFalse(is_pdf_image_only("dummy.pdf"))
        
        # Mock an image-only PDF
        mock_page.get_text.return_value = ""
        self.assertTrue(is_pdf_image_only("dummy.pdf"))

    @patch('requests.get')
    def test_fetch_metadata_list_success(self, mock_get):
        """Test successful single-page fetch"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": self.mock_tags,
            "next": None
        }
        mock_get.return_value = mock_response
    
        result = fetch_metadata_list("http://test/api/tags/")
        self.assertEqual(len(result), 2)
    
    @patch('requests.get')
    def test_fetch_metadata_list_pagination(self, mock_get):
        """Test multi-page pagination"""
        page1_response = MagicMock()
        page1_response.status_code = 200
        page1_response.json.return_value = {
            "results": self.mock_tags[:1],
            "next": "http://test/api/tags/?page=2"
        }
    
        page2_response = MagicMock()
        page2_response.status_code = 200
        page2_response.json.return_value = {
            "results": self.mock_tags[1:],
            "next": None
        }
    
        mock_get.side_effect = [page1_response, page2_response]
    
        result = fetch_metadata_list("http://test/api/tags/")
        self.assertEqual(len(result), 2)
    
    @patch('requests.get')
    def test_fetch_metadata_list_error(self, mock_get):
        """Test error handling"""
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_get.return_value = error_response
    
        result = fetch_metadata_list("http://test/api/tags/")
        self.assertEqual(len(result), 0)

    @patch('requests.get')
    def test_download_document(self, mock_get):
        # Test successful download
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "content_type": "application/pdf",
            "content": "PDF content",
            "other_data": "value"
        }
    
        # Test HTTP error case
        http_error_response = MagicMock()
        http_error_response.status_code = 404
        http_error_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
    
        # Test JSON decode error case
        json_error_response = MagicMock()
        json_error_response.status_code = 200
        json_error_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    
        # Set up mock to return these responses in sequence
        mock_get.side_effect = [success_response, http_error_response, json_error_response]
    
        # Case 1: Successful download
        content_type, metadata = download_document(self.document_id)
        self.assertEqual(content_type, "application/pdf")
        self.assertEqual(metadata["content"], "PDF content")
    
        # Case 2: HTTP error
        content_type, metadata = download_document(self.document_id)
        self.assertIsNone(content_type)
        self.assertIsNone(metadata)
    
        # Case 3: JSON decode error
        content_type, metadata = download_document(self.document_id)
        self.assertIsNone(content_type)
        self.assertIsNone(metadata)

    @patch('PIL.Image.open')
    def test_resize_image(self, mock_img_open):
        # Mock image operations
        mock_img = MagicMock()
        mock_img.size = (3000, 4000)  # Large image
    
        # Mock the resize and save operations
        mock_img.resize.return_value = mock_img
        mock_img_open.return_value.__enter__.return_value = mock_img
    
        # Test successful resize
        with tempfile.NamedTemporaryFile(suffix='.png') as tmp_file:
            # Mock the save operation to return the original path
            mock_img.save.return_value = None
    
            result = resize_image(tmp_file.name)
            self.assertEqual(result, tmp_file.name)
    
            # Verify resize was called with expected dimensions
            mock_img.resize.assert_called_once()
            new_width, new_height = mock_img.resize.call_args[0][0]
            self.assertTrue(max(new_width, new_height) <= 2048)

    @patch('requests.post')
    @patch('llm.encode_image')
    @patch('llm.resize_image')
    def test_ocr_document_success(self, mock_resize, mock_encode, mock_post):
        """Test successful OCR processing"""
        # Setup mocks
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
    
        # Configure mock response
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "Extracted text"}}]
        }
        mock_post.return_value = success_response
    
        # Execute and verify
        result = ocr_document(self.test_image_path)
        self.assertEqual(result["choices"][0]["message"]["content"], "Extracted text")
    
    @patch('requests.post')
    @patch('llm.encode_image')
    @patch('llm.resize_image')
    @patch('time.sleep', return_value=None)
    def test_ocr_document_rate_limiting_success(self, mock_sleep, mock_resize, mock_encode, mock_post):
        """Test OCR with rate limiting that eventually succeeds"""
        # Setup mocks
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
    
        # Configure mock responses
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}
    
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "Extracted text"}}]
        }
    
        mock_post.side_effect = [rate_limit_response, success_response]
    
        # Execute and verify
        result = ocr_document(self.test_image_path)
        self.assertEqual(result["choices"][0]["message"]["content"], "Extracted text")
        mock_sleep.assert_called_once_with(1)  # Verify retry delay
    
    @patch('requests.post')
    @patch('llm.encode_image')
    @patch('llm.resize_image')
    @patch('time.sleep', return_value=None)
    def test_ocr_document_rate_limiting_failure(self, mock_sleep, mock_resize, mock_encode, mock_post):
        """Test OCR with rate limiting that exceeds max retries"""
        # Setup mocks
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
        
        # Configure mock response
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}
        
        # MAX_RETRIES + 1 calls (initial attempt + MAX_RETRIES retries)
        MAX_RETRIES = 8
        mock_post.side_effect = [rate_limit_response] * (MAX_RETRIES + 1)
        
        # Execute and verify
        result = ocr_document(self.test_image_path)
        self.assertIsNone(result)
        
        # Should sleep MAX_RETRIES times (once per retry)
        self.assertEqual(mock_sleep.call_count, MAX_RETRIES)
        mock_sleep.assert_called_with(1)  # Verify last sleep duration
    
    @patch('llm.encode_image')
    @patch('llm.resize_image')
    def test_ocr_document_debug_mode(self, mock_resize, mock_encode):
        """Test OCR in debug mode returns debug response"""
        # Setup mocks
        mock_resize.return_value = self.test_image_path
        mock_encode.return_value = "base64encoded"
    
        # Expected debug output (complete text)
        expected_text = (
            "Lowes\nHow doers\nget more done.\n\n"
            "00001 66868 03/19/24 11:39 AM\n"
            "SALE CASHIER BRAD\n\n"
            "678885209193 BEHR CAULK <A>\n"
            "BEHR RAPID DRY CAULK 10.1 OZ WHITE\n"
            "$11.96\n\n"
            "079340689695 LOCPROFCON <A>\n"
            "LOCTITE ULTRA LIQ SUPER GLUE .14 OZ\n"
            "$10.36\n\n"
            "730232000126 12MMBIRCH <A>\n"
            "1/2 4X8 BIRCH PLYWOOD\n"
            "$69.58\n\n"
            "SUBTOTAL $91.90\n"
            "SALES TAX $9.42\n"
            "TOTAL $101.32\n"
            "CASH $102.00\n"
            "CHANGE DUE $0.68\n\n"
            "4706 03/19/24 11:39 AM\n"
            "4706 01 66868 03/19/2024 0770\n\n"
            "RETURN POLICY DEFINITIONS\n"
            "POLICY ID DAYS POLICY EXPIRES ON\n"
            "1 90 06/17/2024\n"
            "A\n\n"
            "DID WE NAIL IT?\n\n"
            "Take a short survey for a chance to WIN\n"
            "A $5,000 LOWES GIFT CARD"
        )
    
        # Execute and verify
        result = ocr_document(self.test_image_path, debug=True)
        self.assertEqual(result["choices"][0]["message"]["content"], expected_text)

    @patch('requests.post')
    def test_classify_document(self, mock_post):
        # Test successful classification
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "creation_date": "2023-01-01",
                "tag": ["Invoice"],
                "correspondent": "ACME Corp",
                "document_type": "Financial",
                "title": "Test Document"
            })}}]
        }
        mock_post.return_value = mock_response
        
        result = classify_document(
            image_path=self.test_image_path,
            ocr_text="Document content",
            tags=self.mock_tags,
            correspondents=self.mock_correspondents,
            document_types=self.mock_document_types
        )
        self.assertIsNotNone(result)
        
        # Test text-only classification
        result = classify_document(
            image_path=None,
            ocr_text="Document content",
            tags=self.mock_tags,
            correspondents=self.mock_correspondents,
            document_types=self.mock_document_types
        )
        self.assertIsNotNone(result)

    def test_extract_classification_data(self):
        # Test valid JSON extraction
        test_result = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "creation_date": "2023-01-01",
                        "tag": ["Invoice"],
                        "correspondent": "ACME Corp",
                        "document_type": "Financial",
                        "title": "Test Document"
                    })
                }
            }]
        }
        
        result = extract_classification_data(test_result)
        self.assertEqual(result["title"], "Test Document")
        
        # Test invalid JSON
        test_result["choices"][0]["message"]["content"] = "Invalid JSON"
        result = extract_classification_data(test_result)
        self.assertEqual(result["title"], "")

    @patch('requests.patch')
    def test_update_document_content(self, mock_patch):
        # Test successful update
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_patch.return_value = mock_response
        
        classification_result = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "creation_date": "2023-01-01",
                        "tag": ["Invoice"],
                        "correspondent": "ACME Corp",
                        "document_type": "Financial",
                        "title": "Test Document"
                    })
                }
            }]
        }
        
        success = update_document_content(
            document_id=self.document_id,
            ocr_text="Extracted content",
            classification_result=classification_result,
            tags=self.mock_tags,
            correspondents=self.mock_correspondents,
            document_types=self.mock_document_types
        )
        self.assertTrue(success)
        
        # Test with default tags
        classification_result["choices"][0]["message"]["content"] = json.dumps({
            "creation_date": "",
            "tag": [],
            "correspondent": "",
            "document_type": "",
            "title": ""
        })
        
        success = update_document_content(
            document_id=self.document_id,
            ocr_text="Extracted content",
            classification_result=classification_result,
            tags=self.mock_tags,
            correspondents=self.mock_correspondents,
            document_types=self.mock_document_types
        )
        self.assertTrue(success)

    @patch('llm.ocr_document')
    @patch('llm.classify_document')
    @patch('llm.update_document_content')
    @patch('fitz.open')
    @patch('tempfile.NamedTemporaryFile')
    def test_process_pdf_document(self, mock_tempfile, mock_fitz, mock_update,
                                mock_classify, mock_ocr):
        """Test PDF document processing pipeline with minimal PDF"""
        # Minimal PDF with one empty page (valid PDF structure)
        MINIMAL_PDF = b"""%PDF-1.0
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000114 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
175
%%EOF"""
    
        # Create complete mock structure
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
    
        # Configure document mock
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = [mock_page]  # Critical for iteration
        mock_page.get_pixmap.return_value = mock_pix
        mock_pix.save.return_value = None
        mock_fitz.return_value = mock_doc
    
        # Mock temporary file handling
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/mock_temp.png"
        mock_temp.__enter__.return_value = mock_temp
        mock_tempfile.return_value = mock_temp
    
        # Mock responses
        mock_ocr.return_value = {
            "choices": [{"message": {"content": "Extracted text"}}]
        }
        mock_classify.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "creation_date": "2023-01-01",
                        "tag": ["Invoice"],
                        "correspondent": "ACME Corp",
                        "document_type": "Financial",
                        "title": "Test Document"
                    })
                }
            }]
        }
    
        # Create real PDF file
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp_pdf:
            tmp_pdf.write(MINIMAL_PDF)
            tmp_pdf.flush()
    
            with patch('llm.ENABLE_VISION', True):
                process_pdf_document(
                    pdf_path=tmp_pdf.name,
                    document_id=self.document_id,
                    tags=self.mock_tags,
                    correspondents=self.mock_correspondents,
                    document_types=self.mock_document_types,
                    debug=False
                )
    
        # Verify calls
        mock_fitz.assert_called_once_with(tmp_pdf.name)
        mock_page.get_pixmap.assert_called_once()
        mock_pix.save.assert_called_once_with("/tmp/mock_temp.png")
        mock_ocr.assert_called_once_with("/tmp/mock_temp.png", False)
        mock_classify.assert_called_once()
        mock_update.assert_called_once()

    @patch('llm.ocr_document')
    @patch('llm.classify_document')
    @patch('llm.update_document_content')
    def test_process_image_document(self, mock_update, mock_classify, mock_ocr):
        """Test image document processing pipeline"""
        # Mock responses
        mock_ocr.return_value = {
            "choices": [{"message": {"content": "Extracted text"}}]
        }
        mock_classify.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "creation_date": "2023-01-01",
                        "tag": ["Invoice"],
                        "correspondent": "ACME Corp",
                        "document_type": "Financial",
                        "title": "Test Document"
                    })
                }
            }]
        }
    
        # Create test image
        with tempfile.NamedTemporaryFile(suffix='.png') as tmp_file:
            img = Image.new('RGB', (100, 100), color='red')
            img.save(tmp_file.name)
    
            # Run with vision enabled
            with patch('llm.ENABLE_VISION', True):
                process_image_document(
                    file_content=open(tmp_file.name, 'rb').read(),
                    document_id=self.document_id,
                    tags=self.mock_tags,
                    correspondents=self.mock_correspondents,
                    document_types=self.mock_document_types,
                    debug=False
                )
    
        # Verify pipeline execution
        mock_ocr.assert_called_once()
        mock_classify.assert_called_once()
        mock_update.assert_called_once()

    @patch('llm.download_document')
    @patch('llm.fetch_tags')
    @patch('llm.fetch_correspondents')
    @patch('llm.fetch_document_types')
    @patch('llm.process_pdf_document')
    @patch('llm.is_pdf_image_only')
    @patch('llm.classify_document')
    def test_main_pdf(self, mock_classify, mock_is_pdf, mock_process,
                     mock_fetch_dt, mock_fetch_corr, mock_fetch_tags,
                     mock_download):
        """Test main() with a PDF document"""
        # Mock dependencies
        mock_download.return_value = ("application/pdf", {"content": b"PDF content"})
        mock_fetch_tags.return_value = self.mock_tags
        mock_fetch_corr.return_value = self.mock_correspondents
        mock_fetch_dt.return_value = self.mock_document_types
    
        # Mock PDF check and classification
        mock_is_pdf.return_value = True  # Pretend it's an image PDF
        mock_classify.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "creation_date": "2023-01-01",
                        "tag": ["Invoice"],
                        "correspondent": "ACME Corp",
                        "document_type": "Financial",
                        "title": "Test Document"
                    })
                }
            }]
        }
    
        # Execute with vision enabled
        with patch('llm.ENABLE_VISION', True):
            main(self.document_id)
    
        # Verify
        mock_process.assert_called_once()
        mock_is_pdf.assert_called_once()

    @patch('llm.download_document')
    @patch('llm.fetch_tags')
    @patch('llm.fetch_correspondents')
    @patch('llm.fetch_document_types')
    @patch('llm.process_image_document')
    @patch('llm.classify_document')
    def test_main_image(self, mock_classify, mock_process, mock_fetch_dt,
                       mock_fetch_corr, mock_fetch_tags, mock_download):
        """Test main() with an image document"""
        # Mock document data - use actual image bytes or empty bytes
        mock_image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00...'
    
        # Mock dependencies
        mock_download.return_value = ("image/png", {"content": mock_image_content})
        mock_fetch_tags.return_value = self.mock_tags
        mock_fetch_corr.return_value = self.mock_correspondents
        mock_fetch_dt.return_value = self.mock_document_types
    
        # Mock successful classification
        mock_classify.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "creation_date": "2023-01-01",
                        "tag": ["Invoice"],
                        "correspondent": "ACME Corp",
                        "document_type": "Financial",
                        "title": "Test Document"
                    })
                }
            }]
        }
    
        # Execute
        with patch('llm.ENABLE_VISION', True):
            main(self.document_id)
    
        # Verify
        mock_process.assert_called_once_with(
            mock_image_content, self.document_id,
            self.mock_tags, self.mock_correspondents,
            self.mock_document_types, False
        )

    @patch('llm.download_document')
    def test_main_error_handling(self, mock_download):
        # Test error handling when download fails
        mock_download.return_value = (None, None)
        
        with self.assertLogs(level='ERROR'):
            main(self.document_id)

if __name__ == '__main__':
    unittest.main()
