import shutil
import tempfile
import unittest
from pathlib import Path

from bond_network.database import (
    AgentRepo,
    BondRepo,
    Database,
    EmotionRepo,
    EventRepo,
    TieRepo,
)
from bond_network.engine import BondEngine
from bond_network.infer import InferEngine
from bond_network.models import BondType, EmotionType


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.db = Database(db_path=self.db_path)
        self.db.connect()
        self.agent_repo = AgentRepo(self.db)
        self.bond_repo = BondRepo(self.db)
        self.tie_repo = TieRepo(self.db)
        self.emotion_repo = EmotionRepo(self.db)
        self.event_repo = EventRepo(self.db)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmpdir)

    def test_create_database(self):
        cursor = self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        self.assertIn("agents", tables)
        self.assertIn("bonds", tables)
        self.assertIn("ties", tables)
        self.assertIn("emotions", tables)
        self.assertIn("events", tables)

    def test_agent_crud(self):
        agent = self.agent_repo.create("alice", "test agent")
        self.assertEqual(agent.name, "alice")
        self.assertEqual(agent.description, "test agent")

        found = self.agent_repo.get_by_name("alice")
        self.assertIsNotNone(found)
        self.assertEqual(found.id, agent.id)

        found_by_id = self.agent_repo.get_by_id(agent.id)
        self.assertIsNotNone(found_by_id)

        all_agents = self.agent_repo.list_all()
        self.assertEqual(len(all_agents), 1)

        deleted = self.agent_repo.delete(agent.id)
        self.assertTrue(deleted)

        found_after = self.agent_repo.get_by_name("alice")
        self.assertIsNone(found_after)

    def test_bond_crud(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")

        bond = self.bond_repo.create(alice.id, bob.id)
        self.assertEqual(bond.source_agent_id, alice.id)
        self.assertEqual(bond.target_agent_id, bob.id)

        tie = self.tie_repo.get_by_bond_id(bond.id)
        self.assertIsNotNone(tie)

        found = self.bond_repo.get(alice.id, bob.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, bond.id)

        bonds = self.bond_repo.list_by_agent(alice.id)
        self.assertEqual(len(bonds), 1)

        deleted = self.bond_repo.delete(bond.id)
        self.assertTrue(deleted)

        found_after = self.bond_repo.get(alice.id, bob.id)
        self.assertIsNone(found_after)

    def test_tie_crud(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")
        bond = self.bond_repo.create(alice.id, bob.id)

        tie = self.tie_repo.get_by_bond_id(bond.id)
        self.assertIsNotNone(tie)
        self.assertEqual(tie.type, BondType.stranger)
        self.assertAlmostEqual(tie.valence, 0.0)
        self.assertAlmostEqual(tie.trust, 0.0)

        updated = self.tie_repo.update(bond.id, valence=1.5)
        self.assertAlmostEqual(updated.valence, 1.0)

        updated = self.tie_repo.update(bond.id, valence=-1.5)
        self.assertAlmostEqual(updated.valence, -1.0)

        updated = self.tie_repo.update(bond.id, strength=2.0)
        self.assertAlmostEqual(updated.strength, 1.0)

        updated = self.tie_repo.update(bond.id, strength=-0.5)
        self.assertAlmostEqual(updated.strength, 0.0)

        updated = self.tie_repo.update(bond.id, trust=1.5)
        self.assertAlmostEqual(updated.trust, 1.0)

        updated = self.tie_repo.update(bond.id, trust=-1.5)
        self.assertAlmostEqual(updated.trust, -1.0)

    def test_emotion_crud(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")
        bond = self.bond_repo.create(alice.id, bob.id)

        emotion = self.emotion_repo.create(
            bond.id, "joy", 0.8, 0.05, "", 0.1, 0.8
        )
        self.assertEqual(emotion.type, EmotionType.joy)
        self.assertAlmostEqual(emotion.intensity, 0.8)

        active = self.emotion_repo.list_active(bond.id)
        self.assertEqual(len(active), 1)

        by_type = self.emotion_repo.find_by_type(bond.id, "joy")
        self.assertEqual(len(by_type), 1)

        row = self.db.conn.execute(
            "SELECT id FROM emotions WHERE bond_id = ?", (bond.id,)
        ).fetchone()
        emotion_id = row["id"]

        self.emotion_repo.update_intensity(emotion_id, 0.005)
        active_after = self.emotion_repo.list_active(bond.id)
        self.assertEqual(len(active_after), 0)

        self.emotion_repo.delete(emotion_id)
        all_emotions = self.emotion_repo.list_by_bond(bond.id)
        self.assertEqual(len(all_emotions), 0)

    def test_event_crud(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")

        event = self.event_repo.create(
            alice.id, bob.id, "help", "helped", 0.3, 0.2, 0.0
        )
        self.assertEqual(event.event_type, "help")
        self.assertEqual(event.source_agent_id, alice.id)

        by_agent = self.event_repo.list_by_agent(alice.id)
        self.assertEqual(len(by_agent), 1)

        by_pair = self.event_repo.list_by_pair(alice.id, bob.id)
        self.assertEqual(len(by_pair), 1)

    def test_cascade_delete(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")
        bond = self.bond_repo.create(alice.id, bob.id)
        self.emotion_repo.create(bond.id, "joy", 0.8, 0.05, "", 0.1, 0.8)

        tie_before = self.tie_repo.get_by_bond_id(bond.id)
        self.assertIsNotNone(tie_before)
        emotions_before = self.emotion_repo.list_by_bond(bond.id)
        self.assertEqual(len(emotions_before), 1)

        self.bond_repo.delete(bond.id)

        tie_after = self.tie_repo.get_by_bond_id(bond.id)
        self.assertIsNone(tie_after)
        emotions_after = self.emotion_repo.list_by_bond(bond.id)
        self.assertEqual(len(emotions_after), 0)

        self.agent_repo.delete(alice.id)
        self.agent_repo.delete(bob.id)
        self.assertIsNone(self.agent_repo.get_by_id(alice.id))
        self.assertIsNone(self.agent_repo.get_by_id(bob.id))


class TestBondEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.db = Database(db_path=self.db_path)
        self.db.connect()
        self.engine = BondEngine(self.db)
        self.agent_repo = AgentRepo(self.db)
        self.bond_repo = BondRepo(self.db)
        self.tie_repo = TieRepo(self.db)
        self.emotion_repo = EmotionRepo(self.db)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmpdir)

    def test_process_event_basic(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")

        self.engine.process_event(
            alice.id, bob.id, "help", "alice helped bob",
            impact_valence=0.3, impact_trust=0.2,
        )

        state = self.engine.get_bond_state(alice.id, bob.id)
        self.assertIsNotNone(state)
        tie = state["tie"]
        self.assertAlmostEqual(tie["valence"], 0.15, places=4)
        self.assertAlmostEqual(tie["trust"], 0.1, places=4)
        self.assertAlmostEqual(tie["strength"], 0.15, places=4)

    def test_process_event_creates_emotion(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")

        self.engine.process_event(
            alice.id, bob.id, "help", "alice helped bob",
            impact_valence=0.5, impact_trust=0.1,
        )

        bond = self.bond_repo.get(alice.id, bob.id)
        emotions = self.emotion_repo.find_by_type(bond.id, "joy")
        self.assertEqual(len(emotions), 1)
        self.assertAlmostEqual(emotions[0].intensity, 0.5, places=4)

    def test_emotion_reinforcement(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")
        bond = self.bond_repo.create(alice.id, bob.id)

        self.emotion_repo.create(bond.id, "joy", 0.3, 0.05, "", 0.1, 0.3)

        self.engine.process_event(
            alice.id, bob.id, "help", "alice helped bob",
            impact_valence=0.5, impact_trust=0.1,
        )

        emotions = self.emotion_repo.find_by_type(bond.id, "joy")
        self.assertEqual(len(emotions), 2)
        max_intensity = max(e.intensity for e in emotions)
        expected = 0.5 * (1 + 0.3 * 0.5)
        self.assertAlmostEqual(max_intensity, expected, places=4)

    def test_tick_decay(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")
        bond = self.bond_repo.create(alice.id, bob.id)

        self.emotion_repo.create(bond.id, "joy", 0.5, 0.1, "", 0.1, 0.5)

        self.engine.tick()

        emotions = self.emotion_repo.list_by_bond(bond.id)
        self.assertEqual(len(emotions), 1)
        self.assertAlmostEqual(emotions[0].intensity, 0.45, places=4)

    def test_tick_residue(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")
        bond = self.bond_repo.create(alice.id, bob.id)

        self.emotion_repo.create(bond.id, "joy", 0.019, 0.5, "", 0.2, 0.8)

        self.engine.tick()

        emotions = self.emotion_repo.list_by_bond(bond.id)
        self.assertEqual(len(emotions), 0)

        tie = self.tie_repo.get_by_bond_id(bond.id)
        self.assertAlmostEqual(tie.trust, 0.16, places=4)

    def test_repair_asymmetry(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")
        bond = self.bond_repo.create(alice.id, bob.id)

        self.tie_repo.update(bond.id, trust=-0.5)
        self.emotion_repo.create(bond.id, "joy", 0.019, 0.5, "", 0.2, 0.8)

        self.engine.tick()

        emotions = self.emotion_repo.list_by_bond(bond.id)
        self.assertEqual(len(emotions), 0)

        tie = self.tie_repo.get_by_bond_id(bond.id)
        self.assertAlmostEqual(tie.trust, -0.404, places=4)

    def test_type_transition(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")

        bond = self.bond_repo.create(alice.id, bob.id)
        tie = self.tie_repo.get_by_bond_id(bond.id)
        self.assertEqual(tie.type, BondType.stranger)

        self.engine.set_tie(alice.id, bob.id, strength=0.2)

        state = self.engine.get_bond_state(alice.id, bob.id)
        self.assertEqual(state["tie"]["type"], "acquaintance")

    def test_valence_clamp(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")

        bond = self.bond_repo.create(alice.id, bob.id)
        self.tie_repo.update(bond.id, stability=0)

        self.engine.process_event(
            alice.id, bob.id, "help", "big help",
            impact_valence=2.0, impact_trust=0.0,
        )

        state = self.engine.get_bond_state(alice.id, bob.id)
        self.assertAlmostEqual(state["tie"]["valence"], 1.0, places=4)


class TestInferEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.db = Database(db_path=self.db_path)
        self.db.connect()
        self.infer_engine = InferEngine(self.db)
        self.bond_engine = BondEngine(self.db)
        self.agent_repo = AgentRepo(self.db)
        self.bond_repo = BondRepo(self.db)
        self.tie_repo = TieRepo(self.db)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmpdir)

    def test_trust_transitivity(self):
        a = self.agent_repo.create("A")
        b = self.agent_repo.create("B")
        c = self.agent_repo.create("C")

        bond_ab = self.bond_repo.create(a.id, b.id)
        self.tie_repo.update(bond_ab.id, trust=0.7)

        bond_bc = self.bond_repo.create(b.id, c.id)
        self.tie_repo.update(bond_bc.id, trust=0.6)

        result = self.infer_engine.infer_trust_transitivity(a.id, b.id, c.id)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["inferred_trust"], 0.21, places=4)

    def test_inferred_bond_creation(self):
        a = self.agent_repo.create("A")
        b = self.agent_repo.create("B")
        c = self.agent_repo.create("C")

        bond_ab = self.bond_repo.create(a.id, b.id)
        self.tie_repo.update(bond_ab.id, trust=0.7)

        bond_bc = self.bond_repo.create(b.id, c.id)
        self.tie_repo.update(bond_bc.id, trust=0.6)

        result = self.infer_engine.infer_bond(a.id, a.id, c.id)
        self.assertTrue(result["inferred"])
        self.assertAlmostEqual(result["confidence"], 0.3, places=4)

        bond_ac = self.bond_repo.get(a.id, c.id)
        self.assertIsNotNone(bond_ac)
        self.assertTrue(bond_ac.inferred)

    def test_get_agent_network(self):
        a = self.agent_repo.create("A")
        b = self.agent_repo.create("B")
        c = self.agent_repo.create("C")

        self.bond_repo.create(a.id, b.id)
        self.bond_repo.create(b.id, c.id)

        network = self.infer_engine.get_agent_network(a.id, depth=2)

        node_ids = {n["id"] for n in network["nodes"]}
        self.assertIn(a.id, node_ids)
        self.assertIn(b.id, node_ids)
        self.assertIn(c.id, node_ids)

        self.assertEqual(len(network["edges"]), 2)


class TestRepairAsymmetryE2E(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.db = Database(db_path=self.db_path)
        self.db.connect()
        self.engine = BondEngine(self.db)
        self.agent_repo = AgentRepo(self.db)
        self.bond_repo = BondRepo(self.db)
        self.tie_repo = TieRepo(self.db)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmpdir)

    def test_betrayal_vs_repair(self):
        alice = self.agent_repo.create("alice")
        bob = self.agent_repo.create("bob")

        bond = self.bond_repo.create(alice.id, bob.id)
        self.tie_repo.update(bond.id, trust=0.5)

        self.engine.process_event(
            alice.id, bob.id, "betrayal", "bob betrayed alice",
            impact_valence=-0.8, impact_trust=-0.8,
        )

        state = self.engine.get_bond_state(alice.id, bob.id)
        self.assertTrue(state["tie"]["trust"] < 0.5)

        for _ in range(100):
            result = self.engine.tick()
            if result["faded"] > 0:
                break

        for _ in range(5):
            self.engine.process_event(
                alice.id, bob.id, "help", "repair",
                impact_valence=0.0, impact_trust=0.16,
            )

        state = self.engine.get_bond_state(alice.id, bob.id)
        self.assertTrue(state["tie"]["trust"] < 0.5)


if __name__ == "__main__":
    unittest.main()
