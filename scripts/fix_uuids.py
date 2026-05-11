import os
import re
import yaml
from pathlib import Path

WIKI_DIR = Path('wiki')

def is_uuid(name):
    return bool(re.match(r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$', name) or re.match(r'^[0-9a-f]{8}$', name))

def extract_title(content):
    # Skip frontmatter
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
    
    # Try to find common patterns in academic papers
    # Pattern 1: Journal info + Title
    # Example: "Applied Surface Science 407 (2017) 177-184 ... Full Length Article ... [Title]"
    match = re.search(r'(?:Full Length Article|Review Article|Communication)\s*(.*?)\n', body, re.IGNORECASE | re.DOTALL)
    if match:
        potential = match.group(1).strip()
        if len(potential) > 15 and len(potential) < 200:
            return potential

    # Pattern 2: Lines after a journal name
    journals = ['Applied Surface Science', 'Nature', 'Science', 'Advanced Materials', 'ACS Nano', 'Journal of Power Sources', 'Electrochimica Acta', 'Energy Storage Materials']
    for j in journals:
        if j.lower() in body.lower():
            # Find the journal mention and look for the next prominent line
            start = body.lower().find(j.lower())
            after_j = body[start + len(j):start + 500]
            # Look for a line that looks like a title (not too short, not just numbers)
            lines = after_j.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) > 30 and not any(kw in line.lower() for kw in ['contents lists', 'homepage', 'elsevier', 'doi:', 'http']):
                    return line

    # Pattern 3: Just look for the first non-header, non-marker line
    lines = body.split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or 'Abstract' in line or 'Extraction' in line or is_uuid(line.replace(' ', '')):
            continue
        if len(line) > 40:
            return line
            
    return None

def rename_uuids():
    files = list(WIKI_DIR.glob('*.md'))
    renamed = 0
    
    for f in files:
        if is_uuid(f.stem):
            content = f.read_text(encoding='utf-8', errors='ignore')
            new_title = extract_title(content)
            
            if new_title:
                # Sanitize title for filename
                new_title = re.sub(r'[^a-zA-Z0-9\s-]', '', new_title).strip()
                # Limit length
                if len(new_title) > 80:
                    new_title = new_title[:80].rsplit(' ', 1)[0]
                
                if not new_title: continue
                
                new_path = WIKI_DIR / f"{new_title}.md"
                
                # Check for existing
                if new_path.exists():
                    print(f"Skipping [[{f.stem}]] -> [[{new_title}]] (already exists)")
                    # This is likely a duplicate, we could delete it but let's be careful
                    continue
                
                print(f"Renaming [[{f.stem}]] -> [[{new_title}]]")
                
                # Update content title and metadata
                new_content = content.replace(f"title: {f.stem}", f"title: \"{new_title}\"")
                new_content = re.sub(rf'^# {f.stem}', f'# {new_title}', new_content, flags=re.MULTILINE)
                
                f.rename(new_path)
                new_path.write_text(new_content, encoding='utf-8')
                
                # Update links in other files
                for other_f in files:
                    if other_f.exists():
                        try:
                            c = other_f.read_text(encoding='utf-8', errors='ignore')
                            nc = c.replace(f"[[{f.stem}]]", f"[[{new_title}]]")
                            if nc != c:
                                other_f.write_text(nc, encoding='utf-8')
                        except: pass
                renamed += 1
                
    print(f"Renamed {renamed} UUID files.")

if __name__ == '__main__':
    rename_uuids()
