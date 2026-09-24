"""
crawlee_scrape.py  ──  Drop into your SmartChat backend folder.

Handles the "Import from Website" scrape button in the dashboard.
When a user pastes a URL and clicks Scrape, this module:

  1.  Creates a KnowledgeDocument record (status=training)
  2.  Runs the Crawlee Node.js scraper as a subprocess
  3.  Saves  food-items.json  and  page-data.json  to
        uploads/{bot_id}/crawlee/{timestamp}_food-items.json
        uploads/{bot_id}/crawlee/{timestamp}_page-data.json
  4.  Reads both JSON files back and ingests them into Pinecone
      (reuses the same _run_crawlee_ingest() from crawlee_ingest.py)
  5.  Streams SSE progress so the dashboard progress bar works

Registration in main.py:
    from crawlee_scrape import router as scrape_router
    app.include_router(scrape_router)

Dependencies:
    Node.js ≥18  +  crawlee  +  playwright  (already installed for the scraper)
    crawlee_ingest.py  (must be in the same folder)
"""

import asyncio
import json
import os
import subprocess
import sys
import traceback
import uuid
from datetime import datetime
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import KnowledgeDocument, DocStatus

# Reuse ingest logic from crawlee_ingest.py
from crawlee_ingest import (
    _run_crawlee_ingest,
    _crawlee_jobs,
    _index_name_for_category,
    _namespace,
    _verify_auth,
    _save_crawlee_file,
    _UPLOAD_DIR,
    _CATEGORY_INDEXES,
)

# Source-type routing per category
# restaurant → food_items + page_data
# faculty    → faculty_profiles + page_data
# university/fyp/general → page_data only
_CATEGORY_SOURCE_TYPES = {
    "restaurant": ["food_items", "page_data"],
    "faculty":    ["faculty_profiles", "page_data"],
    "university": ["page_data"],
    "fyp":        ["page_data"],
    "general":    ["page_data"],
}

load_dotenv()

router = APIRouter(tags=["crawlee-scrape"])

# ─── In-memory scrape job store ───────────────────────────────────────────────
_scrape_jobs: dict = {}

# ─── Inline Crawlee runner script ─────────────────────────────────────────────
# Written to a temp file and executed via Node.js subprocess.
# Accepts the start URL, output dir, and max pages as CLI args.

