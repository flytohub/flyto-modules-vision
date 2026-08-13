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

# The two flyto-core names this package asks for by hand. Only these two going
# missing is "no flyto-core here"; anything else that fails to import while
# they are being fetched is flyto-core's own breakage, or this package's.
_CORE_BASE = "core.modules.base"
_CORE_REGISTRY = "core.modules.registry"

# The import machinery's own frames. Named exactly rather than by prefix: a
# third-party module whose name merely starts with "importlib" is ordinary code
# and must not be mistaken for the machinery, since being mistaken for it is
# what would let a failure be swallowed.
_IMPORT_MACHINERY = frozenset(
    {"importlib", "importlib._bootstrap", "importlib._bootstrap_external"}
)


def _raised_inside_executed_code(exc: BaseException) -> bool:
    """Whether ``exc`` came out of a module *body* rather than out of resolution.

    The discriminator the name alone cannot provide. When the import system
    cannot resolve a module, the only frames left on the traceback are this
    function's caller and the machinery's own — CPython strips its
    ``importlib._bootstrap`` frames from an ``ImportError`` for exactly this
    reason, and the ``cannot import name`` failure never has any to strip. When
    a module is found and its body raises, that body's frame is on the
    traceback and no stripping removes it.

    So a flyto-core that is installed and breaks while initialising is visible
    here even when it raises an error naming ``core.modules.base`` itself — a
    circular import, or a partially initialised package re-importing its own
    name. Those carry the identical ``name`` an uninstalled flyto-core carries,
    and only where they were raised tells them apart.
    """
    frames = exc.__traceback__
    while frames is not None:
        origin = frames.tb_frame.f_globals.get("__name__", "")
        # This module's own frame is where the import statement sits; the
        # machinery's frames are resolution, not execution. Anything else on
        # the traceback is code that ran.
        if origin != __name__ and origin not in _IMPORT_MACHINERY:
            return True
        frames = frames.tb_next
    return False


def _is_core_api_unavailable(exc: ImportError, wanted: str) -> bool:
    """Whether ``exc`` is *the named flyto-core API itself* being unavailable.

    This is the only failure :func:`register_all` is allowed to swallow, and
    the distinction is the whole point of the function. A ``ModuleNotFoundError``
    raised from *inside* flyto-core — its own dependency missing on this host —
    is indistinguishable from "flyto-core is not installed" if you only look at
    the exception's type, and often indistinguishable by its ``name`` too.
    Reporting it as the latter sends whoever has to fix it to the wrong
    repository and hides a broken engine behind a message saying the engine is
    simply absent.

    Two things must both hold, and they answer different questions: nothing
    executed (so this is resolution failing, not flyto-core failing), and what
    failed to resolve is the module asked for here (so this is not some third
    dependency that happened to be reached along the way).
    """
    if _raised_inside_executed_code(exc):
        return False
    failed = getattr(exc, "name", None)
    if not failed:
        # The import system always names the module it could not supply. An
        # ImportError arriving without one was raised by code, not by the
        # machinery, and is not this function's to interpret.
        return False
    if isinstance(exc, ModuleNotFoundError):
        # ``core``, ``core.modules`` or ``core.modules.base``: the module asked
        # for, or a package it lives in. A third-party name flyto-core imports
        # is none of those and must travel.
        return failed == wanted or wanted.startswith(f"{failed}.")
    # ``cannot import name 'BaseModule' from 'core.modules.base'`` — installed,
    # but not offering this API. An incompatible flyto-core, which registers
    # nothing here for the same reason an absent one does.
    return failed == wanted


def _log_core_unavailable(exc: ImportError) -> None:
    logger.warning(
        "flyto-modules-vision could not reach flyto-core, so no vision "
        "steps were registered: %s",
        exc,
    )


def register_all() -> None:
    """Register the vision modules with flyto-core's registry.

    Imports flyto-core here rather than at module scope: this package must stay
    importable — and its parsing testable — where flyto-core is absent.

    **A missing or incompatible flyto-core is logged and returns** rather than
    raising. flyto-core loads every plugin in one loop, so a raise here would
    take down module discovery for every other plugin as well.

    **Everything else raises.** A dependency flyto-core cannot import, a module
    of this package that fails to load, a decorator that refuses — those are
    real plugin failures, and flyto-core's discovery boundary is the only place
    an operator will ever see them named. Swallowing one would leave a host
    reporting "no vision steps" with nothing anywhere saying why.

    **Nothing is cached.** The host calls this every time it discovers, and it
    registers every time, so a registry that was cleared or hot-reloaded gets
    the same set back. An already-registered flag would make the second call a
    no-op and leave the builder permanently empty. Ownership of the modules is
    assigned by the host around this call; this package never claims it.
    """
    try:
        from core.modules.base import BaseModule
    except ImportError as exc:
        if not _is_core_api_unavailable(exc, _CORE_BASE):
            raise
        _log_core_unavailable(exc)
        return

    try:
        from core.modules.registry import register_module
    except ImportError as exc:
        if not _is_core_api_unavailable(exc, _CORE_REGISTRY):
            raise
        _log_core_unavailable(exc)
        return

    # Outside the guard deliberately. From here on a failure is this plugin's,
    # and flyto-core has to be told about it to be able to report it.
    from .modules import build_modules

    registered = build_modules(BaseModule, register_module)
    logger.info(
        "flyto-modules-vision registered %d vision steps: %s",
        len(registered),
        ", ".join(sorted(module_id for module_id, _ in registered)),
    )
