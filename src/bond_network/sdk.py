import json
import urllib.request
import urllib.error
from pathlib import Path

from .constants import DEFAULT_DB_PATH
from .database import AgentRepo, Database
from .engine import BondEngine
from .infer import InferEngine


class BondClient:
    def __init__(self, base_url=None, db_path=None):
        if base_url is not None:
            self._remote = True
            self._base_url = base_url.rstrip("/")
            self._db = None
            self._engine = None
            self._infer_engine = None
        else:
            self._remote = False
            self._db_path = db_path or DEFAULT_DB_PATH
            self._db = None
            self._engine = None
            self._infer_engine = None

    def _ensure_connected(self):
        if self._db is None:
            self._db = Database(Path(self._db_path))
            self._db.connect()
            self._engine = BondEngine(self._db)
            self._infer_engine = InferEngine(self._db)

    def _request(self, method, path, data=None):
        url = f"{self._base_url}{path}"
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                if raw:
                    return json.loads(raw)
                return {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                detail = json.loads(raw).get("detail", raw)
            except (json.JSONDecodeError, ValueError):
                detail = raw
            raise RuntimeError(f"HTTP {e.code}: {detail}") from e

    def _resolve_agent(self, name_or_id):
        if self._remote:
            agents = self._request("GET", "/api/agents")
            for a in agents:
                if a["name"] == name_or_id or a["id"] == name_or_id:
                    return a["id"]
            return None
        else:
            self._ensure_connected()
            repo = AgentRepo(self._db)
            agent = repo.get_by_name(name_or_id)
            if agent:
                return agent.id
            agent = repo.get_by_id(name_or_id)
            if agent:
                return agent.id
            return None

    def _agent_to_dict(self, agent):
        return {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }

    def register_agent(self, name, description=""):
        if self._remote:
            return self._request("POST", "/api/agents", {"name": name, "description": description})
        else:
            self._ensure_connected()
            repo = AgentRepo(self._db)
            agent = repo.create(name=name, description=description)
            return self._agent_to_dict(agent)

    def remove_agent(self, name_or_id):
        agent_id = self._resolve_agent(name_or_id)
        if agent_id is None:
            return False
        if self._remote:
            try:
                self._request("DELETE", f"/api/agents/{agent_id}")
                return True
            except RuntimeError:
                return False
        else:
            self._ensure_connected()
            repo = AgentRepo(self._db)
            return repo.delete(agent_id)

    def list_agents(self):
        if self._remote:
            return self._request("GET", "/api/agents")
        else:
            self._ensure_connected()
            repo = AgentRepo(self._db)
            agents = repo.list_all()
            return [self._agent_to_dict(a) for a in agents]

    def get_bond(self, agent_name, target_name):
        agent_id = self._resolve_agent(agent_name)
        if agent_id is None:
            return None
        target_id = self._resolve_agent(target_name)
        if target_id is None:
            return None
        if self._remote:
            try:
                return self._request("GET", f"/api/agents/{agent_id}/bonds/{target_id}")
            except RuntimeError:
                return None
        else:
            self._ensure_connected()
            return self._engine.get_bond_state(agent_id, target_id)

    def list_bonds(self, agent_name):
        agent_id = self._resolve_agent(agent_name)
        if agent_id is None:
            return []
        if self._remote:
            try:
                return self._request("GET", f"/api/agents/{agent_id}/bonds")
            except RuntimeError:
                return []
        else:
            self._ensure_connected()
            return self._engine.list_bonds(agent_id)

    def set_bond(self, agent_name, target_name, **kwargs):
        agent_id = self._resolve_agent(agent_name)
        if agent_id is None:
            raise ValueError(f"agent not found: {agent_name}")
        target_id = self._resolve_agent(target_name)
        if target_id is None:
            raise ValueError(f"target agent not found: {target_name}")
        if self._remote:
            return self._request("PUT", f"/api/agents/{agent_id}/bonds/{target_id}", kwargs)
        else:
            self._ensure_connected()
            return self._engine.set_tie(agent_id, target_id, **kwargs)

    def emit_event(self, agent_name, target_name, event_type, description, impact_valence, impact_trust, impact_strength=0.0):
        agent_id = self._resolve_agent(agent_name)
        if agent_id is None:
            raise ValueError(f"agent not found: {agent_name}")
        target_id = self._resolve_agent(target_name)
        if target_id is None:
            raise ValueError(f"target agent not found: {target_name}")
        if self._remote:
            return self._request("POST", f"/api/agents/{agent_id}/events", {
                "target_id": target_id,
                "event_type": event_type,
                "description": description,
                "impact_valence": impact_valence,
                "impact_trust": impact_trust,
                "impact_strength": impact_strength,
            })
        else:
            self._ensure_connected()
            return self._engine.process_event(
                source_agent_id=agent_id,
                target_agent_id=target_id,
                event_type=event_type,
                description=description,
                impact_valence=impact_valence,
                impact_trust=impact_trust,
                impact_strength=impact_strength,
            )

    def tick(self):
        if self._remote:
            return self._request("POST", "/api/tick")
        else:
            self._ensure_connected()
            return self._engine.tick()

    def network_stats(self):
        if self._remote:
            return self._request("GET", "/api/network/stats")
        else:
            self._ensure_connected()
            return self._engine.get_network_stats()

    def infer(self, agent_name, target_a_name, target_b_name):
        agent_id = self._resolve_agent(agent_name)
        if agent_id is None:
            raise ValueError(f"agent not found: {agent_name}")
        target_a_id = self._resolve_agent(target_a_name)
        if target_a_id is None:
            raise ValueError(f"target_a agent not found: {target_a_name}")
        target_b_id = self._resolve_agent(target_b_name)
        if target_b_id is None:
            raise ValueError(f"target_b agent not found: {target_b_name}")
        if self._remote:
            return self._request("POST", f"/api/agents/{agent_id}/infer", {
                "agent_a_id": target_a_id,
                "agent_b_id": target_b_id,
            })
        else:
            self._ensure_connected()
            return self._infer_engine.infer_bond(agent_id, target_a_id, target_b_id)

    def get_network(self, agent_name, depth=1):
        agent_id = self._resolve_agent(agent_name)
        if agent_id is None:
            raise ValueError(f"agent not found: {agent_name}")
        if self._remote:
            return self._request("GET", f"/api/agents/{agent_id}/network?depth={depth}")
        else:
            self._ensure_connected()
            return self._infer_engine.get_agent_network(agent_id, depth=depth)
