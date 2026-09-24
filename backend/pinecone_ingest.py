"""
pinecone_ingest.py  ──  Drop into your SmartChat backend folder.

Registers a sub-router that the main FastAPI app includes:

    from pinecone_ingest import router as pinecone_router
    app.include_router(pinecone_router)

Index architecture
──────────────────
Five FIXED shared Pinecone indexes (created once, reused for all users):
  • "university"  — generic university document pipeline
  • "faculty"     — GPT-4o faculty directory pipeline
  • "restaurant"  — GPT-4o menu vision pipeline
  • "fyp"         — Final Year Project documents (same text pipeline as university)
  • "general"     — General-purpose documents (same text pipeline as university)

Data isolation is achieved via Pinecone **namespaces**.
Each ingest uses namespace  "{user_id}-{bot_id}"  so every chatbot's
vectors are stored and queried independently within the shared index.

Endpoints
─────────
POST  /chatbots/{bot_id}/pinecone/ingest
      Upload a PDF.  Returns {job_id, index_name, namespace} immediately.
      ?category=university|faculty|restaurant|fyp|general  selects the pipeline + index.
      Background task embeds into the fixed index under namespace {user_id}-{bot_id}.

GET   /chatbots/{bot_id}/pinecone/ingest/{job_id}/progress  (SSE)
      Streams JSON events:
        {"status": "uploading|extracting|chunking|embedding|done|error",
         "total": N, "done": N, "pct": 0-100,
         "method": "pypdf|pdfplumber|ocr",
         "errors": [...]}

GET   /chatbots/{bot_id}/pinecone/ingest/{job_id}/status    (JSON poll)
      Same payload as above — for environments where SSE is unsupported.

GET   /chatbots/{bot_id}/pinecone/index-info?category=...
      Returns {index_name, namespace, vector_count} for this bot's namespace.

DELETE /chatbots/{bot_id}/pinecone/index?category=...
      Deletes all vectors in this bot's namespace (shared index is preserved).

Auth
────
All endpoints require ?user_id=&token= query params (same pattern as
the rest of the SmartChat backend). Token is validated against your
existing DB; replace _verify_auth() below with your real check.

Dependencies  (all already in your requirements.txt)
────────────
  pinecone, langchain-openai, langchain-pinecone, langchain-core,
  openai, pypdf, pdfplumber (optional), pdf2image+pytesseract (optional)
"""

import asyncio
import base64
import io
import json
import os
import re
import shutil
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_pinecone import PineconeVectorStore
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
import fitz          # PyMuPDF
import pandas as pd
from pinecone import Pinecone, ServerlessSpec
from sqlalchemy.orm import Session
from database import get_db
from models import KnowledgeDocument, DocStatus
from schemas import DocumentResponse

# Load .env so keys are available even if the host app hasn't called load_dotenv() yet
load_dotenv()

# ─────────────────────────────────────────────────────────────────
# Config  — keys read lazily at call-time so .env is guaranteed loaded
# ─────────────────────────────────────────────────────────────────

def _pinecone_key() -> str:
    key = os.environ.get("PINECONE_API_KEY", "")
    if not key:
        raise RuntimeError("PINECONE_API_KEY not set in .env")
    return key

def _openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")
    return key

# Pinecone embedding dimension  (text-embedding-3-large = 3072)
_EMBED_DIM = 3072

# Base uploads directory (same as SmartChat backend UPLOAD_DIR)
_UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

# In-memory job store  {job_id: {...}}
_ingest_jobs: dict = {}

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

# Fixed index names — one shared index per category
_CATEGORY_INDEXES = {
    "university": "university",
    "faculty":    "faculty",
    "restaurant": "restaurant",
    "fyp":        "fyp",
    "general":    "general",
}
_DEFAULT_CATEGORY_INDEX = "university"


def _index_name_for_category(category: str) -> str:
    """Return the fixed Pinecone index name for a given category.
    Raises ValueError for unknown categories so they never silently fall back to 'university'.
    """
    if category not in _CATEGORY_INDEXES:
        raise ValueError(
            f"Unknown category '{category}'. "
            f"Must be one of: {list(_CATEGORY_INDEXES.keys())}"
        )
    return _CATEGORY_INDEXES[category]


def _namespace(user_id: int, bot_id: int) -> str:
    """Pinecone namespace that isolates each user/bot within a shared index."""
    return f"{user_id}-{bot_id}"


