import os
import re
import json

WIKI_DIR = "/mnt/d/Google Drive/Document-literature/Boon-tiny-brain-01/wiki/"

def fix_sources(content):
    frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not frontmatter_match:
        return content
        
    fm_text = frontmatter_match.group(1)
    body = content[frontmatter_match.end():]
    
    fm_lines = fm_text.split('\n')
    new_fm_lines = []
    
    for line in fm_lines:
        if line.startswith('sources:'):
            val = line.split(':', 1)[1].strip()
            # Case 1: [[raw/UUID.pdf]], [[raw/UUID.pdf]]
            sources = re.findall(r'\[\[(raw/.*?)\]\]', val)
            if sources:
                new_fm_lines.append(f"sources: {json.dumps(sources)}")
                continue
            
            # Case 2: [UUID.pdf] or [raw/UUID.pdf] or [ "UUID.pdf" ]
            # Clean up the brackets and split by comma
            cleaned = val.strip('[]').strip()
            if not cleaned:
                new_fm_lines.append("sources: []")
                continue
            
            items = [s.strip().strip('"\'') for s in cleaned.split(',')]
            fixed_items = []
            for item in items:
                if not item: continue
                if not item.startswith('raw/'):
                    item = 'raw/' + item
                fixed_items.append(item)
            new_fm_lines.append(f"sources: {json.dumps(fixed_items)}")
        else:
            new_fm_lines.append(line)
            
    return "---\n" + "\n".join(new_fm_lines) + "\n---\n" + body

def main():
    files = [f for f in os.listdir(WIKI_DIR) if f.endswith('.md')]
    for filename in files:
        file_path = os.path.join(WIKI_DIR, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = fix_sources(content)
        if new_content != content:
            print(f"Fixing sources in {filename}...")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

if __name__ == "__main__":
    main()
