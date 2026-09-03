from collections import defaultdict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import json, jwt
from app.core.security import decode_token

router=APIRouter(tags=["realtime"])
rooms=defaultdict(set)

@router.websocket("/ws/tournaments/{public_id}")
async def socket(ws:WebSocket, public_id:str, token: str = Query(...)):
    try:
        payload=decode_token(token)
        if payload.get("type")!="access": raise ValueError()
    except Exception:
        await ws.close(code=1008)
        return
    await ws.accept()
    rooms[public_id].add(ws)
    try:
        while True:
            # Client messages are intentionally ignored: the browser cannot publish
            # authoritative game/economy events through WebSocket.
            await ws.receive_text()
    except WebSocketDisconnect:
        rooms[public_id].discard(ws)
    except Exception:
        rooms[public_id].discard(ws)

async def broadcast(public_id:str,event:dict):
    message=json.dumps(event,default=str)
    dead=[]
    for peer in list(rooms.get(public_id,set())):
        try: await peer.send_text(message)
        except Exception: dead.append(peer)
    for peer in dead: rooms[public_id].discard(peer)
