"""
Simple UCB1 Monte Carlo Tree Search agent for Forge decision-making.

Each node in the tree corresponds to (game_state, action_taken).
Rollouts are random (or LLM-guided for top-N nodes when the sidecar is available).

Usage::

    agent = MctsAgent(rollouts_per_action=20)
    chosen_index = agent(options, state)
"""

from __future__ import annotations

import math
import random

from llm_client import generate_text, is_configured, llm_pick as _llm_pick_remote


def _llm_eval(state: dict, player_idx: int, system_prompt: str = "") -> float:
    """
    Ask the LLM to rate the board position for ``player_idx`` (0-10).

    Returns 0.5 (neutral) on any failure so MCTS keeps working without AI.
    When ``system_prompt`` is non-empty it is prepended to give the model
    archetype-specific strategic context before the board description.
    """
    if not is_configured():
        return 0.5
    life = state.get("life", [20, 20])
    battlefield = state.get("battlefield", [])
    board_desc = (
        f"You are evaluating a Magic: The Gathering board state for player {player_idx}.\n"
        f"Life totals: player 0 = {life[0]}, player 1 = {life[1]}.\n"
        f"Battlefield (player {player_idx}): "
        f"{', '.join(battlefield[:10]) or 'empty'}.\n"
        f"Turn: {state.get('turn', 1)}, Phase: {state.get('phase', '?')}.\n\n"
        f"Rate player {player_idx}'s position 0 (losing badly) to 10 (winning easily). "
        "Respond with a single integer only."
    )
    prompt = f"{system_prompt}\n\n{board_desc}" if system_prompt else board_desc
    text = generate_text(prompt, temperature=0.1, max_tokens=20)
    if not text:
        return 0.5
    try:
        score = float(text.split()[0])
        return max(0.0, min(10.0, score)) / 10.0
    except (ValueError, IndexError):
        return 0.5


def llm_pick(
    question: str,
    option_names: list[str],
    state: dict,
    system_prompt: str = "",
) -> tuple[int, str]:
    """
    Ask the LLM to choose one option from a numbered list.

    Used by the interactive game's pilot logic to pick which spell to cast,
    guided by an archetype-specific or deck-notes pilot prompt.

    Returns ``(index, reasoning)`` where ``index`` is 0-based and
    ``reasoning`` is the raw LLM response text.  Falls back to
    ``(0, "")`` on any failure or when AI is not configured.
    """
    return _llm_pick_remote(question, option_names, state, system_prompt)


class _Node:
    """One node in the MCTS tree, representing a candidate action."""

    __slots__ = ("index", "visits", "wins", "children", "parent")

    def __init__(self, index: int, parent: "_Node | None" = None) -> None:
        """Initialise a node for the given action index."""
        self.index: int = index
        self.visits: int = 0
        self.wins: float = 0.0
        self.children: list[_Node] = []
        self.parent: _Node | None = parent

    def ucb1(self, exploration: float = math.sqrt(2)) -> float:
        """Return the UCB1 score used for node selection."""
        if self.visits == 0:
            return float("inf")
        parent_visits = self.parent.visits if self.parent else self.visits
        return (
            self.wins / self.visits
            + exploration * math.sqrt(math.log(parent_visits) / self.visits)
        )

    def win_rate(self) -> float:
        """Return win rate as a fraction, or 0 when unvisited."""
        return self.wins / self.visits if self.visits > 0 else 0.0


class MctsAgent:
    """
    Callable agent that uses UCB1 MCTS to pick an action index.

    For each option it runs ``rollouts_per_action`` simulated rollouts.
    If ``use_llm`` is True the LLM scores the resulting board state.
    """

    def __init__(
        self,
        rollouts_per_action: int = 20,
        use_llm: bool = False,
        player_idx: int = 0,
        pilot_prompt: str = "",
    ) -> None:
        """Initialise the MCTS agent with rollout budget and LLM toggle."""
        self.rollouts_per_action = rollouts_per_action
        self.use_llm = use_llm
        self.player_idx = player_idx
        self.pilot_prompt = pilot_prompt

    def __call__(self, options: list[str], state: dict) -> int:
        """Pick the best action index given the list of option strings."""
        if not options:
            return 0
        if len(options) == 1:
            return 0

        root = _Node(index=-1)
        nodes = [_Node(index=i, parent=root) for i in range(len(options))]
        root.children = nodes

        for _ in range(self.rollouts_per_action * len(options)):
            node = max(nodes, key=lambda n: n.ucb1())
            score = (
                _llm_eval(state, self.player_idx, self.pilot_prompt)
                if self.use_llm
                else random.random()
            )
            node.visits += 1
            node.wins += score
            root.visits += 1

        return max(nodes, key=lambda n: n.visits).index

    def __repr__(self) -> str:
        """Return a human-readable representation of the agent."""
        has_prompt = bool(self.pilot_prompt)
        return (
            f"MctsAgent(rollouts={self.rollouts_per_action}, "
            f"llm={self.use_llm}, player={self.player_idx}, "
            f"pilot={'yes' if has_prompt else 'none'})"
        )


class RandomAgent:
    """Baseline agent that picks a uniformly random action."""

    def __call__(self, options: list[str], state: dict) -> int:
        """Return a random index from the available options."""
        return random.randrange(len(options)) if options else 0

    def __repr__(self) -> str:
        """Return a human-readable representation of the agent."""
        return "RandomAgent()"
