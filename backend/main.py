import os
from fastapi import FastAPI
from fastapi.responses import FileResponse 
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import Base, engine
from config import get_settings
from routers import auth, chatbots, payment, admin     
from pinecone_ingest import router as pinecone_router
from crawlee_ingest import router as crawlee_router
from crawlee_scrape import router as scrape_router
from routers import whatsapp
  
    

app = FastAPI(title="SmartChat API", version="2.0.0")

@app.on_event("startup")
def initialize_database():
    # Create missing tables on startup. Use the same models as local development.
    Base.metadata.create_all(bind=engine)

# ── CORS ───────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static uploads (logo + documents) ─────────────────────
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ── Routers ────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(payment.router)
app.include_router(chatbots.router)
app.include_router(pinecone_router)
app.include_router(admin.router)
app.include_router(crawlee_router)
app.include_router(scrape_router)
app.include_router(whatsapp.router)


@app.get("/admin")          
def admin_panel():
    return FileResponse(os.path.join(os.path.dirname(__file__), "admin_dashboard.html"))

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
