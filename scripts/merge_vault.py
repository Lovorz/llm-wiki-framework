import os
import re
import yaml
from pathlib import Path
from collections import defaultdict

WIKI_DIR = Path('wiki')

def normalize_title(name):
    # Remove extension
    name = name.replace('.md', '')
    # Replace separators with spaces
    name = name.replace('-', ' ').replace('_', ' ')
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name

def merge_vault():
    files = list(WIKI_DIR.glob('*.md'))
    norm_map = defaultdict(list)
    
    for f in files:
        if f.name == 'index.md': continue
        norm = normalize_title(f.stem)
        # Handle "full" suffix
        norm = norm.replace(' full', '')
        norm_map[norm].append(f)
        
    merged_count = 0
    rename_map = {}
    
    for norm, file_list in norm_map.items():
        if len(file_list) > 1:
            # Pick the best name: prefer one with spaces and proper casing if possible
            # For now, pick the longest one that doesn't have a dash
            file_list.sort(key=lambda x: (' ' in x.stem, len(x.stem)), reverse=True)
            master = file_list[0]
            redundant = file_list[1:]
            
            print(f"Merging into [[{master.stem}]]:")
            for r in redundant:
                print(f"  - [[{r.stem}]]")
                rename_map[f"[[{r.stem}]]"] = f"[[{master.stem}]]"
                
                # Copy claims/entities if master is missing them
                # (Simple append for now)
                try:
                    m_content = master.read_text(encoding='utf-8', errors='ignore')
                    r_content = r.read_text(encoding='utf-8', errors='ignore')
                    
                    if '## Entities' in r_content and '## Entities' not in m_content:
                        master.write_text(m_content + "\n\n" + r_content[r_content.find('## Entities'):], encoding='utf-8')
                except: pass
                
                r.unlink()
                merged_count += 1

    # Update links
    if rename_map:
        print(f"Updating links in remaining files...")
        for f in WIKI_DIR.glob('*.md'):
            if not f.exists(): continue
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                new_content = content
                for old, new in rename_map.items():
                    new_content = new_content.replace(old, new)
                if new_content != content:
                    f.write_text(new_content, encoding='utf-8')
            except: pass
            
    print(f"Merged {merged_count} duplicate files.")

if __name__ == '__main__':
    merge_vault()
