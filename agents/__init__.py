from typing import Type, cast

from dotenv import load_dotenv

from .agent import Agent, Playback
from .recorder import Recorder
from .swarm import Swarm
from .arg.agent_arg import ARG
from .arg.baselines import BARE, RAW  # §8 pinned comparator protocols

load_dotenv()

AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    cls.__name__.lower(): cast(Type[Agent], cls)
    for cls in Agent.__subclasses__()
    if cls.__name__ != "Playback"
}

# add all the recording files as valid agent names
for rec in Recorder.list():
    AVAILABLE_AGENTS[rec] = Playback

AVAILABLE_AGENTS["arg"] = ARG
AVAILABLE_AGENTS["argbare"] = BARE
AVAILABLE_AGENTS["argraw"] = RAW

__all__ = [
    "Swarm",
    "AVAILABLE_AGENTS",
]
