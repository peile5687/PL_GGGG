from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CharacterState:
    key: str
    name: str
    faction: str
    max_hp: int
    hp: int
    atk: int
    eva: int
    skills: list[str]
    shield: int = 0
    atk_mod: int = 0
    eva_mod: int = 0
    is_ko: bool = False
    cooldowns: dict[str, int] = field(default_factory=dict)
    uses_left: dict[str, int] = field(default_factory=dict)


@dataclass
class Action:
    actor: str
    action_type: str
    target: str | None = None
    skill: str | None = None


@dataclass
class RoundLog:
    round_no: int
    entries: list[str] = field(default_factory=list)


@dataclass
class GameResult:
    winner: str
    rounds_played: int
    logs: list[RoundLog]
    surviving_hp: dict[str, int]


@dataclass
class SkillDef:
    name: str
    type: str
    cooldown: int
    effect: str
    value: int
    uses: int


@dataclass
class RuleSet:
    raw: dict[str, Any]
