import json
import sqlite3
import urllib.request
import urllib.error

import click

from .constants import DEFAULT_HOST, DEFAULT_PORT
from .database import Database
from .engine import BondEngine

DAEMON_BASE = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"

_daemon_running_cache = None


class AgentGroup(click.Group):
    def parse_args(self, ctx, args):
        if not args:
            return super().parse_args(ctx, args)
        first = args[0]
        if first.startswith("-") or first in self.commands:
            return super().parse_args(ctx, args)
        ctx.ensure_object(dict)
        ctx.obj["agent_name"] = first
        return super().parse_args(ctx, args[1:])


def _is_daemon_running():
    global _daemon_running_cache
    if _daemon_running_cache is not None:
        return _daemon_running_cache
    try:
        req = urllib.request.Request(f"{DAEMON_BASE}/api/network/stats")
        with urllib.request.urlopen(req, timeout=1) as resp:
            _daemon_running_cache = resp.status == 200
    except Exception:
        _daemon_running_cache = False
    return _daemon_running_cache


def _api_call(method, path, data=None):
    url = f"{DAEMON_BASE}{path}"
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            detail = json.loads(error_body).get("detail", error_body)
        except json.JSONDecodeError:
            detail = error_body
        raise click.ClickException(f"API error {e.code}: {detail}")
    except urllib.error.URLError:
        raise click.ClickException("Cannot connect to daemon")


def _get_engine():
    db = Database()
    db.connect()
    return BondEngine(db), db


def _resolve_agent(name):
    if _is_daemon_running():
        agents = _api_call("GET", "/api/agents")
        for a in agents:
            if a["name"] == name:
                return a["id"]
        raise click.ClickException(f"Agent '{name}' not found")
    else:
        engine, db = _get_engine()
        try:
            agent = engine._agent_repo.get_by_name(name)
            if not agent:
                raise click.ClickException(f"Agent '{name}' not found")
            return agent.id
        finally:
            db.close()


def _build_name_map():
    if _is_daemon_running():
        agents = _api_call("GET", "/api/agents")
        return {a["id"]: a["name"] for a in agents}
    else:
        engine, db = _get_engine()
        try:
            agents = engine._agent_repo.list_all()
            return {a.id: a.name for a in agents}
        finally:
            db.close()


def _format_valence(v):
    if v >= 0:
        return f"+{v:.2f}"
    return f"{v:.2f}"


def _print_bond(state, name_map=None):
    src = name_map.get(state["source_agent_id"], state["source_agent_id"][:8]) if name_map else state["source_agent_id"][:8]
    tgt = name_map.get(state["target_agent_id"], state["target_agent_id"][:8]) if name_map else state["target_agent_id"][:8]
    tie = state.get("tie", {})
    click.echo(f"Bond: {src} -> {tgt}")
    click.echo(
        f"Type: {tie.get('type', 'stranger')} | "
        f"Valence: {_format_valence(tie.get('valence', 0.0))} | "
        f"Trust: {_format_valence(tie.get('trust', 0.0))} | "
        f"Strength: {tie.get('strength', 0.0):.2f} | "
        f"Stability: {tie.get('stability', 1.0):.2f}"
    )
    click.echo(f"Visibility: {tie.get('visibility', 'private')}")
    emotions = state.get("emotions", [])
    if emotions:
        click.echo("Emotions:")
        for e in emotions:
            click.echo(f"  {e['type']} (intensity: {e['intensity']:.2f}, decay_rate: {e['decay_rate']:.2f})")


@click.group()
def bond():
    pass


@bond.group(cls=AgentGroup)
def agent():
    pass


@agent.command("register")
@click.argument("name")
@click.option("--desc", "-d", default="")
def agent_register(name, desc):
    if _is_daemon_running():
        result = _api_call("POST", "/api/agents", {"name": name, "description": desc})
        click.echo(f"Agent '{name}' registered (id: {result['id']})")
    else:
        engine, db = _get_engine()
        try:
            a = engine._agent_repo.create(name=name, description=desc)
            click.echo(f"Agent '{name}' registered (id: {a.id})")
        finally:
            db.close()


