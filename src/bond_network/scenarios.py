from .database import AgentRepo, BondRepo, EmotionRepo, EventRepo, TieRepo, Database
from .engine import BondEngine
from .constants import DEFAULT_EMOTION_DECAY_RATES, DEFAULT_EMOTION_RESIDUES


def _create_agents(agent_repo, agents_spec):
    ids = {}
    for name, desc in agents_spec:
        agent = agent_repo.create(name, desc)
        ids[name] = agent.id
    return ids


def load_scenario_simple(db: Database):
    db.connect()
    engine = BondEngine(db)
    agent_repo = AgentRepo(db)
    
    ids = _create_agents(agent_repo, [
        ("alice", "Alice - 主角"),
        ("bob", "Bob - 好友"),
    ])
    
    engine.process_event(ids["alice"], ids["bob"], "help", "帮忙修bug", 0.5, 0.4)
    engine.process_event(ids["bob"], ids["alice"], "help", "回帮", 0.4, 0.3)
    
    return {"scenario": "simple", "agents": 2, "bonds": 2}


def load_scenario_medium(db: Database):
    db.connect()
    engine = BondEngine(db)
    agent_repo = AgentRepo(db)
    
    ids = _create_agents(agent_repo, [
        ("alice", "Alice - 团队领导"),
        ("bob", "Bob - 核心开发"),
        ("charlie", "Charlie - 新成员"),
        ("diana", "Diana - 设计师"),
        ("eve", "Eve - 竞争对手"),
    ])
    
    engine.process_event(ids["alice"], ids["bob"], "cooperation", "长期合作", 0.6, 0.5)
    engine.process_event(ids["bob"], ids["alice"], "cooperation", "信任领导", 0.5, 0.6)
    engine.process_event(ids["alice"], ids["charlie"], "help", "指导新人", 0.3, 0.2)
    engine.process_event(ids["charlie"], ids["alice"], "gratitude", "感谢指导", 0.4, 0.3)
    engine.process_event(ids["bob"], ids["charlie"], "cooperation", "代码协作", 0.3, 0.2)
    engine.process_event(ids["alice"], ids["diana"], "cooperation", "产品协作", 0.4, 0.3)
    engine.process_event(ids["diana"], ids["bob"], "help", "设计支持", 0.2, 0.2)
    engine.process_event(ids["alice"], ids["eve"], "betrayal", "抢夺资源", -0.5, -0.4)
    engine.process_event(ids["eve"], ids["alice"], "attack", "恶意竞争", -0.4, -0.3)
    engine.process_event(ids["bob"], ids["eve"], "threat", "威胁团队", -0.3, -0.2)
    
    return {"scenario": "medium", "agents": 5, "bonds": 10}


def load_scenario_complex(db: Database):
    db.connect()
    engine = BondEngine(db)
    agent_repo = AgentRepo(db)
    
    ids = _create_agents(agent_repo, [
        ("alice", "Alice - CEO"),
        ("bob", "Bob - CTO"),
        ("charlie", "Charlie - 产品总监"),
        ("diana", "Diana - 设计主管"),
        ("eve", "Eve - 竞争公司CEO"),
        ("frank", "Frank - 核心工程师"),
        ("grace", "Grace - 市场总监"),
        ("henry", "Henry - 财务总监"),
        ("ivy", "Ivy - 新员工"),
        ("jack", "Jack - 前员工(离职)"),
    ])
    
    engine.process_event(ids["alice"], ids["bob"], "cooperation", "创业伙伴", 0.8, 0.7)
    engine.process_event(ids["bob"], ids["alice"], "cooperation", "忠诚", 0.7, 0.8)
    engine.process_event(ids["alice"], ids["charlie"], "cooperation", "战略伙伴", 0.5, 0.4)
    engine.process_event(ids["charlie"], ids["alice"], "help", "支持决策", 0.4, 0.3)
    engine.process_event(ids["bob"], ids["frank"], "help", "技术指导", 0.5, 0.4)
    engine.process_event(ids["frank"], ids["bob"], "gratitude", "感谢培养", 0.4, 0.5)
    engine.process_event(ids["charlie"], ids["diana"], "cooperation", "产品协作", 0.5, 0.4)
    engine.process_event(ids["diana"], ids["charlie"], "help", "设计支持", 0.3, 0.3)
    engine.process_event(ids["alice"], ids["grace"], "cooperation", "市场战略", 0.4, 0.3)
    engine.process_event(ids["grace"], ids["charlie"], "cooperation", "推广协作", 0.3, 0.2)
    engine.process_event(ids["alice"], ids["henry"], "cooperation", "财务管理", 0.3, 0.3)
    engine.process_event(ids["henry"], ids["bob"], "help", "预算支持", 0.2, 0.2)
    engine.process_event(ids["bob"], ids["ivy"], "help", "入职培训", 0.3, 0.2)
    engine.process_event(ids["ivy"], ids["frank"], "cooperation", "学习协作", 0.2, 0.1)
    engine.process_event(ids["alice"], ids["eve"], "betrayal", "商业竞争", -0.6, -0.5)
    engine.process_event(ids["eve"], ids["alice"], "attack", "恶意挖人", -0.5, -0.4)
    engine.process_event(ids["eve"], ids["bob"], "threat", "挖角威胁", -0.4, -0.3)
    engine.process_event(ids["bob"], ids["eve"], "anger", "拒绝挖角", -0.3, -0.2)
    engine.process_event(ids["jack"], ids["alice"], "betrayal", "离职带走客户", -0.5, -0.6)
    engine.process_event(ids["alice"], ids["jack"], "anger", "解雇", -0.4, -0.3)
    engine.process_event(ids["jack"], ids["eve"], "cooperation", "投靠竞争", 0.4, 0.3)
    
    engine.process_event(ids["alice"], ids["bob"], "gift", "生日礼物", 0.3, 0.2)
    engine.process_event(ids["frank"], ids["ivy"], "help", "代码review", 0.2, 0.2)
    engine.process_event(ids["charlie"], ids["grace"], "cooperation", "产品推广", 0.3, 0.2)
    
    return {"scenario": "complex", "agents": 10, "bonds": 22}