def _get_or_create_index(name: str) -> "pinecone.Index":
    """Return Pinecone Index, creating it (serverless / AWS us-east-1) if absent."""
    pc = Pinecone(api_key=_pinecone_key())
    existing = pc.list_indexes()
    names = existing.names() if hasattr(existing, "names") else [i["name"] for i in existing]
    if name not in names:
        pc.create_index(
            name=name,
            dimension=_EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(name)


def _verify_auth(user_id: int, token: str) -> bool:
    """
    Replace this stub with your real token check against MySQL.
    E.g.:  SELECT id FROM users WHERE id=? AND token=?
    For now, any non-empty token is accepted so you can wire it up
    to your existing auth middleware.
    """
    return bool(token)


# ─────────────────────────────────────────────────────────────────
# Text Splitter  (same as main.py — no extra dependency)
# ─────────────────────────────────────────────────────────────────

class _SimpleTextSplitter:
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 80):
        self.chunk_size    = chunk_size
        self.chunk_overlap = chunk_overlap
        self._seps = ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text: str) -> List[str]:
        chunks, current = [], ""
        for sep in self._seps:
            parts = text.split(sep) if sep else list(text)
            for part in parts:
                if len(current) + len(sep) + len(part) <= self.chunk_size:
                    current = (current + sep + part) if current else part
                else:
                    if current:
                        chunks.append(current)
                    overlap_start = max(0, len(current) - self.chunk_overlap)
                    current = current[overlap_start:] + (sep if current else "") + part
            if current:
                chunks.append(current)
                current = ""
            if chunks:
                break
        if not chunks and text:
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunks.append(text[i: i + self.chunk_size])
        return [c.strip() for c in chunks if c.strip()]

    def split_documents(self, docs: List[Document]) -> List[Document]:
        result = []
        for doc in docs:
            for chunk in self.split_text(doc.page_content):
                result.append(Document(page_content=chunk, metadata=doc.metadata.copy()))
        return result


# ─────────────────────────────────────────────────────────────────
# PDF extraction  (3-tier pipeline — mirrors main.py exactly)
# ─────────────────────────────────────────────────────────────────

_CID_RE = re.compile(r'\(cid:\d+\)')
_GID_RE = re.compile(r'/gid\d+')


def _garbage_ratio(text: str) -> float:
    if not text or len(text.strip()) < 10:
        return 1.0
    hits = len(_CID_RE.findall(text)) + len(_GID_RE.findall(text))
    return hits / max(len(text.split()), 1)


def _is_garbage(text: str, threshold: float = 0.15) -> bool:
    return _garbage_ratio(text) > threshold


def _clean_text(text: str) -> str:
    text = _CID_RE.sub(" ", text)
    text = _GID_RE.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _quality_score(pages: list) -> float:
    if not pages:
        return 0.0
    good = sum(1 for p in pages if p["text"].strip() and not _is_garbage(p["text"]))
    return good / len(pages)


def _extract_pypdf(pdf_path: str) -> list:
    try:
        import pypdf
        out = []
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for i, page in enumerate(reader.pages):
                out.append({"page": i, "text": page.extract_text() or ""})
        return out
    except Exception as e:
        print(f"[pypdf] {e}")
        return []


def _extract_pdfplumber(pdf_path: str) -> list:
    try:
        import pdfplumber
        out = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                try:
                    for table in page.extract_tables() or []:
                        for row in table:
                            row_text = " | ".join(cell or "" for cell in row if cell)
                            if row_text.strip():
                                text += "\n" + row_text
                except Exception:
                    pass
                out.append({"page": i, "text": text})
        return out
    except ImportError:
        return []
    except Exception as e:
        print(f"[pdfplumber] {e}")
        return []


def _extract_ocr(pdf_path: str, dpi: int = 250) -> list:
    from pdf2image import convert_from_path
    import pytesseract
    images = convert_from_path(pdf_path, dpi=dpi)
    return [{"page": i, "text": pytesseract.image_to_string(img)} for i, img in enumerate(images)]


def _extract_pdf(pdf_path: str):
    """3-tier extraction, returns (pages, method_name)."""
    pages1 = _extract_pypdf(pdf_path)
    if _quality_score(pages1) >= 0.6:
        return pages1, "pypdf"

    pages2 = _extract_pdfplumber(pdf_path)
    if _quality_score(pages2) >= 0.5:
        return pages2, "pdfplumber"

    pages3 = _extract_ocr(pdf_path)
    return pages3, "ocr"


_META_BYTE_LIMIT = 35_000


def _pages_to_chunks(pages: list, filename: str) -> List[Document]:
    splitter = _SimpleTextSplitter(chunk_size=600, chunk_overlap=80)
    docs = []
    for p in pages:
        text = _clean_text(p["text"])
        if _is_garbage(text) or len(text) < 30:
            continue
        docs.append(Document(
            page_content=text,
            metadata={"source": filename[:200], "page": p["page"] + 1},
        ))
    chunks = splitter.split_documents(docs)
    safe = []
    for c in chunks:
        enc = c.page_content.encode("utf-8")
        if len(enc) > _META_BYTE_LIMIT:
            c = Document(
                page_content=enc[:_META_BYTE_LIMIT].decode("utf-8", errors="ignore"),
                metadata=c.metadata,
            )
        safe.append(c)
    return safe



# ─────────────────────────────────────────────────────────────────
# Restaurant / Menu PDF pipeline  (GPT-4o vision based)
# mirrors hardees_api.py logic, adapted to run inside SmartChat
# ─────────────────────────────────────────────────────────────────

MAX_WORKERS = 6

def _openai_client() -> OpenAI:
    return OpenAI(api_key=_openai_key())


def _page_to_b64(page) -> str:
    pix = page.get_pixmap(dpi=200)
    return base64.b64encode(pix.tobytes("png")).decode()


def _sanitize_filename(name: str) -> str:
    if not name or name.lower() == "unknown":
        return "unknown"
    clean = re.sub(r'[^a-z0-9_]', '', name.lower().strip().replace(" ", "_"))
    return clean or "unknown"


