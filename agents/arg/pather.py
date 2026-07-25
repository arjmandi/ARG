"""NAVIGATE bootstrap (build plan §11 blocker, M6).

Routing is deterministic and solved (a route delivered Sensi to the winning
referent at t10, 8× faster than frontier reasoning) — but only AFTER an action
model is learned. This module learns dx/dy/quantum per action from the
consequences of movement-correlated ("controllable") referents, then routes. A
NAVIGATE step is inadmissible until the model has support; until then the query
walk falls back to the cheapest Z4 probe.
"""

from __future__ import annotations

from math import gcd
from typing import Optional


def _single_mover_delta(adapter, prev_grid: list, curr_grid: list) -> Optional[tuple]:
    """The consistent (dx,dy) of the one component that kept its signature but
    shifted — the controllable-referent self-diff. Returns ((dx,dy), mover_sig)
    or None if ambiguous/absent."""
    if not prev_grid or not curr_grid:
        return None
    prev = adapter.segment(prev_grid)
    curr = adapter.segment(curr_grid)
    by_sig_prev: dict = {}
    for c in prev:
        by_sig_prev.setdefault(c.signature, []).append(c)
    deltas: dict = {}
    for c in curr:
        cands = by_sig_prev.get(c.signature, [])
        if len(cands) == 1:
            p = cands[0]
            dx = c.centroid[0] - p.centroid[0]
            dy = c.centroid[1] - p.centroid[1]
            if (dx, dy) != (0, 0):
                deltas[(dx, dy)] = c.signature
    if len(deltas) == 1:
        d, sig = next(iter(deltas.items()))
        return d, sig
    return None


def learn_action_model(store, run_id: str, adapter, action: str, prev_grid: list,
                       curr_grid: list, turn_id: int,
                       targeted: Optional[set] = None) -> Optional[tuple]:
    """Record a single-mover (dx,dy) for `action` if this beat produced one.
    The mover's signature is stored so `controllable` can be EARNED from
    movement-correlated receipts (§2.2). Returns ((dx,dy), mover_sig) or None.
    Targeted tools carry no intrinsic displacement — excluded via the tool
    descriptors (never by string-matching action names); RESET is protocol."""
    if targeted is None:
        targeted = adapter.targeted_actions() if hasattr(adapter, "targeted_actions") else set()
    if action == "RESET" or action in targeted:
        return None
    hit = _single_mover_delta(adapter, prev_grid, curr_grid)
    if hit is None:
        return None
    (dx, dy), sig = hit
    q = gcd(abs(dx), abs(dy)) or max(abs(dx), abs(dy)) or 1
    seq = store.next_seq(run_id, "action_model")
    store.conn.execute(
        "INSERT INTO action_model (run_id, seq, turn_id, action, dx, dy, quantum, support, "
        "mover_sig) VALUES (?,?,?,?,?,?,?,1,?)", (run_id, seq, turn_id, action, dx, dy, q, sig))
    return (dx, dy), sig


def action_deltas(store, run_id: str, min_support: int = 1) -> dict:
    """Current learned {action: (dx,dy,quantum)} — the modal observed delta per
    action, requiring ≥ min_support corroborating observations."""
    rows = store.conn.execute(
        "SELECT action, dx, dy, quantum, COUNT(*) n FROM action_model WHERE run_id=? "
        "GROUP BY action, dx, dy ORDER BY action, n DESC", (run_id,)).fetchall()
    best: dict = {}
    for r in rows:
        if r["action"] not in best and r["n"] >= min_support:
            best[r["action"]] = (r["dx"], r["dy"], r["quantum"])
    return best


def quantum(deltas: dict) -> int:
    mags = [abs(v) for d in deltas.values() for v in (d[0], d[1]) if v]
    q = 0
    for m in mags:
        q = gcd(q, m)
    return q or 1


def route(deltas: dict, mover_centroid: tuple, target_bbox: tuple,
          max_steps: int = 64, adjacent_ok: bool = True) -> Optional[list]:
    """BFS in learned-delta steps from the mover centroid to (inside, or
    press-against) the target bbox. Returns [action, ...] or None."""
    if not deltas:
        return None
    tx0, ty0, tx1, ty1 = target_bbox
    move_actions = {a: (d[0], d[1]) for a, d in deltas.items() if (d[0], d[1]) != (0, 0)}
    if not move_actions:
        return None
    start = (round(mover_centroid[0]), round(mover_centroid[1]))
    from collections import deque
    seen = {start}
    q = deque([(start, [])])
    while q:
        (x, y), path = q.popleft()
        if len(path) > max_steps:
            continue
        inside = tx0 <= x <= tx1 and ty0 <= y <= ty1
        adjacent = adjacent_ok and (tx0 - 1 <= x <= tx1 + 1 and ty0 - 1 <= y <= ty1 + 1)
        if inside or (adjacent and not (tx0 <= x <= tx1 and ty0 <= y <= ty1) and path):
            return path
        for a, (dx, dy) in sorted(move_actions.items()):
            nx, ny = x + dx, y + dy
            if (nx, ny) not in seen and 0 <= nx < 64 and 0 <= ny < 64:
                seen.add((nx, ny))
                q.append(((nx, ny), path + [a]))
    return None
