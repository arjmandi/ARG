"""ARG configuration — the single place every constant and kill switch is read.

Convention (build plan §9): `ARG_<NAME>=0` kills, `=1`/unset = on. FULL cell =
every ARG_* at default with ARG_SPLIT=0. Threshold constants are pre-registered
tunables (the §8 sensitivity sweep varies them); each default is justified in
docs_arg_buildplan.md §3.
"""

from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _on(name: str) -> bool:
    """A gate is ON unless explicitly '0' (build plan §9)."""
    return os.environ.get(name, "1") != "0"


# ---- pinned constants (build plan §3; defaults + rationale in the doc) ----
TAU = _float("ARG_TAU", 0.15)                 # merge margin; below → NEW + same_as HYPOTHESIS
TAU_AUTO = _float("ARG_TAU_AUTO", 0.40)       # margin ≥ this → Executive auto-binds, 0 LLM calls
K_SUPPORT = _int("ARG_K", 2)                  # HYPOTHESIS→TESTED when support ≥ k & mismatch < θ
K_DEMOTE = _int("ARG_K_DEMOTE", 3)            # K mismatches demote (never delete)
THETA = _float("ARG_THETA", 0.34)             # mismatch-ratio demotion ceiling
K_FISS = _int("ARG_K_FISS", 3)                # fission-check mismatch floor (distinct from K_DEMOTE)
FISS_R = _float("ARG_FISS_R", 0.5)            # point-biserial |r| threshold to fire fission-check
TTL = _int("ARG_TTL", 50)                     # negative-evidence decay / re-probe / rejected-goal window (turns)
LEASE_MAX_BEATS = _int("ARG_LEASE", 20)       # beats/step; expiry = T-trigger + qualifying evidence
B_RENDER = _int("ARG_B", 6000)                # hard per-call render ceiling (tokens)
W_WORKING_SET = _int("ARG_W", 40)             # working-set referent cap (Z2 rows / Z5 annotations)
N_MAX_BINDINGS = _int("ARG_N_MAX", 24)        # Σ|bindings| over live goals (gate-6; ≤ B by arithmetic)
C_MAX_CHANGESET = _int("ARG_C_MAX", 20)       # Observer changeset entries per call (≈20 at B=6000)
L_LOG_TAIL = _int("ARG_L", 8)                 # Observer log-tail attribution window (turns)
K_CANARY = _int("ARG_K_CANARY", 8)            # ZCR cadence (LLM calls per organ)
ZCR_FLOOR = _float("ARG_ZCR_FLOOR", 0.90)     # per-zone echo floor at warm state
ZCR_WARMUP_EPOCHS = _int("ARG_ZCR_WARMUP", 2)
S_STALL = _int("ARG_S", 12)                   # T4 stall: beats with no new evidence
C_EPOCH_RATE = _int("ARG_C", 10)              # epoch rate-limit (beats), T1 exempt
SURVEYOR_CALLS_PER_EPOCH = _int("ARG_EPOCH_CALLS", 3)
EPOCH_CAP_BASE = _int("ARG_EPOCH_CAP", 8)     # per-level epoch cap = base × (level+1); T1 exempt
WER_FLOOR = _float("ARG_WER_FLOOR", 0.25)     # per-organ; breach → run invalid for attribution (§2.1)
WER_MIN_OPS = _int("ARG_WER_MIN_OPS", 5)      # floor applies once an organ has ≥ this many write ops
MAX_ACTIONS = _int("SENSI_MAX_ACTIONS", 200)  # §8 horizon (base Agent is 80)

# id minting: per-run, per-type, zero-padded width; widen on overflow, never wrap
ID_WIDTH = _int("ARG_ID_WIDTH", 4)

