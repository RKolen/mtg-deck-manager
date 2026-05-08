"""
ForgeAdapter — manages the Forge headless subprocess and socket protocol.

When FORGE_JAR, FORGE_HOST, and FORGE_PORT are all set the adapter launches
Forge and routes decisions through the socket. Otherwise it runs in mock mode,
returning plausible random game outcomes for testing the statistics pipeline.

Socket protocol (newline-delimited JSON, $FORGE_HOST:$FORGE_PORT):
  Forge -> Python  {"type":"choose_ability","game_id":"X","player":0,...}
  Python -> Forge  {"type":"choice","game_id":"X","index":2}

Required environment variables (all must be set to enable real Forge mode):
  FORGE_JAR    - Absolute path to the built forge-ai JAR
  FORGE_HOST   - Hostname of the Forge socket server (e.g. localhost)
  FORGE_PORT   - Port of the Forge socket server (e.g. 9876)
"""

from __future__ import annotations

import json
import logging
import os
import random
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Protocol, cast

logger = logging.getLogger(__name__)


class _SocketFile(Protocol):
    """Structural protocol for the binary file-like object returned by socket.makefile."""

    def write(self, buffer: bytes, /) -> int:
        """Write bytes to the socket stream."""
        raise NotImplementedError

    def flush(self) -> None:
        """Flush the write buffer."""

    def readline(self) -> bytes:
        """Read one line of bytes from the socket stream."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the stream."""


FORGE_JAR: str = os.environ.get("FORGE_JAR", "")
FORGE_HOST: str = os.environ.get("FORGE_HOST", "")
FORGE_PORT: str = os.environ.get("FORGE_PORT", "")


def _forge_available() -> bool:
    """Return True when all Forge connection env vars are set and the JAR exists."""
    return bool(FORGE_JAR and FORGE_HOST and FORGE_PORT and os.path.isfile(FORGE_JAR))


def _spawn_process(cmd: list[str]) -> "subprocess.Popen[bytes]":
    """
    Start a long-lived subprocess and return the handle to the caller.

    Extracted so that the resource lifetime is owned by ForgeAdapter.close(),
    not by a context manager block.
    """
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


@dataclass
class GameState:
    """Minimal game state snapshot returned by Forge."""

    life: list[int] = field(default_factory=lambda: [20, 20])
    hand_sizes: list[int] = field(default_factory=lambda: [7, 7])
    battlefield: list[str] = field(default_factory=list)
    phase: str = ""
    turn: int = 1
    is_terminal: bool = False
    winner: Optional[int] = None

    @classmethod
    def from_dict(cls, raw: dict) -> "GameState":
        """Construct a GameState from a raw Forge state dict."""
        return cls(
            life=raw.get("life", [20, 20]),
            hand_sizes=raw.get("hand_sizes", [7, 7]),
            battlefield=raw.get("battlefield", []),
            phase=raw.get("phase", ""),
            turn=int(raw.get("turn", 1)),
            is_terminal=bool(raw.get("is_terminal", False)),
            winner=raw.get("winner"),
        )


@dataclass
class SimResult:
    """Outcome of a single simulated game."""

    winner: int
    turns: int
    player_life: int
    opponent_life: int
    key_cards_on_loss: list[str] = field(default_factory=list)

    @property
    def player_won(self) -> bool:
        """Return True when the player (index 0) won."""
        return self.winner == 0


