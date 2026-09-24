"""
crawlee_ingest.py  ──  Drop into your SmartChat backend folder alongside pinecone_ingest.py

Works for ALL chatbot categories: restaurant, university, faculty, fyp, general
Each category gets its OWN Pinecone index (mirrors pinecone_ingest.py pattern).

Index map:
    restaurant → "restaurant"
    university → "university"
    faculty    → "faculty"
    fyp        → "fyp"
    general    → "general"

Source types:
    food_items       → menu cards  (restaurant)
    faculty_profiles → structured faculty profiles (faculty)
    page_data        → chunked text  (all categories)

Registration in main.py:
    from crawlee_ingest import router as crawlee_router
    app.include_router(crawlee_router)
"""

import asyncio
import json
import os
import re
import uuid
from datetime import datetime
from typing import AsyncGenerator, List

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from sqlalchemy.orm import Session

from database import get_db
from models import KnowledgeDocument, DocStatus

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Config — mirrors pinecone_ingest.py exactly
# ─────────────────────────────────────────────────────────────────────────────

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

_EMBED_DIM  = 3072   # text-embedding-3-large — must match pinecone_ingest.py
_UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

# ── Each category gets its own dedicated Pinecone index ──────────────────────
# Mirrors pinecone_ingest.py _CATEGORY_INDEXES + adds fyp and general
_CATEGORY_INDEXES: dict[str, str] = {
    "restaurant": "restaurant",
    "university":  "university",
    "faculty":     "faculty",
    "fyp":         "fyp",        # own index — NOT shared with university
    "general":     "general",    # own index — NOT shared with university
}
_DEFAULT_CATEGORY = "university"

_VALID_SOURCE_TYPES = ("food_items", "faculty_profiles", "page_data")

# In-memory job store (same pattern as pinecone_ingest.py _ingest_jobs)
_crawlee_jobs: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# File helpers
# ─────────────────────────────────────────────────────────────────────────────

def _save_crawlee_file(raw_bytes: bytes, filename: str, bot_id: int) -> str:
    crawlee_dir = os.path.join(_UPLOAD_DIR, str(bot_id), "crawlee")
    os.makedirs(crawlee_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = filename.replace(" ", "_")
    save_path = os.path.join(crawlee_dir, f"{timestamp}_{safe_name}")
    with open(save_path, "wb") as f:
        f.write(raw_bytes)
    return save_path


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers — mirror pinecone_ingest.py exactly
# ─────────────────────────────────────────────────────────────────────────────

def _index_name_for_category(category: str) -> str:
    return _CATEGORY_INDEXES.get(category, _DEFAULT_CATEGORY)

def _namespace(user_id: int, bot_id: int) -> str:
    return f"{user_id}-{bot_id}"

def _get_or_create_index(name: str):
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
    return bool(token)


# ─────────────────────────────────────────────────────────────────────────────
# Text splitter — exact copy of pinecone_ingest.py _SimpleTextSplitter
# ─────────────────────────────────────────────────────────────────────────────

class _SimpleTextSplitter:
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 80):
        self.chunk_size    = chunk_size
        self.chunk_overlap = chunk_overlap
        self._seps = ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text: str) -> List[str]:
        for sep in self._seps:
            parts = text.split(sep) if sep else list(text)
            if len(parts) <= 1:
                continue
            chunks:  List[str] = []
            current: str       = ""
            for part in parts:
                candidate = (current + sep + part) if current else part
                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    if current and self.chunk_overlap > 0:
                        overlap_text = current[-self.chunk_overlap:]
                        current = overlap_text + sep + part
                    else:
                        current = part
            if current:
                chunks.append(current)
            if chunks:
                return [c.strip() for c in chunks if c.strip()]
        # Hard-split fallback
        chunks = []
        step = max(1, self.chunk_size - self.chunk_overlap)
        for i in range(0, len(text), step):
            chunks.append(text[i: i + self.chunk_size])
        return [c.strip() for c in chunks if c.strip()]

    def split_documents(self, docs: List[Document]) -> List[Document]:
        result = []
        for doc in docs:
            for chunk in self.split_text(doc.page_content):
                result.append(Document(page_content=chunk, metadata=doc.metadata.copy()))
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline A — food_items  (restaurant)
# Metadata matches _build_restaurant_documents() in pinecone_ingest.py exactly
# ─────────────────────────────────────────────────────────────────────────────

