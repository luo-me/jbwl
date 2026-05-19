from .constants import (
    DEFAULT_EMOTION_DECAY_RATES,
    DEFAULT_EMOTION_RESIDUES,
    EMOTION_DECAY_THRESHOLD,
    EMOTION_REINFORCEMENT_FACTOR,
    INTERACTION_STRENGTH_GAIN,
    REPAIR_ASYMMETRY_FACTOR,
)
from .database import (
    AgentRepo,
    BondRepo,
    EmotionRepo,
    EventRepo,
    TieRepo,
    clamp_intensity,
    clamp_strength,
    clamp_trust,
    clamp_valence,
)

EVENT_EMOTION_MAP = {
    "help": "joy",
    "cooperation": "joy",
    "gift": "gratitude",
    "surprise_event": "surprise",
    "betrayal": "anger",
    "attack": "anger",
    "threat": "fear",
    "loss": "sadness",
    "insult": "disgust",
}

POSITIVE_EMOTIONS = {"joy", "gratitude", "surprise"}
NEGATIVE_EMOTIONS = {"anger", "fear", "sadness", "disgust", "resentment"}


class BondEngine:
    def __init__(self, db):
        self.db = db
        self._agent_repo = AgentRepo(db)
        self._bond_repo = BondRepo(db)
        self._tie_repo = TieRepo(db)
        self._emotion_repo = EmotionRepo(db)
        self._event_repo = EventRepo(db)

    def process_event(self, source_agent_id, target_agent_id, event_type, description, impact_valence, impact_trust, impact_strength=0.0):
        source = self._agent_repo.get_by_id(source_agent_id)
        if not source:
            raise ValueError(f"source agent not found: {source_agent_id}")
        target = self._agent_repo.get_by_id(target_agent_id)
        if not target:
            raise ValueError(f"target agent not found: {target_agent_id}")

        bond = self._bond_repo.get(source_agent_id, target_agent_id)
        if not bond:
            bond = self._bond_repo.create(source_agent_id, target_agent_id)
            self._tie_repo.update(bond.id, strength=0.1)

        tie = self._tie_repo.get_by_bond_id(bond.id)

        delta_valence = impact_valence / (1 + tie.stability)
        delta_trust = impact_trust / (1 + tie.stability)
        new_valence = clamp_valence(tie.valence + delta_valence)
        new_trust = clamp_trust(tie.trust + delta_trust)
        new_strength = clamp_strength(tie.strength + INTERACTION_STRENGTH_GAIN + impact_strength)

        self._tie_repo.update(bond.id, valence=new_valence, trust=new_trust, strength=new_strength)

        event = self._event_repo.create(
            source_agent_id, target_agent_id, event_type, description,
            impact_valence, impact_trust, impact_strength,
        )

        if abs(impact_valence) > 0.3:
            emotion_type_str = EVENT_EMOTION_MAP.get(event_type)
            if emotion_type_str:
                intensity = abs(impact_valence)
                existing = self._emotion_repo.find_by_type(bond.id, emotion_type_str)
                if existing:
                    max_existing = max(e.intensity for e in existing)
                    intensity = intensity * (1 + max_existing * EMOTION_REINFORCEMENT_FACTOR)
                intensity = clamp_intensity(intensity)
                decay_rate = DEFAULT_EMOTION_DECAY_RATES.get(emotion_type_str, 0.1)
                residue = DEFAULT_EMOTION_RESIDUES.get(emotion_type_str, 0.0)
                self._emotion_repo.create(
                    bond.id, emotion_type_str, intensity, decay_rate,
                    event.id, residue, intensity,
                )

        self.check_type_transition(bond.id)

        return self.get_bond_state(source_agent_id, target_agent_id)

    def tick(self):
        rows = self.db.conn.execute(
            "SELECT * FROM emotions WHERE intensity > ?",
            (EMOTION_DECAY_THRESHOLD,),
        ).fetchall()

        decayed_count = 0
        faded_count = 0
        residue_count = 0

        for row in rows:
            emotion_id = row["id"]
            bond_id = row["bond_id"]
            emotion_type = row["type"]
            current_intensity = row["intensity"]
            decay_rate = row["decay_rate"]
            residue_val = row["residue"]
            peak_intensity = row["peak_intensity"]

            new_intensity = current_intensity * (1 - decay_rate)
            decayed_count += 1

            if new_intensity < EMOTION_DECAY_THRESHOLD:
                sign = 1 if emotion_type in POSITIVE_EMOTIONS else -1
                residue_impact = residue_val * sign * peak_intensity
                tie = self._tie_repo.get_by_bond_id(bond_id)
                if tie:
                    if tie.trust < 0 and residue_impact > 0:
                        residue_impact *= REPAIR_ASYMMETRY_FACTOR
                    new_trust = clamp_trust(tie.trust + residue_impact)
                    self._tie_repo.update(bond_id, trust=new_trust)
                self._emotion_repo.delete(emotion_id)
                faded_count += 1
                residue_count += 1
            else:
                self._emotion_repo.update_intensity(emotion_id, new_intensity)

        return {
            "decayed": decayed_count,
            "faded": faded_count,
            "residue_writes": residue_count,
        }

    def check_type_transition(self, bond_id):
        bond = self._bond_repo.get_by_id(bond_id)
        if not bond:
            return None
        tie = self._tie_repo.get_by_bond_id(bond_id)
        if not tie:
            return None

        current_type = tie.type.value
        v = tie.valence
        t = tie.trust
        s = tie.strength

        new_type = None

        if current_type == "friend":
            if v < -0.3 and t < -0.3:
                new_type = "enemy"
            elif v > 0.8 and t > 0.7 and s > 0.7:
                new_type = "best_friend"
            elif v > 0.3 and t > 0.3 and s > 0.3:
                events = self._event_repo.list_by_pair(bond.source_agent_id, bond.target_agent_id)
                if any(e.event_type == "cooperation" for e in events):
                    new_type = "collaborator"
        elif current_type == "acquaintance":
            if v > 0.3 and s > 0.3:
                new_type = "friend"
            elif v < -0.2 and s > 0.2:
                new_type = "rival"
        elif current_type == "stranger":
            if s > 0.1:
                new_type = "acquaintance"
        elif current_type == "enemy":
            if v > -0.3 or t > -0.3:
                new_type = "rival"
        elif current_type == "best_friend":
            if v < 0.7 or t < 0.5:
                new_type = "friend"
        elif current_type == "collaborator":
            if v > 0.6 and t > 0.5 and s > 0.5:
                new_type = "partner"

        if new_type:
            self._tie_repo.update(bond_id, type=new_type)
            return new_type
        return None

    def get_bond_state(self, source_agent_id, target_agent_id):
        bond = self._bond_repo.get(source_agent_id, target_agent_id)
        if not bond:
            return None
        tie = self._tie_repo.get_by_bond_id(bond.id)
        emotions = self._emotion_repo.list_by_bond(bond.id)
        result = {
            "id": bond.id,
            "source_agent_id": bond.source_agent_id,
            "target_agent_id": bond.target_agent_id,
            "inferred": bond.inferred,
            "confidence": bond.confidence,
            "last_update": bond.last_update.isoformat() if bond.last_update else None,
            "created_at": bond.created_at.isoformat() if bond.created_at else None,
        }
        if tie:
            result["tie"] = {
                "bond_id": tie.bond_id,
                "type": tie.type.value,
                "valence": tie.valence,
                "strength": tie.strength,
                "stability": tie.stability,
                "trust": tie.trust,
                "visibility": tie.visibility.value,
            }
        result["emotions"] = [
            {
                "bond_id": e.bond_id,
                "type": e.type.value,
                "intensity": e.intensity,
                "decay_rate": e.decay_rate,
                "trigger_event_id": e.trigger_event_id,
                "residue": e.residue,
                "peak_intensity": e.peak_intensity,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in emotions
        ]
        return result

    def list_bonds(self, agent_id):
        bonds = self._bond_repo.list_by_agent(agent_id)
        result = []
        for bond in bonds:
            state = self.get_bond_state(bond.source_agent_id, bond.target_agent_id)
            if state:
                result.append(state)
        return result

    def set_tie(self, source_agent_id, target_agent_id, **kwargs):
        bond = self._bond_repo.get(source_agent_id, target_agent_id)
        if not bond:
            source = self._agent_repo.get_by_id(source_agent_id)
            if not source:
                raise ValueError(f"source agent not found: {source_agent_id}")
            target = self._agent_repo.get_by_id(target_agent_id)
            if not target:
                raise ValueError(f"target agent not found: {target_agent_id}")
            bond = self._bond_repo.create(source_agent_id, target_agent_id)

        self._tie_repo.update(bond.id, **kwargs)
        self.check_type_transition(bond.id)
        return self.get_bond_state(source_agent_id, target_agent_id)

    def get_network_stats(self):
        agent_count = len(self._agent_repo.list_all())

        bond_row = self.db.conn.execute("SELECT COUNT(*) FROM bonds").fetchone()
        bond_count = bond_row[0]

        emotion_row = self.db.conn.execute(
            "SELECT COUNT(*) FROM emotions WHERE intensity > ?",
            (EMOTION_DECAY_THRESHOLD,),
        ).fetchone()
        active_emotion_count = emotion_row[0]

        tie_rows = self.db.conn.execute("SELECT valence, trust, strength FROM ties").fetchall()
        if tie_rows:
            avg_valence = sum(r["valence"] for r in tie_rows) / len(tie_rows)
            avg_trust = sum(r["trust"] for r in tie_rows) / len(tie_rows)
            avg_strength = sum(r["strength"] for r in tie_rows) / len(tie_rows)
        else:
            avg_valence = 0.0
            avg_trust = 0.0
            avg_strength = 0.0

        return {
            "agent_count": agent_count,
            "bond_count": bond_count,
            "active_emotion_count": active_emotion_count,
            "avg_valence": avg_valence,
            "avg_trust": avg_trust,
            "avg_strength": avg_strength,
        }