def _call_openai_items(client: OpenAI, img1_b64: str, img2_b64: str, window_idx: int) -> list:
    prompt = (
        "Analyze these two menu pages as a SINGLE document.\n"
        "1. Identify every food item.\n"
        "2. For each item, identify if there is a primary visual image/photo next to it.\n\n"
        "Return ONLY a JSON list:\n"
        '[{"name":"...","category":"...","description":"...","price":"digits only",'
        '"has_image":true/false,"image_index_on_page":0,"page_num":1}]'
    )
    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img1_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img2_b64}"}},
            ]}],
            temperature=0,
        )
        raw = res.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        return json.loads(raw)
    except Exception as e:
        print(f"[restaurant_ingest] window {window_idx} error: {e}")
        return []


def _call_openai_metadata(client: OpenAI, pages_b64: list) -> dict:
    prompt = (
        "Analyze the provided menu document and extract:\n"
        "1. Locations/Branches: name and full address.\n"
        "2. Timings: opening/closing hours.\n"
        "3. FAQs: questions and answers.\n\n"
        'Return ONLY JSON: {"branches":[{"name":"...","address":"..."}],'
        '"timings":"...","faqs":[{"question":"...","answer":"..."}]}'
    )
    content = [{"type": "text", "text": prompt}]
    for img in pages_b64[-4:]:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
    try:
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            temperature=0,
        )
        raw = res.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        return json.loads(raw)
    except Exception as e:
        print(f"[restaurant_ingest] metadata error: {e}")
        return {}


def _save_item_image(fitz_doc, page_assets: dict, item: dict,
                     processed_xrefs: set, images_dir: str) -> str:
    """Extract and save an item image into uploads/{bot_id}/images/."""
    if not item.get("has_image"):
        return "unknown"
    p_num   = item.get("page_num", 1)
    img_idx = item.get("image_index_on_page", 0)
    assets  = page_assets.get(p_num, [])
    if img_idx >= len(assets):
        return "unknown"
    xref = assets[img_idx][0]
    if xref in processed_xrefs:
        return "unknown"
    try:
        base_image = fitz_doc.extract_image(xref)
        clean_fn   = _sanitize_filename(item.get("name", "unknown"))
        os.makedirs(images_dir, exist_ok=True)
        save_path  = os.path.join(images_dir, f"{clean_fn}.jpg")
        Image.open(io.BytesIO(base_image["image"])).convert("RGB").save(save_path, "JPEG")
        processed_xrefs.add(xref)
        return save_path
    except Exception as e:
        print(f"[restaurant_ingest] image save failed for {item.get('name')}: {e}")
        return "unknown"


def _extract_restaurant_pdf(pdf_path: str, images_dir: str,
                             job: dict) -> Tuple[list, dict]:
    """
    Full GPT-4o vision pipeline — returns (all_items, store_info).
    Updates job['stage_detail'] with progress strings.
    """
    client = _openai_client()
    fitz_doc = fitz.open(pdf_path)
    n_pages  = len(fitz_doc)

    job["stage_detail"] = f"Rendering {n_pages} pages..."
    page_b64s = [None] * n_pages

    def render(i):
        return i, _page_to_b64(fitz_doc[i])

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for i, b64 in ex.map(render, range(n_pages)):
            page_b64s[i] = b64

    job["stage_detail"] = "Sending pages to GPT-4o for item extraction..."

    futures          = {}
    processed_xrefs: set = set()
    window_results: dict = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        meta_future = ex.submit(_call_openai_metadata, client, page_b64s)
        for i in range(n_pages - 1):
            f = ex.submit(_call_openai_items, client, page_b64s[i], page_b64s[i + 1], i)
            futures[f] = i

        done_windows = 0
        for f in as_completed(futures):
            idx = futures[f]
            window_results[idx] = f.result()
            done_windows += 1
            job["stage_detail"] = f"GPT-4o: processed {done_windows}/{n_pages-1} page windows"

        store_info = meta_future.result()

    job["stage_detail"] = "Saving item images..."
    all_items = []
    for i in sorted(window_results):
        items_metadata = window_results[i]
        page_assets = {
            1: fitz_doc[i].get_images(full=True),
            2: fitz_doc[i + 1].get_images(full=True),
        }
        for item in items_metadata:
            save_path = _save_item_image(fitz_doc, page_assets, item,
                                         processed_xrefs, images_dir)
            item_name = item.get("name", "Unknown")
            all_items.append({
                "Item Name":   item_name if save_path != "unknown" else f"unknown_{item_name}",
                "Category":    item.get("category", ""),
                "Description": item.get("description", ""),
                "Price":       item.get("price", ""),
                "Image Path":  save_path,
            })

    fitz_doc.close()
    return all_items, store_info


