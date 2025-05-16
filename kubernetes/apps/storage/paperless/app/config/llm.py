#!/usr/bin/env python
import random
import time
from dateutil import parser
from datetime import datetime
import re
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

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
PAPERLESS_HOST = os.getenv('PAPERLESS_HOST', 'http://paperless.storage.svc.cluster.local:80/api')
#PAPERLESS_HOST = os.getenv('PAPERLESS_HOST', 'http://192.168.5.217/api')
PAPERLESS_API_KEY = os.getenv('PAPERLESS_APIKEY')
OPENAI_API_ENDPOINT = os.getenv('OPENAI_API_ENDPOINT', 'https://ai.thekao.cloud')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Model Configuration
ENABLE_VISION = os.getenv('ENABLE_VISION', 'false').lower() == 'true'
VISION_MODEL = os.getenv('VISION_MODEL', 'qwen2.5-vl-7b')
VISION_MODEL_TOKENS_MAX = int(os.getenv('VISION_MODEL_TOKENS_MAX', 32000))
TEXT_MODEL = os.getenv('TEXT_MODEL', 'default')
TEXT_MODEL_TOKENS_MAX = int(os.getenv('TEXT_MODEL_TOKENS_MAX', 40960))
MAX_RETURN_TOKENS = int(os.getenv('MAX_RETURN_TOKENS', 8192))
DEFAULT_TAGS = list(map(int, os.getenv('DEFAULT_TAGS', '111,112').split(',')))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 8))
INITIAL_RETRY_WAIT = int(os.getenv('INITIAL_RETRY_WAIT', 5))

# Validate configuration
def validate_config():
    """Validate required configuration with detailed error messages."""
    missing_vars = []
    
    if not PAPERLESS_API_KEY:
        missing_vars.append("PAPERLESS_APIKEY")
    
    if not OPENAI_API_KEY:
        missing_vars.append("OPENAI_API_KEY")
    
    if missing_vars:
        error_msg = (
            "Missing required environment variables:\n"
            f"- {', '.join(missing_vars)}\n\n"
            "Configuration check failed. Please ensure these variables are set:\n"
            "1. For Paperless API access:\n"
            "   - PAPERLESS_APIKEY: Your Paperless-ngx API token\n"
            "   - PAPERLESS_HOST: Paperless API endpoint (default: http://192.168.5.217/api)\n\n"
            "2. For OpenAI/LocalAI access:\n"
            "   - OPENAI_API_KEY: Your API key\n"
            "   - OPENAI_API_ENDPOINT: API endpoint (default: https://ai.thekao.cloud)\n\n"
            "These can be set in:\n"
            "- The Paperless-ngx admin interface (for post-consume scripts)\n"
            "- Your container environment variables\n"
            "- The .env file for local development"
        )
        logger.error(error_msg)
        if __name__ == "__main__":
            sys.exit(1)
        return False
    
    # Additional validation for API endpoints
    if not PAPERLESS_HOST.startswith(('http://', 'https://')):
        logger.error(f"Invalid PAPERLESS_HOST format: {PAPERLESS_HOST}\n"
                    "Must start with http:// or https://")
        if __name__ == "__main__":
            sys.exit(1)
        return False
    
    return True