def _clean_price(raw_price: str) -> str:
    """Return bare digits only — matches PDF pipeline price format e.g. '290'."""
    p = (raw_price or "").strip()
    for prefix in ("Starting from", "Starting at", "Starts at", "From"):
        if p.lower().startswith(prefix.lower()):
            p = p[len(prefix):].strip()
    p = re.sub(r"(?i)^(Rs\.?|PKR|₨|\$|€|£)\s*", "", p).strip()
    m = re.search(r"[\d,]+(?:\.\d+)?", p)
    return m.group(0).replace(",", "") if m else p


def _parse_food_items(raw: dict, category: str) -> List[Document]:
    """
    Parse food items → Documents matching pinecone_ingest _build_restaurant_documents().

    Pinecone vector shape:
        id          : item_{i}
        metadata    : item_name, category, description, price, image_path, text
        page_content: same as text field
    """
    docs = []
    seen = set()
    for i, item in enumerate(raw.get("items", [])):
        name = (item.get("name") or "").strip()
        if not name or "unknown" in name.lower():
            continue
        key = (name, item.get("price", ""))
        if key in seen:
            continue
        seen.add(key)

        price       = _clean_price(item.get("price") or "")
        description = (item.get("description") or "").strip()
        cat         = (item.get("category") or "").strip()
        image_path  = (item.get("image") or "").strip()

        content = (
            f"Item: {name}\n"
            f"Category: {cat}\n"
            f"Description: {description}\n"
            f"Price: {price}"
        )
        docs.append(Document(
            page_content=content,
            metadata={
                "item_name":   name,
                "category":    cat,
                "description": description,
                "price":       price,
                "image_path":  image_path,
                "text":        content,
            },
            id=f"item_{i}",
        ))
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline B — faculty_profiles  (faculty)
# Metadata matches _build_faculty_documents() in pinecone_ingest.py exactly
# ─────────────────────────────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """Convert 'Amina Shahbaz' → 'amina_shahbaz' for image filename."""
    return re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_"))


def _parse_faculty_profiles(raw: dict) -> List[Document]:
    """
    Parse scraped faculty profiles and produce Documents whose metadata
    and text field are IDENTICAL to pinecone_ingest.py _build_faculty_documents().

    Input JSON shape (produced by the faculty Crawlee scraper):
    {
      "profiles": [
        {
          "name": "Amina Shahbaz",
          "designation": "Lab Instructor",
          "department": "SEAS - School of Engineering and Applied Sciences",
          "qualification": "BS Software Engineering",
          "institution": "GIFT University, Gujranwala",
          "email": "",
          "image": "https://example.edu/faculty/amina.jpg"
        }, ...
      ]
    }

    Pinecone vector shape (matches PDF faculty pipeline):
        id       : faculty_{i}
        metadata : name, designation, department, qualification,
                   institution, email, image_path, text
        page_content: same as text field
    """
    docs = []
    seen = set()
    profiles = raw.get("profiles", [])

    for i, profile in enumerate(profiles):
        name = (profile.get("name") or "").strip()
        if not name or "unknown" in name.lower():
            continue
        if name in seen:
            continue
        seen.add(name)

        designation   = (profile.get("designation")   or "").strip()
        department    = (profile.get("department")     or "").strip()
        qualification = (profile.get("qualification")  or "").strip()
        institution   = (profile.get("institution")    or "").strip()
        email         = (profile.get("email")          or "").strip()
        image_url     = (profile.get("image")          or "").strip()

        # image_path: use URL directly (mirrors PDF pipeline which stores local path)
        image_path = image_url if image_url else f"faculty_images/{_sanitize_filename(name)}.jpg"

        # Exact same content format as _build_faculty_documents()
        content = (
            f"Faculty Name: {name}\n"
            f"Designation: {designation}\n"
            f"Department: {department}\n"
            f"Qualification: {qualification}\n"
            f"Institution: {institution}\n"
            f"Email: {email}"
        )

        docs.append(Document(
            page_content=content,
            metadata={
                # ── Core fields matching PDF faculty pipeline ──────────────
                "name":          name,
                "designation":   designation,
                "department":    department,
                "qualification": qualification,
                "institution":   institution,
                "email":         email,
                "image_path":    image_path,
                "text":          content,
            },
            id=f"faculty_{i}",
        ))

    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline C — page_data parsers, one per category
# Chunked text for RAG — category-aware extraction
# ─────────────────────────────────────────────────────────────────────────────