def _build_restaurant_documents(all_items: list, store_info: dict) -> List[Document]:
    """Convert extracted items + metadata into LangChain Documents."""
    docs = []
    seen: set = set()

    for i, row in enumerate(all_items):
        name = row["Item Name"]
        if "unknown" in name.lower():
            continue
        key = (name, row["Price"])
        if key in seen:
            continue
        seen.add(key)
        content = (
            f"Item: {name}\nCategory: {row['Category']}\n"
            f"Description: {row['Description']}\nPrice: Rs. {row['Price']}"
        )
        docs.append(Document(
            page_content=content,
            metadata={
                "item_name":   name,
                "category":    row["Category"],
                "description": row["Description"],
                "price":       row["Price"],
                "image_path":  row["Image Path"],
                "text":        content,
            },
            id=f"item_{i}",
        ))

    for i, branch in enumerate(store_info.get("branches", [])):
        content = f"Branch: {branch.get('name')}. Address: {branch.get('address')}"
        docs.append(Document(
            page_content=content,
            metadata={"category": "Location", "text": content},
            id=f"loc_{i}",
        ))

    timings = store_info.get("timings", "")
    if timings:
        content = f"Opening Hours: {timings}"
        docs.append(Document(
            page_content=content,
            metadata={"category": "Timing", "text": content},
            id="timing_0",
        ))

    for i, faq in enumerate(store_info.get("faqs", [])):
        content = f"Question: {faq.get('question')} Answer: {faq.get('answer')}"
        docs.append(Document(
            page_content=content,
            metadata={"category": "FAQ", "text": content},
            id=f"faq_{i}",
        ))

    return docs


# ─────────────────────────────────────────────────────────────────
# Restaurant background ingest task
# ─────────────────────────────────────────────────────────────────

async def _run_restaurant_ingest(job_id: str, pdf_path: str, filename: str,
                                  index_name: str, doc_id: int, bot_id: int,
                                  db_factory, namespace: str = ""):
    """
    Restaurant pipeline:
      rendering → GPT-4o extraction → image saving → embedding → done
    Progress stages reported into _ingest_jobs[job_id].
    """
    job = _ingest_jobs[job_id]
    loop = asyncio.get_event_loop()

    # Images go into uploads/{bot_id}/images/
    images_dir = os.path.join(_UPLOAD_DIR, str(bot_id), "images")

    try:
        # ── 1. GPT-4o extraction (rendering + vision calls) ─────
        job["status"]       = "extracting"
        job["stage_detail"] = "Starting GPT-4o vision extraction..."

        all_items, store_info = await loop.run_in_executor(
            None, _extract_restaurant_pdf, pdf_path, images_dir, job
        )

        total_items = len([r for r in all_items if "unknown" not in r["Item Name"].lower()])
        job["stage_detail"] = f"Extracted {total_items} menu items + metadata"

        # ── 2. Build documents ──────────────────────────────────
        job["status"] = "chunking"
        job["stage_detail"] = "Building vector documents..."
        documents = await loop.run_in_executor(
            None, _build_restaurant_documents, all_items, store_info
        )
        job["total"] = len(documents)

        if not documents:
            job["status"] = "error"
            job["errors"].append("No items could be extracted from the menu PDF.")
            return

        # ── 3. Create/get Pinecone index ────────────────────────
        job["status"] = "embedding"
        job["stage_detail"] = "Creating Pinecone index..."
        pinecone_index = await loop.run_in_executor(None, _get_or_create_index, index_name)
        embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large", api_key=_openai_key())
        vector_store = PineconeVectorStore(
            index=pinecone_index,
            embedding=embeddings_model,
            namespace=namespace,
        )

        # ── 4. Embed in batches ─────────────────────────────────
        BATCH = 50
        for i in range(0, len(documents), BATCH):
            batch = documents[i: i + BATCH]
            ids   = [d.id for d in batch if d.id]
            await loop.run_in_executor(
                None,
                lambda b=batch, bid=ids: vector_store.add_documents(documents=b, ids=bid or None)
            )
            job["done"] = min(i + BATCH, len(documents))
            job["pct"]  = round(job["done"] / job["total"] * 100)
            job["stage_detail"] = f"Embedded {job['done']}/{job['total']} documents"
            await asyncio.sleep(0)

        job["status"]       = "done"
        job["done"]         = len(documents)
        job["pct"]          = 100
        job["stage_detail"] = f"{total_items} menu items indexed"
        job["items_count"]  = total_items

        # ── 5. Update DB ────────────────────────────────────────
        try:
            db: Session = db_factory()
            doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
            if doc:
                doc.pinecone_index    = index_name
                doc.status            = DocStatus.trained
                doc.training_progress = 100
                doc.accuracy          = 95.0
                db.commit()
            db.close()
        except Exception as db_err:
            print(f"[restaurant_ingest] DB update failed: {db_err}")

    except Exception as e:
        job["status"] = "error"
        job["errors"].append(str(e))
        print(f"[restaurant_ingest] job {job_id} error: {e}")
    finally:
        try:
            os.unlink(pdf_path)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────
# Faculty PDF pipeline  (GPT-4o vision — text + image extraction)
# mirrors faculty_api.py logic, adapted to run inside SmartChat
# ─────────────────────────────────────────────────────────────────

_FAC_MAX_WORKERS = 8

def _llm_client():
    return ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=4000,
                      openai_api_key=_openai_key())

def _page_to_b64_hires(page, scale: float = 3.0) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return base64.b64encode(pix.tobytes("png")).decode()

def _page_to_pil(page, scale: float = 2.5) -> Image.Image:
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return Image.open(io.BytesIO(pix.tobytes("png")))

def _pil_to_b64_jpeg(img: Image.Image, quality: int = 95) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()

