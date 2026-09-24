# Restaurant Chatbot — FastAPI

## Files
```
restaurant_chatbot/
├── main.py              ← FastAPI backend (converted from Streamlit)
├── static/
│   └── index.html       ← Full-page chat UI
├── widget.html          ← Embeddable floating bubble widget
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create `.env`
```env
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_HARDEES=your-index-name
TWILIO_SID=...
TWILIO_AUTH_TOKEN=...
```

### 3. Run locally
```bash
uvicorn main:app --reload --port 8000
```

Open: http://localhost:8000

---

## Deploy to Railway / Render / Fly.io

### Railway (recommended — free tier)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```
Set your `.env` variables in the Railway dashboard → Variables tab.

### Render
1. Push to GitHub
2. New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add env vars in dashboard

### Fly.io
```bash
fly launch
fly secrets set OPENAI_API_KEY=sk-... PINECONE_API_KEY=... ...
fly deploy
```

---

## Embed Widget on Any Website

After deploying, open `widget.html` and change line:
```js
const W_API_URL = "http://localhost:8000";
// → change to your deployed URL e.g. "https://your-app.railway.app"
```

Then embed it in any HTML page:
```html
<!-- Option A: iframe -->
<iframe src="https://your-app.railway.app" width="100%" height="600px" style="border:none;border-radius:16px;"></iframe>

<!-- Option B: drop widget.html script into your site -->
<!-- Just paste the contents of widget.html before </body> -->
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Main chat endpoint |
| POST | `/finalize` | Finalize & save order |
| DELETE | `/cancel` | Cancel active order |
| GET | `/health` | Health check |

### POST /chat — Request
```json
{
  "session_id": "uuid",
  "message": "show me burgers",
  "cart_items": [],
  "order_details": {},
  "awaiting_order_details": false,
  "current_field": null,
  "pending_cart": []
}
```

### POST /chat — Response types
```json
{ "type": "menu_items", "message": "...", "items": [...], "state": {} }
{ "type": "text", "message": "...", "state": {} }
{ "type": "order_start", "message": "...", "new_items": [...], "state": {} }
{ "type": "order_collection", "message": "...", "state": {} }
{ "type": "cart_summary", "message": "...", "cart": [...], "total": 0, "state": {} }
```
