"""EnergyHub FastAPI Application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api import nem12, invoices, tariffs, reconciliation

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Energy management and invoice reconciliation platform",
    version="0.1.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(nem12.router, prefix="/api/nem12", tags=["NEM12"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(tariffs.router, prefix="/api/tariffs", tags=["Tariffs"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["Reconciliation"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}
