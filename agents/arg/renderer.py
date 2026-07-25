"""The serialization contract — Z1–Z6 zones, rules R1–R9 (build plan §6).

The load-bearing surface: the mechanized generalization of the single variable
that flipped Sensi's 0/200 → 3/3. Every deciding call sees a fixed positional
layout, identical across turns/games. The bidirectional join is the crux: one
shared join table materializes, per working-set referent, a single coordinate
string emitted byte-identically into BOTH Z5's inline render annotation (side A)
and Z6's goal-card anchor column (side B), so cross-reference costs zero
long-range attention.

Deterministic Executive code (no LLM). Token accounting uses a pluggable
estimator (char/4) by default; the live path may swap Anthropic count_tokens.
"""

from __future__ import annotations

import json
import math
from typing import Optional

from . import config

RUNG_ORDER = {"ANCHORED": 1, "ENGAGED": 2, "CHARACTERIZED": 3}


def est_tokens(text: str) -> int:
    """Fast char-based token estimate (~4 chars/token). Swap for the backbone's
    real tokenizer in the live R9 enforcement path; the renderer's internal
    budgeting is estimator-agnostic."""
    return math.ceil(len(text) / 4)


class Renderer:
    """Builds the BudgetedView — the only shared state between organs."""

    def __init__(self, store, exec_, run_id: str, adapter) -> None:
        self.store = store
        self.exec = exec_
        self.run_id = run_id
        self.adapter = adapter

    # ---- data gathering ----
    def _current_referents(self) -> list:
        c = self.store.conn
        rows = c.execute(
            "SELECT r.ref_id, r.kind, r.signature, g.cells_json, g.colors_json, g.bbox_x0, "
            "g.bbox_y0, g.bbox_x1, g.bbox_y1 FROM referent r JOIN locator_gridregion g "
            "  ON g.run_id=r.run_id AND g.locator_id=r.anchor_locator_id "
            "WHERE r.run_id=? AND r.version=(SELECT MAX(version) FROM referent r2 "
            "  WHERE r2.run_id=r.run_id AND r2.ref_id=r.ref_id) ORDER BY r.ref_id",
            (self.run_id,)).fetchall()
        dormant = self.exec._dormant_refs()
        out = []
        for row in rows:
            if row["ref_id"] in dormant:
                continue
            cells = json.loads(row["cells_json"])
            n = len(cells) or 1
            cx = round(sum(p[0] for p in cells) / n)
            cy = round(sum(p[1] for p in cells) / n)
            rung = self.exec.current_status("REFERENT_RUNG", row["ref_id"]) or "ANCHORED"
            inter = c.execute(
                "SELECT COUNT(*) n FROM consequence_record WHERE run_id=? AND target_ref=?",
                (self.run_id, row["ref_id"])).fetchone()["n"]
            last = c.execute(
                "SELECT MAX(turn_id) t FROM consequence_record WHERE run_id=? AND target_ref=?",
                (self.run_id, row["ref_id"])).fetchone()["t"]
            label = c.execute(
                "SELECT label FROM referent_alias WHERE run_id=? AND ref_id=? "
                "ORDER BY seq DESC LIMIT 1", (self.run_id, row["ref_id"])).fetchone()
            serves = [r["goal_id"] for r in c.execute(
                "SELECT DISTINCT goal_id FROM goal_binding WHERE run_id=? AND ref_id=?",
                (self.run_id, row["ref_id"]))]
            try:
                color = json.loads(row["colors_json"])[0]
            except (ValueError, TypeError, IndexError):
                color = 0
            out.append({
                "ref_id": row["ref_id"], "kind": row["kind"], "size": n, "color": color,
                "bbox": (row["bbox_x0"], row["bbox_y0"], row["bbox_x1"], row["bbox_y1"]),
                "centroid": (cx, cy), "cells": cells, "rung": rung, "interactions": inter,
                "last_consequence": last, "label": label["label"] if label else None,
                "serves": serves})
        return out

    def _active_chain(self) -> list:
        """Root→leaf active goal chain — the Executive's live rank walk (C2);
        the renderer never re-derives goal order."""
        return self.exec.goal_chain()

    def _active_bound_refs(self, chain: list) -> set:
        if not chain:
            return set()
        c = self.store.conn
        qs = ",".join("?" * len(chain))
        rows = c.execute(
            f"SELECT DISTINCT ref_id FROM goal_binding WHERE run_id=? AND goal_id IN ({qs})",
            (self.run_id, *chain)).fetchall()
        return {r["ref_id"] for r in rows}

    def working_set(self, refs: list, chain: list) -> list:
        """Active-chain bindings (never-evicted, unless ARG_RETAIN=0) ∪ top-(W)
        by mechanical eviction rank: link-to-active-chain, recency-of-consequence,
        grounding rung. Salience-blind: size is not a term (R7/A7)."""
        active = self._active_bound_refs(chain) if config.RETAIN_ON else set()

        def rank_key(r: dict) -> tuple:
            return (0 if r["ref_id"] in active else 1,
                    -(r["last_consequence"] if r["last_consequence"] is not None else -1),
                    -RUNG_ORDER.get(r["rung"], 1), r["ref_id"])
        ordered = sorted(refs, key=rank_key)
        kept = [r for r in ordered if r["ref_id"] in active]
        for r in ordered:
            if len(kept) >= config.W_WORKING_SET:
                break
            if r["ref_id"] not in active:
                kept.append(r)
        return kept[:config.W_WORKING_SET]

    def _coord_string(self, r: dict) -> str:
        """THE shared join string — emitted byte-identically into Z5 and Z6."""
        cx, cy = r["centroid"]
        return f"@r{cy}c{cx}"

    def substitute_mentions(self, text: str) -> str:
        """R2 — no naked mentions: any prose mention of a known alias label is
        rewritten label#R### against the alias table, so every mention carries
        its own ground and distance between mentions becomes irrelevant."""
        if not text:
            return text
        import re
        latest: dict = {}
        for r in self.store.conn.execute(
                "SELECT ref_id, label FROM referent_alias WHERE run_id=? ORDER BY seq",
                (self.run_id,)):
            if r["label"]:
                latest[r["label"]] = r["ref_id"]
        for label in sorted(latest, key=len, reverse=True):
            if "#" in label or not label.strip():
                continue
            text = re.sub(rf"\b{re.escape(label)}\b(?!#)", f"{label}#{latest[label]}", text)
        return text

    # ---- zones ----
    def z1_head(self, head: dict, chain: list, active_step: Optional[str]) -> str:
        lines = [f"turn={head['turn']} level={head['level']} score={head['score']} "
                 f"lives={head.get('lives', '-')}",
                 "GOAL CHAIN: " + " > ".join(chain) if chain else "GOAL CHAIN: (none)",
                 "ACTIVE: " + (self.substitute_mentions(active_step) if active_step
                               else "(no active commitment step)")]
        return "\n".join(lines)

    def z2_roster(self, ws: list, archived: int = 0) -> str:
        if not config.FLAT_ON:
            # A7 ablation: only referents with interactions>0 or bound
            ws = [r for r in ws if r["interactions"] > 0 or r["serves"]]
        head = "ROSTER: id | kind | anchor | rung | interactions | last_consequence | serves"
        rows = []
        for r in ws:
            x0, y0, x1, y1 = r["bbox"]
            anchor = f"r{y0}-{y1}c{x0}-{x1}"
            last = r["last_consequence"] if r["last_consequence"] is not None else "-"
            serves = ",".join(r["serves"]) if r["serves"] else "-"
            rows.append(f"{r['ref_id']} | {r['kind']} | {anchor} | {r['rung']} | "
                        f"{r['interactions']} | {last} | {serves}")
        if archived > 0:
            # §2.4.1 archive index line — silent truncation is a Q11 failure
            rows.append(f"(+{archived} referents archived by eviction rank; "
                        f"recoverable by anchor or id — never by dump)")
        return head + "\n" + "\n".join(rows)

    def z3_rules(self) -> str:
        c = self.store.conn
        rows = c.execute(
            "SELECT r.rule_id, r.template FROM rule r WHERE r.run_id=? "
            "AND r.version=(SELECT MAX(version) FROM rule r2 WHERE r2.run_id=r.run_id "
            "AND r2.rule_id=r.rule_id)", (self.run_id,)).fetchall()
        tested, hyp = [], []
        for row in rows:
            st = self.exec.current_status("RULE", row["rule_id"]) or "HYPOTHESIS"
            if st == "DEMOTED":
                continue
            line = f"{row['rule_id']}: {self.substitute_mentions(row['template'])}"
            scope = self.exec.rule_scope(row["rule_id"])
            if scope != "UNKNOWN":
                line += f" [{scope}]"
            (tested if st == "TESTED" else hyp).append(line if st == "TESTED" else f"[HYP] {line}")
        body = tested[:16] + hyp[:8]
        return "RULES/RELATIONS:\n" + ("\n".join(body) if body else "(none yet)")

    def z4_frontier(self, ws: list, available: list, chain: Optional[list] = None,
                    level: int = 0) -> str:
        """Never-tried pairs IN ACTIVE GOAL SCOPE (§2.5 Z4): targeted pairs are
        (referent × ACTION6) over the working set restricted to the active
        chain's bindings when any exist; global actions (no target semantics)
        render once each and prune once they hold a receipt in the CURRENT
        context class — settled questions are never re-enumerated."""
        c = self.store.conn
        acts = [a for a in available if a != "RESET"]
        rows: list = []
        # global (non-targeted) actions, pruned per current regime
        cur_class = c.execute(
            "SELECT context_class_id FROM context_class WHERE run_id=? AND level_index=? "
            "ORDER BY minted_turn DESC, context_class_id DESC LIMIT 1",
            (self.run_id, level)).fetchone()
        covered = set()
        if cur_class:
            covered = {r["action"] for r in c.execute(
                "SELECT DISTINCT action FROM consequence_record WHERE run_id=? AND "
                "context_class_id=?", (self.run_id, cur_class["context_class_id"]))}
        for a in acts:
            if a != "ACTION6" and a not in covered:
                rows.append(f"{a} (global)")
        # targeted ACTION6 pairs, scoped to active-chain bindings when bound
        if "ACTION6" in acts:
            bound = self._active_bound_refs(chain or [])
            scoped = [r for r in ws if not bound or r["ref_id"] in bound]
            done = {(row["target_ref"], row["action"]) for row in c.execute(
                "SELECT DISTINCT target_ref, action FROM consequence_record WHERE run_id=? "
                "AND action='ACTION6'", (self.run_id,))}
            pairs = [(r["interactions"], r["ref_id"]) for r in scoped
                     if (r["ref_id"], "ACTION6") not in done]
            pairs.sort()
            rows += [f"{rid} × ACTION6" for _, rid in pairs[:20]]
            if len(pairs) > 20:
                rows.append(f"(+{len(pairs) - 20} more pairs by rank)")
        return "UNTOUCHED FRONTIER:\n" + ("\n".join(rows) if rows else "(all explored)")

    def z5_render(self, grid: list, ws: list, compact: bool = False) -> str:
        """The grid render WITH inline joins (JOIN SIDE A) — the model sees the
        WORLD and the join, or there is nothing to join (review S3). Hex rows
        (one digit per cell, rows top-down) + per-working-set-region
        annotations carrying the shared coordinate string and the region's
        true machine-derived color. compact=True is the R6 fallback tier:
        coordinate-only joins, no grid."""
        if not grid:
            return "RENDER: (no frame)"
        h, w = len(grid), len(grid[0]) if grid else 0
        lines = [f"RENDER: {w}x{h} grid (hex colors; row r0 first):"]
        if not compact:
            for row in grid:
                lines.append("".join(format(int(c) % 16, "x") for c in row))
        if config.JOIN_ON:
            lines.append("working-set region joins:")
            for r in ws:
                lines.append(f"  «R:{r['ref_id']} {r['rung']} {self._coord_string(r)}» "
                             f"color={r['color']} size={r['size']}")
        else:
            lines.append("  (joins disabled: ARG_JOIN=0)")
        return "\n".join(lines)

    def z6_goal_card(self, chain: list, ws: list, active_step: Optional[str],
                     predicted_effect: Optional[str], suppress_join: bool = False) -> str:
        c = self.store.conn
        if not chain:
            return "GOAL CARD: (no active goal)"
        leaf = chain[-1]
        g = c.execute(
            "SELECT statement, achievement_test_json FROM goal WHERE run_id=? AND goal_id=? "
            "AND version=(SELECT MAX(version) FROM goal g2 WHERE g2.run_id=? AND g2.goal_id=?)",
            (self.run_id, leaf, self.run_id, leaf)).fetchone()
        status = self.exec.current_status("GOAL", leaf) or "PROPOSED"
        lines = [f"GOAL CARD [{leaf}] status={status}",
                 f"  statement: {self.substitute_mentions(g['statement']) if g else '?'}",
                 f"  achievement_test: {g['achievement_test_json'] if g else '{}'}"]
        bound = self._active_bound_refs(chain)
        ws_by_id = {r["ref_id"]: r for r in ws}
        if config.JOIN_ON and bound and not suppress_join:
            lines.append("  BOUND REFERENTS (id | anchor coordinates | render xref | rung | last):")
            for ref_id in sorted(bound)[:config.N_MAX_BINDINGS]:
                r = ws_by_id.get(ref_id)
                if not r:
                    row = c.execute(
                        "SELECT g.bbox_x0,g.bbox_y0,g.bbox_x1,g.bbox_y1,g.cells_json FROM referent rr "
                        "JOIN locator_gridregion g ON g.run_id=rr.run_id AND g.locator_id=rr.anchor_locator_id "
                        "WHERE rr.run_id=? AND rr.ref_id=? ORDER BY rr.version DESC LIMIT 1",
                        (self.run_id, ref_id)).fetchone()
                    if not row:
                        continue
                    cells = json.loads(row["cells_json"]); nn = len(cells) or 1
                    r = {"ref_id": ref_id, "centroid": (round(sum(p[0] for p in cells) / nn),
                         round(sum(p[1] for p in cells) / nn)),
                         "rung": self.exec.current_status("REFERENT_RUNG", ref_id) or "ANCHORED",
                         "last_consequence": None}
                coord = self._coord_string(r)   # SAME shared string as Z5 (side B)
                # §2.4.5 evidence compaction: the one-line consequence
                # signature (count + change/no-op split + exemplar pointers)
                sig = self.exec.consequence_signature(ref_id)
                lines.append(f"    {ref_id} | {coord} | {coord} | {r['rung']} | {sig}")
        lines.append(f"  STEP: {self.substitute_mentions(active_step) if active_step else '(no active commitment step)'}")
        if predicted_effect:
            lines.append(f"  predicted effect: {predicted_effect}")
        return "\n".join(lines)

    # ---- composition + R9 ----
    def budgeted_view(self, head: dict, grid: list, available: list,
                      active_step: Optional[str] = None,
                      predicted_effect: Optional[str] = None,
                      force_compact: bool = False) -> dict:
        refs = self._current_referents()
        chain = self._active_chain()
        ws = self.working_set(refs, chain)
        archived = max(0, len(refs) - len(ws))
        z1 = self.z1_head(head, chain, active_step)
        z2 = self.z2_roster(ws, archived=archived)
        z3 = self.z3_rules()
        z4 = self.z4_frontier(ws, available, chain=chain, level=head.get("level", 0))
        z5 = self.z5_render(grid, ws)
        z6 = self.z6_goal_card(chain, ws, active_step, predicted_effect,
                               suppress_join=(config.GOALCARD_POS == "restated"))
        zones = {"Z1": z1, "Z2": z2, "Z3": z3, "Z4": z4, "Z5": z5, "Z6": z6}
        # A10 (ARG_GOALCARD_POS): 'adjacent' (default) = Z6 at the recency
        # tail; 'mid' = Z6 mid-context; 'restated' = adjacent, join removed —
        # the same information restated without the mechanical join.
        order = ("Z1", "Z2", "Z3", "Z6", "Z4", "Z5") if config.GOALCARD_POS == "mid" \
            else ("Z1", "Z2", "Z3", "Z4", "Z5", "Z6")
        if force_compact:
            # R6 LIVE fallback (ZCR zone-differential trigger): straight to the
            # compact tier — coordinate-only joins, corroboration dropped
            view = "\n\n".join((zones["Z1"], zones["Z2"],
                                self.z5_render(grid, ws, compact=True), zones["Z6"]))
        else:
            view = "\n\n".join(zones[z] for z in order)
        tokens = est_tokens(view)
        # R6 small-context fallback if over B: drop Z4/Z3 corroboration first,
        # then the grid (Z5 falls back to coordinate-only joins), then Z1+Z6
        if tokens > config.B_RENDER:
            view = "\n\n".join(zones[z] for z in ("Z1", "Z2", "Z5", "Z6"))
            tokens = est_tokens(view)
        if tokens > config.B_RENDER:
            z5c = self.z5_render(grid, ws, compact=True)
            view = "\n\n".join((zones["Z1"], zones["Z2"], z5c, zones["Z6"]))
            tokens = est_tokens(view)
        if tokens > config.B_RENDER:
            view = "\n\n".join(zones[z] for z in ("Z1", "Z6"))  # irreducible
            tokens = est_tokens(view)
        # Terminal HARD clamp (R9 guarantee): even the irreducible Z1+Z6 can
        # exceed B if a stored goal carries a huge statement/achievement_test.
        # Truncate to a bounded prefix with an honest marker so the returned
        # view is ALWAYS ≤ B — a guarantee, not best-effort. A safety margin
        # below B absorbs the char/4 estimator's underestimation.
        cap_chars = int(config.B_RENDER * 4 * 0.9)
        if len(view) > cap_chars:
            view = view[:cap_chars] + "\n…[render clamped to B — full state via probe]"
            tokens = est_tokens(view)
        return {"view": view, "zones": zones, "render_tokens": tokens, "working_set": ws,
                "chain": chain, "archived": archived}

    # ---- render_capture + ZCR salting (echo check consumes at M4) ----
    def capture(self, probe, turn_id: int, call_idx: int, organ: str, zones: dict,
                shadow: bool = False, rank_snapshot: str = "") -> None:
        try:
            for tier, text in zones.items():
                probe.conn.execute(
                    "INSERT OR REPLACE INTO render_capture (run_id, turn_id, call_idx, organ, "
                    "zone_tier, view_bytes, render_tokens, shadow_flag, rank_snapshot) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (self.run_id, turn_id, call_idx, organ, tier, text, est_tokens(text),
                     1 if shadow else 0, rank_snapshot))
            probe.conn.commit()
        except Exception:
            probe.write_failures += 1

    def salt_canaries(self, probe, turn_id: int, organ: str, call_idx: int, zones: dict,
                      tiers: tuple = ("Z2", "Z3", "Z6")) -> dict:
        """Salt one nonce row per zone tier at cadence; record to zcr_salt. The
        organ echoes them back (canary_echo) so the Executive can compute
        per-zone consumption rate — content being in the view is necessary,
        not sufficient. `tiers` must be the zones the ORGAN actually consumes
        (a nonce salted into a zone outside its contract is unanswerable).
        Returns the mutated zones + the salted nonces."""
        import hashlib
        nonces = {}
        salted = dict(zones)
        for tier in tiers:
            nonce = "ZQ" + hashlib.sha1(f"{self.run_id}{turn_id}{organ}{tier}".encode()).hexdigest()[:8]
            nonces[tier] = nonce
            salted[tier] = zones[tier] + f"\n  [{tier}-CANARY {nonce}]"
            try:
                seq = probe._seq("zcr_salt", self.run_id)
                probe.conn.execute(
                    "INSERT INTO zcr_salt (run_id, seq, turn_id, organ, call_idx, zone_tier, nonce) "
                    "VALUES (?,?,?,?,?,?,?)", (self.run_id, seq, turn_id, organ, call_idx, tier, nonce))
                probe.conn.commit()
            except Exception:
                probe.write_failures += 1
        return {"zones": salted, "nonces": nonces}

    # ---- R3 cross-zone coordinate equality (legibility invariant) ----
    def cross_zone_violations(self, zones: dict, ws: list) -> list:
        """For every working-set referent bound to the active goal, its shared
        coordinate string must appear byte-identically in Z5 and Z6. Any
        mismatch marks the run INVALID (probe_arg_legibility)."""
        chain = self._active_chain()
        bound = self._active_bound_refs(chain)
        viol = []
        for r in ws:
            if r["ref_id"] not in bound:
                continue
            coord = self._coord_string(r)
            in_z5 = f"«R:{r['ref_id']} " in zones["Z5"] and coord in zones["Z5"]
            in_z6 = coord in zones["Z6"]
            if not (in_z5 and in_z6):
                viol.append({"ref_id": r["ref_id"], "coord": coord,
                             "in_z5": in_z5, "in_z6": in_z6})
        return viol
