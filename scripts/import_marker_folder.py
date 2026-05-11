import os
import sys
import re
import yaml
import shutil
from pathlib import Path
from datetime import datetime

# Configuration
WIKI_DIR = Path('wiki')
LOG_DIR = Path('log')
ASSETS_DIR = WIKI_DIR / 'assets'
RAW_DIR = Path('raw')

def import_marker_folder(folder_path):
    folder_path = Path(folder_path)
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"Error: Folder {folder_path} not found.")
        return

    # Find the markdown file
    md_files = list(folder_path.glob("*.md"))
    if not md_files:
        print(f"Error: No markdown file found in {folder_path}")
        return
    
    md_file = md_files[0]
    content = md_file.read_text(encoding='utf-8', errors='ignore')

    # Title and base names
    title = folder_path.name.replace('-', ' ').strip()
    pdf_name = folder_path.name + ".pdf"
    
    # Setup Log file path
    log_file_path = LOG_DIR / f"{folder_path.name}.md"

    # Identify and move images
    marker_assets_dir = folder_path / 'assets'
    if marker_assets_dir.exists():
        for img in marker_assets_dir.glob("*"):
            new_img_name = f"{folder_path.name}_{img.name}"
            target_img_path = ASSETS_DIR / new_img_name
            shutil.copy2(img, target_img_path)
            
            # Update links in MD content
            # Marker usually uses: ![alt](assets/filename)
            old_link = f"assets/{img.name}"
            # Relative link from log/ to wiki/assets/
            new_link = f"../wiki/assets/{new_img_name}"
            content = content.replace(old_link, new_link)

    # Prepend Frontmatter
    fm = {
        'title': title,
        'type': 'paper',
        'confidence': 1.0,
        'sources': [f"raw/{pdf_name}"],
        'last_updated': datetime.now().strftime('%Y-%m-%d'),
        'extraction_method': 'marker'
    }
    
    final_content = f"---\n{yaml.dump(fm, sort_keys=False)}---\n"
    # Ensure title is a top-level header if it's not already
    if not content.strip().startswith("# "):
        final_content += f"# {title}\n\n"
    
    final_content += content
    
    log_file_path.write_text(final_content, encoding='utf-8')
    print(f"Imported Marker data for: {title}")
    print(f"Log created: {log_file_path}")
    print(f"Images moved to: {ASSETS_DIR}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        import_marker_folder(sys.argv[1])
    else:
        print("Usage: python scripts/import_marker_folder.py raw/Your-Folder-Name")