class ForgeAdapter:
    """
    Manages the Forge JAR subprocess (if available) and the socket connection.

    Usage::

        adapter = ForgeAdapter()
        try:
            game_id = adapter.start_game(player_deck, opponent_deck)
            result = adapter.run_game(game_id, agent_player, agent_opponent)
        finally:
            adapter.close()
    """

    def __init__(self, mock: bool = False) -> None:
        """Initialise the adapter, launching Forge when all env vars are set."""
        self._mock: bool = mock or not _forge_available()
        self._proc: Optional["subprocess.Popen[bytes]"] = None
        self._sock: Optional[socket.socket] = None
        self._sock_file: Optional[_SocketFile] = None

        if not self._mock:
            self._launch_forge()
        else:
            logger.info(
                "ForgeAdapter in MOCK mode — set FORGE_JAR, FORGE_HOST, FORGE_PORT to enable Forge."
            )

    @property
    def is_mock(self) -> bool:
        """Return True when running in mock mode (Forge env vars not set)."""
        return self._mock

    def start_game(self, player_deck: list[dict], opponent_deck: list[dict]) -> str:
        """Start a new game and return its game_id."""
        if self._mock:
            return str(uuid.uuid4())
        game_id = str(uuid.uuid4())
        self._send({"type": "start_game", "game_id": game_id,
                    "player_deck": player_deck, "opponent_deck": opponent_deck})
        resp = self._recv()
        if resp.get("type") != "game_started":
            raise RuntimeError(f"Unexpected start_game response: {resp}")
        return game_id

    def run_game(
        self,
        game_id: str,
        player_agent,
        opponent_agent,
        on_the_play: bool = True,
    ) -> SimResult:
        """
        Run a complete game, routing decisions through the provided agents.

        In mock mode returns a plausible random outcome without Forge.
        """
        if self._mock:
            return _mock_game(on_the_play)
        return self._live_game(game_id, player_agent, opponent_agent)

    def close(self) -> None:
        """Shut down the socket connection and Forge subprocess."""
        if self._sock_file is not None:
            try:
                self._sock_file.close()
            except OSError:
                pass
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._proc is not None:
            self._proc.terminate()

    def _live_game(self, game_id: str, player_agent, opponent_agent) -> SimResult:
        """Drive a live Forge game via the socket protocol."""
        agents = [player_agent, opponent_agent]
        turns = 0
        while True:
            msg = self._recv()
            msg_type = msg.get("type", "")
            if msg_type in ("choose_ability", "declare_attackers", "declare_blockers"):
                player_idx = int(msg.get("player", 0))
                options = msg.get("options", ["pass"])
                state = msg.get("state", {})
                index = agents[player_idx](options, state)
                self._send({"type": "choice", "game_id": game_id, "index": index})
                turns = msg.get("state", {}).get("turn", turns)
            elif msg_type == "game_over":
                winner = int(msg.get("winner", 1))
                life = msg.get("life", [0, 20])
                key_cards = msg.get("key_cards_on_loss", [])
                return SimResult(
                    winner=winner,
                    turns=turns,
                    player_life=life[0] if len(life) > 0 else 0,
                    opponent_life=life[1] if len(life) > 1 else 0,
                    key_cards_on_loss=key_cards,
                )
            elif msg_type == "error":
                raise RuntimeError(f"Forge error: {msg.get('message', '?')}")

    def _launch_forge(self) -> None:
        """Launch the Forge JAR subprocess and wait for the socket to open."""
        port = int(FORGE_PORT)
        cmd = ["java", "-jar", FORGE_JAR, "--sim-server", "--port", str(port)]
        self._proc = _spawn_process(cmd)
        logger.info("Launched Forge subprocess (pid %d)", self._proc.pid)
        for _ in range(20):
            time.sleep(0.5)
            try:
                self._connect()
                logger.info("Connected to Forge at %s:%d", FORGE_HOST, port)
                return
            except OSError:
                pass
        raise RuntimeError(f"Could not connect to Forge after 10 s at {FORGE_HOST}:{port}")

    def _connect(self) -> None:
        """Open a socket connection to the Forge server."""
        port = int(FORGE_PORT)
        self._sock = socket.create_connection((FORGE_HOST, port), timeout=5)
        self._sock_file = cast(_SocketFile, self._sock.makefile("rwb"))

    def _send(self, data: dict) -> None:
        """Serialise and write one JSON message to the socket."""
        assert self._sock_file is not None, "_send called before _connect"
        line = (json.dumps(data) + "\n").encode()
        self._sock_file.write(line)
        self._sock_file.flush()

    def _recv(self) -> dict:
        """Read and deserialise one JSON message from the socket."""
        assert self._sock_file is not None, "_recv called before _connect"
        line = self._sock_file.readline()
        if not line:
            raise EOFError("Forge socket closed.")
        return json.loads(line.decode().strip())


def _mock_game(_on_the_play: bool) -> SimResult:
    """
    Return a plausible random game result without running Forge.

    Used to verify the statistics pipeline when the Forge env vars are absent.
    """
    turns = random.randint(3, 8)
    player_wins = random.random() < 0.5
    mock_threats = [
        "Liliana of the Veil", "Tarmogoyf", "Thoughtseize",
        "Lightning Bolt", "Dark Confidant",
    ]
    key_cards = (
        []
        if player_wins
        else random.sample(mock_threats, k=random.randint(1, 3))
    )
    return SimResult(
        winner=0 if player_wins else 1,
        turns=turns,
        player_life=random.randint(1, 20) if player_wins else 0,
        opponent_life=0 if player_wins else random.randint(1, 20),
        key_cards_on_loss=key_cards,
    )