def encode_image(image_path: str) -> str:
    """Encode image file to base64 string."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        raise

def is_pdf_image_only(pdf_path: str) -> bool:
    """Check if PDF contains only images (no text)."""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            if page.get_text("text"):
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking if PDF is image-only: {e}")
        return False

def fetch_metadata_list(url: str) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Token {PAPERLESS_API_KEY}"}
    all_data = []

    while url:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raises HTTPError for bad status codes

            try:
                data = response.json()
                results = data.get('results', data) if isinstance(data, dict) else data
                all_data.extend(results)
                url = data.get('next', None)
            except ValueError as e:
                logger.error(f"Failed to parse JSON from {url}: {e}")
                break

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch metadata from {url}: {e}")
            break

    return all_data

def fetch_tags() -> List[Dict[str, Any]]:
    """Fetch all tags from Paperless."""
    return fetch_metadata_list(f'{PAPERLESS_HOST}/tags/')

def fetch_correspondents() -> List[Dict[str, Any]]:
    """Fetch all correspondents from Paperless."""
    return fetch_metadata_list(f'{PAPERLESS_HOST}/correspondents/')

def fetch_document_types() -> List[Dict[str, Any]]:
    """Fetch all document types from Paperless."""
    return fetch_metadata_list(f'{PAPERLESS_HOST}/document_types/')

def download_document(document_id: int) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Download document metadata from Paperless."""
    url = f'{PAPERLESS_HOST}/documents/{document_id}/'
    headers = {"Authorization": f"Token {PAPERLESS_API_KEY}"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses

        try:
            data = response.json()
            return data.get('content_type', ''), data
        except ValueError as e:  # catches JSONDecodeError (subclass of ValueError)
            logger.error(f"Failed to parse JSON response: {e}")
            return None, None

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download document: {e}")
        return None, None

def resize_image(image_path: str, max_length: int = 2048) -> Optional[str]:
    """Resize image to reduce processing load."""
    try:
        with Image.open(image_path) as img:
            ratio = max_length / max(img.size)
            new_size = tuple([int(x * ratio) for x in img.size])
            resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
            resized_img.save(image_path)
        return image_path
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return None

def ocr_document(image_path: str, debug: bool = False) -> Optional[Dict[str, Any]]:
    """Perform OCR on an image document using vision model.

    Args:
        image_path: Path to the image file to process
        debug: Whether to return debug data instead of making API call

    Returns:
        Dictionary with OCR results or None if processing failed
    """
    # Debug mode returns sample data
    if debug:
        return {
            'id': 'chatcmpl-95RcNLqoVk9gY6qaUZDddAZh8JdeK',
            'object': 'chat.completion',
            'created': 1711084831,
            'model': 'gpt-4-1106-vision-preview',
            'choices': [{
                'message': {
                    'content': (
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
                },
                'finish_reason': 'length'
            }],
            'usage': {
                'prompt_tokens': 1475,
                'completion_tokens': 300,
                'total_tokens': 1775
            },
            'system_fingerprint': None
        }

    retry_wait = INITIAL_RETRY_WAIT

    for attempt in range(MAX_RETRIES + 1):  # Initial attempt + MAX_RETRIES retries
        try:
            # 1. Resize image to reduce processing load
            resized_image_path = resize_image(image_path)
            if not resized_image_path:
                logger.error("Failed to resize image")
                return None

            # 2. Encode image to base64
            base64_image = encode_image(resized_image_path)

            # 3. Prepare API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }

            # BNF grammar for strict JSON output
            bnf_grammar = """
            root ::= "{" ws creation_date ws "," ws tag ws "," ws correspondent ws "," ws document_type ws "," ws title ws "}"
            creation_date ::= "\"creation_date\" : " ws string
            tag ::= "\"tag\" : " ws "[" ws (string (ws "," ws string)* ws "]"
            correspondent ::= "\"correspondent\" : " ws string
            document_type ::= "\"document_type\" : " ws string
            title ::= "\"title\" : " ws string
            string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
            ws ::= [ \t\n]*
            """

            payload = {
                "model": VISION_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Only provide the OCR text from this image. "
                                   "Do not provide any additional commentary or "
                                   "text that is not in the image. Do not include backticks (```) only the raw json"
                                   "Your response MUST follow this BNF grammar: \n" + bnf_grammar + "\n\n"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }],
                "max_tokens": MAX_RETURN_TOKENS
            }

            # 4. Make API request
            response = requests.post(
                f"{OPENAI_API_ENDPOINT}/v1/chat/completions",
                headers=headers,
                json=payload
            )

            # 5. Handle response
            if response.status_code == 200:
                return response.json()

            elif response.status_code == 429:
                # Rate limited - implement exponential backoff
                if attempt < MAX_RETRIES:
                    retry_after = int(response.headers.get("Retry-After", retry_wait))
                    time.sleep(retry_after)
                    retry_wait = min(retry_wait * 2, 60)  # Cap at 60 seconds
                    continue

            logger.error(
                f"OCR request failed with status {response.status_code}: "
                f"{response.text}"
            )
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error during OCR request (attempt {attempt + 1}): {e}")
            if attempt == MAX_RETRIES:
                break
            time.sleep(retry_wait)
            retry_wait = min(retry_wait * 2, 60)  # Cap at 60 seconds

        except Exception as e:
            logger.error(f"Unexpected error during OCR: {e}")
            return None

    logger.error(f"Max retries ({MAX_RETRIES}) exceeded for OCR document request")
    return None

