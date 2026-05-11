import sys
import requests
import os
import base64
import json
from pathlib import Path

MARKER_ENDPOINT = "http://192.168.134.133:8080/convert"
ASSETS_DIR = Path('wiki/assets')

def extract_with_marker(pdf_path):
    """Sends PDF to Marker-API and returns markdown content with saved images."""
    pdf_path = Path(pdf_path)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'pdf_file': (pdf_path.name, f, 'application/pdf')}
            print(f"Sending {pdf_path.name} to Marker-API...")
            response = requests.post(MARKER_ENDPOINT, files=files, timeout=600)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'Success' and 'result' in data:
                    result = data['result']
                    markdown = result.get('markdown', '')
                    images = result.get('images', {})
                    
                    # Process and save images
                    for img_name, img_b64 in images.items():
                        # Standardize image name: PDFName_OriginalName
                        safe_pdf_name = pdf_path.stem.replace(' ', '_')
                        new_img_name = f"{safe_pdf_name}_{img_name}"
                        img_path = ASSETS_DIR / new_img_name
                        
                        try:
                            img_data = base64.b64decode(img_b64)
                            with open(img_path, 'wb') as img_f:
                                img_f.write(img_data)
                            
                            # Update markdown links
                            # Marker usually uses: ![](img_name) or ![...](img_name)
                            # We replace the local filename with the relative path to our assets
                            old_link = f"({img_name})"
                            new_link = f"(../wiki/assets/{new_img_name})"
                            markdown = markdown.replace(old_link, new_link)
                            
                        except Exception as e:
                            print(f"Warning: Failed to save image {img_name}: {e}")
                            
                    return markdown
                else:
                    return f"Error: API returned unsuccessful status: {data.get('status')}"
            else:
                return f"Error from Marker-API (Status {response.status_code}): {response.text}"
    except Exception as e:
        return f"Marker-API connection failed: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = extract_with_marker(sys.argv[1])
        print(result)
