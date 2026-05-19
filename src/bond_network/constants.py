from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".bond-network" / "bonds.db"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 19527

EMOTION_DECAY_THRESHOLD = 0.01
INTERACTION_STRENGTH_GAIN = 0.05
REPAIR_ASYMMETRY_FACTOR = 0.6
EMOTION_REINFORCEMENT_FACTOR = 0.5

DEFAULT_EMOTION_DECAY_RATES = {
    "joy": 0.05,
    "anger": 0.08,
    "fear": 0.10,
    "sadness": 0.03,
    "disgust": 0.07,
    "surprise": 0.15,
    "gratitude": 0.02,
    "resentment": 0.04,
}

DEFAULT_EMOTION_RESIDUES = {
    "joy": 0.1,
    "anger": 0.3,
    "fear": 0.2,
    "sadness": 0.25,
    "disgust": 0.15,
    "surprise": 0.05,
    "gratitude": 0.2,
    "resentment": 0.35,
}

BOND_TYPE_TRANSITIONS = [
    ("stranger", "acquaintance"),
    ("acquaintance", "friend"),
    ("acquaintance", "rival"),
    ("friend", "best_friend"),
    ("friend", "collaborator"),
    ("friend", "partner"),
    ("rival", "enemy"),
    ("collaborator", "partner"),
    ("partner", "best_friend"),
    ("enemy", "rival"),
    ("best_friend", "friend"),
    ("friend", "acquaintance"),
    ("acquaintance", "stranger"),
    ("subordinate", "collaborator"),
    ("collaborator", "subordinate"),
]
