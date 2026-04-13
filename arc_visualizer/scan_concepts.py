import json
import os
from collections import Counter

DATA_FILE = 'new_dataset.jsonl'
OUTPUT_FILE = 'concepts.json'

def scan():
    concepts = Counter()
    print(f"Scanning {DATA_FILE} for concepts... This may take a while.")
    
    try:
        with open(DATA_FILE, 'r') as f:
            for i, line in enumerate(f):
                if line.strip():
                    try:
                        # Quick string check to speed up before parsing JSON
                        # (Optional optimization, strictly parsing is safer)
                        data = json.loads(line)
                        concept = data.get('meta', {}).get('concept')
                        if concept:
                            concepts[concept] += 1
                    except:
                        continue
                
                if i % 10000 == 0:
                    print(f"Processed {i} lines...", end='\r')

        print(f"\nScan complete. Found {len(concepts)} unique concepts.")
        
        # Save to file
        with open(OUTPUT_FILE, 'w') as out:
            json.dump(dict(concepts), out, indent=2)
            
        print(f"Saved concept list to {OUTPUT_FILE}")

    except FileNotFoundError:
        print("Error: data.jsonl not found.")

if __name__ == "__main__":
    scan()