# ---- kill switches / gates (build plan §9) ----
JOIN_ON = _on("ARG_JOIN")                     # Z5 annotations + Z6 bindings + R2 substitution
AGENDA_ON = _on("ARG_AGENDA")                 # Commitment persistence; =0 → shadow instrumentation
SEARCH_ON = _on("ARG_SEARCH")                 # Surveyor epochs (A3)
CONSEQ_ON = _on("ARG_CONSEQ")                 # consequence gating (A4)
RETAIN_ON = _on("ARG_RETAIN")                 # active-chain binding retention (A5)
SEEDS_ON = _on("ARG_SEEDS")                   # seeded LEARN-* templates (A6)
FLAT_ON = _on("ARG_FLAT")                     # salience-flat exhaustive Z2 roster (A7)
TRIGGERS_ON = _on("ARG_TRIGGERS")             # T1-immediacy + T4 + lease-expiry (A9)
SPLIT_ON = os.environ.get("ARG_SPLIT", "0") == "1"   # A8 (3 backbones); RESERVED — not consumed in build-1
GOALS_ON = _on("ARG_GOALS")                   # goal machinery; with CONSEQ_ON=0 gates B-CACHE
FISSION_ON = _on("ARG_FISSION")               # execute the §2.6.4 re-split when the check fires
BASELINE = os.environ.get("ARG_BASELINE", "")        # {bare,bcache,raw}; single-variable-exempt
GOALCARD_POS = os.environ.get("ARG_GOALCARD_POS", "adjacent")   # {adjacent,mid,restated} (A10)
STRESS_MULT = _int("ARG_STRESS_MULT", 1)      # A11 store-inflation factor

# ---- backbone / LLM ----
MODEL = os.environ.get("ARG_MODEL", os.environ.get("SENSI_MODEL", "anthropic/claude-sonnet-5"))
REASONING_EFFORT = os.environ.get("ARG_REASONING_EFFORT", os.environ.get("SENSI_REASONING_EFFORT", "medium"))
# small-backbone emission lever (P4): append worked per-op examples to the
# Surveyor contract — default OFF so the pinned Sonnet contract stays fixed
OP_EXAMPLES = _int("ARG_OP_EXAMPLES", 0) == 1
MAX_TOKENS = _int("ARG_MAX_TOKENS", 16000)
TEMPERATURE = os.environ.get("ARG_TEMPERATURE")   # None → drop for anthropic

STORE_PATH = os.environ.get("ARG_STORE_PATH", "arg_state.db")
PROBE_PATH = os.environ.get("ARG_PROBE_PATH", "arg_probe.db")


def snapshot() -> dict:
    """Full config as a JSON-serializable dict — stamped into run.config_json
    and run_config so every play is reproducible and attributable."""
    return {
        "tau": TAU, "tau_auto": TAU_AUTO, "k_support": K_SUPPORT, "k_demote": K_DEMOTE,
        "theta": THETA, "k_fiss": K_FISS, "fiss_r": FISS_R, "ttl": TTL,
        "lease_max_beats": LEASE_MAX_BEATS, "b_render": B_RENDER, "w_working_set": W_WORKING_SET,
        "n_max_bindings": N_MAX_BINDINGS, "c_max_changeset": C_MAX_CHANGESET, "l_log_tail": L_LOG_TAIL,
        "k_canary": K_CANARY, "zcr_floor": ZCR_FLOOR, "s_stall": S_STALL, "c_epoch_rate": C_EPOCH_RATE,
        "surveyor_calls_per_epoch": SURVEYOR_CALLS_PER_EPOCH, "epoch_cap_base": EPOCH_CAP_BASE,
        "wer_floor": WER_FLOOR, "fission_on": FISSION_ON, "max_actions": MAX_ACTIONS,
        "gates": {
            "join": JOIN_ON, "agenda": AGENDA_ON, "search": SEARCH_ON, "conseq": CONSEQ_ON,
            "retain": RETAIN_ON, "seeds": SEEDS_ON, "flat": FLAT_ON, "triggers": TRIGGERS_ON,
            "split": SPLIT_ON, "goals": GOALS_ON,
        },
        "baseline": BASELINE, "goalcard_pos": GOALCARD_POS, "stress_mult": STRESS_MULT,
        "model": MODEL, "reasoning_effort": REASONING_EFFORT,
    }