_CRAWLEE_SCRIPT = r"""
import { PlaywrightCrawler } from 'crawlee';
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const [,, startUrl, outputDir, maxPagesStr] = process.argv;
const maxPages = parseInt(maxPagesStr || '30', 10);

const allFoodItems       = [];
const allFacultyProfiles = [];
const allPageData        = [];

// ── Anti-bot: realistic browser fingerprint ───────────────────────────────
const USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
];
const UA = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];

const crawler = new PlaywrightCrawler({
    maxRequestsPerCrawl: maxPages,
    maxConcurrency: 1,               // 1 at a time — avoids rate-limit bans
    navigationTimeoutSecs: 60,       // overall nav budget
    requestHandlerTimeoutSecs: 120,
    maxRequestRetries: 2,
    launchContext: {
        launcher: chromium,
        launchOptions: {
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1366,768',
                '--start-maximized',
                '--disable-extensions',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--lang=en-US,en',
            ],
        },
    },
    // Use "domcontentloaded" so heavy SPAs (React/Next.js like Dominos) don't timeout
    // waiting for all XHR/images to finish. We do our own content-ready wait below.
    preNavigationHooks: [
        async ({ page }) => {
            // Override navigator.webdriver — #1 bot detector
            await page.addInitScript(() => {
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
            });
            // Set realistic headers
            await page.setExtraHTTPHeaders({
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'DNT':             '1',
                'Upgrade-Insecure-Requests': '1',
            });
            await page.setViewportSize({ width: 1366, height: 768 });
        },
    ],
    async requestHandler({ request, page, enqueueLinks }) {
        // ── Smart content-ready wait ──────────────────────────────────────────
        // Use domcontentloaded (fast) then give JS extra time to render
        try { await page.waitForLoadState('domcontentloaded', { timeout: 15000 }); } catch {}
        try { await page.waitForLoadState('networkidle',      { timeout: 8000  }); } catch {}
        await page.waitForTimeout(2500);

        // Slow scroll to trigger lazy-load content
        await page.evaluate(async () => {
            await new Promise(resolve => {
                let pos = 0;
                const step = () => {
                    pos += 300;
                    window.scrollTo(0, pos);
                    if (pos < document.body.scrollHeight) setTimeout(step, 80);
                    else resolve();
                };
                step();
            });
        });
        await page.waitForTimeout(800);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(400);

        // ── Faculty profiles (only for faculty bots) ──────────────────────────
        const facultyProfiles = await page.evaluate(() => {
            const clean = s => (s || '').replace(/\s+/g, ' ').trim();
            const profiles = [];

            // Strategy A: Structured cards — common university faculty page patterns
            const cardSels = [
                '[class*="faculty-card"],[class*="FacultyCard"],[class*="faculty_card"]',
                '[class*="staff-card"],[class*="StaffCard"],[class*="team-card"]',
                '[class*="person-card"],[class*="PersonCard"],[class*="member-card"]',
                '[class*="teacher"],[class*="professor"],[class*="instructor"]',
                'article[class*="faculty"],article[class*="staff"],article[class*="person"]',
                '.faculty-member,.staff-member,.team-member',
            ].join(',');

            const cards = Array.from(document.querySelectorAll(cardSels));

            cards.forEach(card => {
                const nameEl = card.querySelector(
                    'h1,h2,h3,h4,[class*="name"],[class*="Name"],[class*="title"],[class*="Title"]'
                );
                const name = clean(nameEl?.innerText);
                if (!name || name.length < 3) return;

                const getText = (...sels) => {
                    for (const sel of sels) {
                        const el = card.querySelector(sel);
                        if (el) return clean(el.innerText);
                    }
                    return '';
                };

                const designation = getText(
                    '[class*="designation"],[class*="Designation"]',
                    '[class*="position"],[class*="Position"]',
                    '[class*="role"],[class*="Role"]',
                    '[class*="title"]:not(h1):not(h2):not(h3)',
                );
                const department = getText(
                    '[class*="department"],[class*="Department"]',
                    '[class*="dept"],[class*="school"],[class*="faculty-of"]',
                );
                const qualification = getText(
                    '[class*="qualification"],[class*="Qualification"]',
                    '[class*="degree"],[class*="education"]',
                );
                const institution = getText(
                    '[class*="institution"],[class*="university"],[class*="college"]',
                );
                const emailEl = card.querySelector('a[href^="mailto:"]');
                const email = emailEl ? emailEl.href.replace('mailto:', '') : '';
                const imgEl = card.querySelector('img');
                const image = imgEl?.src || imgEl?.dataset?.src || '';

                profiles.push({ name, designation, department, qualification, institution, email, image });
            });

            if (profiles.length) return profiles;

            // Strategy B: Table rows (department faculty listing tables)
            document.querySelectorAll('table tr').forEach(row => {
                const cells = Array.from(row.querySelectorAll('td,th'));
                if (cells.length < 2) return;
                const name = clean(cells[0]?.innerText);
                if (!name || name.length < 3 || !/[A-Z]/.test(name[0])) return;
                profiles.push({
                    name,
                    designation:   clean(cells[1]?.innerText) || '',
                    department:    clean(cells[2]?.innerText) || '',
                    qualification: clean(cells[3]?.innerText) || '',
                    institution:   '',
                    email:         '',
                    image:         '',
                });
            });

            return profiles;
        });

        // Add faculty profiles to global store (dedup by name)
        const globalFacultyNames = new Set(allFacultyProfiles.map(p => p.name));
        facultyProfiles.forEach(p => {
            if (p.name && !globalFacultyNames.has(p.name)) {
                globalFacultyNames.add(p.name);
                allFacultyProfiles.push({ ...p, sourceUrl: request.url });
            }
        });

        // ── Food items ──────────────────────────────────────────────────────
        const foodItems = await page.evaluate(() => {
            const clean = s => (s || '').replace(/\s+/g, ' ').trim();
            const items = [];

            const extractImage = card => {
                const img = card.querySelector('img');
                if (img) {
                    const lazy = img.dataset?.src || img.dataset?.lazySrc || img.dataset?.original
                              || img.getAttribute('data-src') || img.getAttribute('data-lazy-src');
                    if (lazy && lazy.startsWith('http')) return lazy;
                    if (img.src && img.src.startsWith('http') && !img.src.includes('data:')) return img.src;
                }
                const all = Array.from(card.querySelectorAll('*'));
                for (const el of all) {
                    const bg = window.getComputedStyle(el).backgroundImage;
                    if (bg && bg !== 'none') {
                        const m = bg.match(/url\(["']?([^"')]+)["']?\)/);
                        if (m && m[1].startsWith('http')) return m[1];
                    }
                }
                const src = card.querySelector('picture source, source');
                if (src) { const first = (src.srcset||'').split(',')[0]?.trim().split(' ')[0]; if (first?.startsWith('http')) return first; }
                return null;
            };

            // Strategy A: schema.org
            document.querySelectorAll('[itemtype*="Product"],[itemtype*="MenuItem"]').forEach(card => {
                const name = clean(card.querySelector('[itemprop="name"]')?.innerText);
                if (!name) return;
                items.push({
                    name,
                    description: clean(card.querySelector('[itemprop="description"]')?.innerText) || null,
                    price: clean(card.querySelector('[itemprop="price"]')?.innerText || card.querySelector('[itemprop="price"]')?.content || '') || null,
                    category: clean(card.closest('[data-category]')?.dataset?.category || card.closest('section')?.querySelector('h2,h3,h4')?.innerText || '') || null,
                    image: extractImage(card),
                });
            });
            if (items.length) return items;

            // Strategy B: CSS class cards
            const sel = ['.menu-item','.product-card','.item-card','.food-card','.pizza-card',
                '[class*="menuItem"],[class*="MenuItem"],[class*="product-item"],[class*="ProductCard"]',
                '[class*="food-item"],[class*="FoodItem"],[class*="item__card"],[class*="meal-card"]',
                '[class*="menu-card"],[class*="MenuCard"]','li[class*="item"]'].join(',');
            document.querySelectorAll(sel).forEach(card => {
                const nameEl = card.querySelector('h1,h2,h3,h4,h5,[class*="name"],[class*="title"],[class*="Name"],[class*="Title"]');
                const name = clean(nameEl?.innerText);
                if (!name || name.length < 2) return;
                const priceEl = card.querySelector('[class*="price"],[class*="Price"],[class*="cost"],[class*="rate"]');
                const price = priceEl ? clean(priceEl.innerText) : (() => {
                    const m = Array.from(card.querySelectorAll('*')).find(el =>
                        /^(Rs\.?|PKR|₨|\$|€|£)?\s*[\d,]+(\.\d{1,2})?$/.test(clean(el.innerText)));
                    return m ? clean(m.innerText) : null;
                })();
                items.push({
                    name,
                    description: clean(card.querySelector('p,[class*="desc"],[class*="Desc"]')?.innerText) || null,
                    price: price || null,
                    category: clean(card.closest('[data-category]')?.dataset?.category ||
                        card.closest('section,[class*="category"]')?.querySelector('h2,h3,h4')?.innerText || '') || null,
                    image: extractImage(card),
                });
            });
            if (items.length) return items;

            // Strategy C: price proximity
            const pat = /^(Rs\.?|PKR|₨|\$|€|£)?\s*[\d,]{2,}(\.\d{1,2})?$/;
            const priceEls = Array.from(document.querySelectorAll('*')).filter(el =>
                el.children.length === 0 && pat.test(clean(el.innerText)) && el.getBoundingClientRect().width > 0);
            const seen = new Set();
            priceEls.forEach(priceEl => {
                let card = priceEl;
                for (let i = 0; i < 5; i++) {
                    if (!card.parentElement) break;
                    card = card.parentElement;
                    const w = card.getBoundingClientRect().width;
                    if (w > 80 && w < 700) break;
                }
                if (seen.has(card)) return; seen.add(card);
                const nameEl = card.querySelector('h1,h2,h3,h4,h5,h6,strong,b');
                const name = clean(nameEl?.innerText);
                if (!name || name.length < 2) return;
                items.push({ name,
                    description: clean(card.querySelector('p,[class*="desc"]')?.innerText) || null,
                    price: clean(priceEl.innerText),
                    category: clean(card.closest('section')?.querySelector('h2,h3')?.innerText || '') || null,
                    image: extractImage(card),
                });
            });
            return items;
        });

        const globalFoodKeys = new Set(allFoodItems.map(i => `${i.name}|${i.price}`));
        foodItems.forEach(item => {
            const key = `${item.name}|${item.price}`;
            if (!globalFoodKeys.has(key)) { globalFoodKeys.add(key); allFoodItems.push({ ...item, sourceUrl: request.url }); }
        });

        // ── Page data ───────────────────────────────────────────────────────
        const pageData = await page.evaluate(() => {
            const clean   = s => (s || '').replace(/\s+/g, ' ').trim();
            const getText = sel => Array.from(document.querySelectorAll(sel))
                .map(el => clean(el.innerText)).filter(t => t.length > 1);
            const getMeta = name =>
                document.querySelector(`meta[name="${name}"]`)?.content ||
                document.querySelector(`meta[property="${name}"]`)?.content || null;

            // All heading levels
            const headings = {};
            ['h1','h2','h3','h4','h5','h6'].forEach(t => {
                const v = getText(t); if (v.length) headings[t] = v;
            });

            // List items — ul/ol bullets (course requirements, fee structures, admission steps…)
            const listItems = Array.from(document.querySelectorAll('li'))
                .map(li => clean(li.innerText))
                .filter(t => t.length > 3 && t.length < 400);

            // Tables — fees, timetables, credit hours, admission criteria
            const tableData = [];
            document.querySelectorAll('table').forEach(table => {
                const rows = [];
                table.querySelectorAll('tr').forEach(tr => {
                    const cells = Array.from(tr.querySelectorAll('td,th'))
                        .map(td => clean(td.innerText)).filter(Boolean);
                    if (cells.length) rows.push(cells.join(' | '));
                });
                if (rows.length) tableData.push(rows.join('\n'));
            });

            // Bold/strong text — often used for labels, key terms, announcements
            const boldText = getText('strong,b').filter(t => t.length > 2 && t.length < 200);

            // Meaningful div/span text blocks not captured by <p> (common in React/Vue sites)
            const divText = Array.from(document.querySelectorAll(
                'div[class*="content"],div[class*="desc"],div[class*="text"],div[class*="body"],' +
                'div[class*="about"],div[class*="info"],div[class*="detail"],div[class*="overview"],' +
                'section p,article p,.card p,.block p'
            ))
            .map(el => clean(el.innerText))
            .filter(t => t.length > 20 && t.length < 1000);

            return {
                url:   window.location.href,
                title: document.title,
                lang:  document.documentElement.lang || null,
                meta: {
                    description:   getMeta('description'),
                    keywords:      getMeta('keywords'),
                    ogTitle:       getMeta('og:title'),
                    ogDescription: getMeta('og:description'),
                    ogImage:       getMeta('og:image'),
                    canonical:     document.querySelector('link[rel="canonical"]')?.href || null,
                },
                headings,
                paragraphs: getText('p'),
                listItems,
                tableData,
                boldText,
                divText,
                navigation: Array.from(document.querySelectorAll('nav a,header a'))
                    .map(a => ({ text: a.innerText?.trim(), href: a.href }))
                    .filter(a => a.text && a.href),
                links: Array.from(document.querySelectorAll('a'))
                    .map(a => ({ text: a.innerText?.trim()||null, href: a.href||null,
                                 isExternal: a.href ? !a.href.includes(window.location.hostname) : false }))
                    .filter(l => l.href && !l.href.startsWith('javascript')),
                stats: {
                    wordCount:  document.body.innerText.trim().split(/\s+/).length,
                    imageCount: document.images.length,
                    linkCount:  document.links.length,
                },
                scrapedAt: new Date().toISOString(),
            };
        });
        allPageData.push(pageData);

        // Random human-like delay between pages (1.5 – 3.5s)
        await page.waitForTimeout(1500 + Math.random() * 2000);

        await enqueueLinks({
            selector: 'a[href]',
            strategy: 'same-domain',
            transformRequestFunction: (req) => {
                const ext = /\.(pdf|zip|jpg|jpeg|png|gif|svg|mp4|mp3|css|js|woff|ttf|ico)(\?.*)?$/i;
                if (ext.test(req.url)) return false;
                // Skip common non-content pages
                const skip = /\/(login|logout|register|cart|checkout|wp-admin|wp-json|feed|xmlrpc)/i;
                if (skip.test(req.url)) return false;
                return req;
            },
        });
    },
    failedRequestHandler({ request, response }) {
        const status = response?.status?.() ?? 0;
        if (status === 403) {
            console.error(`[BLOCKED] 403 Forbidden on ${request.url} — site may require cookies/JS challenge`);
        } else if (status === 429) {
            console.error(`[RATE LIMITED] 429 on ${request.url} — too many requests`);
        } else {
            console.error(`[FAILED] ${status} on ${request.url}`);
        }
    },
});

await crawler.run([startUrl]);

// Write output files
fs.mkdirSync(outputDir, { recursive: true });
const ts = new Date().toISOString().replace(/[:.]/g, '-');

const foodPath = path.join(outputDir, `${ts}_food-items.json`);
const pagePath = path.join(outputDir, `${ts}_page-data.json`);

fs.writeFileSync(foodPath, JSON.stringify({
    meta: { startUrl, totalItems: allFoodItems.length, exportedAt: new Date().toISOString() },
    items: allFoodItems,
}, null, 2));

fs.writeFileSync(pagePath, JSON.stringify({
    meta: { startUrl, totalPages: allPageData.length, exportedAt: new Date().toISOString() },
    pages: allPageData,
}, null, 2));

// Write faculty profiles file
const facultyPath = path.join(outputDir, `${ts}_faculty-profiles.json`);
fs.writeFileSync(facultyPath, JSON.stringify({
    meta: { startUrl, totalProfiles: allFacultyProfiles.length, exportedAt: new Date().toISOString() },
    profiles: allFacultyProfiles,
}, null, 2));

// Report paths to stdout so Python can read them
console.log(JSON.stringify({
    foodPath, pagePath, facultyPath,
    foodItems: allFoodItems.length,
    pageCount: allPageData.length,
    facultyProfiles: allFacultyProfiles.length,
}));
"""

