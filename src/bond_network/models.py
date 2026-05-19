from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class BondType(Enum):
    stranger = "stranger"
    acquaintance = "acquaintance"
    friend = "friend"
    enemy = "enemy"
    best_friend = "best_friend"
    rival = "rival"
    collaborator = "collaborator"
    partner = "partner"
    subordinate = "subordinate"


class EmotionType(Enum):
    joy = "joy"
    anger = "anger"
    fear = "fear"
    sadness = "sadness"
    disgust = "disgust"
    surprise = "surprise"
    gratitude = "gratitude"
    resentment = "resentment"


class Visibility(Enum):
    private = "private"
    mutual = "mutual"
    public = "public"


@dataclass
class Agent:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Bond:
    id: str = field(default_factory=lambda: str(uuid4()))
    source_agent_id: str = ""
    target_agent_id: str = ""
    inferred: bool = False
    confidence: float = 1.0
    last_update: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Tie:
    bond_id: str = ""
    type: BondType = BondType.stranger
    valence: float = 0.0
    strength: float = 0.0
    stability: float = 0.0
    trust: float = 0.0
    visibility: Visibility = Visibility.private


@dataclass
class Emotion:
    bond_id: str = ""
    type: EmotionType = EmotionType.joy
    intensity: float = 0.0
    decay_rate: float = 0.1
    trigger_event_id: str = ""
    residue: float = 0.0
    peak_intensity: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Event:
    id: str = field(default_factory=lambda: str(uuid4()))
    source_agent_id: str = ""
    target_agent_id: str = ""
    event_type: str = ""
    description: str = ""
    impact_valence: float = 0.0
    impact_trust: float = 0.0
    impact_strength: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
