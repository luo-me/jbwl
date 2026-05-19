# 羁绊网络 (Bond Network)

为 AI Agent 赋予情感与关系管理能力，让多智能体系统从"协作机器"进化为"社会有机体"。

## 概述

羁绊网络是一个本地运行的 AI Agent 情感关系管理系统，提供：

- **羁绊图谱** — 可视化 Agent 之间的关系网络
- **情感引擎** — 事件驱动的情感产生、衰减与残留
- **信任模型** — 信任度计算与修复不对称机制
- **关系演变** — 动态类型转换（陌生人→朋友→仇人...）
- **推断系统** — 基于信任传导的关系推断

## 安装

```bash
pip install bond-network
```

或从源码安装：

```bash
git clone https://github.com/yourname/bond-network.git
cd bond-network
pip install -e .
```

## 快速开始

### 启动服务

```bash
# 启动 Daemon（含 Dashboard 和 API）
python -m bond_network.daemon_cli start

# 查看状态
python -m bond_network.daemon_cli status

# 停止服务
python -m bond_network.daemon_cli stop
```

服务启动后，打开浏览器访问 **http://127.0.0.1:19527/** 查看 Dashboard。

### CLI 使用

```bash
# 注册 Agent
python -m bond_network.cli agent register alice --desc "Alice Agent"
python -m bond_network.cli agent register bob --desc "Bob Agent"

# 记录事件（建立羁绊）
python -m bond_network.cli agent alice event bob --type help --desc "帮忙修bug" --impact-valence 0.4 --impact-trust 0.3

# 查看羁绊
python -m bond_network.cli agent alice get bob

# 列出所有羁绊
python -m bond_network.cli agent alice list

# 执行情感衰减
python -m bond_network.cli tick

# 网络统计
python -m bond_network.cli network stats
```

### Python SDK

```python
from bond_network.sdk import BondClient

# 本地模式（直连 SQLite）
client = BondClient()

# 或远程模式（连接 Daemon）
# client = BondClient(base_url="http://127.0.0.1:19527")

# 注册 Agent
client.register_agent("alice", "Alice Agent")
client.register_agent("bob", "Bob Agent")

# 记录事件
result = client.emit_event("alice", "bob", "help", "帮忙修bug", 0.4, 0.3)
print(f"效价: {result['tie']['valence']}, 信任: {result['tie']['trust']}")

# 获取羁绊
bond = client.get_bond("alice", "bob")
print(f"类型: {bond['tie']['type']}")

# 网络统计
stats = client.network_stats()
print(f"Agent: {stats['agent_count']}, 羁绊: {stats['bond_count']}")
```

### MCP Server（供 AI Agent 接入）

在 Claude Desktop 或其他支持 MCP 的 Agent 中配置：

```json
{
  "mcpServers": {
    "bond-network": {
      "command": "python",
      "args": ["-m", "bond_network.mcp_server"]
    }
  }
}
```

Agent 可使用以下 Tool：
- `bond_get` — 获取羁绊状态
- `bond_list` — 列出所有羁绊
- `bond_event` — 记录事件
- `bond_infer` — 推断羁绊
- `bond_network` — 获取网络拓扑

## 核心概念

### 羁绊 (Bond)

智能体 A 对智能体 B 的关系与情感状态总和：

```
B(A→B) = { Tie, Emotions[] }
```

### 纽带 (Tie) — 结构层

| 属性 | 值域 | 说明 |
|------|------|------|
| type | 枚举 | 关系类型：stranger, acquaintance, friend, enemy, best_friend... |
| valence | [-1, +1] | 效价：正面/负面倾向 |
| trust | [-1, +1] | 信任度 |
| strength | [0, 1] | 强度：紧密程度 |
| stability | [0, +∞) | 稳定性：抵抗变化的能力 |

### 情感 (Emotion) — 反应层

情感由事件触发，随时间衰减，消退时在纽带上留下残留：

```
衰减公式：intensity(t+1) = intensity(t) × (1 - decay_rate)
残留写入：tie.trust += residue × sign(emotion) × peak_intensity
```

### 事件处理

事件对纽带的影响由稳定性调节：

```
Δvalence = impact_valence / (1 + stability)
Δtrust = impact_trust / (1 + stability)
```

稳定性越高，同一事件的影响越小。

### 修复不对称

负面情感的破坏力大于正面情感的修复力：

```
正面修复负面信任的效率 = 负面破坏效率 × 0.6
```

这解释了"一次背叛需要多次善意才能修复"。

## 预览场景

Dashboard 提供 4 个预览场景：

| 场景 | Agent 数 | 描述 |
|------|---------|------|
| 简单 | 2 | 基础友谊关系 |
| 中等 | 5 | 团队协作与竞争 |
| 复杂 | 10 | 公司组织架构 |
| 超复杂 | 20 | 多团队网络战 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/agents | 列出所有 Agent |
| POST | /api/agents | 注册 Agent |
| DELETE | /api/agents/{id} | 删除 Agent |
| GET | /api/agents/{id}/bonds | 列出羁绊 |
| GET | /api/agents/{id}/bonds/{target} | 获取羁绊详情 |
| PUT | /api/agents/{id}/bonds/{target} | 更新羁绊 |
| POST | /api/agents/{id}/events | 记录事件 |
| POST | /api/tick | 执行情感衰减 |
| GET | /api/network/stats | 网络统计 |
| GET | /api/network/graph | 完整图谱数据 |
| POST | /api/scenarios/{name} | 加载预览场景 |

WebSocket: `ws://127.0.0.1:19527/ws` — 实时推送羁绊变化

## 项目结构

```
bond-network/
├── src/bond_network/
│   ├── models.py        # 数据模型
│   ├── constants.py     # 常量配置
│   ├── database.py      # SQLite 存储层
│   ├── engine.py        # 羁绊引擎核心
│   ├── infer.py         # 推断引擎
│   ├── api.py           # REST API
│   ├── daemon_cli.py    # Daemon CLI
│   ├── cli.py           # 用户 CLI
│   ├── sdk.py           # Python SDK
│   ├── mcp_server.py    # MCP Server
│   ├── scenarios.py     # 预览场景
│   └── static/          # Dashboard 前端
├── tests/
│   └── test_integration.py
└── pyproject.toml
```

## 运行测试

```bash
python -m unittest tests.test_integration -v
```

## 配置

数据存储在 `~/.bond-network/bonds.db`（SQLite 单文件）。

环境变量：
- `BOND_TICK_INTERVAL` — 情感衰减间隔秒数（默认 60）

## 理论基础

详见 [羁绊网络设计文档](./羁绊网络.md)。

核心命题：**关系与情感并非不可计算的模糊概念。在任意静止时刻，羁绊是确定的；所谓复杂，不过是时效性长短的差异在时间维度上的投影。**

## 许可证

MIT License

## 贡献

欢迎 Issue 和 Pull Request！