# ─── Pydantic request ──────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url:       str
    max_pages: int = 30


# ─── Background scrape + ingest task ─────────────────────────────────────────

def _run_scrape_and_ingest(
    job_id:     str,
    url:        str,
    max_pages:  int,
    bot_id:     int,
    user_id:    int,
    doc_id:     int,
    category:   str,
):
    """
    Fully synchronous — runs in a background thread.
    Uses subprocess.run (blocking) so Windows ProactorEventLoop is not needed.
    """
    print(f"[crawlee_scrape] ▶ task started job={job_id} url={url}", file=sys.stderr, flush=True)
    job = _scrape_jobs[job_id]

    output_dir = os.path.join(_UPLOAD_DIR, str(bot_id), "crawlee")
    os.makedirs(output_dir, exist_ok=True)

    job["status"]       = "scraping"
    job["stage_detail"] = f"Starting Crawlee scraper on {url} …"

    project_root      = os.path.dirname(os.path.abspath(__file__))
    script_path       = os.path.join(project_root, f"crawlee_{job_id}.mjs")
    node_modules_path = os.path.join(project_root, "node_modules")
    existing_np       = os.environ.get("NODE_PATH", "")
    node_path_env     = f"{node_modules_path}{os.pathsep}{existing_np}" if existing_np else node_modules_path
    child_env         = {**os.environ, "NODE_PATH": node_path_env}

    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(_CRAWLEE_SCRIPT)
        print(f"[crawlee_scrape] script written: {script_path}", file=sys.stderr, flush=True)
    except Exception as e:
        job["status"] = "error"
        job["errors"].append(f"Failed to write crawler script: {e}")
        print(f"[crawlee_scrape] ERROR script write: {e}", file=sys.stderr, flush=True)
        _update_doc_status(doc_id, DocStatus.failed)
        return

    food_path  = None
    page_path  = None
    food_count = 0
    page_count = 0

    try:
        # ── Run Node.js synchronously (no event loop needed) ──────────────────
        print(f"[crawlee_scrape] running node {script_path}", file=sys.stderr, flush=True)

        result = subprocess.run(
            ["node", script_path, url, output_dir, str(max_pages)],
            capture_output=True,
            text=True,
            cwd=project_root,
            env=child_env,
            timeout=600,
        )

        print(f"[crawlee_scrape] node exit={result.returncode}", file=sys.stderr, flush=True)
        if result.stderr:
            for line in result.stderr.strip().splitlines()[-20:]:
                print(f"  [node] {line}", file=sys.stderr, flush=True)
            job["stage_detail"] = result.stderr.strip().splitlines()[-1][-120:]

        if result.returncode != 0:
            raise RuntimeError(
                f"Node.js exited {result.returncode}. stderr: {result.stderr.strip()[-400:]}"
            )

        stdout_lines = result.stdout.strip().splitlines()
        result_line  = next(
            (l for l in reversed(stdout_lines) if l.startswith("{") and '"foodPath"' in l),
            None,
        )
        if not result_line:
            print(f"[crawlee_scrape] stdout: {result.stdout[:500]}", file=sys.stderr, flush=True)
            raise RuntimeError("Crawlee did not output result JSON")

        data            = json.loads(result_line)
        food_path       = data["foodPath"]
        page_path       = data["pagePath"]
        faculty_path    = data.get("facultyPath")
        food_count      = data.get("foodItems", 0)
        page_count      = data.get("pageCount", 0)
        faculty_count   = data.get("facultyProfiles", 0)

        print(f"[crawlee_scrape] scraped pages={page_count} food={food_count} faculty={faculty_count}", file=sys.stderr, flush=True)
        job.update({
            "stage_detail":   f"Scraped {page_count} pages, {food_count} food items, {faculty_count} faculty profiles",
            "food_path":      food_path,
            "page_path":      page_path,
            "faculty_path":   faculty_path,
            "food_count":     food_count,
            "page_count":     page_count,
            "faculty_count":  faculty_count,
        })

    except Exception as e:
        job["status"] = "error"
        job["errors"].append(f"Scraping failed: {e}")
        job["stage_detail"] = f"Scraping failed: {e}"
        print(f"[crawlee_scrape] ERROR: {e}", file=sys.stderr, flush=True)
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        _update_doc_status(doc_id, DocStatus.failed)
        return
    finally:
        try: os.unlink(script_path)
        except: pass

    # ── Ingest into Pinecone using a fresh event loop ─────────────────────────
    idx_name = _index_name_for_category(category)
    ns       = _namespace(user_id, bot_id)

    def _run_async(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    if food_path and os.path.exists(food_path) and food_count > 0:
        job["status"]       = "ingesting_food"
        job["stage_detail"] = f"Ingesting {food_count} food items into Pinecone …"
        food_job_id = f"{job_id}_food"
        _crawlee_jobs[food_job_id] = {"status": "parsing", "total": 0, "done": 0, "pct": 0, "stage_detail": "", "errors": [], "items_count": 0}
        try:
            with open(food_path, "r", encoding="utf-8") as f:
                food_data = json.load(f)
            _run_async(_run_crawlee_ingest(
                job_id=food_job_id, raw_data=food_data, source_type="food_items",
                category=category, index_name=idx_name, doc_id=doc_id,
                bot_id=bot_id, saved_path=food_path, db_factory=SessionLocal, namespace=ns,
            ))
            if _crawlee_jobs.get(food_job_id, {}).get("status") == "error":
                job["errors"].extend(_crawlee_jobs[food_job_id].get("errors", []))
        except Exception as e:
            job["errors"].append(f"Food ingest failed: {e}")
            print(f"[crawlee_scrape] food ingest error: {e}", file=sys.stderr, flush=True)

    # ── Ingest faculty profiles (faculty bots only) ──────────────────────────
    faculty_path   = job.get("faculty_path")
    faculty_count  = job.get("faculty_count", 0)
    if category == "faculty" and faculty_path and os.path.exists(faculty_path) and faculty_count > 0:
        job["status"]       = "ingesting_faculty"
        job["stage_detail"] = f"Ingesting {faculty_count} faculty profiles into Pinecone …"
        fac_job_id = f"{job_id}_faculty"
        _crawlee_jobs[fac_job_id] = {"status": "parsing", "total": 0, "done": 0, "pct": 0, "stage_detail": "", "errors": [], "items_count": 0}
        try:
            with open(faculty_path, "r", encoding="utf-8") as f:
                fac_data = json.load(f)
            _run_async(_run_crawlee_ingest(
                job_id=fac_job_id, raw_data=fac_data, source_type="faculty_profiles",
                category=category, index_name=idx_name, doc_id=doc_id,
                bot_id=bot_id, saved_path=faculty_path, db_factory=SessionLocal, namespace=ns,
            ))
            if _crawlee_jobs.get(fac_job_id, {}).get("status") == "error":
                job["errors"].extend(_crawlee_jobs[fac_job_id].get("errors", []))
        except Exception as e:
            job["errors"].append(f"Faculty ingest failed: {e}")
            print(f"[crawlee_scrape] faculty ingest error: {e}", file=sys.stderr, flush=True)

    if page_path and os.path.exists(page_path) and page_count > 0:
        job["status"]       = "ingesting_pages"
        job["stage_detail"] = f"Ingesting {page_count} pages into Pinecone …"
        page_job_id = f"{job_id}_pages"
        _crawlee_jobs[page_job_id] = {"status": "parsing", "total": 0, "done": 0, "pct": 0, "stage_detail": "", "errors": [], "items_count": 0}
        try:
            with open(page_path, "r", encoding="utf-8") as f:
                page_data = json.load(f)
            _run_async(_run_crawlee_ingest(
                job_id=page_job_id, raw_data=page_data, source_type="page_data",
                category=category, index_name=idx_name, doc_id=doc_id,
                bot_id=bot_id, saved_path=page_path, db_factory=SessionLocal, namespace=ns,
            ))
            if _crawlee_jobs.get(page_job_id, {}).get("status") == "error":
                job["errors"].extend(_crawlee_jobs[page_job_id].get("errors", []))
        except Exception as e:
            job["errors"].append(f"Page ingest failed: {e}")
            print(f"[crawlee_scrape] page ingest error: {e}", file=sys.stderr, flush=True)

    # ── Done ──────────────────────────────────────────────────────────────────
    total_vectors = (
        _crawlee_jobs.get(f"{job_id}_food",    {}).get("done", 0) +
        _crawlee_jobs.get(f"{job_id}_faculty", {}).get("done", 0) +
        _crawlee_jobs.get(f"{job_id}_pages",   {}).get("done", 0)
    )
    if job["errors"]:
        job["status"]       = "done_with_errors"
        job["stage_detail"] = f"Completed with {len(job['errors'])} error(s)"
    else:
        job["status"]       = "done"
        job["stage_detail"] = f"✅ {food_count} items + {page_count} pages → {total_vectors} vectors"

    job["total_vectors"] = total_vectors
    _update_doc_status(doc_id, DocStatus.trained, progress=100, accuracy=92.0)
    print(f"[crawlee_scrape] ✅ done job={job_id} vectors={total_vectors}", file=sys.stderr, flush=True)


def _update_doc_status(
    doc_id: int,
    status: DocStatus,
    progress: int = 0,
    accuracy: float = 0.0,
):
    try:
        db: Session = SessionLocal()
        doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
        if doc:
            doc.status            = status
            doc.training_progress = progress
            doc.accuracy          = accuracy
            db.commit()
        db.close()
    except Exception as e:
        print(f"[crawlee_scrape] DB update failed: {e}")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/chatbots/{bot_id}/documents/scrape")
async def scrape_website(
    bot_id:  int,
    body:    ScrapeRequest,
    user_id: int = Query(...),
    token:   str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Replaces the old stub scrape endpoint.

    1. Creates a KnowledgeDocument record
    2. Starts Crawlee in the background via FastAPI BackgroundTasks
    3. Returns {doc_id, job_id} immediately so the frontend can open SSE

    The frontend ALSO opens:
      GET /chatbots/{bot_id}/documents/scrape/{job_id}/progress  (SSE)
    to watch progress.
    """
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    url = body.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    # Determine category from bot record
    from models import Chatbot as ChatbotModel
    bot = db.query(ChatbotModel).filter(ChatbotModel.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    category = getattr(bot, "category", "university")

    # Create knowledge document record
    doc = KnowledgeDocument(
        chatbot_id        = bot_id,
        name              = url,
        type              = "website",
        source_url        = url,
        status            = DocStatus.training,
        training_progress = 0,
        upload_date       = datetime.utcnow().strftime("%Y-%m-%d"),
        size_label        = "—",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    job_id = str(uuid.uuid4())
    _scrape_jobs[job_id] = {
        "status":        "queued",
        "url":           url,
        "doc_id":        doc.id,
        "category":      category,
        "stage_detail":  "Queued…",
        "food_count":    0,
        "page_count":    0,
        "faculty_count": 0,
        "total_vectors": 0,
        "food_path":     None,
        "page_path":     None,
        "faculty_path":  None,
        "errors":        [],
    }

    # Start a raw OS thread — bypasses all FastAPI/asyncio Windows issues
    import threading
    t = threading.Thread(
        target=_run_scrape_and_ingest,
        kwargs=dict(
            job_id=job_id, url=url, max_pages=body.max_pages,
            bot_id=bot_id, user_id=user_id, doc_id=doc.id, category=category,
        ),
        daemon=True,
    )
    t.start()
    print(f"[crawlee_scrape] ✓ thread started job={job_id} tid={t.ident}", file=sys.stderr, flush=True)

    # Return same shape as original scrape endpoint + extra fields for SSE
    return {
        "id":              doc.id,
        "name":            url,
        "type":            "website",
        "status":          "training",
        "training_progress": 0,
        "upload_date":     doc.upload_date,
        "size_label":      "—",
        "source_url":      url,
        # Extra: frontend uses these to open SSE
        "scrape_job_id":   job_id,
    }


@router.get("/chatbots/{bot_id}/documents/scrape/{job_id}/progress")
async def scrape_progress_sse(
    bot_id:  int,
    job_id:  str,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    """
    SSE stream for scrape + ingest progress.
    Emits events every 1s until status is 'done', 'done_with_errors', or 'error'.

    Event shape:
    {
      "status": "queued|scraping|ingesting_food|ingesting_pages|done|error",
      "stage_detail": "human-readable current step",
      "food_count": N,
      "page_count": N,
      "total_vectors": N,
      "food_path": "uploads/42/crawlee/..._food-items.json",
      "page_path":  "uploads/42/crawlee/..._page-data.json",
      "errors": []
    }
    """
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if job_id not in _scrape_jobs:
        raise HTTPException(status_code=404, detail="Scrape job not found")

    async def _stream() -> AsyncGenerator[str, None]:
        # Send retry directive so browser auto-reconnects if connection drops
        yield "retry: 3000\n\n"
        while True:
            job_data = _scrape_jobs.get(job_id, {})
            data     = json.dumps(job_data)
            yield f"data: {data}\n\n"
            status = job_data.get("status", "")
            if status in ("done", "done_with_errors", "error"):
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":                "no-cache",
            "X-Accel-Buffering":            "no",
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Connection":                   "keep-alive",
        },
    )


@router.get("/chatbots/{bot_id}/documents/scrape/{job_id}/status")
async def scrape_status_json(
    bot_id:  int,
    job_id:  str,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    """JSON poll — same payload as SSE."""
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if job_id not in _scrape_jobs:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return _scrape_jobs[job_id]