import os
import re
import database
import openai

# Use path relative to this script file to ensure it works regardless of CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "documentos")

# Regex patterns for dependencies
DEP_PATTERNS = [
    r"(Ley\s+N[°ºo]?\s*\.?\s*\d+)",      # Ley N° 12345
    r"(Decreto\s+Supremo\s+N[°ºo]?\s*\.?\s*\d+[-–]\d+[-–]\w+)", # DS N° 001-2020-PCM
    r"(Resolución\s+Ministerial\s+N[°ºo]?\s*\.?\s*\d+[-–]\d+[-–]\w+)",
    r"(Decreto\s+Legislativo\s+N[°ºo]?\s*\.?\s*\d+)"
]

# Keywords for rules
OBLIGATION_KEYWORDS = ["debe", "deberá", "tiene que", "es obligatorio", "corresponde a"]
PROHIBITION_KEYWORDS = ["prohibido", "no podrá", "no se permite", "queda prohibido"]

STOP_WORDS = {"el", "la", "los", "las", "un", "una", "de", "del", "a", "ante", "bajo", "cabe", "con", "contra", "de", "desde", "en", "entre", "hacia", "hasta", "para", "por", "según", "sin", "sobe", "tras", "y", "o", "que", "se", "su", "sus", "es", "son", "no", "lo", "al", "como", "más", "pero", "si", "mi", "me", "te", "ti", "nos"}

def scan_directory():
    """Scans the 'documentos' directory, updates DB, and processes docs."""
    if not os.path.exists(DOCS_DIR):
        print(f"Directory {DOCS_DIR} not found.")
        return

    # 1. Load all files
    for filename in os.listdir(DOCS_DIR):
        if filename.endswith(".txt"):
            filepath = os.path.join(DOCS_DIR, filename)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            # Save to DB
            doc_id = database.add_document(filename, content)
            
            # 2. Extract Dependencies
            extract_dependencies_from_text(doc_id, content)

            # 3. Extract Rules
            extract_rules_from_text(doc_id, content)

    # 4. Resolve dependencies (link names to IDs)
    database.resolve_dependencies()

def extract_dependencies_from_text(doc_id, text):
    """Finds references to other legal docs using regex."""
    found_refs = set()
    for pattern in DEP_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            found_refs.add(m)
    
    for ref in found_refs:
        database.add_dependency(doc_id, ref)

def extract_rules_from_text(doc_id, text):
    """Splits text into chunks/sentences and looks for rule keywords."""
    # Simple splitting by newline or period (naive approach)
    # Ideally use NLTK or Spacy, but sticking to stdlib for MVP
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        lower_line = line.lower()
        
        rule_type = None
        if any(w in lower_line for w in PROHIBITION_KEYWORDS):
            rule_type = "PROHIBITION"
        elif any(w in lower_line for w in OBLIGATION_KEYWORDS):
            rule_type = "OBLIGATION"
            
        if rule_type:
            database.add_rule(doc_id, line, rule_type)

def check_compliance(child_content, parent_rule_text):
    """
    Checks if a rule from the parent exists in the child content.
    For this MVP, we perform a 'fuzzy' keyword match.
    We take the 'core' of the rule (excluding stopwords could be better)
    and see if a significant portion exists in the child.
    
    Alternative Naive approach:
    Just check if ANY of the significant words (nouns/verbs) from the rule appear in the child.
    """
    
    rule_words = set(parent_rule_text.lower().split())
    keywords = rule_words - STOP_WORDS
    
    if not keywords:
        return "UNKNOWN" # Rule was too short or only stopwords
    
    hits = 0
    child_lower = child_content.lower()
    
    for kw in keywords:
        if kw in child_lower:
            hits += 1
            
    # If a significant chunk of keywords are found, we assume "adderssed"
    ratio = hits / len(keywords)
    
    if ratio > 0.6:
        return "MATCH" # Green
    elif ratio > 0.3:
        return "PARTIAL" # Yellow
    else:
        return "MISSING" # Red

def generate_summary(text, num_sentences=3):
    """Generates a summary. Uses OpenAI if key is present, else extractive fallback."""
    if not text:
        return ""
    
    # Check for OpenAI Key
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un auditor legal experto. Resume el siguiente texto legal de manera clara, concisa y profesional en español. Destaca el objetivo, obligaciones y prohibiciones principales si las hay."},
                    {"role": "user", "content": f"Resume este texto en aproximadamente {num_sentences+1} oraciones:\n\n{text[:15000]}"} # Limit input to avoid token limits
                ],
                max_tokens=250
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI Error: {e}")
            # Fallback to legacy method
            return _generate_summary_legacy(text, num_sentences)
            
    return _generate_summary_legacy(text, num_sentences)

