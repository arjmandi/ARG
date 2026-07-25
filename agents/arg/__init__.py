"""ARG — Aligned Referent Grounding (docs_arg_design.md, docs_arg_buildplan.md).

A new system inspired by Sensi's findings, not a Sensi revision. The public
export is the ARG agent; importing this package registers it in
AVAILABLE_AGENTS via Agent.__subclasses__() (agents/__init__.py adds the import).
"""

# ARG (the Agent subclass) is exported once agent_arg lands (M2). Until then the
# package exposes only the offline foundation so M1 tests can import it.
try:
    from .agent_arg import ARG  # noqa: F401
except ImportError:  # M1: agent_arg not written yet
    ARG = None
