from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import json
from server.agent_manager import agent_manager
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BDI Agent API", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateAgentRequest(BaseModel):
    brief: str


@app.post("/agents")
async def create_agent(req: CreateAgentRequest):
    if not req.brief.strip():
        raise HTTPException(status_code=400, detail="Brief cannot be empty")
    managed = await agent_manager.create_agent(req.brief)
    snap = agent_manager.snapshot(managed.agent_id)
    return {"state": snap.__dict__, "initial_messages": []}


@app.get("/agents")
async def list_agents():
    snaps = agent_manager.list_snapshots()
    return [
        {
            "agent_id": s.agent_id,
            "status": s.status,
            "cycle_count": s.cycle_count,
            "created_at": s.created_at,
            "brief": s.brief,
        }
        for s in snaps
    ]


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    snap = agent_manager.snapshot(agent_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Agent not found")
    return snap.__dict__


@app.get("/agents/{agent_id}/events")
async def stream_events(agent_id: str):
    ma = agent_manager.get_agent(agent_id)
    if not ma:
        raise HTTPException(status_code=404, detail="Agent not found")

    async def event_generator():
        while True:
            event = await ma.event_queue.get()
            yield (
                f"event: {event.type}\n"
                + f"data: {json.dumps({'type': event.type, 'at': event.at, **event.payload})}\n\n"
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    ma = agent_manager.get_agent(agent_id)
    if not ma:
        raise HTTPException(status_code=404, detail="Agent not found")
    if ma.status not in ["running", "initializing"]:
        return {"status": ma.status}
    ma.stop_flag = True
    ma.status = "stopped"
    # Emit status + chat message
    await ma.emit(
        "agent.status",
        {
            "state": {
                "status": ma.status,
                "cycleCount": ma.cycle_count,
                "lastProgressAt": ma.last_progress_at,
                "activeIntentionId": None,
            }
        },
    )
    await ma.emit(
        "chat.message",
        {
            "message": {
                "id": "stop_" + agent_id,
                "at": ma.last_progress_at or "",
                "sender": "system",
                "content": f"Agent {agent_id} stopped.",
            }
        },
    )
    return {"status": "stopping"}
