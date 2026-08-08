"""One table mapping a module identifier to what it means.

The robotics package learned this the hard way: the module ids were spelled out
in the builder registration, again in the robot's own job runner, and a rename
in one place left the other reporting a step nobody could run. Everything that
needs to know what ``vision.observe`` is asks here.
"""

from __future__ import annotations

MODULE_OBSERVE = "vision.observe"

# The capability each module satisfies, which is what flyto-cloud's evidence
# layer matches a gap against. Named here so the package states what it claims
# to provide, rather than that being implied by whatever an operator typed into
# a command's `requires` field.
CAPABILITIES = {
    MODULE_OBSERVE: "vision.observe",
}

# Deliberately one module. `vision.read_code` and `vision.record` are the other
# two capabilities flyto-cloud's PRODUCED_BY names, and both belong here when
# something can actually perform them — read_code needs a decoder this has no
# business shipping, and record needs a camera close enough to the subject to
# be worth recording, which today means the robot's own. Declaring them now
# would make a gap look filled: the evidence layer would match a capability to
# a module that returns nothing, and the mission would stall instead of
# escalating to something that could really do it.
MODULE_IDS = tuple(CAPABILITIES)


def is_vision_step(module_id: str) -> bool:
    return module_id in CAPABILITIES


def capability_for(module_id: str) -> str:
    """The capability a module provides, or empty for one this does not own."""
    return CAPABILITIES.get(module_id, "")
