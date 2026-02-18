"""EnergyHub FastAPI Application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.core.config import get_settings
from app.api import account, auth, emulator, energy_plans, invoices, nem12, reconciliation, tariffs, tou

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Energy management and invoice reconciliation platform",
    version="0.1.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(nem12.router, prefix="/api/nem12", tags=["NEM12"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(account.router, prefix="/api/account", tags=["Account"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(tariffs.router, prefix="/api/tariffs", tags=["Tariffs"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["Reconciliation"])
app.include_router(energy_plans.router, prefix="/api/energy-plans", tags=["Energy Plans"])
app.include_router(tou.router, prefix="/api/tou", tags=["TOU"])
app.include_router(emulator.router, prefix="/api/emulator", tags=["Emulator"])


@app.on_event("startup")
async def on_startup() -> None:
    """Initialize local DB schema."""
    init_db()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}