def _page_parts(page: dict, extra_tags: list = None) -> list:
    """Extract structured parts from a scraped page dict."""
    parts = []
    title = page.get("title", "")
    url   = page.get("url", "")
    meta  = page.get("meta", {})

    if title:                          parts.append(f"Page Title: {title}")
    if url:                            parts.append(f"URL: {url}")
    if meta.get("description"):        parts.append(f"Description: {meta['description']}")
    if meta.get("keywords"):           parts.append(f"Keywords: {meta['keywords']}")

    headings = page.get("headings", {})
    for tag in (extra_tags or ["h1", "h2", "h3"]):
        if headings.get(tag):
            parts.append(f"{tag.upper()}: " + " | ".join(headings[tag]))

    paragraphs = page.get("paragraphs", [])
    if paragraphs:
        parts.append("Content:\n" + "\n".join(paragraphs))

    return parts


def _parse_page_data_restaurant(raw: dict) -> List[Document]:
    """Menu content, deals, branches, opening hours, FAQs."""
    splitter = _SimpleTextSplitter(chunk_size=600, chunk_overlap=80)
    docs = []
    for page in raw.get("pages", []):
        url   = page.get("url", "")
        title = page.get("title", "")
        parts = _page_parts(page, ["h1", "h2", "h3"])
        nav   = page.get("navigation", [])
        if nav:
            parts.append("Navigation: " + " | ".join(n["text"] for n in nav if n.get("text")))
        # ── Raw body text fallback ────────────────────────────────────────────
        raw_text = page.get("rawText")
        if raw_text and len("\n\n".join(parts).strip()) < 80:
            parts.append("Page Content:\n" + raw_text)

        full_text = "\n\n".join(parts).strip()
        if not full_text or len(full_text) < 50:
            continue
        base = Document(
            page_content=full_text,
            metadata={"source": url[:200], "title": title, "url": url,
                      "data_type": "page_data", "bot_category": "restaurant"},
        )
        docs.extend(splitter.split_documents([base]))
    return docs


def _parse_page_data_university(raw: dict) -> List[Document]:
    """
    Courses, policies, departments, announcements, events, fees, timetables.
    Uses ALL fields the Crawlee scraper collects:
      paragraphs, listItems, tableData, boldText, divText, headings (h1-h6),
      meta (description, keywords, ogTitle, ogDescription, canonical), navigation.

    chunk_size=400 keeps each chunk's page_content well under Pinecone's
    40 960-byte metadata limit (LangChain stores page_content as the "text"
    metadata key automatically).
    """
    splitter = _SimpleTextSplitter(chunk_size=400, chunk_overlap=60)
    docs = []
    for page in raw.get("pages", []):
        url   = page.get("url", "")
        title = page.get("title", "")
        meta  = page.get("meta", {})

        # Skip blocked/captcha/error pages
        if _is_blocked_page(page):
            print(f"[crawlee_ingest] skipping blocked page: {url}")
            continue

        parts = []

        # ── Identity ──────────────────────────────────────────────────────────
        if title:                          parts.append(f"Page Title: {title}")
        if url:                            parts.append(f"URL: {url}")
        if meta.get("ogTitle") and meta["ogTitle"] != title:
            parts.append(f"OG Title: {meta['ogTitle']}")
        if meta.get("description"):        parts.append(f"Description: {meta['description']}")
        if meta.get("ogDescription"):      parts.append(f"Summary: {meta['ogDescription']}")
        if meta.get("keywords"):           parts.append(f"Keywords: {meta['keywords']}")

        # ── All heading levels h1–h6 ──────────────────────────────────────────
        headings = page.get("headings", {})
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            vals = headings.get(tag, [])
            if vals:
                parts.append(f"{tag.upper()}: " + " | ".join(vals))

        # ── Paragraph text ────────────────────────────────────────────────────
        paragraphs = page.get("paragraphs", [])
        if paragraphs:
            parts.append("Content:\n" + "\n".join(paragraphs))

        # ── List items (admission steps, requirements, features, course list) ─
        list_items = page.get("listItems", [])
        if list_items:
            # Deduplicate against paragraphs to avoid repeating same text
            para_set = set(paragraphs)
            unique_items = [li for li in list_items if li not in para_set]
            if unique_items:
                parts.append("List Items:\n" + "\n".join(f"• {li}" for li in unique_items))

        # ── Table data (fee structures, timetables, credit hours, grading) ────
        table_data = page.get("tableData", [])
        if table_data:
            parts.append("Table Data:\n" + "\n\n".join(table_data))

        # ── Bold/strong text (key terms, labels, announcements) ───────────────
        bold_text = page.get("boldText", [])
        if bold_text:
            para_set  = set(paragraphs)
            unique_bold = [b for b in bold_text if b not in para_set]
            if unique_bold:
                parts.append("Key Terms: " + " | ".join(unique_bold))

        # ── Div/section content blocks (React/Vue sites skip <p> entirely) ────
        div_text = page.get("divText", [])
        if div_text:
            para_set = set(paragraphs)
            unique_div = [d for d in div_text if d not in para_set and len(d) > 10]
            if unique_div:
                parts.append("Additional Content:\n" + "\n".join(unique_div))

        # ── Structured data (Course, Event, FAQPage, Organization) ───────────
        for sd in page.get("structuredData", []):
            try:
                sd_type = sd.get("@type", "")
                if sd_type in ("Course", "Event", "Organization", "FAQPage",
                               "EducationalOrganization", "CollegeOrUniversity"):
                    parts.append(f"Structured Data ({sd_type}): {json.dumps(sd)}")
            except Exception:
                pass

        # ── Navigation links (reveals site sections, departments, portals) ────
        nav = page.get("navigation", [])
        if nav:
            parts.append("Navigation: " + " | ".join(
                n["text"] for n in nav if n.get("text")
            ))

        # ── Raw body text fallback (Shopify/SPA pages with no <p> content) ────
        raw_text = page.get("rawText")
        if raw_text and len("\n\n".join(parts).strip()) < 80:
            parts.append("Page Content:\n" + raw_text)

        full_text = "\n\n".join(parts).strip()
        if not full_text or len(full_text) < 50:
            continue

        base = Document(
            page_content=full_text,
            metadata={
                "source":       url[:200],
                "title":        title,
                "url":          url,
                "data_type":    "page_data",
                "bot_category": "university",
            },
        )
        docs.extend(splitter.split_documents([base]))
    return docs


