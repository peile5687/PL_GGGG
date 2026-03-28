from __future__ import annotations

import json
import random
from collections import defaultdict

from simulator.agents import AgentContext, BaseAgent
from simulator.models import Action, CharacterState, GameResult, RoundLog


class GameEngine:
    def __init__(self, rules_path: str):
        with open(rules_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)
        self.max_rounds = self.rules["meta"]["max_rounds"]
        self.base_damage = int(self.rules["hit_formula"]["base_damage"])
        self.action_priority = {"defend": 0, "assist": 1, "skill": 2, "attack": 3}

    def init_state(self) -> dict[str, CharacterState]:
        state: dict[str, CharacterState] = {}
        for key, cfg in self.rules["characters"].items():
            skills = cfg["skills"]
            uses = {s: self.rules["skills"][s]["uses"] for s in skills}
            cds = {s: 0 for s in skills}
            state[key] = CharacterState(
                key=key,
                name=cfg["name"],
                faction=cfg["faction"],
                max_hp=cfg["hp"],
                hp=cfg["hp"],
                atk=cfg["atk"],
                eva=cfg["eva"],
                skills=skills,
                cooldowns=cds,
                uses_left=uses,
            )
        return state

    def run_game(self, agents: dict[str, BaseAgent], seed: int | None = None, log: bool = False) -> GameResult:
        rng = random.Random(seed)
        state = self.init_state()
        logs: list[RoundLog] = []

        for round_no in range(1, self.max_rounds + 1):
            rlog = RoundLog(round_no=round_no)
            actions = self._collect_actions(state, agents, rng, round_no)
            self._resolve_actions(state, actions, rng, rlog)
            self._decrement_cooldowns(state)
            self._clear_temp_mods(state)

            winner = self._check_winner(state)
            if log:
                logs.append(rlog)
            if winner:
                return GameResult(
                    winner=winner,
                    rounds_played=round_no,
                    logs=logs,
                    surviving_hp={k: v.hp for k, v in state.items()},
                )

        return GameResult(
            winner="villains",
            rounds_played=self.max_rounds,
            logs=logs,
            surviving_hp={k: v.hp for k, v in state.items()},
        )

    def _collect_actions(
        self,
        state: dict[str, CharacterState],
        agents: dict[str, BaseAgent],
        rng: random.Random,
        round_no: int,
    ) -> list[Action]:
        actions: list[Action] = []
        for key, actor in state.items():
            if actor.is_ko:
                continue
            allies = [c for c in state.values() if c.faction == actor.faction and c.key != actor.key]
            enemies = [c for c in state.values() if c.faction != actor.faction]
            ctx = AgentContext(actor=actor, allies=allies, enemies=enemies, round_no=round_no)
            agent = agents[key]
            chosen = agent.choose_action(ctx, rng)
            actions.append(self._sanitize_action(chosen, actor, state))
        return actions

    def _sanitize_action(self, action: Action, actor: CharacterState, state: dict[str, CharacterState]) -> Action:
        legal_types = {"attack", "defend", "assist", "skill"}
        action_type = action.action_type if action.action_type in legal_types else "attack"

        if action_type == "skill":
            skill = action.skill
            if not skill or skill not in actor.skills:
                action_type = "attack"
                skill = None
            else:
                return Action(actor=actor.key, action_type="skill", target=action.target, skill=skill)

        if action_type == "defend":
            return Action(actor=actor.key, action_type="defend", target=actor.key)

        if action_type == "assist":
            ally = action.target if action.target in state and state[action.target].faction == actor.faction else actor.key
            return Action(actor=actor.key, action_type="assist", target=ally)

        target = action.target if action.target in state else self._default_enemy_target(actor, state)
        return Action(actor=actor.key, action_type="attack", target=target)

    @staticmethod
    def _default_enemy_target(actor: CharacterState, state: dict[str, CharacterState]) -> str | None:
        for c in state.values():
            if c.faction != actor.faction and not c.is_ko:
                return c.key
        return None

    def _resolve_actions(
        self,
        state: dict[str, CharacterState],
        actions: list[Action],
        rng: random.Random,
        rlog: RoundLog,
    ) -> None:
        actions.sort(key=lambda a: self.action_priority.get(a.action_type, 3))

        # Simultaneous intent model: if actor was alive at collection time,
        # its action is still resolved this round even if KO later in the same round.
        for action in actions:
            actor = state.get(action.actor)
            if not actor:
                continue

            if action.action_type == "defend":
                actor.shield += 1
                rlog.entries.append(f"{actor.key} defends and gains 1 shield")
                continue

            if action.action_type == "assist":
                target = state.get(action.target or "")
                if target and not target.is_ko and target.faction == actor.faction:
                    target.atk_mod += 1
                    rlog.entries.append(f"{actor.key} assists {target.key} (+1 atk this round)")
                continue

            if action.action_type == "skill" and action.skill:
                self._resolve_skill(state, actor, action, rng, rlog)
                continue

            if action.action_type == "attack":
                target = state.get(action.target or "")
                if target and not target.is_ko:
                    self._apply_hit(actor, target, rng, self.base_damage, 0, rlog)

    def _resolve_skill(
        self,
        state: dict[str, CharacterState],
        actor: CharacterState,
        action: Action,
        rng: random.Random,
        rlog: RoundLog,
    ) -> None:
        skill = action.skill
        if skill not in actor.skills:
            return
        if actor.cooldowns.get(skill, 0) > 0 or actor.uses_left.get(skill, 0) <= 0:
            return

        cfg = self.rules["skills"][skill]
        effect = cfg["effect"]
        value = int(cfg["value"])
        target = state.get(action.target or "")

        if effect == "single_hit_plus_damage" and target and not target.is_ko:
            self._apply_hit(actor, target, rng, self.base_damage + value, 0, rlog)
        elif effect == "single_hit_plus_hit" and target and not target.is_ko:
            self._apply_hit(actor, target, rng, self.base_damage, value, rlog)
        elif effect == "gain_shield":
            who = target if target and target.faction == actor.faction else actor
            who.shield += value
            rlog.entries.append(f"{actor.key} uses {skill}: {who.key} gains {value} shield")
        elif effect == "heal_ally":
            who = target if target and target.faction == actor.faction and not target.is_ko else actor
            who.hp = min(who.max_hp, who.hp + value)
            if who.hp > 0:
                who.is_ko = False
            rlog.entries.append(f"{actor.key} uses {skill}: heals {who.key} for {value}")
        elif effect == "team_atk_buff":
            for c in state.values():
                if c.faction == actor.faction and not c.is_ko:
                    c.atk_mod += value
            rlog.entries.append(f"{actor.key} uses {skill}: team atk +{value}")
        elif effect == "enemy_atk_debuff":
            for c in state.values():
                if c.faction != actor.faction and not c.is_ko:
                    c.atk_mod -= value
            rlog.entries.append(f"{actor.key} uses {skill}: enemies atk -{value}")
        elif effect == "enemy_eva_debuff":
            if target and target.faction != actor.faction and not target.is_ko:
                target.eva_mod -= value
                rlog.entries.append(f"{actor.key} uses {skill}: {target.key} eva -{value}")
        elif effect == "intercept_for_boss":
            boss = state.get("boss")
            if boss and not boss.is_ko:
                boss.shield += value
                rlog.entries.append(f"{actor.key} uses {skill}: boss gains {value} shield")

        actor.uses_left[skill] = actor.uses_left.get(skill, 0) - 1
        actor.cooldowns[skill] = int(cfg["cooldown"])

    @staticmethod
    def _apply_hit(
        actor: CharacterState,
        target: CharacterState,
        rng: random.Random,
        dmg: int,
        hit_bonus: int,
        rlog: RoundLog,
    ) -> None:
        roll = rng.randint(1, 6)
        attack_val = actor.atk + actor.atk_mod + hit_bonus
        evade_val = target.eva + target.eva_mod
        hit = (roll + attack_val) >= (evade_val + 4)

        if not hit:
            rlog.entries.append(f"{actor.key} attacks {target.key}: miss (roll={roll})")
            return

        damage = max(0, dmg)
        if target.shield > 0:
            blocked = min(target.shield, damage)
            target.shield -= blocked
            damage -= blocked

        if damage > 0:
            target.hp -= damage
            if target.hp <= 0:
                target.hp = 0
                target.is_ko = True

        rlog.entries.append(
            f"{actor.key} attacks {target.key}: hit (roll={roll}), damage={damage}, target_hp={target.hp}"
        )

    @staticmethod
    def _decrement_cooldowns(state: dict[str, CharacterState]) -> None:
        for c in state.values():
            for s, cd in list(c.cooldowns.items()):
                if cd > 0:
                    c.cooldowns[s] = cd - 1

    @staticmethod
    def _clear_temp_mods(state: dict[str, CharacterState]) -> None:
        for c in state.values():
            c.atk_mod = 0
            c.eva_mod = 0

    @staticmethod
    def _check_winner(state: dict[str, CharacterState]) -> str | None:
        heroes = [state[k] for k in ["hero_a", "hero_b", "hero_c"]]
        villains = [state[k] for k in ["boss", "minion"]]

        if all(c.is_ko for c in heroes):
            return "villains"
        if state["boss"].is_ko or all(c.is_ko for c in villains):
            return "heroes"
        return None


def simulate_many(engine: GameEngine, agents: dict[str, BaseAgent], games: int, seed: int = 42) -> dict[str, float]:
    rng = random.Random(seed)
    counts = defaultdict(int)
    total_rounds = 0
    for _ in range(games):
        gseed = rng.randint(1, 10**9)
        result = engine.run_game(agents=agents, seed=gseed, log=False)
        counts[result.winner] += 1
        total_rounds += result.rounds_played

    return {
        "games": games,
        "heroes_win_rate": counts["heroes"] / games,
        "villains_win_rate": counts["villains"] / games,
        "avg_rounds": total_rounds / games,
    }
