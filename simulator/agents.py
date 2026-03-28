from __future__ import annotations

import random
from dataclasses import dataclass

from simulator.models import Action, CharacterState


@dataclass
class AgentContext:
    actor: CharacterState
    allies: list[CharacterState]
    enemies: list[CharacterState]
    round_no: int


class BaseAgent:
    def choose_action(self, ctx: AgentContext, rng: random.Random) -> Action:
        raise NotImplementedError


class RandomAgent(BaseAgent):
    """Simple baseline agent using random legal-ish choices."""

    def choose_action(self, ctx: AgentContext, rng: random.Random) -> Action:
        available = ["attack", "defend", "assist"]
        usable_skills = [
            s
            for s in ctx.actor.skills
            if ctx.actor.cooldowns.get(s, 0) == 0 and ctx.actor.uses_left.get(s, 0) > 0
        ]
        if usable_skills:
            available.append("skill")

        action_type = rng.choice(available)

        if action_type == "defend":
            return Action(actor=ctx.actor.key, action_type="defend", target=ctx.actor.key)

        if action_type == "assist":
            target = rng.choice([a.key for a in ctx.allies if not a.is_ko] or [ctx.actor.key])
            return Action(actor=ctx.actor.key, action_type="assist", target=target)

        live_enemies = [e.key for e in ctx.enemies if not e.is_ko]
        if not live_enemies:
            return Action(actor=ctx.actor.key, action_type="defend", target=ctx.actor.key)

        if action_type == "attack":
            return Action(actor=ctx.actor.key, action_type="attack", target=rng.choice(live_enemies))

        skill = rng.choice(usable_skills)
        skill_name = skill.lower()
        if "heal" in skill_name or "rescue" in skill_name or "banner" in skill_name:
            target = rng.choice([a.key for a in ctx.allies if not a.is_ko] or [ctx.actor.key])
        elif "shield" in skill_name:
            target = ctx.actor.key
        else:
            target = rng.choice(live_enemies)

        return Action(actor=ctx.actor.key, action_type="skill", target=target, skill=skill)


class HeuristicAgent(BaseAgent):
    """Greedy tactical agent for stronger baseline."""

    def choose_action(self, ctx: AgentContext, rng: random.Random) -> Action:
        actor = ctx.actor
        live_enemies = [e for e in ctx.enemies if not e.is_ko]
        live_allies = [a for a in ctx.allies if not a.is_ko]

        if not live_enemies:
            return Action(actor=actor.key, action_type="defend", target=actor.key)

        # Save ally if possible.
        rescue_skills = [s for s in actor.skills if "rescue" in s or "heal" in s]
        critical_ally = next((a for a in live_allies if a.hp <= 2), None)
        for skill in rescue_skills:
            if actor.cooldowns.get(skill, 0) == 0 and actor.uses_left.get(skill, 0) > 0 and critical_ally:
                return Action(actor=actor.key, action_type="skill", target=critical_ally.key, skill=skill)

        # Offensive skill if available.
        offensive_skills = [
            s
            for s in actor.skills
            if any(k in s for k in ["strike", "blow", "cleave", "shot", "mark"])
            and actor.cooldowns.get(s, 0) == 0
            and actor.uses_left.get(s, 0) > 0
        ]
        if offensive_skills:
            target = min(live_enemies, key=lambda x: x.hp)
            return Action(actor=actor.key, action_type="skill", target=target.key, skill=offensive_skills[0])

        # Focus low hp target.
        target = min(live_enemies, key=lambda x: x.hp)
        return Action(actor=actor.key, action_type="attack", target=target.key)
