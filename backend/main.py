"""FastAPI application entry point."""
from __future__ import annotations
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import init_db
from services.scheduler import build_scheduler, start_scheduler_if_enabled
from websocket_manager import manager
from routers import decisions_v3 as decisions, approvals, backtest, risk, rules, graph, portfolio, factors, strategy, candidate, settlement

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler
    scheduler_started = start_scheduler_if_enabled(scheduler)
    yield
    if scheduler_started:
        scheduler.shutdown(wait=False)

app = FastAPI(
    title="Quant AI 閳?Multi-Agent Trading System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 閳光偓閳光偓閳光偓 Routers 閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓
app.include_router(decisions.router)
app.include_router(approvals.router)
app.include_router(backtest.router)
app.include_router(risk.router)
app.include_router(rules.router)
app.include_router(graph.router)
app.include_router(portfolio.router)
app.include_router(factors.router)
app.include_router(strategy.router)
app.include_router(candidate.router)
app.include_router(settlement.router)

# 閳光偓閳光偓閳光偓 WebSocket 閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    client_id = str(uuid.uuid4())
    await manager.connect(ws, client_id)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await manager.send_personal(client_id, "ping")
    except WebSocketDisconnect:
        manager.disconnect(client_id)

# 閳光偓閳光偓閳光偓 Health 閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓閳光偓
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