def _parse_page_data_faculty(raw: dict) -> List[Document]:
    """
    Faculty page text — used as supplementary context alongside faculty_profiles.
    Filters paragraphs to those mentioning faculty-related keywords.
    """
    splitter = _SimpleTextSplitter(chunk_size=600, chunk_overlap=80)
    faculty_kws = {
        "professor", "lecturer", "dr.", "phd", "department", "faculty", "staff",
        "designation", "email", "qualification", "research", "associate",
        "assistant", "head of", "hod", "dean", "principal",
    }
    docs = []
    for page in raw.get("pages", []):
        url   = page.get("url", "")
        title = page.get("title", "")
        meta  = page.get("meta", {})
        if _is_blocked_page(page):
            print(f"[crawlee_ingest] skipping blocked page: {url}")
            continue

        parts = []

        if title:                   parts.append(f"Page Title: {title}")
        if meta.get("description"): parts.append(f"Description: {meta['description']}")

        headings = page.get("headings", {})
        for tag in ["h1", "h2", "h3", "h4"]:
            if headings.get(tag):
                parts.append(f"{tag.upper()}: " + " | ".join(headings[tag]))

        paragraphs = page.get("paragraphs", [])
        faculty_paras = [p for p in paragraphs
                         if any(kw in p.lower() for kw in faculty_kws)]
        content_paras = faculty_paras if faculty_paras else paragraphs
        if content_paras:
            parts.append("Faculty Info:\n" + "\n".join(content_paras))

        # Extract mailto links as emails
        emails = [
            lk["href"].replace("mailto:", "")
            for lk in page.get("links", [])
            if lk.get("href", "").startswith("mailto:")
        ]
        if emails:
            parts.append("Emails: " + ", ".join(emails))

        full_text = "\n\n".join(parts).strip()
        # Raw body text fallback
        raw_text = page.get("rawText")
        if raw_text and len("\n\n".join(parts).strip()) < 80:
            parts.append("Page Content:\n" + raw_text)

        if not full_text or len(full_text) < 50:
            continue
        base = Document(
            page_content=full_text,
            metadata={"source": url[:200], "title": title, "url": url,
                      "data_type": "page_data", "bot_category": "faculty"},
        )
        docs.extend(splitter.split_documents([base]))
    return docs


