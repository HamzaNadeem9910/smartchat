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
    Node.js >=18  +  crawlee  +  playwright
    crawlee_ingest.py  (must be in the same folder)

CHANGES
───────
 - OpenAI Vision fallback removed entirely
 - PERFORMANCE / TIMEOUT REWRITE (this round):
     Root cause: maxConcurrency=1 + a ~45-50s fixed/ceiling wait chain on
     EVERY page (dominated by two networkidle waits that never resolve
     early on sites with chat widgets / polling / sockets) meant a
     300-page crawl needed 225-250+ minutes against a 20-minute subprocess
     timeout. Fixed by trimming dead waiting, not by raising timeouts further.

     maxConcurrency              1    → configurable, default 4 (CLI arg #4)
     navigationTimeoutSecs      120   → 45   (a hung page now fails fast instead
                                                of eating the whole budget)
     requestHandlerTimeoutSecs  300   → 90
     maxRequestRetries            3   → 1    (retries on a truly broken page
                                                were burning the budget 3x)
     domcontentloaded wait      40s   → 15s  (ceiling only — DOM fires in ~1s
                                                on almost all sites)
     networkidle (main)         20s   → 4s   (was being fully consumed on
                                                nearly every page; treated as
                                                best-effort bonus, not load-bearing)
     fixed sleeps           4s+3s+1s  → 0.8s+0.6s+0.3s
     scroll strategy        37×400px/100ms steps → 3 large hops @250ms
     post-scroll networkidle    10s   → 2.5s
     per-page random delay    3-6s    → 0.4-0.9s
     Blinkco geofence/branch/
       sections live calls    20s   → 10s
     Blinkco products call    30s   → 12s
     Blinkco page.evaluate fetch: added AbortController timeout (was
       unbounded — could hang until requestHandlerTimeoutSecs killed it)
     subprocess timeout       flat 1200s → dynamic, scales with max_pages
       and max_concurrency (600s floor, 3600s ceiling)
 - ACCURACY FIX: auto-dismiss "select your city/location" modals (Blinkco,
   and similar ordering platforms) before the Blinkco resolution logic runs.
   Clicking through lets the site's own JS set whatever cookie/session value
   gates /api/products, which is far more reliable than the existing
   geofence→branch fallback chain alone — and is also what was causing the
   Doctor Saucy / Blinkco scrape to come back empty.
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

load_dotenv()

router = APIRouter(tags=["crawlee-scrape"])

_scrape_jobs: dict = {}

# ─── Crawlee Node.js script ────────────────────────────────────────────────────

_CRAWLEE_SCRIPT = r"""
import { PlaywrightCrawler } from 'crawlee';
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import https from 'https';

// ── CLI args ──────────────────────────────────────────────────────────────────
const [,, startUrl, outputDir, maxPagesStr, maxConcurrencyStr] = process.argv;
const maxPages       = parseInt(maxPagesStr || '30', 10);
const maxConcurrency = Math.min(8, Math.max(1, parseInt(maxConcurrencyStr || '4', 10)));
// maxRequestsPerCrawl is set AFTER sitemap discovery so it can be
// max(maxPages, sitemapUrls.length + buffer).  We patch the crawler
// limit just before calling crawler.run().  Default is a large sentinel.
let crawlLimit = Math.max(maxPages, 500);  // raised after sitemap read

// ── Global accumulators ───────────────────────────────────────────────────────
const allFoodItems       = [];
const allFacultyProfiles = [];
const allPageData        = [];
const allNetworkLog      = [];

// Dedup by name only — store index so we can merge a better price later
const _foodIndex   = new Map();   // name_lower → index in allFoodItems
const _facultyKeys = new Set();

function pushFood(item, sourceUrl) {
    const nameRaw = (item.name || '').trim();
    if (!nameRaw || nameRaw.toLowerCase() === 'page_content') return;

    // ── Garbage filter ────────────────────────────────────────────────────────
    // The price-sibling heading strategy fires on non-menu pages (About Us,
    // history timelines) and captures: bare currency tokens ("Rs", "PKR") as
    // names, and purely numeric strings ("1890", "1997" - years) as headings.
    if (/^\d+$/.test(nameRaw)) return;                            // year/number noise
    if (/^(Rs\.?|PKR|\u20a8|\$|\u20ac|\u00a3|AED|SAR)$/i.test(nameRaw)) return; // bare currency
    if (nameRaw.length < 3) return;                                // 1-2 char noise

    // ── Price normalisation ───────────────────────────────────────────────────
    // DOM strategies on custom Next.js sites (KFC, etc.) capture the visible
    // price label text, e.g. "Rs 310" or "Rs. 2,090". Strip the currency prefix
    // so values are consistent plain numbers regardless of source.
    const _rawP = String(item.price || '');
    const _normP = _rawP.replace(/^(Rs\.?\s*|PKR\s*|\u20a8\s*|\$\s*|\u20ac\s*|\u00a3\s*|AED\s*|SAR\s*)/i,'').replace(/,/g,'').trim();
    if (_normP !== _rawP) item = { ...item, price: _normP };

    // Key by name+category, not name alone. Two different items that happen
    // to share a name (e.g. "Fries" as a standalone side vs. "Fries" inside a
    // combo/category) were previously collapsing into ONE entry, silently
    // dropping real menu items — a direct accuracy loss on any site with
    // repeated names across sections. Items with no category still dedupe by
    // name alone (safe default when we truly can't tell them apart).
    const catKey   = (item.category || '').toLowerCase().trim();
    const nameKey  = catKey ? `${nameRaw.toLowerCase()}|${catKey}` : nameRaw.toLowerCase();
    const newPrice = parseFloat(item.price) || 0;

    if (_foodIndex.has(nameKey)) {
        const existing      = allFoodItems[_foodIndex.get(nameKey)];
        const existingPrice = parseFloat(existing.price) || 0;
        if (newPrice > 0 && existingPrice === 0) existing.price = String(item.price);
        if (!existing.description && item.description) existing.description = item.description;
        if (!existing.category    && item.category)    existing.category    = item.category;
        if (!existing.image       && item.image)       existing.image       = item.image;
        if (item._via === 'blinkco_api')               existing._via        = 'blinkco_api';
    } else {
        _foodIndex.set(nameKey, allFoodItems.length);
        allFoodItems.push({ ...item, name: nameRaw, sourceUrl });
    }
}

function pushFaculty(profile, sourceUrl) {
    const key = (profile.name || '').toLowerCase().trim();
    if (key.length > 2 && !_facultyKeys.has(key)) {
        _facultyKeys.add(key);
        allFacultyProfiles.push({ ...profile, sourceUrl });
    }
}

// ── Deep JSON scanner ─────────────────────────────────────────────────────────
function deepScanJson(obj, sourceUrl, depth = 0) {
    if (!obj || typeof obj !== 'object' || depth > 12) return;

    if (Array.isArray(obj)) {
        if (obj.length > 0 && typeof obj[0] === 'object') {
            const sample   = obj[0];
            const hasName  = 'name' in sample || 'title' in sample || 'item_name' in sample
                          || 'productName' in sample || 'product_name' in sample || 'dishName' in sample;
            const hasPrice = 'price' in sample || 'base_price' in sample || 'cost' in sample
                          || 'amount' in sample || 'rate' in sample || 'selling_price' in sample;
            const hasDesig = 'designation' in sample || 'position' in sample || 'department' in sample;

            if (hasName && hasPrice) {
                obj.forEach(item => {
                    const name = clean(
                        item.name || item.title || item.item_name ||
                        item.productName || item.product_name || item.dishName || ''
                    );
                    if (!name || name.length < 2) return;

                    const rawP = item.price ?? item.base_price ?? item.cost ??
                                 item.amount ?? item.rate ?? item.selling_price ?? null;
                    const price = rawP !== null ? String(rawP).replace(/\.0+$/, '') : null;

                    let category = null;
                    const catRaw = item.category || item.categories || item.category_name
                                || item.section || item.group || item.menu_section || null;
                    if (Array.isArray(catRaw) && catRaw.length) {
                        category = clean(catRaw[0]?.name || catRaw[0] || '');
                    } else if (catRaw && typeof catRaw === 'object') {
                        category = clean(catRaw.name || catRaw.title || '');
                    } else if (catRaw) {
                        category = clean(String(catRaw));
                    }

                    const desc  = item.description || item.short_description ||
                                  item.details || item.subtitle || item.info || null;
                    const image = item.img_url    || item.image       || item.image_url  ||
                                  item.imageUrl  || item.imgUrl     || item.img         ||
                                  item.photo     || item.thumbnail  || item.picture     ||
                                  item.heroImage || item.cardImage  || item.mediaUrl    ||
                                  item.icon      || item.cdnUrl     || item.coverImage  ||
                                  item.productImage || item.listImage || null;

                    pushFood({
                        name,
                        description: desc ? clean(String(desc)) : null,
                        price,
                        category: category || null,
                        image: image ? String(image) : null,
                    }, sourceUrl);
                });
            } else if (hasName && hasDesig) {
                obj.forEach(item => {
                    const name = clean(item.name || item.full_name || item.faculty_name || '');
                    if (!name || name.length < 3) return;
                    pushFaculty({
                        name,
                        designation:   clean(item.designation || item.position || item.role || item.title || ''),
                        department:    clean(item.department || item.dept || item.faculty || ''),
                        qualification: clean(item.qualification || item.degree || item.education || ''),
                        institution:   clean(item.institution || item.university || item.college || ''),
                        email:         clean(item.email || ''),
                        image:         item.image || item.photo || item.picture || item.profile_pic || '',
                    }, sourceUrl);
                });
            } else {
                obj.forEach(el => deepScanJson(el, sourceUrl, depth + 1));
            }
        }
        return;
    }

    Object.values(obj).forEach(v => {
        if (v && typeof v === 'object') deepScanJson(v, sourceUrl, depth + 1);
    });
}

function clean(s) {
    return (s || '').toString().replace(/\s+/g, ' ').trim();
}

// ── Anti-bot fingerprint ──────────────────────────────────────────────────────
const USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
];
const UA = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];

// ── Blinkco cache ─────────────────────────────────────────────────────────────
const blinkcoCache = {};   // restId → { products, sectionMap } | 'fetching' | null

// ── Location/city selector modal auto-dismiss ─────────────────────────────────
// Many delivery-platform sites (Blinkco, Foodics, etc.) block ALL API calls
// behind a "select your city / location" modal until the visitor picks one.
// Auto-click the first reasonable option so the page's own JS sets whatever
// cookie/localStorage/session value gates /api/products — far more reliable
// than guessing a cityId query param by hand, and lets the existing network
// response listener (above) capture the real /api/products payload organically.
async function dismissLocationModal(page) {
    try {
        const clicked = await page.evaluate(() => {
            const MODAL_HINTS = /select\s*(your)?\s*(city|location|area|branch)|choose\s*(your)?\s*(city|location|area)|deliver(y)?\s*to|set\s*(your)?\s*location/i;
            const candidates = Array.from(document.querySelectorAll(
                '[class*="modal"],[class*="Modal"],[class*="dialog"],[class*="Dialog"],[role="dialog"]'
            ));
            for (const modal of candidates) {
                const rect = modal.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;  // not visible
                const text = (modal.innerText || '').slice(0, 300);
                if (!MODAL_HINTS.test(text)) continue;
                const option = modal.querySelector(
                    'li button, li a, [class*="city"], [class*="City"], ' +
                    '[class*="location-item"], [class*="LocationItem"], button, li'
                );
                if (option) { option.click(); return true; }
            }
            return false;
        });
        if (clicked) {
            console.error('[LocationModal] dismissed — waiting for it to settle');
            await page.waitForTimeout(1500);
        }
        return clicked;
    } catch (e) {
        console.error(`[LocationModal] dismiss failed: ${e.message}`);
        return false;
    }
}

// ── Crawler ───────────────────────────────────────────────────────────────────
const crawler = new PlaywrightCrawler({
    maxRequestsPerCrawl:      9999,       // overridden just before crawler.run()
    maxConcurrency:           maxConcurrency,  // was hardcoded 1 — see CLI arg above
    navigationTimeoutSecs:    60,    // 45 was too tight for heavy Next.js SPAs (KFC etc.) — 60 is still 2× faster than the original 120 while giving slow connections headroom
    requestHandlerTimeoutSecs: 90,   // was 300 — per-page work below rarely needs more than ~20s
    maxRequestRetries:        1,     // was 3 — retrying a genuinely broken page 3x just burns the time budget
    launchContext: {
        launcher: chromium,
        launchOptions: {
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1440,900',
                '--disable-extensions',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--lang=en-US,en',
            ],
        },
    },

    preNavigationHooks: [
        async ({ page, request }, gotoOptions) => {
            // Switch from 'load' (waits for ALL resources including fonts/images/JS bundles
            // — can be 60-90s on heavy Next.js sites like KFC) to 'domcontentloaded'
            // (fires when HTML is parsed, typically 1-3s). Our handler then does its own
            // controlled waitForLoadState calls, so nothing is lost.
            gotoOptions.waitUntil = 'domcontentloaded';

            page.on('response', async (response) => {
                try {
                    const url    = response.url();
                    const status = response.status();
                    const ct     = response.headers()['content-type'] || '';

                    if (/\.(png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|css|mp4|webp)(\?|$)/i.test(url)) return;
                    if (status < 200 || status >= 400) return;

                    if (ct.includes('application/json') || ct.includes('text/json')) {
                        let json = null;
                        try { json = await response.json(); } catch {}
                        if (!json) {
                            try {
                                const txt = await response.text();
                                if (txt && (txt.trim().startsWith('{') || txt.trim().startsWith('['))) {
                                    json = JSON.parse(txt);
                                }
                            } catch {}
                        }
                        if (json) {
                            allNetworkLog.push({
                                url, status, contentType: ct,
                                payloadSnippet: JSON.stringify(json).slice(0, 5000),
                            });
                            deepScanJson(json, request.url);
                        }
                    }
                } catch {}
            });

            await page.addInitScript(() => {
                Object.defineProperty(navigator, 'webdriver',  { get: () => undefined });
                Object.defineProperty(navigator, 'plugins',    { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages',  { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'platform',   { get: () => 'Win32' });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
                window.chrome = { runtime: {} };
                delete window.__playwright;
                delete window.__pwInitScripts;
            });

            await page.setExtraHTTPHeaders({
                'Accept-Language':           'en-US,en;q=0.9',
                'Accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'DNT':                       '1',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest':            'document',
                'Sec-Fetch-Mode':            'navigate',
                'Sec-Fetch-Site':            'none',
                'Sec-Ch-Ua':                 '"Chromium";v="124", "Google Chrome";v="124"',
            });
            await page.setViewportSize({ width: 1440, height: 900 });
        },
    ],

    async requestHandler({ request, page, enqueueLinks }) {
        const pageUrl = request.url;

        // ── Wait for content ──────────────────────────────────────────────────
        // NOTE: networkidle is the #1 cause of timeouts. Any page with polling
        // analytics, chat widgets, or websockets NEVER goes truly idle, so the
        // old code burned its FULL ceiling (20s, then another 10s) on almost
        // every page, twice over. Treat it as a short best-effort bonus wait,
        // not something the crawl depends on.
        try { await page.waitForLoadState('domcontentloaded', { timeout: 15000 }); } catch {}
        try { await page.waitForLoadState('networkidle',      { timeout: 4000  }); } catch {}
        await page.waitForTimeout(800);

        // Auto-dismiss "select your city/location" modals (Blinkco and similar
        // ordering platforms gate ALL API calls behind one of these). Doing
        // this lets the page's own JS set whatever cookie/session value is
        // needed, which is more reliable than guessing it via API params.
        await dismissLocationModal(page);

        // Scroll to trigger lazy-load.
        // Use 5 hops (not 3) with a longer pause at each stop so the browser
        // has time to decode and paint lazy images (Next.js loading="lazy",
        // IntersectionObserver-based loaders, etc.) before we evaluate the DOM.
        await page.evaluate(async () => {
            const max = document.body.scrollHeight;
            for (const frac of [0.2, 0.4, 0.6, 0.8, 1.0]) {
                window.scrollTo(0, max * frac);
                await new Promise(r => setTimeout(r, 400));
            }
        });
        await page.waitForTimeout(800);
        // Give the network one more short idle window so lazy image src attrs settle
        try { await page.waitForLoadState('networkidle', { timeout: 3000 }); } catch {}
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(300);

        // ── Blinkco strategy ──────────────────────────────────────────────────
        {
            const html = await page.content();
            const isBlinkco = html.includes('blinkco.io')
                || allNetworkLog.some(r => /\/api\/(geofence|branch|products|sections)/i.test(r.url));

            if (isBlinkco) {
                let restId = null;
                const m1 = html.match(/ordering-system\/(\d{4,6})\//);
                const m2 = html.match(/[?&"'`]restId[=:]["'`]?(\d{4,6})/i);
                const m3 = html.match(/rest_id[=:]["'`]?(\d{4,6})/i);
                if (m1) restId = m1[1]; else if (m2) restId = m2[1]; else if (m3) restId = m3[1];

                if (!restId) {
                    for (const r of allNetworkLog) {
                        const m = r.url.match(/[?&]restId=(\d+)/i);
                        if (m) { restId = m[1]; break; }
                    }
                }

                if (restId && !blinkcoCache[restId]) {
                    blinkcoCache[restId] = 'fetching';

                    const origin = (() => { try { return new URL(pageUrl).origin; } catch { return ''; } })();
                    console.error(`[Blinkco] restId=${restId} — resolving branchId`);

                    let branchId = null;

                    // Read rest_brId from intercepted URL query strings (most reliable)
                    for (const r of allNetworkLog) {
                        const m = r.url.match(/[?&]rest_brId=(\d+)/i);
                        if (m) { branchId = m[1]; break; }
                    }

                    // Fallback: intercepted geofence JSON body
                    if (!branchId) {
                        const geoLog = allNetworkLog.find(r =>
                            r.url.includes('/api/geofence') && r.payloadSnippet
                        );
                        if (geoLog) {
                            try {
                                const gj = JSON.parse(geoLog.payloadSnippet);
                                branchId = gj?.data?.cities?.[0]?.geofences?.[0]?.rest_brId
                                        || gj?.data?.[0]?.rest_brId || null;
                            } catch {}
                        }
                    }

                    // Fallback: live geofence call
                    if (!branchId) {
                        try {
                            const gr = await page.request.get(
                                `${origin}/api/geofence?restId=${restId}`,
                                { headers: { 'Accept': 'application/json', 'Referer': pageUrl }, timeout: 10000 }
                            );
                            if (gr.ok()) {
                                const gj = await gr.json().catch(() => null);
                                branchId = gj?.data?.cities?.[0]?.geofences?.[0]?.rest_brId
                                        || (Array.isArray(gj?.data) ? gj.data[0]?.rest_brId : null) || null;
                            }
                            console.error(`[Blinkco] geofence live → branchId=${branchId}`);
                        } catch(e) { console.error(`[Blinkco] geofence live failed: ${e.message}`); }
                    }

                    // Fallback: live branch call
                    if (!branchId) {
                        try {
                            const br = await page.request.get(
                                `${origin}/api/branch?restId=${restId}&delivery_type=0`,
                                { headers: { 'Accept': 'application/json', 'Referer': pageUrl }, timeout: 10000 }
                            );
                            if (br.ok()) {
                                const bj = await br.json().catch(() => null);
                                branchId = bj?.data?.restaurant_branches?.[0]?.id || null;
                            }
                            console.error(`[Blinkco] branch live → branchId=${branchId}`);
                        } catch(e) { console.error(`[Blinkco] branch live failed: ${e.message}`); }
                    }

                    console.error(`[Blinkco] final branchId=${branchId}`);

                    if (branchId) {
                        // Sections map
                        let sectionMap = {};
                        try {
                            const sr = await page.request.get(
                                `${origin}/api/sections?restId=${restId}&rest_brId=${branchId}`,
                                { headers: { 'Accept': 'application/json', 'Referer': pageUrl }, timeout: 10000 }
                            );
                            if (sr.ok()) {
                                const sj = await sr.json().catch(() => null);
                                (sj?.data || []).forEach(s => { sectionMap[s.id] = s.name || s.title || ''; });
                            }
                            console.error(`[Blinkco] sections: ${Object.keys(sectionMap).length}`);
                        } catch(e) { console.error(`[Blinkco] sections failed: ${e.message}`); }

                        // Products (try same-origin fetch first — carries session cookies)
                        let products = [];
                        for (const dt of [0, 1]) {
                            // Try via page.evaluate so session cookies are included
                            try {
                                const result = await page.evaluate(async ([origin, restId, branchId, dt]) => {
                                    const ctrl = new AbortController();
                                    const t = setTimeout(() => ctrl.abort(), 8000);  // was unbounded — could hang indefinitely
                                    try {
                                        const r = await fetch(
                                            `${origin}/api/products?restId=${restId}&rest_brId=${branchId}&delivery_type=${dt}`,
                                            { headers: { 'Accept': 'application/json' }, signal: ctrl.signal }
                                        );
                                        if (!r.ok) return { ok: false, status: r.status, body: await r.text() };
                                        return { ok: true, data: await r.json() };
                                    } catch (e) {
                                        return { ok: false, status: 0, body: String(e) };
                                    } finally {
                                        clearTimeout(t);
                                    }
                                }, [origin, restId, branchId, dt]);

                                console.error(`[Blinkco] /api/products dt=${dt} ok=${result.ok} status=${result.status || 200}`);

                                if (result.ok) {
                                    const found = result.data?.data || result.data?.items || result.data?.products || [];
                                    if (Array.isArray(found) && found.length) { products = found; break; }
                                    console.error(`[Blinkco] keys: ${Object.keys(result.data || {}).join(',')}`);
                                } else {
                                    console.error(`[Blinkco] error: ${(result.body || '').slice(0, 200)}`);
                                    // Fall back to page.request
                                    const pr = await page.request.get(
                                        `${origin}/api/products?restId=${restId}&rest_brId=${branchId}&delivery_type=${dt}`,
                                        { headers: { 'Accept': 'application/json', 'Referer': pageUrl }, timeout: 12000 }
                                    );
                                    console.error(`[Blinkco] page.request dt=${dt} status=${pr.status()}`);
                                    if (pr.ok()) {
                                        const pj = await pr.json().catch(() => null);
                                        const found = pj?.data || pj?.items || pj?.products || [];
                                        if (Array.isArray(found) && found.length) { products = found; break; }
                                    }
                                }
                            } catch(e) { console.error(`[Blinkco] products dt=${dt} failed: ${e.message}`); }
                        }

                        console.error(`[Blinkco] products fetched: ${products.length}`);

                        if (products.length > 0) {
                            blinkcoCache[restId] = { products, sectionMap, branchId };
                            _pushBlinkcoProducts(products, sectionMap, pageUrl);
                            console.error(`[Blinkco] ✅ ${products.length} items pushed`);
                        } else {
                            blinkcoCache[restId] = null;
                            console.error(`[Blinkco] ⚠ /api/products returned 0 items`);
                        }
                    } else {
                        blinkcoCache[restId] = null;
                        console.error(`[Blinkco] could not resolve branchId`);
                    }

                } else if (restId && blinkcoCache[restId] && blinkcoCache[restId] !== 'fetching') {
                    const { products, sectionMap } = blinkcoCache[restId];
                    _pushBlinkcoProducts(products, sectionMap, pageUrl);
                }
            }
        }

        // ── Window globals (Next.js / Redux / Nuxt) ──────────────────────────
        const windowData = await page.evaluate(() => {
            const KEYS = [
                '__NEXT_DATA__', '__NUXT__', '__INITIAL_STATE__', '__REDUX_STATE__',
                '__APP_STATE__', '__PRELOADED_STATE__', 'initialData', 'pageData',
                'appData', '__DATA__', '__STATE__',
            ];
            const result = {};
            KEYS.forEach(k => {
                try { const v = window[k]; if (v != null) result[k] = v; } catch {}
            });
            try {
                Object.keys(window).forEach(k => {
                    if (/menu|product|categor|item|food|dish|catalog/i.test(k)) {
                        try { result[`window.${k}`] = window[k]; } catch {}
                    }
                });
            } catch {}
            return result;
        });

        // ── indolj.io / Next.js SSR product extraction ────────────────────────
        // kababjeesfriedchicken.com (and many other indolj.io clients) embed the
        // full product object inside window.__NEXT_DATA__.props.pageProps.
        // Pull it out explicitly so deepScanJson can find name/price/category.
        if (windowData.__NEXT_DATA__) {
            try {
                const pp = windowData.__NEXT_DATA__?.props?.pageProps;
                // Product detail page: pp.product or pp.item
                const product = pp?.product || pp?.item || pp?.productData;
                if (product && (product.name || product.title)) {
                    const name = clean(product.name || product.title || '');
                    if (name && name.length > 1) {
                        const rawPrice = product.price ?? product.base_price ?? product.selling_price ?? null;
                        const price = rawPrice !== null ? String(rawPrice).replace(/\.0+$/, '') : null;
                        const category = clean(
                            product.category?.name || product.category_name ||
                            product.section?.name || product.menu_section || ''
                        ) || null;
                        const image = product.full_image_url || product.image_url ||
                                      product.image || product.thumbnail || null;
                        pushFood({
                            name,
                            description: clean(product.description || product.item_description || '') || null,
                            price,
                            category,
                            image: image ? String(image) : null,
                            _via: 'next_data',
                        }, pageUrl);
                        console.error(`[indolj/__NEXT_DATA__] product: ${name} price=${price}`);
                    }
                }
                // Category page: pp.products or pp.items array
                const productList = pp?.products || pp?.items || pp?.menuItems || pp?.categoryProducts;
                if (Array.isArray(productList) && productList.length) {
                    console.error(`[indolj/__NEXT_DATA__] category page: ${productList.length} items`);
                    deepScanJson(productList, pageUrl);
                }
            } catch(e) {
                console.error(`[indolj/__NEXT_DATA__] parse error: ${e.message}`);
            }
        }

        if (Object.keys(windowData).length) deepScanJson(windowData, pageUrl);

        // ── DOM scraping ──────────────────────────────────────────────────────
        const domResults = await page.evaluate(() => {
            const clean = s => (s || '').replace(/\s+/g, ' ').trim();

            // Resolve any image source to an absolute http(s) URL, handling:
            //   • Absolute URLs (most sites)
            //   • Next.js proxy: /_next/image?url=ENCODED → decode actual CDN URL
            //   • Relative paths: /img/foo.jpg → window.location.origin + path
            //   • srcset strings: take the first (best-quality) candidate
            const resolveImgUrl = (v) => {
                if (!v || v.includes('data:') || v.includes('placeholder') || v.includes('blank.gif')) return null;
                if (v.includes('/_next/image')) {
                    const m = v.match(/[?&]url=([^&]+)/);
                    if (m) { try { return decodeURIComponent(m[1]); } catch {} }
                }
                if (v.startsWith('http')) return v;
                if (v.startsWith('/')) return window.location.origin + v;
                return null;
            };

            const extractImage = el => {
                const img = el.querySelector('img');
                if (img) {
                    // currentSrc reflects what the browser actually loaded (post-lazy-load)
                    if (img.currentSrc) { const r = resolveImgUrl(img.currentSrc); if (r) return r; }
                    for (const attr of ['src', 'data-src', 'data-lazy-src', 'data-original', 'srcset', 'data-srcset']) {
                        const v = img.getAttribute(attr);
                        if (!v) continue;
                        // srcset: "url1 640w, url2 1280w" — take first entry
                        const candidate = /\s\d+[wx]/.test(v) ? v.split(/,\s*/)[0].split(/\s+/)[0] : v;
                        const r = resolveImgUrl(candidate);
                        if (r) return r;
                    }
                }
                for (const child of el.querySelectorAll('*')) {
                    const bg = window.getComputedStyle(child).backgroundImage;
                    if (bg && bg !== 'none') {
                        const m = bg.match(/url\(["']?([^"')]+)["']?\)/);
                        if (m) { const r = resolveImgUrl(m[1]); if (r) return r; }
                    }
                }
                return null;
            };

            const foodItems = [];
            const seen = new Set();

            // Strategy A: JSON-LD
            document.querySelectorAll('script[type="application/ld+json"]').forEach(script => {
                try {
                    const ld = JSON.parse(script.textContent || '{}');
                    const graphs = Array.isArray(ld) ? ld : (ld['@graph'] ? ld['@graph'] : [ld]);
                    graphs.forEach(node => {
                        const type = [].concat(node['@type'] || []).join(' ');
                        if (/Menu|FoodEstablishment/.test(type)) {
                            [].concat(node.hasMenuSection || []).forEach(sec => {
                                const secName = clean(sec.name || '');
                                [].concat(sec.hasMenuItem || []).forEach(mi => {
                                    const name = clean(mi.name || '');
                                    if (!name) return;
                                    const offers = [].concat(mi.offers || []);
                                    const price = offers.length
                                        ? clean(String(offers[0].price || offers[0].priceSpecification?.price || ''))
                                        : null;
                                    foodItems.push({ name, description: clean(mi.description||'')||null,
                                        price: price||null, category: secName||null, image: mi.image||null });
                                });
                            });
                        }
                        if (/MenuItem|Product/.test(type)) {
                            const name = clean(node.name || '');
                            if (!name) return;
                            const offers = [].concat(node.offers || []);
                            const price = offers.length
                                ? clean(String(offers[0].price || offers[0].priceSpecification?.price || ''))
                                : null;
                            foodItems.push({ name, description: clean(node.description||'')||null,
                                price: price||null, category: null, image: node.image||null });
                        }
                    });
                } catch {}
            });

            // Strategy B: CSS card selectors
            const CARD_SELECTORS = [
                '.menu-item', '.product-card', '.item-card', '.food-card', '.pizza-card',
                '.meal-card', '.dish-card', '.catalog-item', '.card',
                '[data-product-id]', '[data-item-id]', '[data-menu-item-id]', '[data-dish-id]',
                '[class*="product_item_card"]', '[class*="ProductItem"]', '[class*="product-item"]',
                '[class*="menuItem"]', '[class*="menu-item"]', '[class*="MenuItem"]',
                '[class*="food-item"]', '[class*="FoodItem"]', '[class*="foodItem"]',
                '[class*="dish-item"]', '[class*="DishItem"]', '[class*="dishItem"]',
                '[class*="meal-card"]', '[class*="MealCard"]',
                '[class*="catalog-item"]', '[class*="CatalogItem"]',
                '[class*="item-wrapper"]', '[class*="ItemWrapper"]',
                '[class*="product-wrapper"]', '[class*="ProductWrapper"]',
                '[class*="product-tile"]', '[class*="ProductTile"]',
                '[class*="product-box"]', '[class*="ProductBox"]',
                '[class*="ordering-item"]', '[class*="OrderingItem"]',
                '[class*="grid-item"]', '[class*="GridItem"]',
                '[data-testid*="product"]', '[data-testid*="menu"]',
                '[class*="CategoryProduct"]', '[class*="ItemTile"]',
                '[class*="ComboCard"]', '[class*="FeaturedItem"]',
                '[id^="product-item-"]',
                '[itemtype*="Product"]', '[itemtype*="MenuItem"]',
            ].join(',');

            document.querySelectorAll(CARD_SELECTORS).forEach(card => {
                const nameEl = card.querySelector(
                    'h1,h2,h3,h4,h5,h6,' +
                    '[class*="title"],[class*="Title"],[class*="name"],[class*="Name"],' +
                    '[itemprop="name"]'
                );
                const name = clean(nameEl?.innerText || nameEl?.textContent || '');
                if (!name || name.length < 2 || name.length > 200) return;
                if (seen.has(name.toLowerCase())) return;
                seen.add(name.toLowerCase());

                const priceEl = card.querySelector(
                    '[class*="price"],[class*="Price"],[class*="cost"],[class*="Cost"],' +
                    '[class*="rate"],[class*="Rate"],[class*="amount"],[class*="Amount"],' +
                    '[itemprop="price"]'
                );
                let price = priceEl ? clean(priceEl.innerText || priceEl.textContent || '') : null;
                if (!price) {
                    const priceMatch = Array.from(card.querySelectorAll('*'))
                        .filter(el => el.children.length === 0)
                        .find(el => /^(Rs\.?|PKR|₨|\$|€|£|AED|SAR)?\s*[\d,]+(\.\d{1,2})?$/.test(
                            clean(el.innerText || el.textContent || '')
                        ));
                    if (priceMatch) price = clean(priceMatch.innerText || priceMatch.textContent || '');
                }

                const descEl = card.querySelector(
                    'p,[class*="desc"],[class*="Desc"],[class*="description"],[class*="Description"],' +
                    '[class*="subtitle"],[class*="Subtitle"],[itemprop="description"]'
                );
                const description = descEl ? clean(descEl.innerText || descEl.textContent || '') : null;

                // Category: KFC and many other sites use <div> containers, not <section>.
                // Broaden the closest() selector to include generic divs with category/section
                // class hints, and search headings on the outerCard level too so we aren't
                // restricted to the inner card-body subtree.
                const section = card.closest(
                    'section,[class*="section"],[class*="category"],[class*="Category"],' +
                    'div[class*="section"],div[class*="category"],div[class*="tab"],div[class*="Tab"]'
                );
                const categoryEl = section?.querySelector('h1,h2,h3,h4,[class*="section-name"],[class*="category-name"]');
                const category = categoryEl ? clean(categoryEl.innerText || categoryEl.textContent || '') : null;

                // For Bootstrap-style cards the <img class="card-img-top"> lives as a
                // sibling of <div class="card-body">, NOT inside it.  Walk up to the
                // outermost .card ancestor before calling extractImage so we search the
                // full card subtree (img + card-body), not just the inner div.
                const outerCard = card.closest('.card') || card;
                foodItems.push({ name, description: description||null, price: price||null,
                    category: category||null, image: extractImage(outerCard) });
            });

            // Strategy C: Price-proximity fallback
            if (!foodItems.length) {
                const pricePattern = /^(Rs\.?|PKR|₨|\$|€|£|AED|SAR)?\s*[\d,]{2,}(\.\d{1,2})?$/;
                const priceEls = Array.from(document.querySelectorAll('*'))
                    .filter(el => el.children.length === 0
                        && pricePattern.test(clean(el.innerText || ''))
                        && el.getBoundingClientRect().width > 0);

                const cardsSeen = new Set();
                priceEls.forEach(priceEl => {
                    let card = priceEl;
                    for (let i = 0; i < 6; i++) {
                        if (!card.parentElement) break;
                        card = card.parentElement;
                        const { width } = card.getBoundingClientRect();
                        if (width > 80 && width < 800) break;
                    }
                    if (cardsSeen.has(card)) return;
                    cardsSeen.add(card);
                    const nameEl = card.querySelector('h1,h2,h3,h4,h5,h6,strong,b');
                    const name   = clean(nameEl?.innerText || '');
                    if (!name || name.length < 2) return;
                    foodItems.push({
                        name,
                        description: clean(card.querySelector('p')?.innerText || '') || null,
                        price: clean(priceEl.innerText),
                        // Walk up to the outermost .card ancestor so the img sibling of
                        // card-body (Bootstrap pattern) is reachable — same fix as Strategy B.
                        category: clean(
                            card.closest(
                                'section,[class*="section"],[class*="category"],' +
                                'div[class*="section"],div[class*="category"],div[class*="tab"]'
                            )?.querySelector('h2,h3')?.innerText || ''
                        ) || null,
                        image: extractImage(card.closest('.card') || card),
                    });
                });
            }

            // Faculty profiles
            const facultyProfiles = [];
            const FACULTY_SELECTORS = [
                '[class*="faculty-card"]', '[class*="FacultyCard"]', '[class*="faculty_card"]',
                '[class*="staff-card"]', '[class*="StaffCard"]', '[class*="team-card"]',
                '[class*="person-card"]', '[class*="PersonCard"]', '[class*="member-card"]',
                '[class*="teacher"]', '[class*="professor"]', '[class*="instructor"]',
                '.faculty-member', '.staff-member', '.team-member',
                'article[class*="faculty"]', 'article[class*="staff"]', 'article[class*="person"]',
            ].join(',');

            document.querySelectorAll(FACULTY_SELECTORS).forEach(card => {
                const nameEl = card.querySelector(
                    'h1,h2,h3,h4,[class*="name"],[class*="Name"],[class*="title"],[class*="Title"]'
                );
                const name = clean(nameEl?.innerText || '');
                if (!name || name.length < 3) return;
                const getText = (...sels) => {
                    for (const sel of sels) {
                        const el = card.querySelector(sel);
                        if (el) return clean(el.innerText || '');
                    }
                    return '';
                };
                facultyProfiles.push({
                    name,
                    designation:   getText('[class*="designation"]','[class*="position"]','[class*="role"]'),
                    department:    getText('[class*="department"]','[class*="dept"]','[class*="school"]'),
                    qualification: getText('[class*="qualification"]','[class*="degree"]','[class*="education"]'),
                    institution:   getText('[class*="institution"]','[class*="university"]','[class*="college"]'),
                    email:         card.querySelector('a[href^="mailto:"]')?.href?.replace('mailto:','') || '',
                    image:         card.querySelector('img')?.src || '',
                });
            });

            if (!facultyProfiles.length) {
                document.querySelectorAll('table tr').forEach(row => {
                    const cells = Array.from(row.querySelectorAll('td,th'));
                    if (cells.length < 2) return;
                    const name = clean(cells[0]?.innerText || '');
                    if (!name || name.length < 3 || !/[A-Z]/.test(name[0])) return;
                    facultyProfiles.push({
                        name,
                        designation:   clean(cells[1]?.innerText || ''),
                        department:    clean(cells[2]?.innerText || ''),
                        qualification: clean(cells[3]?.innerText || ''),
                        institution:   '', email: '', image: '',
                    });
                });
            }

            // Page content
            const getTextEls = sel => Array.from(document.querySelectorAll(sel))
                .map(el => clean(el.innerText || el.textContent || '')).filter(t => t.length > 1);
            const getMeta = name =>
                document.querySelector(`meta[name="${name}"]`)?.content ||
                document.querySelector(`meta[property="${name}"]`)?.content || null;

            const headings = {};
            ['h1','h2','h3','h4','h5','h6'].forEach(t => {
                const v = getTextEls(t); if (v.length) headings[t] = v;
            });

            const tableData = [];
            document.querySelectorAll('table').forEach(table => {
                const rows = [];
                table.querySelectorAll('tr').forEach(tr => {
                    const cells = Array.from(tr.querySelectorAll('td,th'))
                        .map(td => clean(td.innerText || td.textContent || '')).filter(Boolean);
                    if (cells.length) rows.push(cells.join(' | '));
                });
                if (rows.length) tableData.push(rows.join('\n'));
            });

            return {
                foodItems,
                facultyProfiles,
                pageContent: {
                    url:   window.location.href,
                    title: document.title,
                    meta: {
                        description:   getMeta('description'),
                        keywords:      getMeta('keywords'),
                        ogTitle:       getMeta('og:title'),
                        ogDescription: getMeta('og:description'),
                        ogImage:       getMeta('og:image'),
                        canonical:     document.querySelector('link[rel="canonical"]')?.href || null,
                    },
                    headings,
                    paragraphs: getTextEls('p'),
                    listItems: Array.from(document.querySelectorAll('li'))
                        .map(li => clean(li.innerText || li.textContent || ''))
                        .filter(t => t.length > 3 && t.length < 400),
                    tableData,
                    boldText: getTextEls('strong,b').filter(t => t.length > 2 && t.length < 200),
                    divText: Array.from(document.querySelectorAll(
                        'div[class*="content"],div[class*="desc"],div[class*="text"],' +
                        'div[class*="about"],div[class*="info"],div[class*="detail"],' +
                        'section p,article p,.card p'
                    )).map(el => clean(el.innerText || el.textContent || ''))
                      .filter(t => t.length > 20 && t.length < 1000),
                    navigation: Array.from(document.querySelectorAll('nav a,header a'))
                        .map(a => ({ text: clean(a.innerText||''), href: a.href }))
                        .filter(a => a.text && a.href),
                    stats: {
                        wordCount:  document.body.innerText.trim().split(/\s+/).length,
                        imageCount: document.images.length,
                        linkCount:  document.links.length,
                    },
                    scrapedAt: new Date().toISOString(),
                },
            };
        });

        domResults.foodItems.forEach(item => pushFood(item, pageUrl));
        domResults.facultyProfiles.forEach(p => pushFaculty(p, pageUrl));
        allPageData.push(domResults.pageContent);

        // Small jitter — with concurrency > 1 the "looks human" framing is
        // moot anyway (parallel requests aren't human-like to begin with);
        // this just avoids hammering one site in lockstep.
        await page.waitForTimeout(400 + Math.random() * 500);  // 0.4–0.9s

        // ── Enqueue links ─────────────────────────────────────────────────────
        const ORDERING_DOMAINS = [
            /blinkco\.io/i, /tossdown\.com/i, /foodics\.com/i,
            /hungerstation\.com/i, /talabat\.com/i, /cheetay\.pk/i,
            /eatoye\.pk/i, /krave\.pk/i, /foodpanda\.pk/i,
            /mcdelivery\.com/i, /kfcpakistan\.com/i, /order\.pizzahut\.com/i,
            /drsaucy/i, /indolj\.io/i,
        ];
        const startHost = (() => {
            try { return new URL(startUrl).hostname.replace(/^www\./, ''); } catch { return ''; }
        })();
        const SKIP_EXT  = /\.(pdf|zip|jpg|jpeg|png|gif|svg|mp4|mp3|css|js|woff|ttf|ico)(\?.*)?$/i;
        const SKIP_PATH = /\/(login|logout|register|cart|checkout|wp-admin|wp-json|feed|xmlrpc)/i;

        // Only spider same-domain links when the sitemap gave us NOTHING to
        // seed from. When a sitemap was found, seedUrls already IS the site's
        // full content map — following every <a href> on every page as well
        // is pure redundancy that snowballs the request queue (nav links,
        // footer links, pagination, related-post widgets all get re-enqueued
        // from every single page) and was the main reason crawls dragged on
        // toward crawlLimit on sites that had a perfectly good sitemap.
        if (!sitemapUrls.length) {
            await enqueueLinks({
                selector: 'a[href]',
                strategy: 'same-domain',
                transformRequestFunction: req => {
                    if (SKIP_EXT.test(req.url) || SKIP_PATH.test(req.url)) return false;
                    return req;
                },
            });
        }

        await enqueueLinks({
            selector: 'a[href]',
            strategy: 'all',
            transformRequestFunction: req => {
                try {
                    const host = new URL(req.url).hostname.replace(/^www\./, '');
                    if (host === startHost) return false;
                    if (!ORDERING_DOMAINS.some(p => p.test(req.url))) return false;
                    if (SKIP_EXT.test(req.url)) return false;
                    return req;
                } catch { return false; }
            },
        });
    },

    failedRequestHandler({ request, response }) {
        const status = response?.status?.() ?? 0;
        if (status === 403)      console.error(`[BLOCKED] 403 on ${request.url}`);
        else if (status === 429) console.error(`[RATE-LIMITED] 429 on ${request.url}`);
        else                     console.error(`[FAILED] ${status} on ${request.url}`);
    },
});

// ── Blinkco variant price resolver ───────────────────────────────────────────
// Blinkco deliberately stores price=0 on any item that requires a customer
// choice (size, flavor, "make it a combo", etc.). The real prices live in
// option_groups[i].options[j].price (nested two levels deep).
// This helper finds the minimum non-zero price across ALL option groups so
// the chatbot can say "starting from Rs X" instead of showing Rs 0.
function _resolveVariantMinPrice(p) {
    let min = null;
    // Walk all common variant container field names
    for (const topKey of ['option_groups', 'options', 'modifiers', 'modifier_groups', 'variants', 'variations']) {
        const topArr = p[topKey];
        if (!Array.isArray(topArr) || !topArr.length) continue;
        for (const entry of topArr) {
            // entry might be a group (with nested options/choices/items) or a flat option
            const optArr = Array.isArray(entry.options)  ? entry.options
                         : Array.isArray(entry.choices)  ? entry.choices
                         : Array.isArray(entry.items)    ? entry.items
                         : [entry];
            for (const opt of optArr) {
                const v = parseFloat(opt.price ?? opt.amount ?? opt.cost ?? opt.additional_price ?? 0);
                if (v > 0 && (min === null || v < min)) min = v;
            }
        }
    }
    return min;
}

// ── Blinkco product push helper ───────────────────────────────────────────────
function _pushBlinkcoProducts(products, sectionMap, pageUrl) {
    products.forEach(p => {
        const name = clean(p.name || p.item_name || p.title || '');
        if (!name || name.length < 2) return;
        const rawPrice = p.price ?? p.base_price ?? p.selling_price ?? null;
        // When the top-level price is 0 (variant-gated item), fall back to
        // the minimum option price so we show the cheapest available price
        // rather than Rs 0.
        let price;
        if (rawPrice !== null && parseFloat(rawPrice) > 0) {
            price = String(rawPrice).replace(/\.0+$/, '');
        } else {
            const varMin = _resolveVariantMinPrice(p);
            price = varMin !== null ? String(varMin) : null;
        }
        const catId    = p.section_id || p.category_id || p.cat_id || null;
        const category = (catId && sectionMap[catId])
            ? sectionMap[catId]
            : clean(p.category_name || p.category || p.section || '');
        const image = p.full_image_url || p.image_url || p.image || p.thumbnail || null;
        pushFood({
            name,
            description: clean(p.description || p.item_description || '') || null,
            price,
            category: category || null,
            image: image ? String(image) : null,
            _via: 'blinkco_api',
        }, pageUrl);
    });
}

// ── Sitemap auto-discovery ────────────────────────────────────────────────────
const nodeFetchText = (url) => new Promise((resolve) => {
    try {
        const parsed = new URL(url);
        const options = {
            hostname: parsed.hostname,
            path:     parsed.pathname + parsed.search,
            method:   'GET',
            headers:  { 'User-Agent': UA, 'Accept': 'text/xml,application/xml,text/plain,*/*' },
        };
        let raw = '';
        const req = https.request(options, (res) => {
            if ((res.statusCode === 301 || res.statusCode === 302) && res.headers.location) {
                resolve(nodeFetchText(res.headers.location));
                return;
            }
            res.on('data', d => raw += d);
            res.on('end', () => resolve({ status: res.statusCode, body: raw }));
        });
        req.on('error', () => resolve({ status: 0, body: '' }));
        req.setTimeout(20000, () => { req.destroy(); resolve({ status: 0, body: '' }); });  // was 10s
        req.end();
    } catch { resolve({ status: 0, body: '' }); }
});

function parseSitemapLocs(xml) {
    const locs  = [];
    const locRe = /<loc>\s*(https?:\/\/[^<\s]+)\s*<\/loc>/gi;
    let m;
    while ((m = locRe.exec(xml)) !== null) locs.push(m[1].trim());
    return locs;
}

async function expandSitemap(url, depth = 0) {
    if (depth > 3) return [];
    const res = await nodeFetchText(url);
    if (res.status !== 200 || !res.body) return [];
    const locs    = parseSitemapLocs(res.body);
    const isIndex = /<sitemapindex/i.test(res.body) ||
                    (locs.length > 0 && locs.every(l => /\.xml(\?.*)?$/i.test(l)));
    if (isIndex) {
        const all = [];
        for (const loc of locs) { const n = await expandSitemap(loc, depth + 1); all.push(...n); }
        return all;
    }
    return locs;
}

const SITEMAP_SKIP     = /\/(login|logout|register|cart|checkout|wp-admin|wp-json|wp-login|feed|xmlrpc|tag\/|author\/|page\/\d|cdn-cgi|\?replytocom)/i;
const SITEMAP_SKIP_EXT = /\.(css|js|jpg|jpeg|png|gif|svg|pdf|zip|mp4|mp3|woff|ttf|ico)(\?.*)?$/i;

/**
 * Deduplicate indolj.io-style sitemap duplicates.
 * The sitemap contains both:
 *   /product/Zenga-Burger          ← canonical slug
 *   /product/Zenga-Burger-649565   ← slug+numericId (same page)
 * We keep only the slug-only version (or the shorter one) so we don't
 * burn crawl budget visiting identical pages twice.
 */
function deduplicateSitemapUrls(urls) {
    // Group by path-without-trailing-numeric-id
    const canonical = new Map(); // normKey → shortest url
    for (const u of urls) {
        let path;
        try { path = new URL(u).pathname; } catch { continue; }
        // Strip trailing -<digits> from the last path segment
        const normKey = path.replace(/-\d{4,7}(\/)?$/, '$1');
        const existing = canonical.get(normKey);
        if (!existing || u.length < existing.length) {
            canonical.set(normKey, u);
        }
    }
    return [...canonical.values()];
}

async function discoverSitemapUrls(baseUrl) {
    const origin = (() => { try { return new URL(baseUrl).origin; } catch { return ''; } })();
    if (!origin) return [];

    const candidates = [];
    const robotsRes  = await nodeFetchText(`${origin}/robots.txt`);
    if (robotsRes.status === 200) {
        (robotsRes.body.match(/^Sitemap:\s*(https?:\/\/\S+)/gim) || []).forEach(l => {
            const u = l.replace(/^Sitemap:\s*/i, '').trim();
            if (u) candidates.push(u);
        });
    }

    [
        '/sitemap.xml', '/sitemap_index.xml', '/sitemap-index.xml',
        '/sitemap/sitemap.xml', '/sitemaps/sitemap.xml',
        '/sitemap-products.xml', '/product-sitemap.xml',
        '/page-sitemap.xml', '/post-sitemap.xml',
        '/news-sitemap.xml', '/sitemap1.xml',
    ].forEach(p => { const u = `${origin}${p}`; if (!candidates.includes(u)) candidates.push(u); });

    if (/\.xml(\?.*)?$/i.test(baseUrl) && !candidates.includes(baseUrl)) candidates.unshift(baseUrl);

    // Probe every candidate sitemap path CONCURRENTLY instead of sequentially.
    // Most of these 11 candidates 404 immediately, but a few sites are slow to
    // respond or hang until the 20s socket timeout — sequential awaiting meant
    // worst case ~11×20s = 220s spent just discovering the sitemap, before a
    // single content page was even crawled. Promise.all collapses that to the
    // slowest single probe (~20s worst case).
    const seen = new Set(), allUrls = [];
    const results = await Promise.all(candidates.map(u => expandSitemap(u).catch(() => [])));
    results.forEach((locs, i) => {
        const sitemapUrl = candidates[i];
        if (locs.length) console.error(`[Sitemap] ${sitemapUrl} → ${locs.length} URLs`);
        for (const loc of locs) {
            if (seen.has(loc) || SITEMAP_SKIP.test(loc) || SITEMAP_SKIP_EXT.test(loc)) continue;
            seen.add(loc);
            allUrls.push(loc);
        }
    });
    console.error(`[Sitemap] total unique content URLs: ${allUrls.length}`);
    const deduped = deduplicateSitemapUrls(allUrls);
    if (deduped.length < allUrls.length) {
        console.error(`[Sitemap] deduped slug+ID duplicates: ${allUrls.length} → ${deduped.length}`);
    }
    return deduped;
}

// ── Run ───────────────────────────────────────────────────────────────────────
const sitemapUrls = await discoverSitemapUrls(startUrl);

// Always include the homepage + a set of common high-value paths so that even
// sites with a thin sitemap (e.g. KFC whose sitemap only returned 1 URL) still
// get the menu page crawled. Deduplicate against whatever the sitemap gave us.
const _origin    = (() => { try { const u = new URL(startUrl); return u.origin; } catch { return ''; } })();
const _guessUrls = [startUrl, ...( _origin ? [
    _origin + '/menu', _origin + '/menu/', _origin + '/our-menu',
    _origin + '/food', _origin + '/order', _origin + '/products',
] : [])];
const _sitemapSet = new Set([startUrl, ...sitemapUrls]);
const _extraSeeds = _guessUrls.filter(u => !_sitemapSet.has(u));
const seedUrls    = sitemapUrls.length > 0
    ? [startUrl, ...sitemapUrls, ..._extraSeeds]
    : [startUrl, ..._extraSeeds];

// Set the crawl limit AFTER we know how many URLs the sitemap has.
// Use whichever is larger: the user's max_pages or (sitemap size + 10% buffer).
// This prevents the old bug where max_pages=30 would stop crawling after 30
// requests even though the sitemap contained 200+ product/category URLs.
crawlLimit = Math.max(maxPages, Math.ceil(seedUrls.length * 1.1) + 10);
crawler._config = crawler._config || {};
// PlaywrightCrawler exposes maxRequestsPerCrawl via its internal queue limit.
// The cleanest way to override it post-construction is to patch the property.
Object.defineProperty(crawler, 'maxRequestsPerCrawl', {
    get() { return crawlLimit; },
    configurable: true,
});
// Also patch the internal _maxRequestsPerCrawl field used by Crawlee v3.
if ('_maxRequestsPerCrawl' in crawler) {
    crawler._maxRequestsPerCrawl = crawlLimit;
}
console.error(sitemapUrls.length > 0
    ? `[Sitemap] seeding crawler with ${seedUrls.length} URLs (crawlLimit=${crawlLimit})`
    : `[Sitemap] no sitemap found — crawling from homepage (crawlLimit=${crawlLimit})`
);

await crawler.run(seedUrls);

// ── Write output files ────────────────────────────────────────────────────────
fs.mkdirSync(outputDir, { recursive: true });
const ts = new Date().toISOString().replace(/[:.]/g, '-');

const foodPath    = path.join(outputDir, `${ts}_food-items.json`);
const pagePath    = path.join(outputDir, `${ts}_page-data.json`);
const facultyPath = path.join(outputDir, `${ts}_faculty-profiles.json`);
const netLogPath  = path.join(outputDir, `${ts}_network-log.json`);

fs.writeFileSync(foodPath,    JSON.stringify({ meta: { startUrl, totalItems:    allFoodItems.length,       exportedAt: new Date().toISOString() }, items:    allFoodItems },       null, 2));
fs.writeFileSync(pagePath,    JSON.stringify({ meta: { startUrl, totalPages:    allPageData.length,        exportedAt: new Date().toISOString() }, pages:    allPageData },         null, 2));
fs.writeFileSync(facultyPath, JSON.stringify({ meta: { startUrl, totalProfiles: allFacultyProfiles.length, exportedAt: new Date().toISOString() }, profiles: allFacultyProfiles }, null, 2));
fs.writeFileSync(netLogPath,  JSON.stringify({ meta: { startUrl, totalRequests: allNetworkLog.length,      exportedAt: new Date().toISOString() }, requests: allNetworkLog },       null, 2));

console.log(JSON.stringify({
    foodPath, pagePath, facultyPath, netLogPath,
    foodItems:       allFoodItems.length,
    pageCount:       allPageData.length,
    facultyProfiles: allFacultyProfiles.length,
    networkRequests: allNetworkLog.length,
}));
"""

# ─── Pydantic request ──────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url:             str
    # Lowered from 300. With the same-domain link-crawl now skipped whenever a
    # sitemap is found (see _CRAWLEE_SCRIPT), sites WITH a sitemap already get
    # their true page count via sitemap_size × 1.1 regardless of this value —
    # this default only bounds sites with NO sitemap, where the crawler must
    # discover pages by following links, and 300 blind link-follows on an
    # unknown site was the single biggest cause of slow crawls in practice.
    max_pages:       int = 100
    max_concurrency: int = 4     # parallel browser pages — was hardcoded to 1 in the script


# ─── Ingest helper ────────────────────────────────────────────────────────────

def _ingest_file(
    job_id:      str,
    job:         dict,
    file_path:   str | None,
    file_count:  int,
    source_type: str,
    label:       str,
    category:    str,
    idx_name:    str,
    ns:          str,
    doc_id:      int,
    bot_id:      int,
) -> int:
    if not file_path or not os.path.exists(file_path) or file_count == 0:
        print(f"[crawlee_scrape] skip {label}: path={file_path} count={file_count}",
              file=sys.stderr, flush=True)
        return 0

    if not ns:
        msg = f"{label} ingest aborted — namespace is empty"
        job["errors"].append(msg)
        print(f"[crawlee_scrape] {msg}", file=sys.stderr, flush=True)
        return 0

    sub_job_id = f"{job_id}_{source_type}"
    _crawlee_jobs[sub_job_id] = {
        "status": "parsing", "total": 0, "done": 0, "pct": 0,
        "stage_detail": "", "errors": [], "items_count": 0,
    }

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        msg = f"{label} JSON load failed: {e}"
        job["errors"].append(msg)
        print(f"[crawlee_scrape] {msg}", file=sys.stderr, flush=True)
        return 0

    async def _run():
        return await _run_crawlee_ingest(
            job_id=sub_job_id, raw_data=raw_data, source_type=source_type,
            category=category, index_name=idx_name, doc_id=doc_id,
            bot_id=bot_id, saved_path=file_path, db_factory=SessionLocal, namespace=ns,
        )

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception as e:
        msg = f"{label} ingest raised: {e}"
        job["errors"].append(msg)
        print(f"[crawlee_scrape] {msg}", file=sys.stderr, flush=True)
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        return 0

    sub = _crawlee_jobs.get(sub_job_id, {})
    if sub.get("status") == "error":
        job["errors"].extend(sub.get("errors", []))

    vectors = sub.get("done", 0)
    print(f"[crawlee_scrape] {label} → {vectors} vectors upserted", file=sys.stderr, flush=True)
    return vectors


# ─── Background scrape + ingest task ─────────────────────────────────────────

def _run_scrape_and_ingest(
    job_id:    str,
    url:       str,
    max_pages: int,
    bot_id:    int,
    user_id:   int,
    doc_id:    int,
    category:  str,
    max_concurrency: int = 4,
):
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
        _update_doc_status(doc_id, DocStatus.failed)
        return

    food_path = page_path = faculty_path = None
    food_count = page_count = faculty_count = 0

    try:
        print(f"[crawlee_scrape] running node {script_path}", file=sys.stderr, flush=True)

        # Timeout now scales with the requested crawl size and concurrency
        # instead of a flat cap — a 300-page sitemap-seeded crawl needs more
        # wall-clock time than a 10-page one, and the old flat 1200s was both
        # too short for large crawls and unnecessarily long for small ones.
        seconds_per_page = max(3, round(20 / max(max_concurrency, 1)))
        dynamic_timeout  = min(3600, max(600, max_pages * seconds_per_page))

        result = subprocess.run(
            ["node", script_path, url, output_dir, str(max_pages), str(max_concurrency)],
            capture_output=True,
            text=True,
            cwd=project_root,
            env=child_env,
            timeout=dynamic_timeout,
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

        data          = json.loads(result_line)
        food_path     = data["foodPath"]
        page_path     = data["pagePath"]
        faculty_path  = data.get("facultyPath")
        food_count    = data.get("foodItems", 0)
        page_count    = data.get("pageCount", 0)
        faculty_count = data.get("facultyProfiles", 0)
        network_reqs  = data.get("networkRequests", 0)

        print(
            f"[crawlee_scrape] scraped pages={page_count} food={food_count} "
            f"faculty={faculty_count} network_requests={network_reqs}",
            file=sys.stderr, flush=True,
        )
        job.update({
            "stage_detail":     f"Scraped {page_count} pages, {food_count} food items, "
                                f"{faculty_count} faculty profiles ({network_reqs} network reqs)",
            "food_path":        food_path,
            "page_path":        page_path,
            "faculty_path":     faculty_path,
            "food_count":       food_count,
            "page_count":       page_count,
            "faculty_count":    faculty_count,
            "network_requests": network_reqs,
        })

    except Exception as e:
        job["status"]       = "error"
        job["errors"].append(f"Scraping failed: {e}")
        job["stage_detail"] = f"Scraping failed: {e}"
        print(f"[crawlee_scrape] ERROR: {e}", file=sys.stderr, flush=True)
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        _update_doc_status(doc_id, DocStatus.failed)
        return
    finally:
        try: os.unlink(script_path)
        except Exception: pass

    # ── Ingest into Pinecone ──────────────────────────────────────────────────
    idx_name = _index_name_for_category(category)
    ns       = _namespace(user_id, bot_id)
    print(f"[crawlee_scrape] namespace={repr(ns)} index={idx_name}", file=sys.stderr, flush=True)

    job["status"] = "ingesting_food"
    job["stage_detail"] = f"Ingesting {food_count} food items into Pinecone …"
    v_food = _ingest_file(job_id, job, food_path, food_count,
                          "food_items", "Food", category, idx_name, ns, doc_id, bot_id)

    v_faculty = 0
    if category == "faculty":
        job["status"] = "ingesting_faculty"
        job["stage_detail"] = f"Ingesting {faculty_count} faculty profiles into Pinecone …"
        v_faculty = _ingest_file(job_id, job, faculty_path, faculty_count,
                                 "faculty_profiles", "Faculty", category, idx_name, ns, doc_id, bot_id)

    job["status"] = "ingesting_pages"
    job["stage_detail"] = f"Ingesting {page_count} pages into Pinecone …"
    v_pages = _ingest_file(job_id, job, page_path, page_count,
                           "page_data", "Pages", category, idx_name, ns, doc_id, bot_id)

    total_vectors = v_food + v_faculty + v_pages

    if job["errors"]:
        job["status"]       = "done_with_errors"
        job["stage_detail"] = f"Completed with {len(job['errors'])} error(s)"
    else:
        job["status"]       = "done"
        job["stage_detail"] = f"✅ {food_count} items + {page_count} pages → {total_vectors} vectors"

    job["total_vectors"] = total_vectors
    _update_doc_status(doc_id, DocStatus.trained, progress=100, accuracy=92.0)
    print(f"[crawlee_scrape] ✅ done job={job_id} vectors={total_vectors}", file=sys.stderr, flush=True)


def _update_doc_status(doc_id, status, progress=0, accuracy=0.0):
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
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    url = body.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    from models import Chatbot as ChatbotModel
    bot = db.query(ChatbotModel).filter(ChatbotModel.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    category = getattr(bot, "category", "university")

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
        "status": "queued", "url": url, "doc_id": doc.id, "category": category,
        "stage_detail": "Queued…", "food_count": 0, "page_count": 0,
        "faculty_count": 0, "network_requests": 0, "total_vectors": 0,
        "food_path": None, "page_path": None, "faculty_path": None, "errors": [],
    }

    import threading
    t = threading.Thread(
        target=_run_scrape_and_ingest,
        kwargs=dict(job_id=job_id, url=url, max_pages=body.max_pages,
                    bot_id=bot_id, user_id=user_id, doc_id=doc.id, category=category,
                    max_concurrency=body.max_concurrency),
        daemon=True,
    )
    t.start()
    print(f"[crawlee_scrape] ✓ thread started job={job_id} tid={t.ident}", file=sys.stderr, flush=True)

    return {
        "id": doc.id, "name": url, "type": "website", "status": "training",
        "training_progress": 0, "upload_date": doc.upload_date,
        "size_label": "—", "source_url": url, "scrape_job_id": job_id,
    }


@router.get("/chatbots/{bot_id}/documents/scrape/{job_id}/progress")
async def scrape_progress_sse(
    bot_id:  int,
    job_id:  str,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if job_id not in _scrape_jobs:
        raise HTTPException(status_code=404, detail="Scrape job not found")

    async def _stream() -> AsyncGenerator[str, None]:
        yield "retry: 3000\n\n"
        while True:
            job_data = _scrape_jobs.get(job_id, {})
            yield f"data: {json.dumps(job_data)}\n\n"
            if job_data.get("status", "") in ("done", "done_with_errors", "error"):
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Connection": "keep-alive",
        },
    )


@router.get("/chatbots/{bot_id}/documents/scrape/{job_id}/status")
async def scrape_status_json(
    bot_id:  int,
    job_id:  str,
    user_id: int = Query(...),
    token:   str = Query(...),
):
    if not _verify_auth(user_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if job_id not in _scrape_jobs:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return _scrape_jobs[job_id]