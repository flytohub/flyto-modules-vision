"""Optional camera-observation modules for Flyto2 workflows.

flyto-core discovers this package through its ``flyto.modules`` entry point and
calls :func:`register_all`. Installing the package is therefore the whole
decision: without it a Flyto2 mission that needs to see something has nothing
to ask, and with it the builder gains a step that reports what a fixed camera
can currently make out.

The package never opens a camera. It asks a gateway on the machine the job was
dispatched to, and that gateway's address is configuration — which is what lets
the same authored step serve a room's overhead lens today and a robot's own
camera later.
"""

from __future__ import annotations

import logging

from .gateway import (
    DEFAULT_GATEWAY_URL,
    GATEWAY_URL_ENV,
    OBSERVATION_PATH,
    GatewayError,
    fetch_observations,
    gateway_url,
)
from .observation import MAX_OBSERVATIONS, ObservationError, for_zone, parse
from .steps import CAPABILITIES, MODULE_IDS, MODULE_OBSERVE, capability_for, is_vision_step

__all__ = [
    "CAPABILITIES",
    "DEFAULT_GATEWAY_URL",
    "GATEWAY_URL_ENV",
    "MAX_OBSERVATIONS",
    "MODULE_IDS",
    "MODULE_OBSERVE",
    "OBSERVATION_PATH",
    "GatewayError",
    "ObservationError",
    "capability_for",
    "fetch_observations",
    "for_zone",
    "gateway_url",
    "is_vision_step",
    "parse",
    "register_all",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


def register_all() -> None:
    """Register the vision modules with flyto-core's registry.

    Imports flyto-core here rather than at module scope: this package must stay
    importable — and its parsing testable — where flyto-core is absent.

    A missing or incompatible flyto-core is logged and returns rather than
    raising. flyto-core loads every plugin in one loop, so a raise here would
    take down module discovery for every other plugin as well.
    """
    try:
        from core.modules.base import BaseModule
        from core.modules.registry import register_module
    except ImportError as exc:  # pragma: no cover - depends on the host install
        logger.warning(
            "flyto-modules-vision could not reach flyto-core, so no vision "
            "steps were registered: %s",
            exc,
        )
        return

    from .modules import build_modules

    registered = build_modules(BaseModule, register_module)
    logger.info(
        "flyto-modules-vision registered %d vision steps: %s",
        len(registered),
        ", ".join(module_id for module_id, _ in registered),
    )