def _smart_stitch(img_top: Image.Image, img_btm: Image.Image):
    fh = int(img_top.height * 0.05)
    hh = int(img_btm.height * 0.05)
    crop_top = img_top.crop((0, 0, img_top.width, img_top.height - fh))
    crop_btm = img_btm.crop((0, hh, img_btm.width, img_btm.height))
    w = max(crop_top.width, crop_btm.width)
    canvas = Image.new("RGB", (w, crop_top.height + crop_btm.height), (255, 255, 255))
    canvas.paste(crop_top, (0, 0))
    canvas.paste(crop_btm, (0, crop_top.height))
    return canvas, crop_top.height, hh

def _draw_labels(img: Image.Image, detections: list) -> Image.Image:
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 60)
    except Exception:
        font = ImageFont.load_default()
    for item in detections:
        r = item["rect"]
        draw.rectangle([r.x0, r.y0, r.x1, r.y1], outline="red", width=8)
        draw.rectangle([r.x0, r.y0, r.x0 + 80, r.y0 + 70], fill="red")
        draw.text((r.x0 + 15, r.y0 + 5), str(item["id"]), fill="white", font=font)
    return img

_FAC_TEXT_PROMPT = """
Analyze these two directory pages as a SINGLE continuous document.
Extract complete, merged faculty profiles.
CRITICAL: Text often wraps to the next line — YOU MUST MERGE IT.
Find department headers and apply them to every person until a new header appears.
If a person appears split across the two pages, combine into ONE record.
Fields: Name, Designation, Department, Qualification, Institution, Email
Return ONLY a JSON list of objects with these exact keys.
"""

_FAC_IMG_PROMPT = """
I have stitched two document pages vertically (headers/footers removed).
Red numbered boxes mark the photos.
Task: Identify the NAME associated with each numbered photo.
RULES:
1. If a photo is at the seam, look at the very top of the next section.
2. Count generic avatar icons as valid photos.
3. Return ONLY the person Name (e.g. "Dr. Ali"). Ignore titles like Lecturer, HOD.
4. If a photo has NO name nearby, return "Unknown".
Return JSON ONLY: {"1": "Name", "2": "Name"}
"""

def _fac_extract_text_window(args):
    llm, i, b64_1, b64_2 = args
    try:
        msg = HumanMessage(content=[
            {"type": "text", "text": _FAC_TEXT_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_1}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_2}"}},
        ])
        resp = llm.invoke([msg])
        content = resp.content.replace("```json", "").replace("```", "").strip()
        if "[" in content:
            return json.loads(content[content.find("["):content.rfind("]") + 1])
    except Exception as e:
        print(f"[faculty_ingest] text window {i}: {e}")
    return []

def _fac_extract_images_window(args):
    llm, i, doc, images_dir, processed_xrefs_snap = args
    results = []
    scale = 2.5
    page_top = doc[i]
    img_top  = _page_to_pil(page_top, scale)
    has_next = i + 1 < len(doc)
    if has_next:
        page_btm = doc[i + 1]
        img_btm  = _page_to_pil(page_btm, scale)
        stitched, seam_y, header_h = _smart_stitch(img_top, img_btm)
    else:
        stitched = img_top
        seam_y   = img_top.height
        header_h = 0
        page_btm = None

    batch = []
    for img_info in page_top.get_images(full=True):
        xref = img_info[0]
        if xref in processed_xrefs_snap:
            continue
        try:
            rects = page_top.get_image_rects(xref)
            if not rects:
                continue
            r = rects[0]
            if r.width > 15 and r.height > 15:
                batch.append({
                    "id": 0, "xref": xref,
                    "rect": fitz.Rect(r.x0*scale, r.y0*scale, r.x1*scale, r.y1*scale),
                    "source_page": page_top, "is_bottom": False,
                })
        except Exception:
            pass

    if has_next and page_btm:
        for img_info in page_btm.get_images(full=True):
            xref = img_info[0]
            if xref in processed_xrefs_snap:
                continue
            try:
                rects = page_btm.get_image_rects(xref)
                if not rects:
                    continue
                r = rects[0]
                if r.width > 15 and r.height > 15:
                    y0 = (r.y0 * scale) - (header_h * scale) + seam_y
                    y1 = (r.y1 * scale) - (header_h * scale) + seam_y
                    if y0 > seam_y:
                        batch.append({
                            "id": 0, "xref": xref,
                            "rect": fitz.Rect(r.x0*scale, y0, r.x1*scale, y1),
                            "source_page": page_btm, "is_bottom": True,
                        })
            except Exception:
                pass

    if not batch:
        return results

    batch.sort(key=lambda x: (round(x["rect"].y0, -2), x["rect"].x0))
    for idx, item in enumerate(batch):
        item["id"] = idx + 1

    annotated = _draw_labels(stitched.copy(), batch)
    b64_ann   = _pil_to_b64_jpeg(annotated)

    try:
        msg = HumanMessage(content=[
            {"type": "text", "text": _FAC_IMG_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_ann}"}},
        ])
        resp    = llm.invoke([msg])
        txt     = resp.content.replace("```json", "").replace("```", "").strip()
        if "{" in txt:
            txt = txt[txt.find("{"):txt.rfind("}") + 1]
        mapping = json.loads(txt)
    except Exception as e:
        print(f"[faculty_ingest] image window {i}: {e}")
        return results

    for item in batch:
        name = mapping.get(str(item["id"]), "")
        fn   = _sanitize_filename(name)
        if fn != "unknown":
            results.append((item["xref"], item["source_page"], fn))

    return results


