"""FastAPI application entry point."""
from __future__ import annotations
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import init_db
from websocket_manager import manager
from routers import decisions, approvals, backtest, risk, rules, graph, portfolio, portfolio

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Quant AI — Multi-Agent Trading System",
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

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(decisions.router)
app.include_router(approvals.router)
app.include_router(backtest.router)
app.include_router(risk.router)
app.include_router(rules.router)
app.include_router(graph.router)
app.include_router(portfolio.router)
app.include_router(portfolio.router)

# ─── WebSocket ────────────────────────────────────────────────────────────────
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

# ─── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}