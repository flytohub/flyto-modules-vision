"""Registering into flyto-core, checked against what flyto-core actually does.

The stand-in base class here *awaits* execute, because the real engine does
(``core/modules/base.py``: ``return await self.execute()``). The sibling
robotics package shipped 0.1.0 with plain functions and all 36 of its tests
passed, because its stand-in called ``.execute()`` directly and the engine's
contract was never in the room. Every step died on a real install. A fake that
accepts what the real service refuses is the defect this repository has
repeated most, so the fake here refuses it too.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from flyto_modules_vision import register_all
from flyto_modules_vision.modules import build_modules
from flyto_modules_vision.steps import CAPABILITIES, MODULE_OBSERVE


class StandInBase:
    """What flyto-core's BaseModule offers a module, and no more."""

    def __init__(self, params: dict[str, Any], context: dict[str, Any] | None = None):
        self.params = params
        self.context = context or {}
        self.validate_params()

    def validate_params(self) -> None:  # pragma: no cover - overridden
        pass

    async def run(self) -> Any:
        # The engine's own line. A plain function fails here exactly as it does
        # in production, rather than passing quietly.
        return await self.execute()


def _registered() -> dict[str, type]:
    captured: dict[str, type] = {}

    def register_module(**meta):
        def decorate(cls):
            captured[meta["module_id"]] = cls
            return cls

        return decorate

    build_modules(StandInBase, register_module)
    return captured


def test_the_declared_modules_are_the_ones_registered():
    assert set(_registered()) == set(CAPABILITIES)


def test_execute_is_a_coroutine_on_every_module():
    """The 0.1.0 defect, pinned. A plain function passes every other test."""
    for module_id, cls in _registered().items():
        assert inspect.iscoroutinefunction(cls.execute), f"{module_id}.execute is not async"


def test_the_engines_own_call_path_works(monkeypatch):
    """Not `execute()` directly — `await run()`, which is what the engine calls."""
    monkeypatch.setattr(
        "flyto_modules_vision.modules.fetch_observations",
        lambda: [{"kind": "zone.overview", "usable": True, "zone": "zone-a"}],
    )
    cls = _registered()[MODULE_OBSERVE]
    result = asyncio.run(cls({}, {}).run())
    assert [item["kind"] for item in result["evidence"]] == ["zone.overview"]


def test_a_missing_flyto_core_is_logged_not_raised(monkeypatch, caplog):
    """Discovery loads every plugin in one loop; raising takes down the others."""
    import builtins

    real_import = builtins.__import__

    def refuse_core(name, *args, **kwargs):
        if name.startswith("core."):
            raise ImportError("no flyto-core here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse_core)
    with caplog.at_level("WARNING"):
        register_all()
    assert "could not reach flyto-core" in caplog.text


def test_the_package_imports_without_flyto_core():
    """A Raspberry Pi with no engine must still be able to install this."""
    import flyto_modules_vision

    assert flyto_modules_vision.MODULE_OBSERVE == "vision.observe"


@pytest.mark.parametrize("module_id, capability", sorted(CAPABILITIES.items()))
def test_each_module_states_the_capability_it_provides(module_id, capability):
    """What flyto-cloud's evidence layer matches a gap against."""
    assert capability and isinstance(capability, str)


def test_each_module_declares_its_capability_to_the_host():
    """The contribution point, pinned.

    Without this the package is a step in the builder that the evidence layer
    cannot find: installing it would make nothing answerable until an operator
    hand-typed the capability into a command somewhere else. That is the gap
    between "an extension" and "an extension the host can use".
    """
    declared = {}

    def register_module(**meta):
        declared[meta["module_id"]] = meta.get("provides_capability")

        def decorate(cls):
            return cls

        return decorate

    build_modules(StandInBase, register_module)
    assert declared == CAPABILITIES


def test_a_declared_capability_is_never_blank():
    """A blank declaration reads as 'declares nothing' and is worse than absent."""
    for module_id, capability in CAPABILITIES.items():
        assert capability.strip(), f"{module_id} declares a blank capability"
