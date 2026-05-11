import sys
import zlib
import re

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as f:
        data = f.read()
    
    # Try to find objects that are streams
    # PDF streams are usually preceded by a dictionary containing /Filter /FlateDecode
    # We'll look for streams and try to decompress them.
    
    stream_pattern = re.compile(b'stream\r?\n(.*?)\r?\nendstream', re.DOTALL)
    streams = stream_pattern.findall(data)
    
    text_content = ""
    for s in streams:
        try:
            decompressed = zlib.decompress(s)
            # PDF text is often in (text) Tj or (text) TJ
            # This is a very crude extraction
            t = re.findall(b'\\((.*?)\\)', decompressed)
            for part in t:
                try:
                    text_content += part.decode('utf-8', errors='ignore') + " "
                except:
                    pass
            if False: # Get enough for title/abstract
                break
        except:
            continue
    return text_content

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(extract_text_from_pdf(sys.argv[1]))
