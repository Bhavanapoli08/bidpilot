"""
BidPilot AI — FastAPI application entrypoint.
Wires up all routers, middleware, and lifecycle events.
"""
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME}")
    init_db()
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered tender analysis and bid scoring",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(round((time.time() - start) * 1000, 2))
    return response


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.APP_NAME}


# ---- Routers ----
from app.api.auth import router as auth_router
from app.api.tenders import router as tenders_router
from app.api.scoring import router as scoring_router
from app.api.company import router as company_router
from app.api.billing import router as billing_router
from app.api.jobs import router as jobs_router
from app.api.monitoring import router as monitoring_router
from app.api.bids import router as bids_router
from app.api.notifications import router as notifications_router

app.include_router(auth_router, prefix="/api")
app.include_router(tenders_router, prefix="/api")
app.include_router(scoring_router, prefix="/api")
app.include_router(company_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")
app.include_router(bids_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
