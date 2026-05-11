import os
import sys
import requests
import time
from pathlib import Path

MISTRAL_API_KEY = "ghAmeaujvGg3uLaFDLuyYYY3VhcqUQEw"
BASE_DIR = Path("/mnt/d/Google Drive/Document-literature/Boon-tiny-brain-02")
WIKI_DIR = BASE_DIR / "wiki"
ORCH_SCRIPT = BASE_DIR / "scripts/orchestrator.py"

def get_next_topic():
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    hubs = [f.stem for f in WIKI_DIR.glob("*Hub.md")]
    prompt = f"Based on these research hubs: {hubs}, suggest one highly specific, complex research question for an Al-S and OER materials scientist to investigate. Return ONLY the question."
    try:
        resp = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json={
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}]
        })
        return resp.json()['choices'][0]['message']['content'].strip('"')
    except:
        return "Advancements in Polysulfide Anchoring"

# 1. Disable interactivity in v2 orchestrator
os.system(f"sed -i 's/input(/# input(/g' \"{ORCH_SCRIPT}\"")

# 2. Run the loop (Batch of 5 to start)
for i in range(5):
    topic = get_next_topic()
    print(f"\n⚡ AUTO-PILOT MISSION {i+1}: {topic}")
    os.system(f"cd \"{BASE_DIR}\" && python3 \"{ORCH_SCRIPT}\" \"{topic}\"")
    time.sleep(5) # Small cooldown

# 3. Keep interactivity disabled so you can wake up to a running system
