"""
GI Copilot - Main Application
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from pathlib import Path

# Import routers
from routes_video import router as video_router
from gi import router as gi_router
from routes_convert import router as convert_router

# Database initialization
from database import init_db

# Create FastAPI app
app = FastAPI(
    title="GI Copilot",
    description="AI-powered educational assistant for endoscopy procedures",
    version="2.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create static directory if it doesn't exist
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(video_router)    # /api/v1/videos/*
app.include_router(gi_router)       # /api/gi/* (real-time routes)
app.include_router(convert_router)  # /api/convert/* (video conversion)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    print("🚀 Starting GI Copilot...")
    
    # Initialize database
    init_db()
    
    print("✅ GI Copilot started successfully")
    print("📡 Access the application at: http://localhost:8000")


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve main UI"""
    index_path = Path(__file__).parent / "index.html"
    
    if not index_path.exists():
        return HTMLResponse("""
        <html>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h1>🏥 GI Copilot</h1>
                <p>index.html not found. Please ensure index.html is in the same directory as main_updated.py</p>
            </body>
        </html>
        """)
    
    with open(index_path, 'r') as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "gi-copilot",
        "version": "2.0.0"
    }


if __name__ == "__main__":
    # Run with uvicorn
    port = int(os.getenv("PORT", 8000))
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║              🏥 GI COPILOT SERVER                    ║
║                                                      ║
║  Starting server on http://localhost:{port}         ║
║                                                      ║
║  Features:                                           ║
║  ✅ Real-time voice chat with OpenAI                ║
║  ✅ Video upload & processing                        ║
║  ✅ Frame-by-frame AI analysis                       ║
║  ✅ Export bundles                                   ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "main_updated:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )