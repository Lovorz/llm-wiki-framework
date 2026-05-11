import os
import re
import yaml
from pathlib import Path
from collections import defaultdict

WIKI_DIR = Path('wiki')

def canonical(name):
    # Normalize for comparison
    n = name.replace('-', ' ').replace('_', ' ').lower()
    return re.sub(r'\s+', ' ', n).strip()

def is_uuid(name):
    return bool(re.match(r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$', name) or re.match(r'^[0-9a-f]{8}$', name))

def is_garbage_text(text):
    if not text: return True
    # If it's a long string of PDF stream junk
    if re.search(r'[A-Z]{15,}', text): return True
    if '111111' in text or '000000' in text: return True
    return False

def rebuild():
    files = list(WIKI_DIR.glob('*.md'))
    groups = defaultdict(list)
    
    print(f"Grouping {len(files)} files...")
    for f in files:
        if f.name == 'index.md': continue
        groups[canonical(f.stem)].append(f)
        
    merged_count = 0
    redirects = {}
    
    for canon_name, file_list in groups.items():
        if len(file_list) > 1:
            # Pick master: prefer no-dashes, longer title, non-UUID
            file_list.sort(key=lambda x: (not is_uuid(x.stem), '-' not in x.stem, len(x.stem)), reverse=True)
            master = file_list[0]
            redundant = file_list[1:]
            
            print(f"Canonical [[{canon_name}]] -> Master: [[{master.stem}]]")
            for r in redundant:
                print(f"  - Merging redundant: [[{r.stem}]]")
                redirects[f"[[{r.stem}]]"] = f"[[{master.stem}]]"
                r.unlink()
                merged_count += 1

    # Now handle remaining UUIDs that might have better titles inside
    remaining_files = list(WIKI_DIR.glob('*.md'))
    for f in remaining_files:
        if is_uuid(f.stem):
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                # Look for a title in H1
                match = re.search(r'^# (.*)', content, re.MULTILINE)
                if match:
                    new_title = match.group(1).strip()
                    if not is_uuid(new_title) and len(new_title) > 10 and not is_garbage_text(new_title):
                        # Sanitize
                        safe_title = re.sub(r'[^a-zA-Z0-9\s-]', '', new_title).strip()
                        if safe_title:
                            new_path = WIKI_DIR / f"{safe_title}.md"
                            if not new_path.exists():
                                print(f"Renaming UUID [[{f.stem}]] -> [[{safe_title}]]")
                                redirects[f"[[{f.stem}]]"] = f"[[{safe_title}]]"
                                f.rename(new_path)
                            else:
                                print(f"UUID [[{f.stem}]] is duplicate of [[{safe_title}]], deleting.")
                                redirects[f"[[{f.stem}]]"] = f"[[{safe_title}]]"
                                f.unlink()
            except: pass

    # Global link update
    print("Updating links...")
    final_files = list(WIKI_DIR.glob('*.md'))
    for f in final_files:
        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
            new_content = content
            for old, new in redirects.items():
                new_content = new_content.replace(old, new)
            
            # Remove "Strange Text" lines
            lines = new_content.split('\n')
            clean_lines = []
            for line in lines:
                if not is_garbage_text(line):
                    clean_lines.append(line)
            
            final_content = '\n'.join(clean_lines)
            if final_content != content:
                f.write_text(final_content, encoding='utf-8')
        except: pass

    print(f"Rebuild complete. Merged {merged_count} duplicates.")

if __name__ == '__main__':
    rebuild()