def classify_document(image_path: Optional[str] = None, 
                     ocr_text: Optional[str] = None, 
                     tags: Optional[List[Dict[str, Any]]] = None, 
                     correspondents: Optional[List[Dict[str, Any]]] = None, 
                     document_types: Optional[List[Dict[str, Any]]] = None, 
                     debug: bool = False) -> Optional[Dict[str, Any]]:
    """Classify document using AI model with strict JSON output enforcement."""
    if not ocr_text or not tags or not correspondents or not document_types:
        logger.error("Missing required parameters for classification")
        return None

    # BNF grammar for strict JSON output
    bnf_grammar = """
    root ::= "{" ws creation_date ws "," ws tag ws "," ws correspondent ws "," ws document_type ws "," ws title ws "}"
    creation_date ::= "\"creation_date\" : " ws string
    tag ::= "\"tag\" : " ws "[" ws (string (ws "," ws string)* ws "]"
    correspondent ::= "\"correspondent\" : " ws string
    document_type ::= "\"document_type\" : " ws string
    title ::= "\"title\" : " ws string
    string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
    ws ::= [ \t\n]*
    """

    retry_wait = INITIAL_RETRY_WAIT
    
    for attempt in range(MAX_RETRIES):
        try:
            if image_path:
                resized_image_path = resize_image(image_path)
                if not resized_image_path:
                    return None
                base64_image = encode_image(resized_image_path)
                model_to_use = VISION_MODEL
                max_context_tokens = VISION_MODEL_TOKENS_MAX
            else:
                base64_image = None
                model_to_use = TEXT_MODEL
                max_context_tokens = TEXT_MODEL_TOKENS_MAX

            tags_str = ", ".join([f"'{tag['name']}'" for tag in tags])
            correspondents_str = ", ".join([f"'{correspondent['name']}'" for correspondent in correspondents])
            document_types_str = ", ".join([f"'{doc_type['name']}'" for doc_type in document_types])

            base_prompt = (
                "Analyze the document and provide classification in EXACTLY this JSON format:\n"
                "{\n"
                "  \"creation_date\": \"YYYY-MM-DD\",\n"
                "  \"tag\": [\"tag1\", \"tag2\"],\n"
                "  \"correspondent\": \"correspondent_name\",\n"
                "  \"document_type\": \"document_type_name\",\n"
                "  \"title\": \"document_title\"\n"
                "}\n\n"
                "Rules:\n"
                "1. Use only values from the provided options\n"
                "2. If no match, use empty string or empty array\n"
                "3. Strictly follow this BNF grammar:\n" + bnf_grammar + "\n"
                "4. Do not include backticks (```), ONLY provide the raw JSON\n\n"
                "Options:\n"
                f"Tags: {tags_str}\n"
                f"Correspondents: {correspondents_str}\n"
                f"Document types: {document_types_str}\n\n"
                "Document content:\n"
            )

            # Token-aware truncation
            combined_text = ocr_text + "\n\n" + base_prompt
            if len(combined_text) > max_context_tokens:
                truncate_length = max_context_tokens - len(base_prompt) - 10
                truncated_ocr_text = ocr_text[:truncate_length]
            else:
                truncated_ocr_text = ocr_text

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }

            payload = {
                "model": model_to_use,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": base_prompt + truncated_ocr_text
                            }
                        ]
                    }
                ],
                "max_tokens": MAX_RETURN_TOKENS,
                "response_format": {"type": "json_object"}
            }

            if base64_image:
                payload["messages"][0]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })

            api_endpoint = f"{OPENAI_API_ENDPOINT}/v1/chat/completions"
            response = requests.post(api_endpoint, headers=headers, json=payload)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", retry_wait))
                time_to_wait = max(retry_wait, retry_after)
                logger.warning(f"Rate limit exceeded. Retrying in {time_to_wait} seconds...")
                time.sleep(time_to_wait)
                retry_wait = min(retry_wait * 2, 60)
                continue
            else:
                logger.error(f"Classification failed with status {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Classification request error: {e}")
            return None
            
    logger.error("Max retries exceeded for classification request")
    return None

