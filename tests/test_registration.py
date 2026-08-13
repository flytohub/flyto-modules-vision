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
import importlib.util
import inspect
import sys
from typing import Any

import pytest

from flyto_modules_vision import register_all
from flyto_modules_vision.modules import build_modules
from flyto_modules_vision.steps import CAPABILITIES, MODULE_OBSERVE

CORE_BASE = "core.modules.base"
CORE_REGISTRY = "core.modules.registry"
PLUGIN_MODULES = "flyto_modules_vision.modules"
PLUGIN_NAME = "vision"

# A dependency nothing has, standing in for whatever a broken install of
# flyto-core — or of this package — turns out to be missing on a host.
ABSENT_DEPENDENCY = "flyto_modules_vision_absent_dependency"


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


# -- The discovery boundary: what register_all() may swallow, and what it may not.
#
# Every fake below is served through the real import machinery, so the
# exceptions register_all() inspects are CPython's own rather than ones a test
# hand-built. That matters here: the previous version of this file raised a bare
# `ImportError("no flyto-core here")`, which the import system never produces,
# and so it could not tell "flyto-core is absent" apart from "flyto-core is
# installed and broken" — the one distinction this boundary exists to make.


HEALTHY = ""

# A body that cannot import its own dependency. Executed as the fake module's
# own source, so the ModuleNotFoundError names the dependency and carries a
# frame belonging to the module that wanted it — exactly what a flyto-core
# whose install is missing a requirement produces.
NEEDS_AN_ABSENT_DEPENDENCY = f"import {ABSENT_DEPENDENCY}\n"


def _raises_naming_itself(exception: str, module_name: str) -> str:
    """A body that fails while initialising, naming *itself* as what failed.

    A circular import, or a partially initialised package re-importing its own
    name, raises this. It carries the identical ``name`` an uninstalled
    flyto-core carries, so an exception's ``name`` cannot tell the two apart —
    only the fact that this one came out of a module that was found and ran.
    """
    return f"raise {exception}('failed while initialising {module_name}', name={module_name!r})\n"


def _never_called(**meta: Any):
    raise AssertionError(f"registration was attempted with {sorted(meta)}")


class _FakeModuleFinder:
    """Serve named modules from source text, through the real import system.

    The source is compiled and executed into the module's own namespace, so a
    frame raised from it reports that module as its ``__name__`` — which is the
    signal `register_all` reads to tell "flyto-core is not installed" apart
    from "flyto-core is installed and broke while loading". A body built out of
    this test file's own functions would report this test file instead and
    would not exercise that at all.
    """

    def __init__(self, sources: dict[str, str], namespace: dict[str, dict[str, Any]] | None = None):
        self._sources = sources
        self._namespace = namespace or {}

    def find_spec(self, fullname: str, path: Any = None, target: Any = None):
        if fullname not in self._sources:
            return None
        is_package = any(other.startswith(f"{fullname}.") for other in self._sources)
        return importlib.util.spec_from_loader(fullname, self, is_package=is_package)

    def create_module(self, spec: Any):
        return None

    def exec_module(self, module: Any) -> None:
        name = module.__name__
        # Published before the body runs, the way a real module's imports are
        # in place before the statements that use them.
        module.__dict__.update(self._namespace.get(name, {}))
        exec(compile(self._sources[name], f"<fake {name}>", "exec"), module.__dict__)


def _purge(prefix: str) -> None:
    for name in [n for n in sys.modules if n == prefix or n.startswith(f"{prefix}.")]:
        del sys.modules[name]


@pytest.fixture
def core_tree(monkeypatch):
    """Own the `core.*` namespace for one test, and leave nothing behind."""
    _purge("core")

    def install(sources: dict[str, str], namespace: dict[str, dict[str, Any]]) -> None:
        served = {"core": HEALTHY, "core.modules": HEALTHY, **sources}
        finder = _FakeModuleFinder(served, namespace)
        monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])

    yield install
    _purge("core")


@pytest.fixture
def core_absent(monkeypatch):
    """No flyto-core at all — a Raspberry Pi carrying only this package."""
    _purge("core")
    # What the import system does with this is raise ModuleNotFoundError naming
    # `core`, which is exactly what an uninstalled flyto-core raises.
    monkeypatch.setitem(sys.modules, "core", None)
    yield
    _purge("core")


def _healthy_core(register_module: Any) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    sources = {CORE_BASE: HEALTHY, CORE_REGISTRY: HEALTHY}
    namespace = {
        CORE_BASE: {"BaseModule": StandInBase},
        CORE_REGISTRY: {"register_module": register_module},
    }
    return sources, namespace


