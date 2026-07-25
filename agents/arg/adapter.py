"""ARC-AGI-3 environment adapter — the ONE env-specific seam (build plan §7, §9).

Everything above this file is Locator-agnostic; only this file knows the world
is a grid game. Reimplements the connected-component geometry proven in
agents/frame_analysis.py (cited in spirit; never imported) so ARG owns its
perception path end to end.

Pinned decisions (build plan §11 blockers):
- canonicalize selects the LAST layer and applies %16 per cell (matches the
  Sensi rendering convention) BEFORE segmentation — layer handling silently
  changes every anchor/ChangeSet/signature, so it is pinned here.
- component_hash = sha1(color + "|" + sorted cells)[:12]  (position-inclusive)
- signature      = shape_hash(color, shape)               (translation-invariant)
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

Grid = list  # list[list[int]] indexed grid[row][col]

# ARC-AGI-3 fixed action vocabulary (opaque symbols; meaning is LEARNED per game)
SIMPLE_ACTIONS = ["ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5", "ACTION7"]
COMPLEX_ACTIONS = ["ACTION6"]  # (x,y)


def shape_hash(color: int, shape: frozenset) -> str:
    """Translation-invariant signature: sha1 of color + bbox-normalized offsets."""
    payload = str(color) + "|" + ";".join(f"{x},{y}" for x, y in sorted(shape))
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def component_hash(color: int, cells: frozenset) -> str:
    """Position-inclusive identity of a single observed component this frame."""
    payload = str(color) + "|" + ";".join(f"{x},{y}" for x, y in sorted(cells))
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


@dataclass
class Component:
    color: int
    cells: frozenset            # frozenset[(col,row)]
    bbox: tuple                 # (x0,y0,x1,y1) inclusive
    centroid: tuple             # (col,row) rounded
    size: int
    shape: frozenset = field(repr=False, default=frozenset())  # normalized offsets

    @property
    def signature(self) -> str:
        return shape_hash(self.color, self.shape)

    @property
    def chash(self) -> str:
        return component_hash(self.color, self.cells)

    def public(self) -> dict:
        return {"color": self.color, "size": self.size, "bbox": list(self.bbox),
                "centroid": list(self.centroid), "cells": sorted(self.cells),
                "signature": self.signature, "component_hash": self.chash}


@dataclass
class ChangeSet:
    cells_changed: int
    changed_components: list          # components present in curr overlapping changed cells
    vanished_components: list         # components in prev overlapping changed cells
    raw: dict = field(default_factory=dict)


class ARCAdapter:
    """Grid-game instantiation of the ARG adapter interface."""

    def canonicalize(self, frame: Any) -> Grid:
        """FrameData.frame (list of int-grids / layers) → one 2D grid.
        Selects the last layer and applies %16 (rendering convention)."""
        if not frame:
            return []
        layer = frame[-1] if isinstance(frame[0], list) and frame and isinstance(frame[0][0], list) else frame
        # `frame` may be [layer] or a bare grid; normalize both to a 2D grid
        if layer and isinstance(layer[0], list):
            grid = layer
        else:
            grid = frame
        return [[int(c) % 16 for c in row] for row in grid]

    def segment(self, grid: Grid) -> list:
        """4-connected same-color components over ALL cells. Salience-blind:
        a 3-cell plate and a 400-cell wall come out of the same code path."""
        h = len(grid)
        w = len(grid[0]) if h else 0
        seen = bytearray(w * h)
        comps: list = []
        for sy in range(h):
            for sx in range(w):
                if seen[sy * w + sx]:
                    continue
                color = grid[sy][sx]
                q = deque([(sx, sy)])
                seen[sy * w + sx] = 1
                cells = []
                while q:
                    x, y = q.popleft()
                    cells.append((x, y))
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] \
                                and grid[ny][nx] == color:
                            seen[ny * w + nx] = 1
                            q.append((nx, ny))
                xs = [c[0] for c in cells]
                ys = [c[1] for c in cells]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                n = len(cells)
                comps.append(Component(
                    color=color, cells=frozenset(cells), bbox=(x0, y0, x1, y1),
                    centroid=(round(sum(xs) / n), round(sum(ys) / n)), size=n,
                    shape=frozenset((x - x0, y - y0) for x, y in cells)))
        comps.sort(key=lambda c: (-c.size, c.color, c.bbox[1], c.bbox[0]))
        return comps

    def locate(self, grid: Grid) -> list:
        """CanonicalState → GridRegion locators (== segmented components)."""
        return self.segment(grid)

    def diff(self, prev: Optional[Grid], curr: Grid) -> ChangeSet:
        """Cell-level diff → the components touching changed cells."""
        curr_comps = self.segment(curr)
        if prev is None:
            return ChangeSet(cells_changed=sum(len(r) for r in curr),
                             changed_components=curr_comps, vanished_components=[],
                             raw={"first_frame": True})
        h = min(len(prev), len(curr))
        changed = set()
        for y in range(h):
            pw = len(prev[y]); cw = len(curr[y])
            for x in range(max(pw, cw)):
                pv = prev[y][x] if x < pw else None
                cv = curr[y][x] if x < cw else None
                if pv != cv:
                    changed.add((x, y))
        prev_comps = self.segment(prev)
        touched = [c for c in curr_comps if c.cells & changed]
        vanished = [c for c in prev_comps if c.cells & changed and c.cells not in
                    {cc.cells for cc in curr_comps}]
        return ChangeSet(cells_changed=len(changed), changed_components=touched,
                         vanished_components=vanished,
                         raw={"changed_cells": sorted(changed)[:512]})

    def signal_channels(self) -> dict:
        """Static verified signal vocabulary + observed transition shapes.
        An achievement test referencing a non-member is gate-2 inadmissible."""
        return {
            "score": {"range": [0, 254], "monotone": "up"},
            "levels_completed": {"range": [0, 64], "monotone": "up"},
            "state": {"values": ["NOT_FINISHED", "WIN", "GAME_OVER", "NOT_STARTED"]},
            "lives": {"range": [0, 64], "monotone": "down_or_reset"},
        }

    def action_vocab(self) -> list:
        """Fixed ARC action vocabulary as ActionSlots (opaque symbols)."""
        slots = [{"action": a, "action_id": int(a[-1]), "param_schema": {}}
                 for a in SIMPLE_ACTIONS]
        slots.append({"action": "ACTION6", "action_id": 6,
                      "param_schema": {"x": [0, 63], "y": [0, 63]}})
        return slots

    def tools(self) -> list:
        """Tool descriptors (cold-start delta 3): the seam above which no
        action name is string-matched. side='actuate' commands the game;
        targeted=True means the tool takes an aim parameter (its param_schema)
        and is realized under R8 containment. The GET side (observe) is frame
        ingestion — one descriptor so organs can be told the whole interface."""
        out = [{"name": s["action"], "side": "actuate",
                "targeted": bool(s.get("param_schema")),
                "param_schema": s.get("param_schema") or {}}
               for s in self.action_vocab()]
        out.append({"name": "OBSERVE", "side": "observe", "targeted": False,
                    "param_schema": {}})
        return out

    def targeted_actions(self) -> set:
        """Names of actuate-side tools that take an aim parameter."""
        return {t["name"] for t in self.tools()
                if t["side"] == "actuate" and t["targeted"]}