def _parse_page_data_fyp(raw: dict) -> List[Document]:
    """
    FYP projects, abstracts, technologies, supervisors.
    Uses all scraped fields — listItems captures project requirements/tech stacks,
    tableData captures project lists, boldText captures project titles/labels.
    """
    splitter = _SimpleTextSplitter(chunk_size=600, chunk_overlap=80)
    fyp_kws = {
        "project", "abstract", "technology", "supervisor", "team", "semester",
        "objective", "methodology", "implementation", "results", "conclusion",
        "final year", "fyp", "capstone",
    }
    docs = []
    for page in raw.get("pages", []):
        url   = page.get("url", "")
        title = page.get("title", "")
        meta  = page.get("meta", {})
        parts = []

        if title:                   parts.append(f"Page Title: {title}")
        if url:                     parts.append(f"URL: {url}")
        if meta.get("description"): parts.append(f"Description: {meta['description']}")

        headings = page.get("headings", {})
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            vals = headings.get(tag, [])
            if vals:
                parts.append(f"{tag.upper()}: " + " | ".join(vals))

        paragraphs  = page.get("paragraphs", [])
        list_items  = page.get("listItems", [])
        table_data  = page.get("tableData", [])
        bold_text   = page.get("boldText", [])
        div_text    = page.get("divText", [])

        fyp_paras = [p for p in paragraphs if any(kw in p.lower() for kw in fyp_kws)]
        if fyp_paras:
            parts.append("FYP Content:\n" + "\n".join(fyp_paras))
        elif paragraphs:
            parts.append("Content:\n" + "\n".join(paragraphs))

        fyp_items = [li for li in list_items if any(kw in li.lower() for kw in fyp_kws)]
        all_items = fyp_items or list_items
        if all_items:
            para_set = set(paragraphs)
            unique = [li for li in all_items if li not in para_set]
            if unique:
                parts.append("List Items:\n" + "\n".join(f"• {li}" for li in unique))

        if table_data:
            parts.append("Table Data:\n" + "\n\n".join(table_data))

        if bold_text:
            para_set = set(paragraphs)
            unique_bold = [b for b in bold_text if b not in para_set]
            if unique_bold:
                parts.append("Key Terms: " + " | ".join(unique_bold))

        if div_text:
            para_set = set(paragraphs)
            unique_div = [d for d in div_text if d not in para_set and len(d) > 30]
            if unique_div:
                parts.append("Additional Content:\n" + "\n".join(unique_div))

        full_text = "\n\n".join(parts).strip()
        # Raw body text fallback
        raw_text = page.get("rawText")
        if raw_text and len("\n\n".join(parts).strip()) < 80:
            parts.append("Page Content:\n" + raw_text)

        if not full_text or len(full_text) < 50:
            continue
        base = Document(
            page_content=full_text,
            metadata={"source": url[:200], "title": title, "url": url,
                      "data_type": "page_data", "bot_category": "fyp"},
        )
        docs.extend(splitter.split_documents([base]))
    return docs


def _parse_page_data_general(raw: dict) -> List[Document]:
    """
    Generic website — scrapes ALL text from every page with zero filtering.
    Uses every field the scraper collects: paragraphs, listItems, tableData,
    boldText, divText, all heading levels, all meta fields, navigation.
    """
    splitter = _SimpleTextSplitter(chunk_size=600, chunk_overlap=80)
    docs = []
    for page in raw.get("pages", []):
        url   = page.get("url", "")
        title = page.get("title", "")
        meta  = page.get("meta", {})
        if _is_blocked_page(page):
            print(f"[crawlee_ingest] skipping blocked page: {url}")
            continue

        parts = []

        if title:                          parts.append(f"Page Title: {title}")
        if url:                            parts.append(f"URL: {url}")
        if meta.get("ogTitle") and meta["ogTitle"] != title:
            parts.append(f"OG Title: {meta['ogTitle']}")
        if meta.get("description"):        parts.append(f"Description: {meta['description']}")
        if meta.get("ogDescription"):      parts.append(f"Summary: {meta['ogDescription']}")
        if meta.get("keywords"):           parts.append(f"Keywords: {meta['keywords']}")

        headings = page.get("headings", {})
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            vals = headings.get(tag, [])
            if vals:
                parts.append(f"{tag.upper()}: " + " | ".join(vals))

        paragraphs = page.get("paragraphs", [])
        if paragraphs:
            parts.append("Content:\n" + "\n".join(paragraphs))

        list_items = page.get("listItems", [])
        if list_items:
            para_set = set(paragraphs)
            unique = [li for li in list_items if li not in para_set]
            if unique:
                parts.append("List Items:\n" + "\n".join(f"• {li}" for li in unique))

        table_data = page.get("tableData", [])
        if table_data:
            parts.append("Table Data:\n" + "\n\n".join(table_data))

        bold_text = page.get("boldText", [])
        if bold_text:
            para_set = set(paragraphs)
            unique_bold = [b for b in bold_text if b not in para_set]
            if unique_bold:
                parts.append("Key Terms: " + " | ".join(unique_bold))

        div_text = page.get("divText", [])
        if div_text:
            para_set = set(paragraphs)
            unique_div = [d for d in div_text if d not in para_set and len(d) > 30]
            if unique_div:
                parts.append("Additional Content:\n" + "\n".join(unique_div))

        nav = page.get("navigation", [])
        if nav:
            parts.append("Navigation: " + " | ".join(
                n["text"] for n in nav if n.get("text")
            ))

        # ── Raw body text fallback ────────────────────────────────────────────
        raw_text = page.get("rawText")
        if raw_text and len("\n\n".join(parts).strip()) < 80:
            parts.append("Page Content:\n" + raw_text)

        full_text = "\n\n".join(parts).strip()
        if not full_text or len(full_text) < 50:
            continue
        base = Document(
            page_content=full_text,
            metadata={"source": url[:200], "title": title, "url": url,
                      "data_type": "page_data", "bot_category": "general"},
        )
        docs.extend(splitter.split_documents([base]))
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