@agent.command("remove")
@click.argument("name")
def agent_remove(name):
    agent_id = _resolve_agent(name)
    if _is_daemon_running():
        _api_call("DELETE", f"/api/agents/{agent_id}")
        click.echo(f"Agent '{name}' removed")
    else:
        engine, db = _get_engine()
        try:
            engine._agent_repo.delete(agent_id)
            click.echo(f"Agent '{name}' removed")
        except sqlite3.IntegrityError:
            raise click.ClickException(f"Cannot remove agent '{name}': has existing bonds")
        finally:
            db.close()


@agent.command("list")
@click.pass_context
def agent_list(ctx):
    agent_name = ctx.obj.get("agent_name") if ctx.obj else None
    if agent_name:
        agent_id = _resolve_agent(agent_name)
        name_map = _build_name_map()
        if _is_daemon_running():
            bonds = _api_call("GET", f"/api/agents/{agent_id}/bonds")
        else:
            engine, db = _get_engine()
            try:
                bonds = engine.list_bonds(agent_id)
            finally:
                db.close()
        click.echo(f"{'Target':<15} {'Type':<15} {'Valence':<10} {'Trust':<10} {'Strength':<10} {'Emotions':<20}")
        click.echo("-" * 80)
        for b in bonds:
            tie = b.get("tie", {})
            target_id = b.get("target_agent_id", "")
            target_name = name_map.get(target_id, target_id[:8])
            emotions = b.get("emotions", [])
            emotion_str = ", ".join(e["type"] for e in emotions) if emotions else "-"
            click.echo(
                f"{target_name:<15} {tie.get('type', 'stranger'):<15} "
                f"{_format_valence(tie.get('valence', 0.0)):<10} "
                f"{_format_valence(tie.get('trust', 0.0)):<10} "
                f"{tie.get('strength', 0.0):<10.2f} "
                f"{emotion_str:<20}"
            )
    else:
        if _is_daemon_running():
            agents = _api_call("GET", "/api/agents")
        else:
            engine, db = _get_engine()
            try:
                agents_raw = engine._agent_repo.list_all()
                agents = [
                    {
                        "name": a.name,
                        "description": a.description,
                        "created_at": a.created_at.isoformat() if a.created_at else "",
                    }
                    for a in agents_raw
                ]
            finally:
                db.close()
        click.echo(f"{'Name':<15} {'Description':<30} {'Created':<25}")
        click.echo("-" * 70)
        for a in agents:
            click.echo(f"{a['name']:<15} {a['description']:<30} {a.get('created_at', ''):<25}")


@agent.command("get")
@click.argument("target")
@click.pass_context
def agent_get(ctx, target):
    agent_name = ctx.obj.get("agent_name") if ctx.obj else None
    if not agent_name:
        raise click.ClickException("Agent name required: bond agent <name> get <target>")
    agent_id = _resolve_agent(agent_name)
    target_id = _resolve_agent(target)
    if _is_daemon_running():
        state = _api_call("GET", f"/api/agents/{agent_id}/bonds/{target_id}")
    else:
        engine, db = _get_engine()
        try:
            state = engine.get_bond_state(agent_id, target_id)
        finally:
            db.close()
    if not state:
        raise click.ClickException(f"No bond found: {agent_name} -> {target}")
    name_map = _build_name_map()
    _print_bond(state, name_map)


@agent.command("set")
@click.argument("target")
@click.option("--type", "bond_type", default=None)
@click.option("--valence", default=None, type=float)
@click.option("--trust", default=None, type=float)
@click.option("--strength", default=None, type=float)
@click.option("--stability", default=None, type=float)
@click.pass_context
def agent_set(ctx, target, bond_type, valence, trust, strength, stability):
    agent_name = ctx.obj.get("agent_name") if ctx.obj else None
    if not agent_name:
        raise click.ClickException("Agent name required: bond agent <name> set <target>")
    agent_id = _resolve_agent(agent_name)
    target_id = _resolve_agent(target)
    kwargs = {}
    if bond_type is not None:
        kwargs["type"] = bond_type
    if valence is not None:
        kwargs["valence"] = valence
    if trust is not None:
        kwargs["trust"] = trust
    if strength is not None:
        kwargs["strength"] = strength
    if stability is not None:
        kwargs["stability"] = stability
    if not kwargs:
        raise click.ClickException("No properties to set")
    if _is_daemon_running():
        state = _api_call("PUT", f"/api/agents/{agent_id}/bonds/{target_id}", kwargs)
    else:
        engine, db = _get_engine()
        try:
            state = engine.set_tie(agent_id, target_id, **kwargs)
        finally:
            db.close()
    name_map = _build_name_map()
    _print_bond(state, name_map)