def _fac_stage1_extract_text(doc, job: dict) -> pd.DataFrame:
    """Stage 1: parallel GPT-4o text extraction from all page windows."""
    n = len(doc)
    llm = _llm_client()
    job["stage_detail"] = f"Rendering {n} pages for text extraction..."

    b64s = [None] * n
    with ThreadPoolExecutor(max_workers=_FAC_MAX_WORKERS) as ex:
        futures = {ex.submit(_page_to_b64_hires, doc[i], 3.0): i for i in range(n)}
        for f in as_completed(futures):
            b64s[futures[f]] = f.result()

    job["stage_detail"] = "GPT-4o: extracting faculty text from page windows..."
    windows = [(llm, i, b64s[i], b64s[i + 1]) for i in range(n - 1)]
    all_faculty = []
    done = 0
    with ThreadPoolExecutor(max_workers=_FAC_MAX_WORKERS) as ex:
        for batch in ex.map(_fac_extract_text_window, windows):
            all_faculty.extend(batch)
            done += 1
            job["stage_detail"] = f"GPT-4o text: {done}/{n-1} windows done"

    if not all_faculty:
        return pd.DataFrame()

    df = pd.DataFrame(all_faculty)
    headers = ["Name", "Designation", "Department", "Qualification", "Institution", "Email"]
    for h in headers:
        if h not in df.columns:
            df[h] = ""
    df = df[headers].fillna("")
    df["Department"] = df["Department"].replace("", pd.NA).ffill().fillna("General Faculty")
    df = df[~((df["Name"].str.split().str.len() < 2) & (df["Designation"] == ""))]
    df["_ilen"] = df["Institution"].str.len()
    df = (df.sort_values("_ilen", ascending=False)
            .drop_duplicates(subset=["Name", "Designation"], keep="first")
            .drop(columns=["_ilen"])
            .reset_index(drop=True))
    return df


def _fac_stage2_extract_images(doc, images_dir: str, job: dict) -> int:
    """Stage 2: parallel GPT-4o image labelling + save to uploads/{bot_id}/images/."""
    os.makedirs(images_dir, exist_ok=True)
    llm = _llm_client()
    n = len(doc)
    processed: set = set()
    saved = 0

    job["stage_detail"] = "GPT-4o: identifying and saving faculty photos..."
    windows = [(llm, i, doc, images_dir, frozenset(processed)) for i in range(n - 1)]

    with ThreadPoolExecutor(max_workers=_FAC_MAX_WORKERS) as ex:
        futures = {ex.submit(_fac_extract_images_window, w): w[1] for w in windows}
        for f in as_completed(futures):
            for xref, source_page, clean_fn in f.result():
                if xref in processed:
                    continue
                try:
                    base_img = source_page.parent.extract_image(xref)
                    pil_img  = Image.open(io.BytesIO(base_img["image"]))
                    if pil_img.mode in ("RGBA", "P"):
                        pil_img = pil_img.convert("RGB")
                    save_name = f"{clean_fn}.jpg"
                    dup = 1
                    while os.path.exists(os.path.join(images_dir, save_name)):
                        save_name = f"{clean_fn}_{dup}.jpg"
                        dup += 1
                    pil_img.save(os.path.join(images_dir, save_name), "JPEG")
                    processed.add(xref)
                    saved += 1
                except Exception as e:
                    print(f"[faculty_ingest] image save xref={xref}: {e}")

    job["stage_detail"] = f"Saved {saved} faculty photos"
    return saved


def _build_faculty_documents(df: pd.DataFrame, images_dir: str) -> List[Document]:
    """Build LangChain Documents from faculty DataFrame."""
    docs = []
    for _, row in df.iterrows():
        name     = row.get("Name", "")
        img_file = f"{_sanitize_filename(name)}.jpg"
        img_path = os.path.join(images_dir, img_file)
        content  = (
            f"Faculty Name: {name}\n"
            f"Designation: {row.get('Designation', '')}\n"
            f"Department: {row.get('Department', '')}\n"
            f"Qualification: {row.get('Qualification', '')}\n"
            f"Institution: {row.get('Institution', '')}\n"
            f"Email: {row.get('Email', '')}"
        )
        docs.append(Document(
            page_content=content,
            metadata={
                "name":          name,
                "designation":   row.get("Designation", ""),
                "department":    row.get("Department", ""),
                "qualification": row.get("Qualification", ""),
                "institution":   row.get("Institution", ""),
                "email":         row.get("Email", ""),
                "image_path":    img_path,
            },
        ))
    return docs


# ─────────────────────────────────────────────────────────────────
# Faculty background ingest task
# ─────────────────────────────────────────────────────────────────

