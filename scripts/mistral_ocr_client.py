import os
import sys
import requests
import json
import tempfile
import base64
import re
from pathlib import Path

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise EnvironmentError("MISTRAL_API_KEY environment variable is not set.")
ASSETS_DIR = Path('wiki/assets')

def clean_pdf_content(raw_data):
    start_marker = b'%PDF'
    start = raw_data.find(start_marker)
    if start == -1: return raw_data
    end_marker = b'%%EOF'
    end = raw_data.rfind(end_marker)
    if end == -1: return raw_data[start:]
    return raw_data[start:end+len(end_marker)]

def extract_with_mistral(pdf_path, include_images=False):
    pdf_path = Path(pdf_path)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    safe_pdf_name = pdf_path.stem.replace(' ', '_').replace('.', '_')
    
    try:
        with open(pdf_path, "rb") as f:
            raw_data = f.read()
        pdf_content = clean_pdf_content(raw_data)
        
        headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
        
        # 1. Upload
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(pdf_content)
            tmp.flush()
            tmp.seek(0)
            files = {"file": (pdf_path.name, tmp, "application/pdf")}
            upload_response = requests.post("https://api.mistral.ai/v1/files", headers=headers, files=files, data={"purpose": "ocr"})
            upload_response.raise_for_status()
            file_id = upload_response.json()["id"]

        # 2. Get URL
        signed_url_req = requests.get(f"https://api.mistral.ai/v1/files/{file_id}/url", headers=headers)
        signed_url = signed_url_req.json()["url"]

        # 3. Process with optional image extraction
        ocr_response = requests.post("https://api.mistral.ai/v1/ocr", headers=headers, json={
            "model": "mistral-ocr-latest",
            "document": {"type": "document_url", "document_url": signed_url},
            "include_image_base64": include_images
        })
        ocr_response.raise_for_status()
        ocr_data = ocr_response.json()

        full_markdown = ""
        for page in ocr_data.get("pages", []):
            markdown = page.get("markdown", "")
            
            if include_images:
                images = page.get("images", [])
                for img in images:
                    img_id = img.get("id")
                    img_b64 = img.get("image_base64")
                    if img_id and img_b64:
                        new_img_filename = f"{safe_pdf_name}_{img_id}"
                        img_path = ASSETS_DIR / new_img_filename
                        try:
                            if "," in img_b64: img_b64 = img_b64.split(",")[1]
                            with open(img_path, 'wb') as img_f:
                                img_f.write(base64.b64decode(img_b64))
                            markdown = markdown.replace(f"({img_id})", f"(../wiki/assets/{new_img_filename})")
                        except: pass
            
            full_markdown += markdown + "\n\n"
            
        return full_markdown

    except Exception as e:
        return f"Mistral OCR error: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(extract_with_mistral(sys.argv[1], include_images=False))
