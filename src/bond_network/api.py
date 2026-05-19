import asyncio
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .database import AgentRepo, BondRepo, Database, EmotionRepo, TieRepo
from .engine import BondEngine
from .infer import InferEngine


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                self.active_connections.remove(connection)


class CreateAgentRequest(BaseModel):
    name: str
    description: str = ""


class UpdateBondRequest(BaseModel):
    type: Optional[str] = None
    valence: Optional[float] = None
    trust: Optional[float] = None
    strength: Optional[float] = None
    stability: Optional[float] = None
    visibility: Optional[str] = None


class CreateEventRequest(BaseModel):
    target_id: str
    event_type: str
    description: str
    impact_valence: float
    impact_trust: float
    impact_strength: Optional[float] = 0.0


class InferBondRequest(BaseModel):
    agent_a_id: str
    agent_b_id: str


def get_db(app: FastAPI) -> Database:
    return app.state.db


def get_engine(app: FastAPI) -> BondEngine:
    return app.state.engine


def get_infer_engine(app: FastAPI) -> InferEngine:
    return app.state.infer_engine


def _broadcast(app: FastAPI, message: dict):
    try:
        asyncio.get_event_loop().create_task(app.state.ws_manager.broadcast(message))
    except RuntimeError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = app.state.db
    db.connect()

    engine = app.state.engine
    try:
        tick_interval = int(os.environ.get("BOND_TICK_INTERVAL", "60"))
    except ValueError:
        tick_interval = 60
    tick_interval = max(1, tick_interval)

    stop_event = threading.Event()

    def tick_loop():
        while not stop_event.wait(tick_interval):
            try:
                engine.tick()
            except Exception:
                pass

    tick_thread = threading.Thread(target=tick_loop, daemon=True)
    tick_thread.start()

    yield

    stop_event.set()
    tick_thread.join(timeout=5)
    db.close()


