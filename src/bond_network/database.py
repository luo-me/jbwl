import sqlite3
from datetime import datetime
from uuid import uuid4

from .constants import DEFAULT_DB_PATH, EMOTION_DECAY_THRESHOLD
from .models import Agent, Bond, BondType, Emotion, EmotionType, Event, Tie, Visibility


def clamp_valence(v):
    return max(-1.0, min(1.0, v))


def clamp_trust(v):
    return max(-1.0, min(1.0, v))


def clamp_strength(v):
    return max(0.0, min(1.0, v))


def clamp_intensity(v):
    return max(0.0, min(1.0, v))


def clamp_stability(v):
    return max(0.0, v)


def _row_to_agent(row):
    return Agent(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_bond(row):
    return Bond(
        id=row["id"],
        source_agent_id=row["source_agent_id"],
        target_agent_id=row["target_agent_id"],
        inferred=bool(row["inferred"]),
        confidence=row["confidence"],
        last_update=datetime.fromisoformat(row["last_update"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_tie(row):
    return Tie(
        bond_id=row["bond_id"],
        type=BondType(row["type"]),
        valence=row["valence"],
        strength=row["strength"],
        stability=row["stability"],
        trust=row["trust"],
        visibility=Visibility(row["visibility"]),
    )


def _row_to_emotion(row):
    return Emotion(
        bond_id=row["bond_id"],
        type=EmotionType(row["type"]),
        intensity=row["intensity"],
        decay_rate=row["decay_rate"],
        trigger_event_id=row["trigger_event_id"],
        residue=row["residue"],
        peak_intensity=row["peak_intensity"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_event(row):
    return Event(
        id=row["id"],
        source_agent_id=row["source_agent_id"],
        target_agent_id=row["target_agent_id"],
        event_type=row["event_type"],
        description=row["description"],
        impact_valence=row["impact_valence"],
        impact_trust=row["impact_trust"],
        impact_strength=row["impact_strength"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.conn = None

    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS bonds (
                id TEXT PRIMARY KEY,
                source_agent_id TEXT NOT NULL,
                target_agent_id TEXT NOT NULL,
                inferred INTEGER DEFAULT 0,
                confidence REAL DEFAULT 1.0,
                last_update TEXT,
                created_at TEXT,
                FOREIGN KEY(source_agent_id) REFERENCES agents(id),
                FOREIGN KEY(target_agent_id) REFERENCES agents(id),
                UNIQUE(source_agent_id, target_agent_id)
            );

            CREATE TABLE IF NOT EXISTS ties (
                bond_id TEXT PRIMARY KEY,
                type TEXT DEFAULT 'stranger',
                valence REAL DEFAULT 0.0,
                strength REAL DEFAULT 0.0,
                stability REAL DEFAULT 1.0,
                trust REAL DEFAULT 0.0,
                visibility TEXT DEFAULT 'private',
                FOREIGN KEY(bond_id) REFERENCES bonds(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS emotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bond_id TEXT NOT NULL,
                type TEXT NOT NULL,
                intensity REAL DEFAULT 0.0,
                decay_rate REAL DEFAULT 0.1,
                trigger_event_id TEXT DEFAULT '',
                residue REAL DEFAULT 0.0,
                peak_intensity REAL DEFAULT 0.0,
                created_at TEXT,
                FOREIGN KEY(bond_id) REFERENCES bonds(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                source_agent_id TEXT NOT NULL,
                target_agent_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                impact_valence REAL DEFAULT 0.0,
                impact_trust REAL DEFAULT 0.0,
                impact_strength REAL DEFAULT 0.0,
                created_at TEXT
            );
        """)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AgentRepo:
    def __init__(self, db):
        self.db = db

    def create(self, name, description=""):
        now = datetime.now().isoformat()
        agent_id = str(uuid4())
        self.db.conn.execute(
            "INSERT INTO agents (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (agent_id, name, description, now, now),
        )
        self.db.conn.commit()
        return Agent(
            id=agent_id,
            name=name,
            description=description,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def get_by_name(self, name):
        row = self.db.conn.execute(
            "SELECT * FROM agents WHERE name = ?", (name,)
        ).fetchone()
        return _row_to_agent(row) if row else None

    def get_by_id(self, id):
        row = self.db.conn.execute(
            "SELECT * FROM agents WHERE id = ?", (id,)
        ).fetchone()
        return _row_to_agent(row) if row else None

    def list_all(self):
        rows = self.db.conn.execute("SELECT * FROM agents").fetchall()
        return [_row_to_agent(row) for row in rows]

    def delete(self, id):
        self.db.conn.execute(
            "DELETE FROM bonds WHERE source_agent_id = ? OR target_agent_id = ?",
            (id, id),
        )
        self.db.conn.execute(
            "DELETE FROM events WHERE source_agent_id = ? OR target_agent_id = ?",
            (id, id),
        )
        cursor = self.db.conn.execute("DELETE FROM agents WHERE id = ?", (id,))
        self.db.conn.commit()
        return cursor.rowcount > 0


class BondRepo:
    def __init__(self, db):
        self.db = db

    def create(self, source_agent_id, target_agent_id, inferred=False, confidence=1.0):
        now = datetime.now().isoformat()
        bond_id = str(uuid4())
        self.db.conn.execute(
            "INSERT INTO bonds (id, source_agent_id, target_agent_id, inferred, confidence, last_update, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bond_id, source_agent_id, target_agent_id, int(inferred), confidence, now, now),
        )
        self.db.conn.execute(
            "INSERT INTO ties (bond_id, type, valence, strength, stability, trust, visibility) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bond_id, "stranger", 0.0, 0.0, 1.0, 0.0, "private"),
        )
        self.db.conn.commit()
        return Bond(
            id=bond_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            inferred=inferred,
            confidence=confidence,
            last_update=datetime.fromisoformat(now),
            created_at=datetime.fromisoformat(now),
        )

    def get(self, source_agent_id, target_agent_id):
        row = self.db.conn.execute(
            "SELECT * FROM bonds WHERE source_agent_id = ? AND target_agent_id = ?",
            (source_agent_id, target_agent_id),
        ).fetchone()
        return _row_to_bond(row) if row else None

    def get_by_id(self, id):
        row = self.db.conn.execute(
            "SELECT * FROM bonds WHERE id = ?", (id,)
        ).fetchone()
        return _row_to_bond(row) if row else None

    def list_by_agent(self, agent_id):
        rows = self.db.conn.execute(
            "SELECT * FROM bonds WHERE source_agent_id = ? OR target_agent_id = ?",
            (agent_id, agent_id),
        ).fetchall()
        return [_row_to_bond(row) for row in rows]

    def delete(self, id):
        cursor = self.db.conn.execute("DELETE FROM bonds WHERE id = ?", (id,))
        self.db.conn.commit()
        return cursor.rowcount > 0


class TieRepo:
    def __init__(self, db):
        self.db = db

    def create(self, bond_id, type="stranger", valence=0.0, strength=0.1, stability=1.0, trust=0.0, visibility="private"):
        valence = clamp_valence(valence)
        strength = clamp_strength(strength)
        stability = clamp_stability(stability)
        trust = clamp_trust(trust)
        self.db.conn.execute(
            "INSERT INTO ties (bond_id, type, valence, strength, stability, trust, visibility) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bond_id, type, valence, strength, stability, trust, visibility),
        )
        self.db.conn.commit()
        return Tie(
            bond_id=bond_id,
            type=BondType(type),
            valence=valence,
            strength=strength,
            stability=stability,
            trust=trust,
            visibility=Visibility(visibility),
        )

    def get_by_bond_id(self, bond_id):
        row = self.db.conn.execute(
            "SELECT * FROM ties WHERE bond_id = ?", (bond_id,)
        ).fetchone()
        return _row_to_tie(row) if row else None

    def update(self, bond_id, **kwargs):
        allowed = {"type", "valence", "strength", "stability", "trust", "visibility"}
        updates = {}
        for key, value in kwargs.items():
            if key in allowed:
                if key == "valence":
                    value = clamp_valence(value)
                elif key == "trust":
                    value = clamp_trust(value)
                elif key == "strength":
                    value = clamp_strength(value)
                elif key == "stability":
                    value = clamp_stability(value)
                updates[key] = value
        if not updates:
            return self.get_by_bond_id(bond_id)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [bond_id]
        self.db.conn.execute(
            f"UPDATE ties SET {set_clause} WHERE bond_id = ?", values
        )
        self.db.conn.commit()
        return self.get_by_bond_id(bond_id)


class EmotionRepo:
    def __init__(self, db):
        self.db = db

    def create(self, bond_id, type, intensity, decay_rate, trigger_event_id, residue, peak_intensity):
        intensity = clamp_intensity(intensity)
        peak_intensity = clamp_intensity(peak_intensity)
        now = datetime.now().isoformat()
        cursor = self.db.conn.execute(
            "INSERT INTO emotions (bond_id, type, intensity, decay_rate, trigger_event_id, residue, peak_intensity, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (bond_id, type, intensity, decay_rate, trigger_event_id, residue, peak_intensity, now),
        )
        self.db.conn.commit()
        return Emotion(
            bond_id=bond_id,
            type=EmotionType(type),
            intensity=intensity,
            decay_rate=decay_rate,
            trigger_event_id=trigger_event_id,
            residue=residue,
            peak_intensity=peak_intensity,
            created_at=datetime.fromisoformat(now),
        )

    def list_by_bond(self, bond_id):
        rows = self.db.conn.execute(
            "SELECT * FROM emotions WHERE bond_id = ?", (bond_id,)
        ).fetchall()
        return [_row_to_emotion(row) for row in rows]

    def list_active(self, bond_id):
        rows = self.db.conn.execute(
            "SELECT * FROM emotions WHERE bond_id = ? AND intensity > ?",
            (bond_id, EMOTION_DECAY_THRESHOLD),
        ).fetchall()
        return [_row_to_emotion(row) for row in rows]

    def find_by_type(self, bond_id, emotion_type):
        rows = self.db.conn.execute(
            "SELECT * FROM emotions WHERE bond_id = ? AND type = ?",
            (bond_id, emotion_type),
        ).fetchall()
        return [_row_to_emotion(row) for row in rows]

    def update_intensity(self, emotion_id, intensity):
        intensity = clamp_intensity(intensity)
        self.db.conn.execute(
            "UPDATE emotions SET intensity = ? WHERE id = ?",
            (intensity, emotion_id),
        )
        self.db.conn.commit()

    def delete(self, emotion_id):
        self.db.conn.execute(
            "DELETE FROM emotions WHERE id = ?", (emotion_id,)
        )
        self.db.conn.commit()


class EventRepo:
    def __init__(self, db):
        self.db = db

    def create(self, source_agent_id, target_agent_id, event_type, description, impact_valence, impact_trust, impact_strength):
        now = datetime.now().isoformat()
        event_id = str(uuid4())
        self.db.conn.execute(
            "INSERT INTO events (id, source_agent_id, target_agent_id, event_type, description, impact_valence, impact_trust, impact_strength, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, source_agent_id, target_agent_id, event_type, description, impact_valence, impact_trust, impact_strength, now),
        )
        self.db.conn.commit()
        return Event(
            id=event_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            event_type=event_type,
            description=description,
            impact_valence=impact_valence,
            impact_trust=impact_trust,
            impact_strength=impact_strength,
            created_at=datetime.fromisoformat(now),
        )

    def list_by_agent(self, agent_id):
        rows = self.db.conn.execute(
            "SELECT * FROM events WHERE source_agent_id = ? OR target_agent_id = ?",
            (agent_id, agent_id),
        ).fetchall()
        return [_row_to_event(row) for row in rows]

    def list_by_pair(self, source_agent_id, target_agent_id):
        rows = self.db.conn.execute(
            "SELECT * FROM events WHERE source_agent_id = ? AND target_agent_id = ?",
            (source_agent_id, target_agent_id),
        ).fetchall()
        return [_row_to_event(row) for row in rows]
