from __future__ import annotations

import unittest

from simulator.agents import BaseAgent, AgentContext
from simulator.engine import GameEngine
from simulator.models import Action


class ScriptedAgent(BaseAgent):
    def __init__(self, action: Action):
        self.action = action

    def choose_action(self, ctx: AgentContext, rng):
        return self.action


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine("simulator/rules_v1.json")

    def test_invalid_action_is_sanitized_to_attack(self):
        state = self.engine.init_state()
        actor = state["hero_a"]
        action = Action(actor="hero_a", action_type="hack", target="boss")
        sanitized = self.engine._sanitize_action(action, actor, state)
        self.assertEqual(sanitized.action_type, "attack")
        self.assertEqual(sanitized.target, "boss")

    def test_invalid_skill_falls_back_to_attack(self):
        state = self.engine.init_state()
        actor = state["hero_a"]
        action = Action(actor="hero_a", action_type="skill", target="boss", skill="not_a_skill")
        sanitized = self.engine._sanitize_action(action, actor, state)
        self.assertEqual(sanitized.action_type, "attack")

    def test_same_round_actions_still_resolve_after_ko(self):
        agents = {
            "hero_a": ScriptedAgent(Action("hero_a", "attack", target="boss")),
            "hero_b": ScriptedAgent(Action("hero_b", "defend", target="hero_b")),
            "hero_c": ScriptedAgent(Action("hero_c", "defend", target="hero_c")),
            "boss": ScriptedAgent(Action("boss", "attack", target="hero_a")),
            "minion": ScriptedAgent(Action("minion", "defend", target="minion")),
        }
        result = self.engine.run_game(agents=agents, seed=1, log=True)
        # Ensure hero_a had at least one attack entry logged even if KO in the same round later.
        lines = [line for rnd in result.logs for line in rnd.entries]
        self.assertTrue(any("hero_a attacks" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
