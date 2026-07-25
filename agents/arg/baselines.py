"""§8 comparator agents — the PINNED baseline protocols (compute-parity rule).

BARE ("argbare"): a fixed minimal context template — current frame render (hex
rows) + score/state/lives header + the last-L action→outcome lines + the task
instruction — with EXACTLY ONE LLM call per emitted action. RAW ("argraw"):
the same template + cadence + budget, plus the full untyped interaction
history. Neither touches any ARG structure; both log to the write-separate
probe store (api_log + llm_calls) so parity rows (ρ_calls, ρ_tokens) come from
the same accounting as every other arm.
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Any, Optional

from requests import Response

from ..agent import Agent
from ..structs import FrameData, GameAction, GameState
from . import config, organs
from .probe_db import ProbeStore

logger = logging.getLogger()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _hex_grid(frame) -> str:
    if not frame:
        return "(no frame)"
    layer = frame[-1] if isinstance(frame[0], list) and frame and isinstance(frame[0][0], list) else frame
    grid = layer if (layer and isinstance(layer[0], list)) else frame
    return "\n".join("".join(format(int(c) % 16, "x") for c in row) for row in grid)


class BARE(Agent):
    """Pinned bare-backbone comparator (§8): one call per action, fixed
    minimal template, no structure, no memory beyond the last-L lines."""

    MAX_ACTIONS = config.MAX_ACTIONS
    HISTORY = False          # RAW flips this

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.turn_id = -1
        self._probe: Optional[ProbeStore] = None
        self._run_id = f"{'argraw' if self.HISTORY else 'argbare'}-{self.game_id}-{int(time.time())}"
        self._tail: list = []      # last-L action→outcome lines
        self._history: list = []   # full untyped history (RAW only)
        self._llm_ready = False

    def is_won(self, frames: list, latest_frame: FrameData) -> bool:
        return latest_frame.state == GameState.WIN

    def choose_action(self, frames: list, latest_frame: FrameData) -> GameAction:
        return self._decide(latest_frame)

    def do_action_request(self, action: GameAction) -> Response:
        resp = super().do_action_request(action)
        try:
            body = resp.json()
        except ValueError:
            body = None
        req = dict(action.action_data.model_dump())
        req["game_id"] = self.game_id
        if self._probe is not None:
            self._probe.log_api(self._run_id, max(self.turn_id, 0), 0, action.name,
                                "BASELINE", req, body, getattr(resp, "status_code", None), _now())
        return resp

    def _view(self, latest: FrameData) -> str:
        avail = [a.name for a in latest.available_actions] or ["ACTION1"]
        head = (f"score={latest.score or 0} state={latest.state.name} "
                f"levels={latest.levels_completed or 0}")
        parts = [head, "AVAILABLE: " + ",".join(avail)]
        if self.HISTORY and self._history:
            parts.append("FULL HISTORY:\n" + "\n".join(self._history))
        elif self._tail:
            parts.append("RECENT:\n" + "\n".join(self._tail[-config.L_LOG_TAIL:]))
        parts.append("FRAME (hex colors, row 0 first):\n" + _hex_grid(latest.frame))
        parts.append("Make verified progress: raise score, complete levels, reach WIN.")
        return "\n\n".join(parts)

    def _decide(self, latest: FrameData) -> GameAction:
        avail = {a.name for a in latest.available_actions} or {"ACTION1"}
        view = self._view(latest)
        choice, x, y = sorted(avail)[0], 0, 0
        try:
            if not self._llm_ready:
                organs.configure_llm()
                self._llm_ready = True
            out = organs.run_baseline(view)
            usage = organs.last_usage()
            if self._probe is not None:
                self._probe.log_llm_call(self._run_id, max(self.turn_id, 0), "baseline",
                                         backbone=config.MODEL, call_idx=0, retry_count=0,
                                         prompt_tokens=usage["prompt_tokens"],
                                         completion_tokens=usage["completion_tokens"],
                                         render_tokens=len(view) // 4, ops_accepted=1,
                                         effort=config.REASONING_EFFORT, ts=_now())
            if out["action"] in avail:
                choice, x, y = out["action"], out["x"], out["y"]
        except Exception as e:
            logger.warning(f"baseline decide failed (deterministic fallback): {e}")
        act = GameAction[choice]
        if choice == "ACTION6":
            act.set_data({"x": x, "y": y})
        return act

    def main(self) -> None:
        self.timer = time.time()
        self._probe = ProbeStore(config.PROBE_PATH)
        self._probe.register(self._run_id, card_id=self.card_id, game_id=self.game_id,
                             backbone=config.MODEL, seed=0, config_json="{}",
                             baseline="raw" if self.HISTORY else "bare",
                             arm=",".join(self.tags) if self.tags else "baseline",
                             started_at=_now())
        self.turn_id += 1
        frame = self.take_action(GameAction.RESET)
        if frame is not None:
            self.append_frame(frame)
        while not self.is_won(self.frames, self.frames[-1]) and self.action_counter < self.MAX_ACTIONS:
            latest = self.frames[-1]
            if latest.state in (GameState.GAME_OVER, GameState.NOT_STARTED):
                cmd = GameAction.RESET
            else:
                cmd = self._decide(latest)
            self.turn_id += 1
            nxt = self.take_action(cmd)
            if nxt is not None:
                self.append_frame(nxt)
                outcome = (f"t{self.turn_id} {cmd.name} -> score={nxt.score or 0} "
                           f"levels={nxt.levels_completed or 0} state={nxt.state.name}")
                self._tail.append(outcome)
                self._history.append(outcome)
            self.action_counter += 1
        self._probe.finish(self._run_id, _now())
        self._probe.close()
        self.cleanup()


class RAW(BARE):
    """Raw-history comparator (§8): the anti-rot bracket — same pinned cadence
    and budget as BARE, plus the FULL untyped interaction history."""
    HISTORY = True