def create_app(db_path=None) -> FastAPI:
    app = FastAPI(title="Bond Network", version="0.1.0")

    db = Database(db_path)
    app.state.db = db
    app.state.engine = BondEngine(db)
    app.state.infer_engine = InferEngine(db)
    app.state.ws_manager = ConnectionManager()

    app.router.lifespan_context = lifespan

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        manager = app.state.ws_manager
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            manager.disconnect(websocket)

    @app.get("/api/agents")
    def list_agents():
        try:
            repo = AgentRepo(get_db(app))
            agents = repo.list_all()
            return [
                {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                }
                for a in agents
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/agents", status_code=201)
    def create_agent(req: CreateAgentRequest):
        try:
            repo = AgentRepo(get_db(app))
            existing = repo.get_by_name(req.name)
            if existing:
                raise HTTPException(status_code=409, detail="agent name already exists")
            agent = repo.create(name=req.name, description=req.description)
            result = {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "created_at": agent.created_at.isoformat() if agent.created_at else None,
                "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            }
            _broadcast(app, {"type": "agent_created", "data": result})
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/agents/{agent_id}")
    def delete_agent(agent_id: str):
        try:
            repo = AgentRepo(get_db(app))
            deleted = repo.delete(agent_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="agent not found")
            _broadcast(app, {"type": "agent_deleted", "data": {"id": agent_id}})
            return {"ok": True}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/agents/{agent_id}/bonds")
    def list_bonds(agent_id: str):
        try:
            repo = AgentRepo(get_db(app))
            agent = repo.get_by_id(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="agent not found")
            engine = get_engine(app)
            return engine.list_bonds(agent_id)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/agents/{agent_id}/bonds/{target_id}")
    def get_bond(agent_id: str, target_id: str):
        try:
            repo = AgentRepo(get_db(app))
            agent = repo.get_by_id(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="agent not found")
            engine = get_engine(app)
            state = engine.get_bond_state(agent_id, target_id)
            if not state:
                raise HTTPException(status_code=404, detail="bond not found")
            return state
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/api/agents/{agent_id}/bonds/{target_id}")
    def update_bond(agent_id: str, target_id: str, req: UpdateBondRequest):
        try:
            repo = AgentRepo(get_db(app))
            agent = repo.get_by_id(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="agent not found")
            engine = get_engine(app)
            kwargs = {}
            if req.type is not None:
                kwargs["type"] = req.type
            if req.valence is not None:
                kwargs["valence"] = req.valence
            if req.trust is not None:
                kwargs["trust"] = req.trust
            if req.strength is not None:
                kwargs["strength"] = req.strength
            if req.stability is not None:
                kwargs["stability"] = req.stability
            if req.visibility is not None:
                kwargs["visibility"] = req.visibility
            try:
                state = engine.set_tie(agent_id, target_id, **kwargs)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            _broadcast(app, {"type": "bond_updated", "data": state})
            return state
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/agents/{agent_id}/events", status_code=201)
    def create_event(agent_id: str, req: CreateEventRequest):
        try:
            repo = AgentRepo(get_db(app))
            agent = repo.get_by_id(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="agent not found")
            engine = get_engine(app)
            try:
                state = engine.process_event(
                    source_agent_id=agent_id,
                    target_agent_id=req.target_id,
                    event_type=req.event_type,
                    description=req.description,
                    impact_valence=req.impact_valence,
                    impact_trust=req.impact_trust,
                    impact_strength=req.impact_strength or 0.0,
                )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            _broadcast(app, {"type": "bond_updated", "data": state})
            return state
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/tick")
    def tick():
        try:
            engine = get_engine(app)
            result = engine.tick()
            _broadcast(app, {"type": "tick_completed", "data": result})
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/network/stats")
    def network_stats():
        try:
            engine = get_engine(app)
            return engine.get_network_stats()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/network/graph")
    def get_network_graph():
        try:
            db = get_db(app)
            agent_repo = AgentRepo(db)
            bond_repo = BondRepo(db)
            tie_repo = TieRepo(db)
            emotion_repo = EmotionRepo(db)

            agents = agent_repo.list_all()
            nodes = [
                {"id": a.id, "name": a.name, "description": a.description}
                for a in agents
            ]

            edges = []
            seen_bonds = set()
            for agent in agents:
                bonds = bond_repo.list_by_agent(agent.id)
                for bond in bonds:
                    if bond.id in seen_bonds:
                        continue
                    seen_bonds.add(bond.id)

                    tie = tie_repo.get_by_bond_id(bond.id)
                    emotions = emotion_repo.list_by_bond(bond.id)

                    edge = {
                        "source": bond.source_agent_id,
                        "target": bond.target_agent_id,
                        "type": tie.type.value if tie else "stranger",
                        "valence": tie.valence if tie else 0.0,
                        "trust": tie.trust if tie else 0.0,
                        "strength": tie.strength if tie else 0.0,
                        "stability": tie.stability if tie else 0.0,
                        "visibility": tie.visibility.value if tie else "private",
                        "inferred": bond.inferred,
                        "emotions": [
                            {
                                "type": e.type.value,
                                "intensity": e.intensity,
                                "decay_rate": e.decay_rate,
                                "residue": e.residue,
                                "peak_intensity": e.peak_intensity,
                            }
                            for e in emotions
                        ],
                    }
                    edges.append(edge)

            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/agents/{agent_id}/infer")
    def infer_bond(agent_id: str, req: InferBondRequest):
        try:
            repo = AgentRepo(get_db(app))
            agent = repo.get_by_id(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="agent not found")
            infer_engine = get_infer_engine(app)
            result = infer_engine.infer_bond(agent_id, req.agent_a_id, req.agent_b_id)
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/agents/{agent_id}/network")
    def get_agent_network(agent_id: str, depth: int = Query(default=1)):
        try:
            repo = AgentRepo(get_db(app))
            agent = repo.get_by_id(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="agent not found")
            infer_engine = get_infer_engine(app)
            return infer_engine.get_agent_network(agent_id, depth=depth)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/scenarios/{scenario_name}")
    def load_scenario(scenario_name: str):
        try:
            from .scenarios import load_demo_scenario
            result = load_demo_scenario(get_db(app), scenario_name)
            _broadcast(app, {"type": "scenario_loaded", "data": result})
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/scenarios")
    def list_scenarios():
        return [
            {"name": "simple", "description": "简单场景 - 2个Agent，基础友谊关系"},
            {"name": "medium", "description": "中等场景 - 5个Agent，团队协作与竞争"},
            {"name": "complex", "description": "复杂场景 - 10个Agent，公司组织架构"},
            {"name": "ultra", "description": "超复杂场景 - 20个Agent，多团队网络战"},
        ]

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def create_app_factory():
    return create_app()
