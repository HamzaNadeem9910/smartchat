import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import Base, engine
from config import get_settings
from routers import auth, chatbots, payment, admin, whatsapp
from pinecone_ingest import router as pinecone_router
from crawlee_ingest import router as crawlee_router
from crawlee_scrape import router as scrape_router


app = FastAPI(
    title="SmartChat API",
    version="2.0.0"
)


# ─────────────────────────────────────────────────────────────
# Database startup
# ─────────────────────────────────────────────────────────────
@app.on_event("startup")
def initialize_database():
    Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────────────────────
settings = get_settings()

cors_origins = list(settings.cors_origins)

required_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://smartchat-55xsv3qeu-hamzanadeem9910.vercel.app",
]

for origin in required_origins:
    if origin not in cors_origins:
        cors_origins.append(origin)


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Static uploads
# ─────────────────────────────────────────────────────────────
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_DIR),
    name="uploads",
)


# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(payment.router)
app.include_router(chatbots.router)
app.include_router(pinecone_router)
app.include_router(admin.router)
app.include_router(crawlee_router)
app.include_router(scrape_router)
app.include_router(whatsapp.router)


# ─────────────────────────────────────────────────────────────
# Root
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "SmartChat API is running",
        "version": "2.0.0",
    }


# ─────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "2.0.0",
    }


# ─────────────────────────────────────────────────────────────
# Admin panel
# ─────────────────────────────────────────────────────────────
@app.get("/admin")
def admin_panel():
    return FileResponse(
        os.path.join(
            os.path.dirname(__file__),
            "admin_dashboard.html",
        )
    )


# ─────────────────────────────────────────────────────────────
# Local development
# Railway uses Gunicorn command instead
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