@agent.command("event")
@click.argument("target")
@click.option("--type", "event_type", required=True)
@click.option("--desc", required=True)
@click.option("--impact-valence", required=True, type=float)
@click.option("--impact-trust", required=True, type=float)
@click.pass_context
def agent_event(ctx, target, event_type, desc, impact_valence, impact_trust):
    agent_name = ctx.obj.get("agent_name") if ctx.obj else None
    if not agent_name:
        raise click.ClickException("Agent name required: bond agent <name> event <target>")
    agent_id = _resolve_agent(agent_name)
    target_id = _resolve_agent(target)
    if _is_daemon_running():
        try:
            before = _api_call("GET", f"/api/agents/{agent_id}/bonds/{target_id}")
        except click.ClickException as e:
            if "404" in str(e):
                before = None
            else:
                raise
        old_type = before.get("tie", {}).get("type", "stranger") if before else "stranger"
        old_emotion_count = len(before.get("emotions", [])) if before else 0
        result = _api_call("POST", f"/api/agents/{agent_id}/events", {
            "target_id": target_id,
            "event_type": event_type,
            "description": desc,
            "impact_valence": impact_valence,
            "impact_trust": impact_trust,
        })
    else:
        engine, db = _get_engine()
        try:
            before = engine.get_bond_state(agent_id, target_id)
            old_type = before.get("tie", {}).get("type", "stranger") if before else "stranger"
            old_emotion_count = len(before.get("emotions", [])) if before else 0
            result = engine.process_event(
                source_agent_id=agent_id,
                target_agent_id=target_id,
                event_type=event_type,
                description=desc,
                impact_valence=impact_valence,
                impact_trust=impact_trust,
            )
        finally:
            db.close()
    click.echo(f"Event recorded: {event_type} -> {target}")
    tie = result.get("tie", {})
    click.echo(f"Bond updated: valence {_format_valence(tie.get('valence', 0.0))}, trust {_format_valence(tie.get('trust', 0.0))}")
    new_emotions = result.get("emotions", [])
    if len(new_emotions) > old_emotion_count:
        for e in new_emotions[old_emotion_count:]:
            click.echo(f"Emotion created: {e['type']} (intensity: {e['intensity']:.2f})")
    new_type = tie.get("type", "stranger")
    if old_type != new_type:
        click.echo(f"Type transition: {old_type} -> {new_type}")


@bond.group()
def network():
    pass


@network.command("stats")
def network_stats():
    if _is_daemon_running():
        stats = _api_call("GET", "/api/network/stats")
    else:
        engine, db = _get_engine()
        try:
            stats = engine.get_network_stats()
        finally:
            db.close()
    click.echo(f"Agents: {stats['agent_count']}")
    click.echo(f"Bonds: {stats['bond_count']}")
    click.echo(f"Active Emotions: {stats['active_emotion_count']}")
    click.echo(f"Avg Valence: {_format_valence(stats['avg_valence'])}")
    click.echo(f"Avg Trust: {_format_valence(stats['avg_trust'])}")
    click.echo(f"Avg Strength: {stats['avg_strength']:.2f}")


@bond.command("tick")
def tick():
    if _is_daemon_running():
        result = _api_call("POST", "/api/tick")
    else:
        engine, db = _get_engine()
        try:
            result = engine.tick()
        finally:
            db.close()
    click.echo(f"Decayed: {result['decayed']}")
    click.echo(f"Faded: {result['faded']}")
    click.echo(f"Residue writes: {result['residue_writes']}")


if __name__ == "__main__":
    bond()
