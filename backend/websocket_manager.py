"""WebSocket connection manager with broadcast support."""
from __future__ import annotations
import json
from datetime import datetime
from typing import Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, client_id: str):
        await ws.accept()
        self.active[client_id] = ws

    def disconnect(self, client_id: str):
        self.active.pop(client_id, None)

    async def broadcast(self, event_type: str, data: dict | None = None):
        msg = json.dumps({
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat(),
        })
        dead = []
        for cid, ws in self.active.items():
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    async def send_personal(self, client_id: str, event_type: str, data: dict | None = None):
        ws = self.active.get(client_id)
        if ws:
            msg = json.dumps({
                "type": event_type,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat(),
            })
            try:
                await ws.send_text(msg)
            except Exception:
                self.disconnect(client_id)

manager = ConnectionManager()
