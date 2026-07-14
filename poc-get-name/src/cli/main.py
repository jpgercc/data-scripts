import subprocess 
import json
import os
import zipfile
import re
import sys
import spacy
from rapidfuzz import fuzz

# LIMITATIONS:
# 1. The code assumes the .docx file is a valid Word document
# 2. The code does not handle password-protected or corrupted files
# 3. The code does not handle documents that lack the expected XML structure (e.g., documents missing the "word" folder or the "document.xml" file)

# --- CONFIGURATION VARIABLES ---

# Modelos e Filtros
SPACY_MODEL = "en_core_web_sm"
STOP_ENTITIES = {'humanitarian', 'response', 'funds', 'policy', 'blog', 'crisis', 'summit', 'forum'}
FUZZ_MATCH_THRESHOLD = 85

# Limiares de Posição (0.0 a 1.0)
THRESHOLD_EDGE_EXTREME = 0.05
THRESHOLD_EDGE_MODERATE = 0.15

# Limiares de Frequência
THRESHOLD_FREQ_HIGH = 3
THRESHOLD_FREQ_LOW = 2

# Modificadores de Pontuação
SCORE_METADATA_MATCH = 50
SCORE_EDGE_EXTREME = 35
SCORE_EDGE_MODERATE = 15
SCORE_FREQ_LOW = 15
SCORE_FREQ_PENALTY = 25

# ----------------------------------

nlp = spacy.load(SPACY_MODEL)

class DocumentProcessor:
    def __init__(self, file_path):
        self.file_path = file_path

    def get_metadata_authors(self):
        cmd = ["exiftool", "-j", "-s3", "-Creator", "-Author", "-LastModifiedBy", self.file_path]
        result = json.loads(subprocess.check_output(cmd, stderr=subprocess.STDOUT))[0]
        filename = os.path.basename(self.file_path)
        return list(set([str(v) for v in result.values() if v and v != filename]))

    def analyze(self):
        authors = self.get_metadata_authors()
        
        with zipfile.ZipFile(self.file_path) as docx:
            xml = docx.read("word/document.xml").decode("utf-8", errors="ignore")
            text = re.sub(r'<[^>]+>', ' ', xml)
            text = re.sub(r'\s+', ' ', text).strip()
            
        doc = nlp(text)
        total_tokens = len(doc)
        
        people_data = {}
        
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                name = ent.text.strip(" .'")
                words = name.lower().split()
                if 1 < len(words) <= 3 and not any(w in STOP_ENTITIES for w in words):
                    if name not in people_data:
                        people_data[name] = {"count": 0, "positions": []}
                    
                    people_data[name]["count"] += 1
                    
                    relative_pos = ent.start / total_tokens if total_tokens > 0 else 0.5
                    people_data[name]["positions"].append(relative_pos)

        results = []
        
        for name, data in people_data.items():
            score = 0
            
            in_metadata = any(fuzz.token_sort_ratio(name.lower(), author.lower()) > FUZZ_MATCH_THRESHOLD for author in authors)
            if in_metadata:
                score += SCORE_METADATA_MATCH
            
            min_edge_distance = min(min(p, 1 - p) for p in data["positions"])
            
            if min_edge_distance <= THRESHOLD_EDGE_EXTREME: 
                score += SCORE_EDGE_EXTREME
            elif min_edge_distance <= THRESHOLD_EDGE_MODERATE: 
                score += SCORE_EDGE_MODERATE
            
            if data["count"] > THRESHOLD_FREQ_HIGH:
                score -= SCORE_FREQ_PENALTY
            elif data["count"] <= THRESHOLD_FREQ_LOW:
                score += SCORE_FREQ_LOW
            
            probability = max(0, min(100, score))
            
            results.append({
                "name": name,
                "probability_score": probability,
                "in_metadata": in_metadata,
                "frequency": data["count"],
                "best_position": round(min_edge_distance, 3)
            })

        results.sort(key=lambda x: x["probability_score"], reverse=True)

        return {
            "status": "success",
            "metadata_authors": authors,
            "author_probabilities": results
        }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(DocumentProcessor(sys.argv[1]).analyze(), indent=4))