def test_a_missing_flyto_core_is_logged_not_raised(core_absent, caplog):
    """Discovery loads every plugin in one loop; raising takes down the others."""
    with caplog.at_level("WARNING"):
        assert register_all() is None
    assert "could not reach flyto-core" in caplog.text


@pytest.mark.parametrize("incompatible", [CORE_BASE, CORE_REGISTRY])
def test_an_incompatible_flyto_core_is_logged_not_raised(core_tree, caplog, incompatible):
    """The module is installed but does not offer the name this asks for.

    An engine too old or too new to have `BaseModule` or `register_module` can
    register nothing here, for the same reason an absent one cannot, and takes
    the rest of discovery down with it if this raises.
    """
    sources, namespace = _healthy_core(_never_called)
    # The module is served and loads cleanly; the name simply is not in it.
    namespace[incompatible] = {}
    core_tree(sources, namespace)
    with caplog.at_level("WARNING"):
        assert register_all() is None
    assert "could not reach flyto-core" in caplog.text


@pytest.mark.parametrize("broken", [CORE_BASE, CORE_REGISTRY])
def test_a_missing_dependency_inside_flyto_core_propagates(core_tree, caplog, broken):
    """flyto-core is installed and cannot import *its own* dependency.

    Same exception type as an absent engine, entirely different repair. If this
    were swallowed the host would report "no vision steps" and nothing anywhere
    would name the module that is actually missing.
    """
    sources, namespace = _healthy_core(_never_called)
    sources[broken] = NEEDS_AN_ABSENT_DEPENDENCY
    core_tree(sources, namespace)
    with caplog.at_level("WARNING"), pytest.raises(ModuleNotFoundError) as raised:
        register_all()
    assert raised.value.name == ABSENT_DEPENDENCY
    assert "could not reach flyto-core" not in caplog.text


@pytest.mark.parametrize("broken", [CORE_BASE, CORE_REGISTRY])
@pytest.mark.parametrize("exception", ["ModuleNotFoundError", "ImportError"])
def test_a_failure_inside_flyto_core_naming_itself_propagates(core_tree, caplog, broken, exception):
    """The case an exception's ``name`` cannot decide.

    flyto-core is installed, is found, runs, and fails while initialising with
    an error naming the very module that was asked for — what a circular import
    or a partially initialised package raises. It is byte-for-byte the ``name``
    an uninstalled flyto-core carries, so a boundary that classifies on ``name``
    alone reports a broken engine as an absent one and the real failure is never
    seen by anybody. What separates them is that this one came out of a module
    that was found and ran.
    """
    sources, namespace = _healthy_core(_never_called)
    sources[broken] = _raises_naming_itself(exception, broken)
    core_tree(sources, namespace)
    with caplog.at_level("WARNING"), pytest.raises(ImportError) as raised:
        register_all()
    assert raised.value.name == broken
    assert "failed while initialising" in str(raised.value)
    assert "could not reach flyto-core" not in caplog.text


def test_a_missing_dependency_inside_this_package_propagates(core_tree, caplog, monkeypatch):
    """flyto-core is fine and `flyto_modules_vision.modules` will not load.

    This plugin is the broken one, and flyto-core's discovery boundary is where
    that gets reported. Blaming the engine would be a lie told to the one log
    line an operator reads.
    """
    core_tree(*_healthy_core(_never_called))
    monkeypatch.delitem(sys.modules, PLUGIN_MODULES, raising=False)
    monkeypatch.setattr(
        sys,
        "meta_path",
        [_FakeModuleFinder({PLUGIN_MODULES: NEEDS_AN_ABSENT_DEPENDENCY}), *sys.meta_path],
    )
    with caplog.at_level("WARNING"), pytest.raises(ModuleNotFoundError) as raised:
        register_all()
    assert raised.value.name == ABSENT_DEPENDENCY
    assert "could not reach flyto-core" not in caplog.text


def test_a_refusing_flyto_core_decorator_propagates(core_tree, caplog):
    """The registration decorator itself raises an import error.

    It looks exactly like an absent engine to a bare `except ImportError`, and
    it means the opposite: flyto-core was reached and rejected the module.
    """

    def refuse(**meta: Any):
        raise ModuleNotFoundError(f"No module named {ABSENT_DEPENDENCY!r}", name=ABSENT_DEPENDENCY)

    core_tree(*_healthy_core(refuse))
    with caplog.at_level("WARNING"), pytest.raises(ModuleNotFoundError) as raised:
        register_all()
    assert raised.value.name == ABSENT_DEPENDENCY
    assert "could not reach flyto-core" not in caplog.text


