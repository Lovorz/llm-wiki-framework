import os
import re
import json

WIKI_DIR = "/mnt/d/Google Drive/Document-literature/Boon-tiny-brain-01/wiki/"
DATE = "2026-04-13"

def migrate_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    filename = os.path.basename(file_path)
    title_from_filename = os.path.splitext(filename)[0]

    # Extract frontmatter
    frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if frontmatter_match:
        fm_text = frontmatter_match.group(1)
        body = content[frontmatter_match.end():]
        
        fm = {}
        for line in fm_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                fm[key.strip()] = value.strip()
    else:
        fm = {}
        body = content

    # 1. Update/Add YAML frontmatter
    # title: Use the filename (no .md) as the title, wrapped in double quotes.
    fm['title'] = f'"{title_from_filename}"'

    # type: Map existing types to "paper", "concept", "experiment", or "entity".
    curr_type = fm.get('type', '').lower().strip('"')
    if curr_type in ['research_paper', 'paper']:
        fm['type'] = 'paper'
    elif curr_type in ['conceptual', 'concept']:
        fm['type'] = 'concept'
    elif curr_type in ['experiment']:
        fm['type'] = 'experiment'
    elif curr_type in ['entity']:
        fm['type'] = 'entity'
    else:
        # Heuristic for type
        if len(title_from_filename.split()) > 5:
            fm['type'] = 'paper'
        else:
            fm['type'] = 'concept'

    # confidence: Map labels (high/medium/low) to 1.0, 0.7, 0.4. Default to 0.9 if missing.
    curr_conf = fm.get('confidence', '').lower().strip('"')
    if curr_conf == 'high' or curr_conf == '1.0':
        fm['confidence'] = '1.0'
    elif curr_conf == 'medium' or curr_conf == '0.7':
        fm['confidence'] = '0.7'
    elif curr_conf == 'low' or curr_conf == '0.4':
        fm['confidence'] = '0.4'
    else:
        fm['confidence'] = fm.get('confidence', '0.9')

    # sources: Convert [[raw/UUID.pdf]] list to JSON-style list ["raw/UUID.pdf"].
    sources_text = fm.get('sources', '')
    sources = re.findall(r'\[\[(raw/.*?)\]\]', sources_text)
    if not sources and sources_text.startswith('[') and sources_text.endswith(']'):
        # Already JSON-ish?
        pass
    elif sources:
        fm['sources'] = json.dumps(sources)
    else:
        # Keep as is or default to empty list if it was something else
        if 'sources' not in fm:
            fm['sources'] = '[]'

    # stale: Ensure it is present (default false).
    fm['stale'] = fm.get('stale', 'false')

    # last_updated: Set to 2026-04-13.
    fm['last_updated'] = DATE

    # Reconstruct frontmatter
    new_fm_lines = ["---"]
    # Order them as requested/standard
    for key in ['title', 'type', 'confidence', 'sources', 'stale', 'last_updated']:
        if key in fm:
            new_fm_lines.append(f"{key}: {fm[key]}")
    # Add any other keys
    for key in fm:
        if key not in ['title', 'type', 'confidence', 'sources', 'stale', 'last_updated']:
            new_fm_lines.append(f"{key}: {fm[key]}")
    new_fm_lines.append("---")
    new_fm_text = "\n".join(new_fm_lines)

    # 3. Migrate internal links
    # Convert [[Page]] to [[Page|related]] if in a "Related" or "References" section.
    # Convert [[Page]] to [[Page|mentions]] if in the general text.
    
    sections = re.split(r'(\n#+ .*)', body)
    new_body_parts = []
    in_related_section = False
    
    for part in sections:
        if part.startswith('\n#') or part.startswith('#'):
            header_text = part.lower()
            if 'related' in header_text or 'references' in header_text:
                in_related_section = True
            else:
                in_related_section = False
            new_body_parts.append(part)
        else:
            rel_type = 'related' if in_related_section else 'mentions'
            # Replace [[Page]] with [[Page|rel_type]]
            # Avoid replacing already typed links [[Page|type]]
            new_part = re.sub(r'\[\[([^|\]]+)\]\]', rf'[[\1|{rel_type}]]', part)
            new_body_parts.append(new_part)
            
    new_body = "".join(new_body_parts)
    
    return new_fm_text + "\n" + new_body

def main():
    files = [f for f in os.listdir(WIKI_DIR) if f.endswith('.md')]
    
    # Deduplication special cases
    # 1. Independent gradient model...
    igm_dash = "Independent gradient model based on Hirshfeld partition - A new method for visual study of interactions in chemical systems.md"
    igm_no_dash = "Independent gradient model based on Hirshfeld partition A new method for visual study of interactions in chemical systems.md"
    
    # 2. ZnO MoX2...
    zno_dash = "ZnO-MoX2 (X = S, Se) composites used for visible light photocatalysis.md"
    zno_no_dash = "ZnO MoX2 (X = S, Se) composites used for visible light photocatalysis.md"
    
    to_delete = []
    
    if igm_dash in files and igm_no_dash in files:
        # Merge if possible, then delete no_dash
        to_delete.append(igm_no_dash)
    
    if zno_dash in files and zno_no_dash in files:
        # Merge if possible, then delete no_dash
        to_delete.append(zno_no_dash)

    for filename in files:
        if filename in to_delete:
            continue
            
        file_path = os.path.join(WIKI_DIR, filename)
        print(f"Processing {filename}...")
        try:
            new_content = migrate_file(file_path)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    for filename in to_delete:
        file_path = os.path.join(WIKI_DIR, filename)
        print(f"Deleting {filename}...")
        os.remove(file_path)

if __name__ == "__main__":
    main()
