# Game

一款桌游。

## 仓库新增：3v2 对抗规则模拟器（原型）

本仓库包含一个 Python 模拟器，用于验证 5 人局（3 好人 vs Boss+手下）规则在随机与策略条件下的胜率。

### 目录

- `simulator/rules_v1.json`：规则参数（角色、技能、判定公式、回合上限）。
- `simulator/engine.py`：回合引擎与结算逻辑（含动作合法化与同回合同步意图结算）。
- `simulator/agents.py`：本地策略代理（随机、启发式）。
- `simulator/minimax_api_player.py`：MiniMax API 代理（可选，读取环境变量）。
- `simulator/run_sim.py`：命令行入口（可分别设置好人和坏人代理）。

### 快速开始

```bash
python simulator/run_sim.py --games 500 --hero-mode heuristic --villain-mode heuristic
```

输出示例：

```json
{
  "hero_mode": "heuristic",
  "villain_mode": "heuristic",
  "games": 500,
  "heroes_win_rate": 0.44,
  "villains_win_rate": 0.56,
  "avg_rounds": 6.2
}
```

### 非对称对局

```bash
python simulator/run_sim.py --games 1000 --hero-mode heuristic --villain-mode random
python simulator/run_sim.py --games 1000 --hero-mode random --villain-mode heuristic
```

### 单局日志

```bash
python simulator/run_sim.py --single --hero-mode heuristic --villain-mode heuristic --seed 7
```

### 接入 MiniMax API

1. 设置环境变量（不要把 key 写入代码）：

```bash
export MINIMAX_API_KEY="<your_key>"
# 可选：自定义 API 地址
export MINIMAX_API_BASE="https://api.minimaxi.com/v1/text/chatcompletion_v2"
```

2. 运行（示例：让坏人侧使用 API 决策）：

```bash
python simulator/run_sim.py --games 100 --hero-mode heuristic --villain-mode minimax_api
```

若 API 不可用或返回格式不匹配，代理会自动回退到本地随机动作，保证模拟不中断。
