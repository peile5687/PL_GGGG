from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator.agents import HeuristicAgent, RandomAgent
from simulator.engine import GameEngine, simulate_many
from simulator.minimax_api_player import MiniMaxAPIPlayer


def _build_side_agent(mode: str):
    if mode == "random":
        return RandomAgent()
    if mode == "heuristic":
        return HeuristicAgent()
    if mode == "minimax_api":
        return MiniMaxAPIPlayer()
    raise ValueError(f"Unsupported mode: {mode}")


def build_agents(hero_mode: str, villain_mode: str):
    hero = _build_side_agent(hero_mode)
    vill = _build_side_agent(villain_mode)
    return {
        "hero_a": hero,
        "hero_b": hero,
        "hero_c": hero,
        "boss": vill,
        "minion": vill,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate 星岚小冒险 3v2 matches")
    parser.add_argument("--rules", default="simulator/rules_v1.json")
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hero-mode", choices=["random", "heuristic", "minimax_api"], default="heuristic")
    parser.add_argument("--villain-mode", choices=["random", "heuristic", "minimax_api"], default="heuristic")
    parser.add_argument("--single", action="store_true", help="Run single game with logs")
    args = parser.parse_args()

    engine = GameEngine(args.rules)
    agents = build_agents(args.hero_mode, args.villain_mode)

    if args.single:
        result = engine.run_game(agents=agents, seed=args.seed, log=True)
        print(f"winner={result.winner}, rounds={result.rounds_played}")
        for round_log in result.logs:
            print(f"\n[Round {round_log.round_no}]")
            for line in round_log.entries:
                print("-", line)
        print("\nfinal_hp=", result.surviving_hp)
        return

    stats = simulate_many(engine=engine, agents=agents, games=args.games, seed=args.seed)
    print(
        json.dumps(
            {
                "hero_mode": args.hero_mode,
                "villain_mode": args.villain_mode,
                **stats,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
