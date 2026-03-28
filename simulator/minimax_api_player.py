from __future__ import annotations

import json
import os
import random
import urllib.error
import urllib.request

from simulator.agents import AgentContext, BaseAgent
from simulator.models import Action


class MiniMaxAPIPlayer(BaseAgent):
    """API-backed agent. Falls back to random legal actions on errors."""

    def __init__(self, model: str = "MiniMax-M1", api_base: str | None = None, timeout: int = 10):
        self.model = model
        self.api_key = os.getenv("MINIMAX_API_KEY", "")
        self.api_base = api_base or os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com/v1/text/chatcompletion_v2")
        self.timeout = timeout

    def choose_action(self, ctx: AgentContext, rng: random.Random) -> Action:
        if not self.api_key:
            return self._fallback(ctx, rng)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是桌游战斗AI。仅返回JSON，字段: action_type, target, skill(可空)。",
                },
                {
                    "role": "user",
                    "content": self._build_prompt(ctx),
                },
            ],
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            self.api_base,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = self._extract_content(data)
            parsed = json.loads(content)
            action_type = parsed.get("action_type", "attack")
            return Action(
                actor=ctx.actor.key,
                action_type=action_type,
                target=parsed.get("target"),
                skill=parsed.get("skill"),
            )
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, ValueError):
            return self._fallback(ctx, rng)

    def _build_prompt(self, ctx: AgentContext) -> str:
        actor = ctx.actor
        allies = [{"key": a.key, "hp": a.hp, "ko": a.is_ko} for a in ctx.allies]
        enemies = [{"key": e.key, "hp": e.hp, "ko": e.is_ko} for e in ctx.enemies]
        return json.dumps(
            {
                "round": ctx.round_no,
                "actor": actor.key,
                "hp": actor.hp,
                "skills": actor.skills,
                "cooldowns": actor.cooldowns,
                "uses_left": actor.uses_left,
                "allies": allies,
                "enemies": enemies,
                "legal_action_types": ["attack", "defend", "assist", "skill"],
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _extract_content(data: dict) -> str:
        # Compatible with several response shapes.
        if "choices" in data and data["choices"]:
            msg = data["choices"][0].get("message", {})
            if isinstance(msg, dict) and "content" in msg:
                return msg["content"]
        if "reply" in data:
            return data["reply"]
        raise KeyError("No supported response content")

    @staticmethod
    def _fallback(ctx: AgentContext, rng: random.Random) -> Action:
        enemies = [e.key for e in ctx.enemies if not e.is_ko]
        if not enemies:
            return Action(actor=ctx.actor.key, action_type="defend", target=ctx.actor.key)
        return Action(actor=ctx.actor.key, action_type="attack", target=rng.choice(enemies))