def extract_classification_data(classification_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and validate classification data from API response."""
    required_keys = ['creation_date', 'tag', 'correspondent', 'document_type', 'title']

    try:
        content = classification_result['choices'][0]['message']['content']
        json_data = json.loads(content)

        # Ensure all required keys are present
        for key in required_keys:
            if key not in json_data:
                json_data[key] = [] if key == 'tag' else ''
        return json_data

    except json.JSONDecodeError as e:
        logger.error(f"{content}")
        logger.error(f"Invalid JSON response: {e}")
        return {key: [] if key == 'tag' else '' for key in required_keys}
    except Exception as e:
        logger.error(f"Error extracting classification: {e}")
        return {key: [] if key == 'tag' else '' for key in required_keys}

def update_document_content(document_id: int, 
                          ocr_text: str, 
                          classification_result: Dict[str, Any], 
                          tags: List[Dict[str, Any]], 
                          correspondents: List[Dict[str, Any]], 
                          document_types: List[Dict[str, Any]]) -> bool:
    """Update document in Paperless with classification results."""
    classification_data = extract_classification_data(classification_result)
    if not classification_data:
        logger.error("No valid classification data to update")
        return False

    # Find IDs for metadata
    tag_ids = []
    for tag_name in classification_data['tag']:
        tag_id = next((tag['id'] for tag in tags if tag['name'] == tag_name), None)
        if tag_id:
            tag_ids.append(tag_id)
    
    # Add default tags if not already present
    for default_tag in DEFAULT_TAGS:
        if default_tag not in tag_ids:
            tag_ids.append(default_tag)

    correspondent_id = next(
        (correspondent['id'] for correspondent in correspondents 
         if correspondent['name'] == classification_data['correspondent']), 
        None
    )
    
    document_type_id = next(
        (doc_type['id'] for doc_type in document_types 
         if doc_type['name'] == classification_data['document_type']), 
        None
    )

    # Parse creation date
    creation_date = classification_data.get('creation_date', '')
    iso_date = ''
    if creation_date:
        try:
            parsed_date = parser.parse(creation_date)
            iso_date = parsed_date.strftime("%Y-%m-%dT00:00:00Z")
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")

    # Prepare payload
    payload = {
        "created": iso_date,
        "tags": tag_ids,
        "correspondent": correspondent_id,
        "document_type": document_type_id,
        "title": classification_data['title']
    }

    # Only add content if OCR was successful
    if not any(phrase in ocr_text.lower() for phrase in ["i can't assist", "i'm sorry"]):
        payload["content"] = ocr_text

    # Clean empty values
    payload = {k: v for k, v in payload.items() if v not in (None, '', [])}

    url = f'{PAPERLESS_HOST}/documents/{document_id}/'
    headers = {
        "Authorization": f"Token {PAPERLESS_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Successfully updated document {document_id}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to update document {document_id}: {str(e)}")
        return False

def process_pdf_document(
    pdf_path: str,  # Changed from tmp_file_path to pdf_path
    document_id: int,
    tags: List[Dict[str, Any]],
    correspondents: List[Dict[str, Any]],
    document_types: List[Dict[str, Any]],
    debug: bool = False
) -> None:
    """Process a PDF document through OCR pipeline.

    Args:
        pdf_path: Path to the PDF file
        document_id: ID of the document being processed
        tags: Available tags for classification
        correspondents: Available correspondents
        document_types: Available document types
        debug: Whether to run in debug mode
    """
    if not ENABLE_VISION:
        logger.warning("Vision processing disabled - skipping PDF")
        return

    try:
        aggregated_ocr_text = []
        classification_result = None

        with fitz.open(pdf_path) as doc:
            for page_number in range(len(doc)):
                page = doc.load_page(page_number)
                pix = page.get_pixmap()

                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as img_file:
                    img_path = img_file.name
                    try:
                        pix.save(img_path)

                        # Perform OCR on page image
                        ocr_result = ocr_document(img_path, debug)
                        if ocr_result:
                            ocr_text = ocr_result['choices'][0]['message']['content']
                            aggregated_ocr_text.append(ocr_text)

                            # Classify based on first page only
                            if page_number == 0:
                                classification_result = classify_document(
                                    img_path,
                                    ocr_text,
                                    tags,
                                    correspondents,
                                    document_types,
                                    debug
                                )
                    finally:
                        try:
                            os.unlink(img_path)
                        except OSError as e:
                            logger.error(f"Error deleting temp image file: {e}")

        # Update document with full OCR text if we have results
        if aggregated_ocr_text and classification_result:
            full_ocr_text = "\n".join(aggregated_ocr_text)
            update_document_content(
                document_id,
                full_ocr_text,
                classification_result,
                tags,
                correspondents,
                document_types
            )

    except Exception as e:
        logger.error(f"Error processing PDF document: {e}")
        raise

def process_image_document(
    file_content: bytes,
    document_id: int,
    tags: List[Dict[str, Any]],
    correspondents: List[Dict[str, Any]],
    document_types: List[Dict[str, Any]],
    debug: bool = False
) -> None:
    """Process an image document (JPEG/PNG) through OCR pipeline.

    Args:
        file_content: Raw bytes of the image file
        document_id: ID of the document being processed
        tags: Available tags for classification
        correspondents: Available correspondents
        document_types: Available document types
        debug: Whether to run in debug mode
    """
    if not ENABLE_VISION:
        logger.warning("Vision processing disabled - skipping image document")
        return

    try:
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            try:
                # Write image content
                tmp_file.write(file_content)
                tmp_file.flush()

                # Perform OCR
                ocr_result = ocr_document(tmp_path, debug)
                if not ocr_result:
                    logger.error("OCR processing failed")
                    return

                # Extract OCR text
                ocr_text = ocr_result['choices'][0]['message']['content']

                # Classify document
                classification_result = classify_document(
                    tmp_path,  # Pass image path for potential visual analysis
                    ocr_text,
                    tags,
                    correspondents,
                    document_types,
                    debug
                )

                if classification_result:
                    update_document_content(
                        document_id,
                        ocr_text,
                        classification_result,
                        tags,
                        correspondents,
                        document_types
                    )

            finally:
                try:
                    os.unlink(tmp_path)
                except OSError as e:
                    logger.error(f"Error deleting temp file {tmp_path}: {e}")

    except Exception as e:
        logger.error(f"Error processing image document: {e}")
        raise

def main(document_id: int, debug: bool = False) -> None:
    """Main document processing pipeline."""
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.info("Running in debug mode")

    try:
        # 1. Fetch metadata
        logger.info("Fetching document metadata...")
        tags = fetch_tags()
        correspondents = fetch_correspondents()
        document_types = fetch_document_types()

        # 2. Download document
        logger.info(f"Downloading document {document_id}...")
        content_type, document_metadata = download_document(document_id)
        if not document_metadata:
            logger.error("Failed to download document metadata")
            return

        # 3. Prepare content
        raw_content = document_metadata.get('content', b'')
        file_content = raw_content if isinstance(raw_content, bytes) else raw_content.encode('utf-8')

        # 4. Process based on content type
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
            try:
                tmp_file.write(file_content)
                tmp_file.flush()

                if content_type == 'application/pdf':
                    _handle_pdf(
                        tmp_path, document_id,
                        tags, correspondents, document_types,
                        document_metadata, debug
                    )
                elif content_type in ['image/jpeg', 'image/png']:
                    _handle_image(
                        file_content, document_id,
                        tags, correspondents, document_types,
                        debug
                    )
                else:
                    _handle_text(
                        document_metadata, document_id,
                        tags, correspondents, document_types,
                        debug
                    )

            except Exception as e:
                logger.error(f"Document processing failed: {str(e)}")
                raise
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError as e:
                    logger.warning(f"Could not delete temp file: {str(e)}")

    except Exception as e:
        logger.error(f"Fatal error in document pipeline: {str(e)}")
        raise

    logger.info("Document processing completed successfully")


def _handle_pdf(pdf_path: str, doc_id: int,
               tags: list, correspondents: list, doc_types: list,
               metadata: dict, debug: bool):
    """Process PDF documents."""
    try:
        is_image_only = is_pdf_image_only(pdf_path)
    except Exception as e:
        logger.error(f"PDF analysis failed: {str(e)}")
        is_image_only = False

    if is_image_only and ENABLE_VISION:
        logger.info("Processing image-only PDF...")
        process_pdf_document(
            pdf_path, doc_id,
            tags, correspondents, doc_types,
            debug
        )
    else:
        logger.info("Processing text PDF...")
        text_content = metadata.get('content', '')
        if isinstance(text_content, bytes):
            text_content = text_content.decode('utf-8', errors='replace')

        classification_result = classify_document(
            None, text_content,
            tags, correspondents, doc_types,
            debug
        )

        if classification_result:
            update_document_content(
                doc_id, text_content,
                classification_result,
                tags, correspondents,
                doc_types
            )


def _handle_image(image_data: bytes, doc_id: int,
                 tags: list, correspondents: list, doc_types: list,
                 debug: bool):
    """Process image documents."""
    if not ENABLE_VISION:
        logger.warning("Vision processing disabled - skipping image")
        return

    logger.info("Processing image document...")
    process_image_document(
        image_data, doc_id,
        tags, correspondents, doc_types,
        debug
    )


def _handle_text(metadata: dict, doc_id: int,
                tags: list, correspondents: list, doc_types: list,
                debug: bool):
    """Process text documents."""
    logger.info("Processing text document...")
    text_content = metadata.get('content', '')
    if isinstance(text_content, bytes):
        text_content = text_content.decode('utf-8', errors='replace')

    classification_result = classify_document(
        None, text_content,
        tags, correspondents, doc_types,
        debug
    )

    if classification_result:
        update_document_content(
            doc_id, text_content,
            classification_result,
            tags, correspondents,
            doc_types
        )

if __name__ == "__main__":
    try:
        if not validate_config():
            sys.exit(1)
        
        # Get document ID from command line or environment
        document_id = None
        if len(sys.argv) > 1:
            document_id = sys.argv[1]
        else:
            document_id = os.getenv('DOCUMENT_ID')

        if not document_id:
            logger.error(
                "No document ID provided\n\n"
                "Usage:\n"
                "  ./llm.py <document_id>\n"
                "Or set DOCUMENT_ID environment variable\n\n"
                "When run from Paperless-ngx as a post-consume script,\n"
                "the document ID is automatically passed as the first argument."
            )
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Initialization failed: {str(e)}")
        sys.exit(1)

    debug_flag = '--debug' in sys.argv
    main(document_id, debug_flag)
