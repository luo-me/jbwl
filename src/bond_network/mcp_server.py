import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .database import Database
from .engine import BondEngine
from .infer import InferEngine

server = Server("bond-network")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="bond_get",
            description="获取当前 Agent 对目标 Agent 的羁绊状态",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "当前 Agent ID"},
                    "target_id": {"type": "string", "description": "目标 Agent ID"},
                },
                "required": ["agent_id", "target_id"],
            },
        ),
        Tool(
            name="bond_list",
            description="列出当前 Agent 的所有羁绊",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "当前 Agent ID"},
                },
                "required": ["agent_id"],
            },
        ),
        Tool(
            name="bond_event",
            description="记录事件并更新羁绊",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "当前 Agent ID"},
                    "target_id": {"type": "string", "description": "目标 Agent ID"},
                    "event_type": {"type": "string", "description": "事件类型"},
                    "description": {"type": "string", "description": "事件描述"},
                    "impact_valence": {"type": "number", "description": "对情感效价的影响"},
                    "impact_trust": {"type": "number", "description": "对信任的影响"},
                    "impact_strength": {"type": "number", "description": "对羁绊强度的影响", "default": 0.0},
                },
                "required": ["agent_id", "target_id", "event_type", "description", "impact_valence", "impact_trust"],
            },
        ),
        Tool(
            name="bond_infer",
            description="推断两个其他 Agent 之间的推测羁绊",
            inputSchema={
                "type": "object",
                "properties": {
                    "requester_id": {"type": "string", "description": "请求者 Agent ID"},
                    "agent_a_id": {"type": "string", "description": "Agent A ID"},
                    "agent_b_id": {"type": "string", "description": "Agent B ID"},
                },
                "required": ["requester_id", "agent_a_id", "agent_b_id"],
            },
        ),
        Tool(
            name="bond_network",
            description="获取以当前 Agent 为中心的羁绊网络拓扑",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "当前 Agent ID"},
                    "depth": {"type": "number", "description": "网络深度", "default": 1},
                },
                "required": ["agent_id"],
            },
        ),
    ]


def _handle_bond_get(arguments):
    with Database() as db:
        engine = BondEngine(db)
        state = engine.get_bond_state(arguments["agent_id"], arguments["target_id"])
    if state is None:
        return "No bond found"
    return json.dumps(state, ensure_ascii=False)


def _handle_bond_list(arguments):
    with Database() as db:
        engine = BondEngine(db)
        bonds = engine.list_bonds(arguments["agent_id"])
    return json.dumps(bonds, ensure_ascii=False)


def _handle_bond_event(arguments):
    with Database() as db:
        engine = BondEngine(db)
        state = engine.process_event(
            arguments["agent_id"],
            arguments["target_id"],
            arguments["event_type"],
            arguments["description"],
            arguments["impact_valence"],
            arguments["impact_trust"],
            arguments.get("impact_strength", 0.0),
        )
    return json.dumps(state, ensure_ascii=False)


def _handle_bond_infer(arguments):
    with Database() as db:
        engine = InferEngine(db)
        result = engine.infer_bond(
            arguments["requester_id"],
            arguments["agent_a_id"],
            arguments["agent_b_id"],
        )
    return json.dumps(result, ensure_ascii=False)


def _handle_bond_network(arguments):
    with Database() as db:
        engine = InferEngine(db)
        result = engine.get_agent_network(
            arguments["agent_id"],
            arguments.get("depth", 1),
        )
    return json.dumps(result, ensure_ascii=False)


_HANDLERS = {
    "bond_get": _handle_bond_get,
    "bond_list": _handle_bond_list,
    "bond_event": _handle_bond_event,
    "bond_infer": _handle_bond_infer,
    "bond_network": _handle_bond_network,
}


@server.call_tool()
async def call_tool(name, arguments):
    handler = _HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    result = handler(arguments)
    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