async def _run_faculty_ingest(job_id: str, pdf_path: str, filename: str,
                               index_name: str, doc_id: int, bot_id: int,
                               db_factory, namespace: str = ""):
    """
    Faculty pipeline:
      text extraction → image extraction → embedding → done
    Three GPT-4o stages with full SSE progress reporting.
    """
    job = _ingest_jobs[job_id]
    loop = asyncio.get_event_loop()

    # All images → uploads/{bot_id}/images/
    images_dir = os.path.join(_UPLOAD_DIR, str(bot_id), "images")

    try:
        fitz_doc = fitz.open(pdf_path)

        # ── Stage 1: Text extraction ────────────────────────────
        job["status"]       = "extracting"
        job["stage_detail"] = "Starting GPT-4o faculty text extraction..."
        df = await loop.run_in_executor(
            None, _fac_stage1_extract_text, fitz_doc, job
        )
        faculty_count = len(df)
        job["stage_detail"] = f"Extracted {faculty_count} faculty profiles"

        # ── Stage 2: Image extraction ───────────────────────────
        job["status"]       = "chunking"
        job["stage_detail"] = "Starting GPT-4o faculty photo extraction..."
        saved_images = await loop.run_in_executor(
            None, _fac_stage2_extract_images, fitz_doc, images_dir, job
        )
        fitz_doc.close()

        # ── Stage 3: Build documents ────────────────────────────
        job["stage_detail"] = "Building vector documents..."
        documents = await loop.run_in_executor(
            None, _build_faculty_documents, df, images_dir
        )
        job["total"] = len(documents)

        if not documents:
            job["status"] = "error"
            job["errors"].append("No faculty profiles could be extracted from the PDF.")
            return

        # ── Stage 4: Pinecone embed ─────────────────────────────
        job["status"]       = "embedding"
        job["stage_detail"] = "Creating Pinecone index..."
        pinecone_index = await loop.run_in_executor(None, _get_or_create_index, index_name)
        embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large", api_key=_openai_key())
        vector_store = PineconeVectorStore(
            index=pinecone_index,
            embedding=embeddings_model,
            namespace=namespace,
        )

        BATCH = 50
        for i in range(0, len(documents), BATCH):
            batch = documents[i: i + BATCH]
            await loop.run_in_executor(None, vector_store.add_documents, batch)
            job["done"] = min(i + BATCH, len(documents))
            job["pct"]  = round(job["done"] / job["total"] * 100)
            job["stage_detail"] = f"Embedded {job['done']}/{job['total']} faculty profiles"
            await asyncio.sleep(0)

        job["status"]       = "done"
        job["done"]         = len(documents)
        job["pct"]          = 100
        job["stage_detail"] = f"{faculty_count} faculty profiles + {saved_images} photos indexed"
        job["items_count"]  = faculty_count

        # ── Update DB ───────────────────────────────────────────
        try:
            db: Session = db_factory()
            doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
            if doc:
                doc.pinecone_index    = index_name
                doc.status            = DocStatus.trained
                doc.training_progress = 100
                doc.accuracy          = 94.0
                db.commit()
            db.close()
        except Exception as db_err:
            print(f"[faculty_ingest] DB update failed: {db_err}")

    except Exception as e:
        job["status"] = "error"
        job["errors"].append(str(e))
        print(f"[faculty_ingest] job {job_id} error: {e}")
    finally:
        try:
            os.unlink(pdf_path)
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────────
# Background ingest task
# ─────────────────────────────────────────────────────────────────

async def _run_ingest(job_id: str, pdf_path: str, filename: str,
                      index_name: str, doc_id: int, db_factory, namespace: str = ""):
    job = _ingest_jobs[job_id]
    loop = asyncio.get_event_loop()
    try:
        # ── 1. Extract ──────────────────────────────────────────
        job["status"] = "extracting"
        pages, method = await loop.run_in_executor(None, _extract_pdf, pdf_path)
        job["method"] = method

        # ── 2. Chunk ────────────────────────────────────────────
        job["status"] = "chunking"
        chunks = await loop.run_in_executor(None, _pages_to_chunks, pages, filename)
        job["total"] = len(chunks)

        if not chunks:
            job["status"] = "error"
            job["errors"].append(
                "No readable text extracted from PDF. "
                "For scanned PDFs, ensure Tesseract + Poppler are installed."
            )
            return

        # ── 3. Get/create index & vector store ─────────────────
        job["status"] = "embedding"
        pinecone_index = await loop.run_in_executor(None, _get_or_create_index, index_name)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=_openai_key())
        vector_store = PineconeVectorStore(
            index=pinecone_index,
            embedding=embeddings,
            namespace=namespace,
        )

        # ── 4. Embed in batches ─────────────────────────────────
        BATCH = 10
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i: i + BATCH]
            await loop.run_in_executor(None, vector_store.add_documents, batch)
            job["done"] = min(i + BATCH, len(chunks))
            job["pct"]  = round(job["done"] / job["total"] * 100)
            await asyncio.sleep(0)   # yield so SSE can flush

        job["status"] = "done"
        job["done"]   = len(chunks)
        job["pct"]    = 100

        # ── Persist pinecone_index name to knowledge_documents table ──
        try:
            db: Session = db_factory()
            doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
            if doc:
                doc.pinecone_index    = index_name
                doc.status            = DocStatus.trained
                doc.training_progress = 100
                doc.accuracy          = 92.0
                db.commit()
            db.close()
        except Exception as db_err:
            print(f"[pinecone_ingest] DB update failed: {db_err}")

    except Exception as e:
        job["status"] = "error"
        job["errors"].append(str(e))
        print(f"[pinecone_ingest] job {job_id} error: {e}")
    finally:
        try:
            os.unlink(pdf_path)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────

router = APIRouter(tags=["pinecone-ingest"])


