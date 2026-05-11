import os
import re
import yaml
from pathlib import Path
from collections import defaultdict

WIKI_DIR = Path('wiki')

def clean_text(text):
    # Remove frontmatter
    text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, flags=re.DOTALL)
    # Remove non-alphanumeric but keep spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text

def is_uuid(name):
    return bool(re.match(r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$', name) or re.match(r'^[0-9a-f]{8}$', name))

def dedupe():
    files = list(WIKI_DIR.glob('*.md'))
    hashes = defaultdict(list)
    
    print(f"Analyzing {len(files)} files for duplicates...")
    
    for f in files:
        if f.name == 'index.md': continue
        try:
            # Read with ignore to skip binary garbage
            content = f.read_text(encoding='utf-8', errors='ignore')
            cleaned = clean_text(content)
            
            # Use the first 300 characters as a fingerprint
            fingerprint = cleaned[:300]
            if len(fingerprint) > 50: # Ignore nearly empty files
                hashes[fingerprint].append(f)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    duplicates_found = 0
    rename_map = {}
    
    for fingerprint, file_list in hashes.items():
        if len(file_list) > 1:
            duplicates_found += 1
            file_list.sort(key=lambda x: (is_uuid(x.stem), -len(x.stem)))
            
            master = file_list[0]
            redundant = file_list[1:]
            
            print(f"\nDuplicate group found. Master: [[{master.stem}]]")
            for r in redundant:
                print(f"  - Redundant: [[{r.stem}]]")
                rename_map[f"[[{r.stem}]]"] = f"[[{master.stem}]]"
                
                try:
                    c = r.read_text(encoding='utf-8', errors='ignore')
                    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', c, re.DOTALL)
                    if match:
                        fm = yaml.safe_load(match.group(1)) or {}
                        fm['stale'] = True
                        fm['supersedes'] = [f"[[{master.stem}]]"]
                        new_c = f"---\n{yaml.dump(fm, sort_keys=False)}---\n\n# STALE: {r.stem}\n\nThis page is a duplicate and has been superseded by [[{master.stem}]].\n"
                        r.write_text(new_c, encoding='utf-8')
                    else:
                        r.unlink()
                except:
                    r.unlink()

    if rename_map:
        print(f"\nUpdating links in {len(files)} files...")
        for f in files:
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                new_content = content
                for old_link, new_link in rename_map.items():
                    new_content = new_content.replace(old_link, new_link)
                
                if new_content != content:
                    f.write_text(new_content, encoding='utf-8')
            except: pass

    print(f"\nProcessed {duplicates_found} duplicate groups.")

if __name__ == '__main__':
    dedupe()
