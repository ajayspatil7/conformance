from .base import Probe
from .params import ParamsProbe
from .reasoning import ReasoningProbe
from .tool_calls import ToolCallsProbe

PROBES: dict[str, type[Probe]] = {
    "tool_calls": ToolCallsProbe,
    "reasoning": ReasoningProbe,
    "params": ParamsProbe,
}


def get_probe(name: str) -> Probe:
    return PROBES[name]()
