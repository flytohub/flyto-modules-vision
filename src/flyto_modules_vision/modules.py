"""The workflow steps this package adds to the builder.

**Why this reads rather than declares, when robotics declares rather than
drives.** The robotics steps build a plan and hand it to the robot's own runner
because flyto-core runs on the worker and the desktop, never on the robot — the
loopback address meaning "this robot" on a Pi means "this container" on a
worker. A vision step has the opposite geometry: the job was dispatched to the
machine holding the camera, flyto-core is running on that machine, and the
gateway is genuinely on its loopback. Reading here is not a shortcut past the
boundary; it is the same rule reaching a different answer because the hardware
is on this side of it.

When the robot gets its own camera the rule does not change and neither does
this module. The gateway address is configuration, so a step dispatched to the
robot asks the robot's gateway, and a step dispatched to the desktop asks the
desktop's. That is the whole difference, and it is a setting.

**Nothing here opens a camera.** It reads what a gateway already observed. A
package that cannot capture cannot be talked into capturing, and a mission
cannot make a lens fire by asking twice.

flyto-core is imported inside :func:`build_modules`, never at module scope, so
``gateway`` and ``observation`` stay importable — and testable — where
flyto-core is absent.
"""

from __future__ import annotations

from typing import Any

from .gateway import GatewayError, fetch_observations, gateway_url
from .observation import ObservationError, for_zone, parse
from .steps import MODULE_OBSERVE

__all__ = ["MODULE_OBSERVE", "build_modules"]

CATEGORY = "vision"
ICON_COLOR = "#A78BFA"


def _zone(step: Any) -> str:
    """Which zone this step is about, if it says.

    A step that names no zone reports everything the gateway can see, which is
    the useful default for a mission asking "is anything wrong here". A step
    that names one is held to it.
    """
    value = step.params.get("zone", "")
    return str(value).strip() if value is not None else ""


def _refuse(exc: Exception) -> dict[str, Any]:
    """A step that could not obtain an observation, said so.

    ``evidence`` is present and empty rather than absent. The evidence layer
    reads that key; omitting it would make "the gateway was unreachable" arrive
    as the same silence as "this step reports no evidence", and an operator
    would have no way to tell a broken camera from one that simply saw nothing.
    """
    return {
        "evidence": [],
        "observed": 0,
        "error": str(exc)[:300],
        "gateway": gateway_url(),
    }


def build_modules(base_module, register_module) -> list[tuple[str, type]]:
    """Define the module classes against whatever flyto-core provides.

    The base class and decorator are passed in rather than imported so this
    function has no import-time dependency on flyto-core, and so a test can
    exercise the classes against a stand-in.
    """

    # flyto-core awaits execute() (core/modules/base.py: `return await
    # self.execute()`). The robotics package shipped a release where these were
    # plain functions and every test passed anyway, because the stand-in base
    # class called .execute() directly and the engine's own contract was never
    # in the room. Against a real flyto-core every step died. A test in this
    # package asserts each one is a coroutine for that reason.
    @register_module(
        module_id=MODULE_OBSERVE,
        version="1.0.0",
        category=CATEGORY,
        subcategory="observe",
        tags=["camera", "vision", "zone", "evidence", "observe"],
        label="Observe Zone",
        label_key="modules.vision.observe.label",
        description="Report what the fixed camera can currently see in a zone",
        description_key="modules.vision.observe.description",
        icon="Eye",
        color=ICON_COLOR,
        input_types=["*"],
        output_types=["object"],
        can_receive_from=["*"],
        can_connect_to=["*"],
        timeout_ms=30000,
        retryable=True,
        concurrent_safe=True,
        requires_credentials=False,
        handles_sensitive_data=False,
    )
    class VisionObserve(base_module):
        module_id = MODULE_OBSERVE
        module_name = "Observe Zone"
        module_description = "Report what the fixed camera can currently see"

        def validate_params(self) -> None:
            zone = self.params.get("zone", "")
            if zone is not None and not isinstance(zone, (str, int)):
                raise ValueError("zone must be text")

        async def execute(self) -> dict[str, Any]:
            try:
                observations = parse(fetch_observations())
            except (GatewayError, ObservationError) as exc:
                return _refuse(exc)

            wanted = _zone(self)
            selected = for_zone(observations, wanted) if wanted else observations
            return {
                # The key the evidence layer reads. A step declaring
                # `output: evidence` lands this dict in the job's variables,
                # and flyto-cloud unwraps the engine envelope to find it.
                "evidence": selected,
                "observed": len(observations),
                "zone": wanted,
                "usable": sum(1 for item in selected if item.get("usable")),
            }

    return [(MODULE_OBSERVE, VisionObserve)]