def test_a_failure_building_the_modules_propagates(core_tree, caplog):
    """`build_modules` cannot define a class on the base flyto-core handed over.

    The decorator is reached and accepts the metadata; the class it is about to
    decorate is what cannot be built. Registration got further than either
    import guard and still must not be reported as a missing engine.
    """
    accepting = StandInRegistry()
    sources, namespace = _healthy_core(accepting.register_module)
    namespace[CORE_BASE] = {"BaseModule": object()}
    core_tree(sources, namespace)
    with caplog.at_level("WARNING"), pytest.raises(TypeError):
        register_all()
    assert "could not reach flyto-core" not in caplog.text


# -- Repeated discovery, and discovery after the registry was cleared.


class StandInRegistry:
    """What flyto-core's ModuleRegistry offers a plugin, and no more.

    Modelled on the public surface `scripts/verify_real_camera_closed_loop.py`
    drives against a real engine: `discover_plugins()`, `get_plugins()`,
    `get_plugin_modules()`, `capabilities()` and `clear()`.

    Ownership is assigned *by the host*, around the entry point call — the
    plugin never names itself. That is why this fake records the owner itself
    rather than accepting one from the registering code.
    """

    def __init__(self) -> None:
        self.modules: dict[str, type] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self.plugin_modules: dict[str, list[str]] = {}
        self._loading: str | None = None

    def register_module(self, **meta: Any):
        module_id = meta["module_id"]

        def decorate(cls):
            self.modules[module_id] = cls
            self.metadata[module_id] = dict(meta)
            owned = self.plugin_modules.setdefault(self._loading, [])
            if module_id not in owned:
                owned.append(module_id)
            return cls

        return decorate

    def discover_plugins(self) -> None:
        """What flyto-core does with a `flyto.modules` entry point: name it, call it."""
        self._loading = PLUGIN_NAME
        try:
            register_all()
        finally:
            self._loading = None

    def get_plugins(self) -> list[str]:
        return sorted(self.plugin_modules)

    def get_plugin_modules(self, plugin: str) -> list[str]:
        return sorted(self.plugin_modules.get(plugin, ()))

    def capabilities(self) -> dict[str, list[str]]:
        return {
            module_id: [meta["provides_capability"]]
            for module_id, meta in sorted(self.metadata.items())
        }

    def clear(self) -> None:
        self.modules.clear()
        self.metadata.clear()
        self.plugin_modules.clear()


@pytest.fixture
def registry(core_tree):
    """A stand-in registry reached the way flyto-core reaches this package."""
    stand_in = StandInRegistry()
    core_tree(*_healthy_core(stand_in.register_module))
    return stand_in


def _assert_fully_registered(stand_in: StandInRegistry) -> None:
    assert stand_in.get_plugins() == [PLUGIN_NAME]
    assert stand_in.get_plugin_modules(PLUGIN_NAME) == sorted(CAPABILITIES)
    assert stand_in.capabilities() == {
        module_id: [capability] for module_id, capability in sorted(CAPABILITIES.items())
    }


def test_discovery_registers_every_module_under_the_hosts_plugin_name(registry):
    registry.discover_plugins()
    _assert_fully_registered(registry)
    assert inspect.iscoroutinefunction(registry.modules[MODULE_OBSERVE].execute)


def test_repeated_discovery_registers_exactly_the_same_set(registry):
    """A host may discover more than once. Twice must not mean twice as much."""
    registry.discover_plugins()
    first = {module_id: dict(meta) for module_id, meta in registry.metadata.items()}
    registry.discover_plugins()
    _assert_fully_registered(registry)
    assert registry.plugin_modules == {PLUGIN_NAME: [MODULE_OBSERVE]}
    assert registry.metadata == first


def test_registration_repopulates_after_the_registry_is_cleared(registry):
    """The test a cached already-registered flag fails.

    flyto-core's own verifier calls `clear()` before `discover_plugins()`, and
    a hot reload does the same. A plugin that remembered having registered once
    would leave the builder permanently empty from the second discovery on, and
    every unit test that only ever registered once would still pass.
    """
    registry.discover_plugins()
    before = {module_id: dict(meta) for module_id, meta in registry.metadata.items()}
    registry.clear()
    assert registry.get_plugin_modules(PLUGIN_NAME) == []

    registry.discover_plugins()
    _assert_fully_registered(registry)
    assert registry.metadata == before


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
