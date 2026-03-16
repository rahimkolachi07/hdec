"""
maintenance/rag_engine.py
─────────────────────────
Lightweight RAG engine using OpenAI embeddings + cosine similarity.
No vector DB needed — stores everything in a JSON index file.
Low cost: uses text-embedding-3-small (cheapest) + gpt-4o-mini (cheapest capable).
"""
import os, json, hashlib, math, logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Index file path ────────────────────────────────────────────────────────────
def _index_path():
    from django.conf import settings
    return Path(settings.HDEC_DOCS_DIR) / "_rag_index.json"

def _docs_dir():
    from django.conf import settings
    return Path(settings.HDEC_DOCS_DIR)

def _load_index():
    p = _index_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {"documents": {}, "chunks": []}

def _save_index(idx):
    _index_path().parent.mkdir(parents=True, exist_ok=True)
    _index_path().write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding='utf-8')

# ── Text extraction ────────────────────────────────────────────────────────────
def extract_text(filepath: str) -> str:
    fp = Path(filepath)
    ext = fp.suffix.lower()
    text = ""
    try:
        if ext == ".pdf":
            import PyPDF2
            with open(fp, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n"
        elif ext in (".docx", ".doc"):
            import docx
            doc = docx.Document(fp)
            for para in doc.paragraphs:
                text += para.text + "\n"
            for table in doc.tables:
                for row in table.rows:
                    text += " | ".join(c.text for c in row.cells) + "\n"
        elif ext in (".txt", ".md", ".csv"):
            import chardet
            raw = fp.read_bytes()
            enc = chardet.detect(raw).get('encoding') or 'utf-8'
            text = raw.decode(enc, errors='replace')
        elif ext in (".xlsx", ".xls"):
            import pandas as pd
            xl = pd.read_excel(fp, sheet_name=None)
            for sheet_name, df in xl.items():
                text += f"\n=== {sheet_name} ===\n"
                text += df.to_string(index=False) + "\n"
        else:
            text = fp.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        logger.error(f"extract_text error {fp}: {e}")
    return text.strip()

# ── Chunking ───────────────────────────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100):
    """Split text into overlapping chunks by words."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

# ── Embeddings ─────────────────────────────────────────────────────────────────
def get_embedding(text: str, api_key: str) -> list:
    """Get embedding using text-embedding-3-small (cheapest)."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000]
    )
    return resp.data[0].embedding

def cosine_similarity(a: list, b: list) -> float:
    dot = sum(x*y for x,y in zip(a,b))
    na  = math.sqrt(sum(x*x for x in a))
    nb  = math.sqrt(sum(x*x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

# ── Index a document ──────────────────────────────────────────────────────────
def index_document(filepath: str, filename: str, api_key: str) -> dict:
    """Extract text, chunk, embed, save to index. Returns stats."""
    text = extract_text(filepath)
    if not text:
        return {"error": "Could not extract text from document"}

    chunks = chunk_text(text)
    if not chunks:
        return {"error": "Document appears to be empty"}

    doc_id = hashlib.md5(filename.encode()).hexdigest()[:12]
    idx = _load_index()

    # Remove old chunks for this doc
    idx["chunks"] = [c for c in idx["chunks"] if c.get("doc_id") != doc_id]

    # Embed each chunk (batch to save cost)
    embedded_chunks = []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        # Batch in groups of 20
        for batch_start in range(0, len(chunks), 20):
            batch = chunks[batch_start:batch_start+20]
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=[c[:8000] for c in batch]
            )
            for j, emb_data in enumerate(resp.data):
                embedded_chunks.append({
                    "doc_id":   doc_id,
                    "filename": filename,
                    "chunk_idx":batch_start + j,
                    "text":     batch[j],
                    "embedding":emb_data.embedding,
                })
    except Exception as e:
        return {"error": f"Embedding failed: {e}"}

    # Save to index
    idx["documents"][doc_id] = {
        "filename":  filename,
        "filepath":  filepath,
        "indexed_at":datetime.now().strftime("%d %b %Y %H:%M"),
        "chunks":    len(embedded_chunks),
        "chars":     len(text),
        "doc_id":    doc_id,
    }
    idx["chunks"].extend(embedded_chunks)
    _save_index(idx)

    return {
        "doc_id":  doc_id,
        "chunks":  len(embedded_chunks),
        "chars":   len(text),
        "success": True,
    }

# ── Remove a document ─────────────────────────────────────────────────────────
def remove_document(doc_id: str):
    idx = _load_index()
    doc = idx["documents"].pop(doc_id, None)
    idx["chunks"] = [c for c in idx["chunks"] if c.get("doc_id") != doc_id]
    _save_index(idx)
    # Delete file
    if doc:
        fp = Path(doc.get("filepath",""))
        if fp.exists():
            try: fp.unlink()
            except: pass
    return bool(doc)

# ── Search ────────────────────────────────────────────────────────────────────
def search_chunks(query: str, api_key: str, top_k: int = 5) -> list:
    """Embed query and return top-k most similar chunks."""
    idx = _load_index()
    if not idx["chunks"]:
        return []
    try:
        q_emb = get_embedding(query, api_key)
    except Exception as e:
        logger.error(f"search embedding error: {e}")
        return []
    scored = []
    for chunk in idx["chunks"]:
        emb = chunk.get("embedding")
        if not emb:
            continue
        score = cosine_similarity(q_emb, emb)
        scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]