def _generate_summary_legacy(text, num_sentences=3):
    """Legacy extractive summary based on word frequency."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) <= num_sentences:
        return text
    
    # Calculate word frequencies
    word_freq = {}
    tokens = re.findall(r'\w+', text.lower())
    for word in tokens:
        if word not in STOP_WORDS:
            word_freq[word] = word_freq.get(word, 0) + 1
            
    # Score sentences
    scores = []
    for i, sentence in enumerate(sentences):
        score = 0
        s_tokens = re.findall(r'\w+', sentence.lower())
        if not s_tokens:
            continue
        for word in s_tokens:
            if word in word_freq:
                score += word_freq[word]
        # Normalize by length to avoid bias towards long sentences
        scores.append((score / len(s_tokens), i, sentence))
        
    # Get top N sentences, preserve order
    scores.sort(key=lambda x: x[0], reverse=True)
    top_sentences = sorted(scores[:num_sentences], key=lambda x: x[1])
    
    return " ".join([s[2] for s in top_sentences])

def analyze_document_structure(text):
    """
    Analyzes document to return:
    - General Summary
    - Sections (Header, Summary, Content) ensuring min 1000 chars per section where possible
    """
    # 1. Generate General Summary (from first 3000 chars approx)
    general_summary = generate_summary(text[:5000], num_sentences=4)
    
    # 2. Split into sections
    # Regex for potential headers: Uppercase lines or specific keywords
    # We look for lines that look like titles
    lines = text.split('\n')
    sections = []
    current_section_title = "Introducción / Preámbulo"
    current_section_lines = []
    
    header_pattern = re.compile(r'^(TÍTULO|TITULO|CAPÍTULO|CAPITULO|SECCIÓN|SECCION|ARTÍCULO|ARTICULO)\s', re.IGNORECASE)
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_section_lines.append(line)
            continue
            
        is_header = False
        
        # Check standard headers
        if header_pattern.match(stripped):
            is_header = True
        # Check uppercase lines that are short enough to be titles, but not too short
        elif stripped.isupper() and len(stripped) > 5 and len(stripped) < 100:
            is_header = True
            
        if is_header:
            # Check if current section is big enough
            current_text = "\n".join(current_section_lines)
            if len(current_text) < 1000 and sections:
                # Too small, append to previous section if exists, OR just keep accumulating
                # User preference: "minimo 1000 caracteres"
                # If we split here, the *previous* section is finished. 
                # Let's check the size of the *accumulated* text.
                # Actually, the logic usually is: convert current buffer to section, start new.
                # But if current buffer is small, maybe we shouldn't split?
                # However, headers are semantic. Merging headers might be confusing.
                # Compromise: We always respect headers, but if a section is tiny, we might flag it or merge it 
                # visually later? No, user explicitly asked for 1000 chars min.
                # Strategy: If current buffer < 1000, DO NOT split, treat this header as subtitle.
                if len(current_text) >= 1000 or not sections:
                     # Save current section
                     sections.append({
                         "title": current_section_title,
                         "content": current_text,
                         "summary": generate_summary(current_text)
                     })
                     current_section_title = stripped
                     current_section_lines = []
                else:
                    # Continue in same section, maybe append header as text
                    current_section_lines.append(line)
            else:
                 # Standard split
                 sections.append({
                     "title": current_section_title,
                     "content": current_text,
                     "summary": generate_summary(current_text)
                 })
                 current_section_title = stripped
                 current_section_lines = [] # Start fresh
        else:
            current_section_lines.append(line)
            
    # Flush last section
    final_text = "\n".join(current_section_lines)
    if sections and len(final_text) < 1000:
        # Merge with last
        sections[-1]["content"] += "\n" + final_text
        # Re-summarize last section
        sections[-1]["summary"] = generate_summary(sections[-1]["content"])
    else:
        sections.append({
            "title": current_section_title,
            "content": final_text,
            "summary": generate_summary(final_text)
        })
        
    return {
        "general_summary": general_summary,
        "sections": sections
    }