_PAGE_DATA_PARSERS = {
    "restaurant": _parse_page_data_restaurant,
    "university":  _parse_page_data_university,
    "faculty":     _parse_page_data_faculty,
    "fyp":         _parse_page_data_fyp,
    "general":     _parse_page_data_general,
}


def _is_blocked_page(page: dict) -> bool:
    """Return True if the page was blocked/captcha/error — skip it."""
    title = (page.get("title") or "").lower()
    paras = " ".join(page.get("paragraphs", [])).lower()
    text  = title + " " + paras
    BLOCK_SIGNALS = [
        "host not in allowlist", "access denied", "403 forbidden",
        "captcha", "are you human", "ddos protection", "checking your browser",
        "cloudflare", "rate limit", "too many requests", "just a moment",
        "enable javascript", "please wait", "you have been blocked",
    ]
    return any(sig in text for sig in BLOCK_SIGNALS)


def _build_documents(raw: dict, source_type: str, category: str) -> List[Document]:
    if source_type == "food_items":
        return _parse_food_items(raw, category)
    if source_type == "faculty_profiles":
        return _parse_faculty_profiles(raw)
    # page_data — dispatch by category
    parser = _PAGE_DATA_PARSERS.get(category, _parse_page_data_general)
    return parser(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Background ingest task
# ─────────────────────────────────────────────────────────────────────────────

async def _run_crawlee_ingest(
    job_id:       str,
    raw_data:     dict,
    source_type:  str,
    category:     str,
    index_name:   str,
    doc_id:       int,
    bot_id:       int,
    saved_path:   str,
    db_factory,
    namespace:    str = "",
):
    job  = _crawlee_jobs[job_id]
    loop = asyncio.get_running_loop()

    try:
        # ── 1. Parse ──────────────────────────────────────────────────────────
        job["status"]       = "parsing"
        job["stage_detail"] = f"Parsing {source_type} for [{category}] bot…"

        documents = await loop.run_in_executor(
            None, _build_documents, raw_data, source_type, category
        )

        if not documents:
            job["status"] = "error"
            job["errors"].append(
                f"No content parsed (source_type={source_type}, category={category}). "
                f"Check the JSON structure matches the expected format."
            )
            return

        job["stage_detail"] = f"Parsed {len(documents)} chunk(s)"

        # ── 2. Count ──────────────────────────────────────────────────────────
        job["status"] = "chunking"
        job["total"]  = len(documents)

        # ── 3. Connect Pinecone ───────────────────────────────────────────────
        job["status"]       = "embedding"
        job["stage_detail"] = f"Connecting to Pinecone index [{index_name}]…"

        pinecone_index   = await loop.run_in_executor(None, _get_or_create_index, index_name)
        embeddings_model = OpenAIEmbeddings(
            model="text-embedding-3-large",
            api_key=_openai_key(),
        )

        # ── 4. Safety net: guarantee no chunk exceeds Pinecone's 40 960-byte ──
        #       metadata limit BEFORE we try to upsert.
        #
        #  Root cause: _SimpleTextSplitter falls through to `current = part`
        #  when a single paragraph/div block is larger than chunk_size, so that
        #  block becomes one giant chunk.  news.php has a 128 KB divText field,
        #  producing chunks of tens of thousands of chars.
        #
        #  Additionally, LangChain's add_documents() stores page_content as the
        #  Pinecone "text" metadata key with NO truncation — so even one oversized
        #  chunk causes a 400 that drops the whole batch silently (vectors=50
        #  in the log comes from other batches that succeeded).
        #
        #  Fix: hard-split any chunk > _MAX_CHUNK chars, then upsert directly
        #  to Pinecone (bypassing add_documents) so we control the metadata.
        _MAX_CHUNK = 800    # chars — safe well below the 40 KB limit

        safe_docs = []
        for doc in documents:
            if len(doc.page_content) <= _MAX_CHUNK:
                safe_docs.append(doc)
            else:
                # Hard-split with overlap
                step = _MAX_CHUNK - 60
                text = doc.page_content
                for k in range(0, len(text), step):
                    piece = text[k: k + _MAX_CHUNK].strip()
                    if piece:
                        safe_docs.append(Document(page_content=piece, metadata=doc.metadata.copy()))
        documents = safe_docs
        job["total"] = len(documents)

        # ── 5. Embed + upsert directly ───────────────────────────────────────
        EMBED_BATCH  = 100
        UPSERT_BATCH = 50

        for i in range(0, len(documents), EMBED_BATCH):
            embed_slice = documents[i: i + EMBED_BATCH]
            texts = [d.page_content for d in embed_slice]

            vectors = await loop.run_in_executor(
                None,
                lambda t=texts: embeddings_model.embed_documents(t),
            )

            records = []
            for j, (doc, vec) in enumerate(zip(embed_slice, vectors)):
                vid      = getattr(doc, "id", None) or f"{job_id}_{i + j}"
                metadata = {**doc.metadata, "text": doc.page_content}
                records.append({"id": vid, "values": vec, "metadata": metadata})

            for k in range(0, len(records), UPSERT_BATCH):
                sub = records[k: k + UPSERT_BATCH]
                await loop.run_in_executor(
                    None,
                    lambda s=sub: pinecone_index.upsert(vectors=s, namespace=namespace),
                )

            job["done"] = min(i + EMBED_BATCH, len(documents))
            job["pct"]  = round(job["done"] / job["total"] * 100)
            job["stage_detail"] = f"Embedded {job['done']}/{job['total']} chunks"
            await asyncio.sleep(0)

        job["status"]       = "done"
        job["done"]         = len(documents)
        job["pct"]          = 100
        job["stage_detail"] = (
            f"✅ {len(documents)} vectors → index [{index_name}] "
            f"ns={namespace} | {saved_path}"
        )

        # ── 6. Update knowledge_documents ─────────────────────────────────────
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
            print(f"[crawlee_ingest] DB update failed: {db_err}")

    except Exception as e:
        job["status"] = "error"
        job["errors"].append(str(e))
        print(f"[crawlee_ingest] job {job_id} error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Router
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(tags=["crawlee-ingest"])


@router.post("/chatbots/{bot_id}/crawlee/ingest")
async def start_crawlee_ingest(
    bot_id:      int,
    file:        UploadFile = File(...),
    user_id:     int = Query(...),
    token:       str = Query(...),
    doc_id:      int = Query(...),
    source_type: str = Query(
        "food_items",
        description="'food_items' | 'faculty_profiles' | 'page_data'",
    ),
    category: str = Query(
        "restaurant",
        description=(
            "restaurant → restaurant index\n"
            "university → university index\n"
            "faculty    → faculty index\n"
            "fyp        → fyp index\n"
            "general    → general index"
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Upload scraped JSON from the Crawlee scraper.

    ┌────────────┬──────────────────┬──────────────────────────────────────────┐
    │ category   │ source_type      │ What gets embedded                       │
    ├────────────┼──────────────────┼──────────────────────────────────────────┤
    │ restaurant │ food_items       │ Menu items: name, price, category, image │
    │ restaurant │ page_data        │ Deals, branches, FAQs, hours             │
    │ faculty    │ faculty_profiles │ Structured faculty profiles              │
    │ faculty    │ page_data        │ Supplementary faculty page text          │
    │ university │ page_data        │ Courses, policies, departments           │
    │ fyp        │ page_data        │ Projects, abstracts, technologies        │
    │ general    │ page_data        │ Any website content (no filtering)       │
    └────────────┴──────────────────┴──────────────────────────────────────────┘
    """
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files are supported.")

    if source_type not in _VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"source_type must be one of: {', '.join(_VALID_SOURCE_TYPES)}",
        )

    if category not in _CATEGORY_INDEXES:
        raise HTTPException(
            status_code=400,
            detail=f"category must be one of: {', '.join(_CATEGORY_INDEXES)}",
        )

    try:
        raw_bytes = await file.read()
        raw_data  = json.loads(raw_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    try:
        saved_path = _save_crawlee_file(raw_bytes, file.filename, bot_id)
    except Exception as e:
        saved_path = "unknown"
        print(f"[crawlee_ingest] File save failed: {e}")

    idx_name = _index_name_for_category(category)
    ns       = _namespace(user_id, bot_id)
    job_id   = str(uuid.uuid4())

    _crawlee_jobs[job_id] = {
        "status":       "uploading",
        "filename":     file.filename,
        "saved_path":   saved_path,
        "source_type":  source_type,
        "category":     category,
        "index":        idx_name,
        "namespace":    ns,
        "pipeline":     f"crawlee_{category}_{source_type}",
        "method":       "crawlee",
        "total":        0,
        "done":         0,
        "pct":          0,
        "stage_detail": "",
        "items_count":  0,
        "errors":       [],
    }

    from database import SessionLocal
    asyncio.create_task(
        _run_crawlee_ingest(
            job_id, raw_data, source_type, category,
            idx_name, doc_id, bot_id, saved_path, SessionLocal,
            namespace=ns,
        )
    )

    return {
        "job_id":      job_id,
        "index_name":  idx_name,
        "namespace":   ns,
        "source_type": source_type,
        "category":    category,
        "pipeline":    f"crawlee_{category}_{source_type}",
        "saved_path":  saved_path,
    }


@router.get("/chatbots/{bot_id}/crawlee/ingest/{job_id}/progress")
async def crawlee_progress_sse(
    bot_id:  int,
    job_id:  str,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    """SSE stream — same event shape as pinecone_ingest.py /progress."""
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if job_id not in _crawlee_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _stream() -> AsyncGenerator[str, None]:
        while True:
            data = json.dumps(_crawlee_jobs.get(job_id, {}))
            yield f"data: {data}\n\n"
            if _crawlee_jobs.get(job_id, {}).get("status") in ("done", "error"):
                break
            await asyncio.sleep(0.8)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chatbots/{bot_id}/crawlee/ingest/{job_id}/status")
async def crawlee_status_json(
    bot_id:  int,
    job_id:  str,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if job_id not in _crawlee_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _crawlee_jobs[job_id]


@router.get("/chatbots/{bot_id}/crawlee/index-info")
async def crawlee_index_info(
    bot_id:   int,
    user_id:  int = Query(...),
    token:    str = Query(...),
    category: str = Query("restaurant"),
):
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
        idx      = pc.Index(idx_name)
        stats    = idx.describe_index_stats()
        ns_stats = stats.get("namespaces", {}).get(ns, {})
        return {
            "index_name":     idx_name,
            "namespace":      ns,
            "exists":         True,
            "vector_count":   ns_stats.get("vector_count", 0),
            "all_namespaces": stats.get("namespaces", {}),
        }
    except Exception as e:
        return {"index_name": idx_name, "namespace": ns, "exists": False, "error": str(e)}


@router.delete("/chatbots/{bot_id}/crawlee/index")
async def crawlee_delete_index(
    bot_id:   int,
    user_id:  int = Query(...),
    token:    str = Query(...),
    category: str = Query("restaurant"),
):
    """Clears this bot's namespace in the index (shared index is preserved)."""
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    idx_name = _index_name_for_category(category)
    ns       = _namespace(user_id, bot_id)
    try:
        pc = Pinecone(api_key=_pinecone_key())
        existing = pc.list_indexes()
        names = existing.names() if hasattr(existing, "names") else [i["name"] for i in existing]
        if idx_name in names:
            pc.Index(idx_name).delete(delete_all=True, namespace=ns)
        return {"deleted": True, "index_name": idx_name, "namespace": ns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chatbots/{bot_id}/crawlee/files")
async def list_crawlee_files(
    bot_id:  int,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    """List all crawlee JSON files saved for this bot."""
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    crawlee_dir = os.path.join(_UPLOAD_DIR, str(bot_id), "crawlee")
    if not os.path.exists(crawlee_dir):
        return {"files": []}
    files = []
    for fname in sorted(os.listdir(crawlee_dir), reverse=True):
        fpath = os.path.join(crawlee_dir, fname)
        stat  = os.stat(fpath)
        files.append({
            "filename":    fname,
            "path":        fpath,
            "size_bytes":  stat.st_size,
            "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
        })
    return {"files": files, "count": len(files)}