# ── RAG Chat ──────────────────────────────────────────────────────────────────
def rag_chat(messages: list, plant_context: str, api_key: str) -> str:
    """
    Full RAG chat using gpt-4o-mini with plant data context + document RAG.
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    # Get last user query
    query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            query = m.get("content", "")
            break

    # Retrieve relevant document chunks
    chunks = search_chunks(query, api_key, top_k=6) if query else []
    doc_context = ""
    if chunks:
        doc_context = "\n\n=== RELEVANT UPLOADED DOCUMENTS ===\n"
        seen = set()
        for c in chunks:
            fname = c.get("filename", "")
            if fname not in seen:
                doc_context += f"\n--- From: {fname} ---\n"
                seen.add(fname)
            doc_context += c.get("text", "") + "\n"

    system_prompt = f"""You are HDEC Bot — the professional AI maintenance assistant for Al Henakiya 1100 MW Solar Power Plant operated by Power China HDEC, Saudi Arabia.

You have access to LIVE PLANT DATA updated every 5 minutes from Google Sheets, plus any uploaded maintenance documents.

RESPONSE FORMAT — CRITICAL:
- Use markdown formatting: **bold** for labels, ## for section headers, - for bullet lists, 1. for numbered steps
- For status queries: give Total, Done, Pending, Rate as a clear summary then list specifics
- For fault queries: list each item with block/equipment/issue on its own line
- For compliance: show weekly breakdown table then monthly total
- Keep responses complete but concise — no waffle
- End responses about critical issues with "Recommended Action:" section
- Do NOT add extra asterisks or symbols outside of proper markdown syntax
- Use section breaks with ---  between major sections

{plant_context}
{doc_context}

IMPORTANT: The plant data above contains full details including individual records for trackers, strings, inverters, equipment failures, and observations. Use this data to give specific, accurate answers."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
        messages=[{"role": "system", "content": system_prompt}] + messages[-12:]
    )
    return resp.choices[0].message.content

# ── List documents ────────────────────────────────────────────────────────────
def list_documents() -> list:
    idx = _load_index()
    return sorted(idx["documents"].values(), key=lambda d: d.get("indexed_at",""), reverse=True)

# ── Stats ─────────────────────────────────────────────────────────────────────
def rag_stats() -> dict:
    idx = _load_index()
    return {
        "document_count": len(idx["documents"]),
        "chunk_count":    len(idx["chunks"]),
        "documents":      list(idx["documents"].values()),
    }