def load_scenario_ultra(db: Database):
    db.connect()
    engine = BondEngine(db)
    agent_repo = AgentRepo(db)
    
    ids = _create_agents(agent_repo, [
        ("alice", "Alpha队长-创始人"),
        ("bob", "Alpha技术核心"),
        ("charlie", "Alpha产品经理"),
        ("diana", "Alpha设计师"),
        ("eve", "Alpha运营"),
        ("frank", "Beta队长-技术总监"),
        ("grace", "Beta架构师"),
        ("henry", "Beta安全专家"),
        ("ivy", "Beta新人"),
        ("jack", "Beta测试主管"),
        ("kate", "Gamma队长-市场VP"),
        ("leo", "Gamma销售冠军"),
        ("mia", "Gamma品牌专家"),
        ("nick", "Gamma数据分析师"),
        ("olivia", "Gamma客户成功"),
        ("peter", "Delta队长-竞争公司CEO"),
        ("quinn", "Delta技术总监"),
        ("rachel", "Delta产品总监"),
        ("sam", "Delta市场总监"),
        ("tina", "Delta前员工"),
    ])
    
    teams = {
        "alpha": ["alice", "bob", "charlie", "diana", "eve"],
        "beta": ["frank", "grace", "henry", "ivy", "jack"],
        "gamma": ["kate", "leo", "mia", "nick", "olivia"],
        "delta": ["peter", "quinn", "rachel", "sam", "tina"],
    }
    
    for team, members in teams.items():
        leader = members[0]
        for member in members[1:]:
            engine.process_event(ids[leader], ids[member], "cooperation", f"{team}团队领导", 0.4, 0.3)
            engine.process_event(ids[member], ids[leader], "help", f"支持{leader}", 0.3, 0.4)
    
    for team, members in teams.items():
        for i, m1 in enumerate(members):
            for m2 in members[i+1:]:
                engine.process_event(ids[m1], ids[m2], "cooperation", f"{team}协作", 0.2, 0.1)
                engine.process_event(ids[m2], ids[m1], "cooperation", f"{team}协作", 0.2, 0.1)
    
    engine.process_event(ids["alice"], ids["frank"], "cooperation", "技术合作", 0.5, 0.4)
    engine.process_event(ids["frank"], ids["alice"], "cooperation", "技术支持", 0.4, 0.5)
    engine.process_event(ids["alice"], ids["kate"], "cooperation", "战略联盟", 0.4, 0.3)
    engine.process_event(ids["kate"], ids["alice"], "cooperation", "市场合作", 0.3, 0.4)
    engine.process_event(ids["frank"], ids["henry"], "help", "安全指导", 0.4, 0.3)
    engine.process_event(ids["henry"], ids["frank"], "gratitude", "感谢信任", 0.3, 0.4)
    engine.process_event(ids["kate"], ids["leo"], "help", "销售指导", 0.4, 0.3)
    engine.process_event(ids["leo"], ids["kate"], "gratitude", "业绩感谢", 0.5, 0.4)
    engine.process_event(ids["charlie"], ids["mia"], "cooperation", "品牌协作", 0.3, 0.2)
    engine.process_event(ids["mia"], ids["charlie"], "help", "设计支持", 0.2, 0.2)
    
    engine.process_event(ids["alice"], ids["peter"], "betrayal", "商业竞争", -0.6, -0.5)
    engine.process_event(ids["peter"], ids["alice"], "attack", "恶意挖角", -0.5, -0.4)
    engine.process_event(ids["peter"], ids["frank"], "threat", "技术威胁", -0.4, -0.3)
    engine.process_event(ids["frank"], ids["peter"], "anger", "拒绝挖角", -0.3, -0.2)
    engine.process_event(ids["peter"], ids["kate"], "attack", "市场战", -0.4, -0.3)
    engine.process_event(ids["kate"], ids["peter"], "anger", "反击", -0.3, -0.2)
    
    engine.process_event(ids["tina"], ids["peter"], "betrayal", "离职带走客户", -0.5, -0.6)
    engine.process_event(ids["peter"], ids["tina"], "anger", "解雇", -0.4, -0.5)
    engine.process_event(ids["tina"], ids["alice"], "cooperation", "投靠对手的对手", 0.3, 0.2)
    
    engine.process_event(ids["alice"], ids["bob"], "gift", "生日礼物", 0.3, 0.2)
    engine.process_event(ids["bob"], ids["charlie"], "help", "技术支持", 0.2, 0.2)
    engine.process_event(ids["frank"], ids["grace"], "gift", "晋升祝贺", 0.3, 0.2)
    engine.process_event(ids["kate"], ids["olivia"], "help", "客户指导", 0.3, 0.2)
    engine.process_event(ids["leo"], ids["nick"], "cooperation", "销售数据协作", 0.2, 0.1)
    
    engine.process_event(ids["eve"], ids["sam"], "threat", "运营冲突", -0.3, -0.2)
    engine.process_event(ids["sam"], ids["eve"], "anger", "反击", -0.2, -0.2)
    engine.process_event(ids["quinn"], ids["henry"], "threat", "安全威胁", -0.3, -0.2)
    engine.process_event(ids["henry"], ids["quinn"], "anger", "安全反击", -0.2, -0.2)
    
    engine.process_event(ids["ivy"], ids["jack"], "cooperation", "测试协作", 0.2, 0.1)
    engine.process_event(ids["jack"], ids["ivy"], "help", "测试培训", 0.2, 0.2)
    engine.process_event(ids["diana"], ids["mia"], "cooperation", "设计品牌协作", 0.2, 0.2)
    
    for _ in range(3):
        engine.tick()
    
    engine.process_event(ids["alice"], ids["bob"], "gift", "节日礼物", 0.2, 0.1)
    engine.process_event(ids["frank"], ids["alice"], "help", "技术支持", 0.3, 0.2)
    
    return {"scenario": "ultra", "agents": 20, "bonds": 60}


SCENARIOS = {
    "simple": load_scenario_simple,
    "medium": load_scenario_medium,
    "complex": load_scenario_complex,
    "ultra": load_scenario_ultra,
}


def load_demo_scenario(db: Database, scenario: str):
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}. Available: {list(SCENARIOS.keys())}")
    
    agent_repo = AgentRepo(db)
    for agent in agent_repo.list_all():
        agent_repo.delete(agent.id)
    
    return SCENARIOS[scenario](db)
