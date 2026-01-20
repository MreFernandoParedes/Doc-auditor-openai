import sqlite3
import os

DB_PATH = "doc_auditor.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Documents table
    c.execute('''CREATE TABLE IF NOT EXISTS docs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE,
                    content TEXT
                )''')
    
    # Dependencies table (Parent -> Child relations)
    # parent_name is the raw string found in text (e.g. "Ley 3000")
    # parent_id is the resolved doc_id if found
    c.execute('''CREATE TABLE IF NOT EXISTS dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_doc_id INTEGER,
                    parent_ref_name TEXT,
                    parent_doc_id INTEGER,
                    status TEXT DEFAULT 'PENDING',
                    FOREIGN KEY(child_doc_id) REFERENCES docs(id)
                )''')

    # Rules table (Extracted constraints)
    c.execute('''CREATE TABLE IF NOT EXISTS rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER,
                    rule_text TEXT,
                    rule_type TEXT,
                    FOREIGN KEY(doc_id) REFERENCES docs(id)
                )''')

    # Migration: Add analysis_json column if not exists
    try:
        c.execute("ALTER TABLE docs ADD COLUMN analysis_json TEXT")
    except sqlite3.OperationalError:
        pass # Column likely exists

    conn.commit()
    conn.close()

def add_document(filename, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO docs (filename, content) VALUES (?, ?)", (filename, content))
        doc_id = c.lastrowid
    except sqlite3.IntegrityError:
        c.execute("SELECT id FROM docs WHERE filename=?", (filename,))
        doc_id = c.fetchone()[0]
        # Update content just in case
        c.execute("UPDATE docs SET content=? WHERE id=?", (content, doc_id))
    conn.commit()
    conn.close()
    return doc_id

def update_doc_analysis(doc_id, analysis_json):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE docs SET analysis_json=? WHERE id=?", (analysis_json, doc_id))
    conn.commit()
    conn.close()

def add_dependency(child_doc_id, parent_ref_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Check if exists
    c.execute("SELECT id FROM dependencies WHERE child_doc_id=? AND parent_ref_name=?", (child_doc_id, parent_ref_name))
    if not c.fetchone():
        c.execute("INSERT INTO dependencies (child_doc_id, parent_ref_name) VALUES (?, ?)", (child_doc_id, parent_ref_name))
    conn.commit()
    conn.close()

def add_rule(doc_id, rule_text, rule_type):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO rules (doc_id, rule_text, rule_type) VALUES (?, ?, ?)", (doc_id, rule_text, rule_type))
    conn.commit()
    conn.close()

def get_all_docs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, filename FROM docs")
    rows = c.fetchall()
    conn.close()
    return rows

def get_doc_by_id(doc_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, filename, content, analysis_json FROM docs WHERE id=?", (doc_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_dependencies_graph():
    """Returns nodes and edges for the graph"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Nodes
    c.execute("SELECT id, filename FROM docs")
    docs = c.fetchall()
    
    # Edges (Resolved dependencies only for now, or raw)
    # We try to join dependencies with docs on parent_ref_name approx match or if parent_doc_id is set
    c.execute('''
        SELECT d.child_doc_id, d.parent_doc_id, d.parent_ref_name 
        FROM dependencies d
    ''')
    deps = c.fetchall()
    
    conn.close()
    return docs, deps

def resolve_dependencies():
    """Attempts to link dependencies to actual doc IDs based on filenames"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, filename FROM docs")
    all_docs = c.fetchall()
    
    # Generic normalization for matching
    # e.g. "Ley 30000.txt" -> "Ley 30000"
    doc_map = {doc[1].replace(".txt","").lower(): doc[0] for doc in all_docs}
    
    c.execute("SELECT id, parent_ref_name FROM dependencies WHERE parent_doc_id IS NULL")
    pending = c.fetchall()
    
    for dep_id, ref_name in pending:
        # Simple heuristic matching
        ref_clean = ref_name.lower().strip()
        matched_id = None
        
        # Exact substring match in knowing filenames
        for name, did in doc_map.items():
            if name in ref_clean or ref_clean in name:
                matched_id = did
                break
        
        if matched_id:
            c.execute("UPDATE dependencies SET parent_doc_id=?, status='RESOLVED' WHERE id=?", (matched_id, dep_id))
            
    conn.commit()
    conn.close()

def get_rules_for_doc(doc_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT rule_text, rule_type FROM rules WHERE doc_id=?", (doc_id,))
    data = c.fetchall()
    conn.close()
    return data

def get_parent_docs(child_doc_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Returns list of parent docs (actual objects if resolved)
    c.execute('''
        SELECT p.id, p.filename 
        FROM dependencies d
        JOIN docs p ON d.parent_doc_id = p.id
        WHERE d.child_doc_id = ?
    ''', (child_doc_id,))
    parents = c.fetchall()
    conn.close()
    return parents
