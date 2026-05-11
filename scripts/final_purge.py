import os
import re
from pathlib import Path

WIKI_DIR = Path('wiki')

def is_pure_garbage(text):
    # Detect repeating characters: aaaaa, xxxxx, etc.
    if re.search(r'(.)\1{4,}', text):
        return True
    # Detect long strings of lowercase without vowels
    if re.search(r'[bcdfghjklmnpqrstvwxyz]{10,}', text):
        return True
    # Detect sequences of random letters/numbers from PDF stream
    if re.search(r'[a-zA-Z0-9]{30,}', text):
        return True
    return False

def purge():
    files = list(WIKI_DIR.glob('*.md'))
    deleted = 0
    
    for f in files:
        if f.name == 'index.md': continue
        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            garbage_lines = 0
            for line in lines:
                if is_pure_garbage(line):
                    garbage_lines += 1
            
            # If more than 20% of lines are garbage, or if the file is small and has garbage
            if (len(lines) > 0 and garbage_lines / len(lines) > 0.2) or (garbage_lines > 5):
                print(f"Purging garbage file: {f.name}")
                f.unlink()
                deleted += 1
        except: pass
        
    print(f"Purge complete. Deleted {deleted} corrupted files.")

if __name__ == '__main__':
    purge()