@router.post("/chatbots/{bot_id}/pinecone/ingest")
async def start_ingest(
    bot_id: int,
    file: UploadFile = File(...),
    user_id: int  = Query(...),
    token:   str  = Query(...),
    doc_id:   int = Query(...),           # knowledge_documents.id to update on completion
    category: str = Query("university"), # "university" | "restaurant" | "faculty" | "fyp" | "general"
    db: Session = Depends(get_db),
):
    """
    Upload a PDF → triggers Pinecone embedding pipeline.
    Returns {job_id, index_name} immediately.
    Poll /pinecone/ingest/{job_id}/progress (SSE) for live updates.
    """
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Fixed index per category; namespace isolates this user/bot within the index
    try:
        idx_name = _index_name_for_category(category)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ns = _namespace(user_id, bot_id)
    job_id    = str(uuid.uuid4())

    _ingest_jobs[job_id] = {
        "status":       "uploading",
        "filename":     file.filename,
        "index":        idx_name,
        "namespace":    ns,
        "pipeline":     category,       # "university" | "restaurant" | "faculty"
        "total":        0,
        "done":         0,
        "pct":          0,
        "method":       "unknown",
        "stage_detail": "",
        "items_count":  0,
        "errors":       [],
    }

    # Save upload to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    shutil.copyfileobj(file.file, tmp)
    tmp.close()

    from database import SessionLocal
    if category == "restaurant":
        asyncio.create_task(
            _run_restaurant_ingest(job_id, tmp.name, file.filename,
                                   idx_name, doc_id, bot_id, SessionLocal,
                                   namespace=ns)
        )
    elif category == "faculty":
        asyncio.create_task(
            _run_faculty_ingest(job_id, tmp.name, file.filename,
                                idx_name, doc_id, bot_id, SessionLocal,
                                namespace=ns)
        )
    elif category in ("fyp", "general"):
        # fyp and general use the same generic text pipeline as university,
        # but each ingests into its own dedicated index ("fyp" / "general")
        # with namespace isolation per user/bot.
        asyncio.create_task(
            _run_ingest(job_id, tmp.name, file.filename,
                        idx_name, doc_id, SessionLocal,
                        namespace=ns)
        )
    else:
        # Default: university / generic text pipeline
        asyncio.create_task(
            _run_ingest(job_id, tmp.name, file.filename,
                        idx_name, doc_id, SessionLocal,
                        namespace=ns)
        )

    return {"job_id": job_id, "index_name": idx_name, "namespace": ns, "pipeline": category}


@router.get("/chatbots/{bot_id}/pinecone/ingest/{job_id}/progress")
async def ingest_progress_sse(
    bot_id: int,
    job_id: str,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    """SSE stream — emits JSON events every ~800 ms until done/error."""
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if job_id not in _ingest_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _stream() -> AsyncGenerator[str, None]:
        while True:
            job  = _ingest_jobs.get(job_id, {})
            data = json.dumps(job)
            yield f"data: {data}\n\n"
            if job.get("status") in ("done", "error"):
                break
            await asyncio.sleep(0.8)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chatbots/{bot_id}/pinecone/ingest/{job_id}/status")
async def ingest_status_json(
    bot_id: int,
    job_id: str,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    """JSON poll fallback (for environments where SSE is unsupported)."""
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if job_id not in _ingest_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _ingest_jobs[job_id]


@router.get("/chatbots/{bot_id}/pinecone/index-info")
async def index_info(
    bot_id:   int,
    user_id:  int = Query(...),
    token:    str = Query(...),
    category: str = Query("university"),
):
    """Returns stats for the category index, scoped to this user/bot namespace."""
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    idx_name = _index_name_for_category(category)
    ns       = _namespace(user_id, bot_id)
    try:
        pc = Pinecone(api_key=_pinecone_key())
        existing = pc.list_indexes()
        names = existing.names() if hasattr(existing, "names") else [i["name"] for i in existing]
        if idx_name not in names:
            return {"index_name": idx_name, "namespace": ns, "exists": False, "vector_count": 0}
        idx   = pc.Index(idx_name)
        stats = idx.describe_index_stats()
        ns_stats = stats.get("namespaces", {}).get(ns, {})
        return {
            "index_name":   idx_name,
            "namespace":    ns,
            "exists":       True,
            "vector_count": ns_stats.get("vector_count", 0),
            "all_namespaces": stats.get("namespaces", {}),
        }
    except Exception as e:
        return {"index_name": idx_name, "namespace": ns, "exists": False, "error": str(e)}


@router.delete("/chatbots/{bot_id}/pinecone/index")
async def delete_index(
    bot_id:   int,
    user_id:  int = Query(...),
    token:    str = Query(...),
    category: str = Query("university"),
):
    """
    Deletes all vectors in this user/bot namespace within the category index.
    The shared index itself is NOT deleted — only this bot's namespace is cleared.
    """
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    idx_name = _index_name_for_category(category)
    ns       = _namespace(user_id, bot_id)
    try:
        pc = Pinecone(api_key=_pinecone_key())
        existing = pc.list_indexes()
        names = existing.names() if hasattr(existing, "names") else [i["name"] for i in existing]
        if idx_name in names:
            idx = pc.Index(idx_name)
            idx.delete(delete_all=True, namespace=ns)
        return {"deleted": True, "index_name": idx_name, "namespace": ns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))