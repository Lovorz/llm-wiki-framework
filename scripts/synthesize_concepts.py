import os
import re
import sys
import yaml
import requests
from pathlib import Path
from datetime import datetime

MISTRAL_API_KEY = "ghAmeaujvGg3uLaFDLuyYYY3VhcqUQEw"
WIKI_DIR = Path('wiki')
CONCEPTS_DIR = WIKI_DIR / 'concepts'

def call_mistral_synthesis(concept_name, findings_text):
    """Sends compiled findings to Mistral to write an expert synthesis."""
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""You are a senior materials scientist. 
Below are experimental and computational findings from multiple papers in a research vault regarding the concept: {concept_name}.

TASK:
Write a cohesive, expert-level 'State of the Art' summary for this concept. 
- Do not just list papers. 
- Synthesize the trends (e.g., which materials show the lowest overpotential, common DFT settings used).
- Identify contradictions or complementary results.
- Use high-quality LaTeX for all chemical formulas and units.
- Keep the tone academic and precise.

FINDINGS DATA:
{findings_text}

OUTPUT FORMAT:
Return only the markdown content for the synthesis. Use headers like ## Overview, ## Current Trends, ## Quantitative Comparison, and ## Strategic Outlook.
"""

    payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Synthesis failed: {e}"

def synthesize_concept(concept_name, keywords):
    """Gathers data and uses Mistral to write an intelligent synthesis."""
    print(f"Intelligent Synthesis for: {concept_name}...")
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    
    raw_findings = []
    sources = []
    
    all_files = list(WIKI_DIR.glob('*.md'))
    for f in all_files:
        if f.name == 'index.md' or "Hub" in f.name or "concepts" in f.parts: continue
        
        content = f.read_text(encoding='utf-8', errors='ignore')
        if f"[[{concept_name}]]" in content or any(kw.lower() in content.lower() for kw in keywords):
            sources.append(f.stem)
            findings_match = re.search(r'### 🎯 Key Findings(.*?)(?:###|$)', content, re.DOTALL)
            if findings_match:
                raw_findings.append(f"SOURCE [[{f.stem}]]:\n{findings_match.group(1).strip()}")

    if not raw_findings:
        print(f"No data for {concept_name}.")
        return

    # Combine all findings into one big block for the AI to read
    compiled_data = "\n\n".join(raw_findings)
    
    # LIMIT DATA size to avoid context issues (keep first 15k chars)
    if len(compiled_data) > 15000:
        compiled_data = compiled_data[:15000] + "... (truncated)"

    # Get the "AI Brain" synthesis
    synthesis_md = call_mistral_synthesis(concept_name, compiled_data)
    
    fm = {
        'title': f"{concept_name} Synthesis",
        'type': 'synthesis',
        'confidence': 1.0,
        'sources': sources[:30],
        'last_updated': datetime.now().strftime('%Y-%m-%d'),
        'brain': 'mistral-large'
    }
    
    final_content = f"---\n{yaml.dump(fm, sort_keys=False)}---\n# {concept_name}: State of the Art Synthesis\n\n"
    final_content += synthesis_md
    final_content += "\n\n---\n## 📂 Integrated Sources\n"
    for s in sources[:20]:
        final_content += f"- [[{s}]]\n"
    
    output_path = CONCEPTS_DIR / f"{concept_name}.md"
    output_path.write_text(final_content, encoding='utf-8')
    print(f"Intelligent Synthesis saved: {output_path}")

if __name__ == "__main__":
    concepts = {
        "OER": ["Oxygen evolution", "OER"],
        "Al-S Batteries": ["Aluminum-Sulfur", "Al-S", "Battery"],
        "MXenes": ["MXene", "V2C", "Ti3C2"],
        "Perovskites": ["Perovskite", "LaNiO3", "LaCoO3"]
    }
    
    for name, kws in concepts.items():
        synthesize_concept(name, kws)
