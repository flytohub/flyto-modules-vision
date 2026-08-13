"""The real-camera verifier, checked without a camera, a gateway or a network.

The verifier's value is what it refuses, so the refusals are what is pinned: a
gateway that is not loopback, an input carrying credentials or a path, a run
making more than one request, evidence that does not state ``usable``, a report
directory that already exists, a report whose bytes changed. Both generations of
the report shape are covered, including the run already recorded here. Nothing
here builds a wheel, imports flyto-core or opens a socket.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:9010/api/spaces/zone-camera/observation"
WHEEL = "flyto_modules_vision-0.1.0-py3-none-any.whl"


def _load_verifier() -> Any:
    """Import the verifier by path; `scripts/` is not an installed package."""
    path = REPO / "scripts" / "verify_real_camera_closed_loop.py"
    spec = importlib.util.spec_from_file_location("_flyto_vision_verifier", path)
    sys.modules[spec.name] = module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verifier = _load_verifier()
CONTRACT = verifier.CONTRACT  # asked of the code, never spelled a second time here


def _evidence(**overrides: Any) -> dict[str, Any]:
    """One well-formed observation, before a test spoils exactly one field."""
    return {"kind": "zone.overview", "usable": True, "zone": "arena", **overrides}


def _result(*items: dict[str, Any]) -> dict[str, Any]:
    """What the module returns for a zone, in the shape the engine hands back."""
    return {"evidence": list(items), "observed": len(items), "zone": "arena"}


# -- inputs the verifier refuses
@pytest.mark.parametrize("url", [
    "http://192.168.1.10:9010", "http://example.com", "https://127.0.0.1:9010",
    "http://user:pass@127.0.0.1:9010", URL, "http://127.0.0.1:9010?zone=arena",
    "http://127.0.0.1:9010#frag", "http://127.0.0.1:99999", "file:///etc/passwd",
    "http://127.0.0.1 :9010", "", "   "])
def test_only_a_bare_loopback_http_base_is_accepted(url):
    """Every one of these aims a report saying "loopback" somewhere else."""
    with pytest.raises(verifier.VerifierError):
        verifier.validate_gateway_base(url)


@pytest.mark.parametrize("zone", ["", " ", "arena ", "two words", "arena\n", "a" * 65])
def test_a_zone_is_taken_literally_or_refused(zone):
    """A repaired zone would match evidence the operator did not ask about."""
    with pytest.raises(verifier.VerifierError):
        verifier.validate_zone(zone)


def test_accepted_inputs_derive_the_contract_url_and_demand_a_toolchain(tmp_path):
    """The path is contract, derived; the interpreter and core have no defaults."""
    for base in ("http://127.0.0.1:9010", "http://127.0.0.1:9010/"):
        gateway = verifier.validate_gateway_base(base)
        assert gateway["base_url"] == "http://127.0.0.1:9010" and gateway["observation_url"] == URL
    assert verifier.OBSERVATION_PATH == "/api/spaces/zone-camera/observation"
    assert verifier.validate_zone("arena") == "arena"
    for python, core in (("", str(tmp_path)), (sys.executable, ""), (sys.executable, str(tmp_path))):
        with pytest.raises(verifier.VerifierError):
            verifier.validate_toolchain(python, core)


# -- the artefact under test is the wheel, not the working tree
def test_the_wheel_is_built_and_installed_without_an_index(tmp_path):
    """No resolution and no network: what is installed is what was just built."""
    build = verifier.wheel_build_argv(Path("/usr/bin/python3"), REPO, tmp_path)
    install = verifier.wheel_install_argv(Path("/usr/bin/python3"), tmp_path / "w", tmp_path / "t")
    assert "--no-isolation" in build and "--wheel" in build
    for flag in ("--no-deps", "--no-index", "--no-build-isolation", "--target"):
        assert flag in install
    assert verifier.offline_env({"PYTHONPATH": "/somewhere/src"}).get("PYTHONPATH") is None


def test_the_child_cannot_see_the_working_tree(tmp_path):
    """The run must exercise the installed wheel, so `src/` is off the path."""
    env = verifier.child_env(
        tmp_path / "target", tmp_path / "core-src", "http://127.0.0.1:9010",
        base={"PYTHONPATH": str(REPO / "src"), "HOME": "/home/x"},
    )
    assert str(REPO / "src") not in env["PYTHONPATH"]
    assert env["PYTHONPATH"].split(":") == [str(tmp_path / "target"), str(tmp_path / "core-src")]
    assert env["PYTHONSAFEPATH"] == "1"
    assert env[verifier.GATEWAY_URL_ENV] == "http://127.0.0.1:9010"


# -- exactly one GET, exactly there, and nothing that could capture
@pytest.mark.parametrize("requests", [
    [], [{"method": "GET", "url": URL}] * 2, [{"method": "POST", "url": URL}],
    [{"method": "GET", "url": "http://127.0.0.1:9010/api/other"}], [URL]])
def test_anything_other_than_one_get_to_the_contract_url_fails(requests):
    """A second request means something reached past the step."""
    with pytest.raises(verifier.VerifierError):
        verifier.check_requests(requests, URL)


class _Request:
    """The little of urllib.request.Request the recording opener reads."""

    def __init__(self, url: str, method: str = "GET"):
        self.full_url, self._method = url, method

    def get_method(self) -> str:
        """The verb this request would send."""
        return self._method


def test_the_child_counts_its_one_request_and_refuses_cameras():
    """Requests are counted where they are made; capture is refused outright."""
    state = {"requests": []}
    opener = verifier.recording_opener(lambda request, *a, **k: "body", state, URL)
    assert opener(_Request(URL)) == "body"
    for bad in (_Request("http://127.0.0.1:9010/api/elsewhere"), _Request(URL, "POST")):
        with pytest.raises(PermissionError):
            opener(bad)
    assert len(state["requests"]) == 3
    verifier.check_requests(state["requests"][:1], URL)
    assert all(map(verifier.is_camera_path, ("/dev/video0", Path("/dev/media0"))))
    assert all(map(verifier.is_camera_module, ("cv2", "PIL.Image")))
    assert not verifier.is_camera_path("/tmp/x.json") and not verifier.is_camera_module("json")


# -- flyto-core is used the way a host uses it
class FakeRegistry:
    """flyto-core's public registry surface, and nothing a host cannot reach."""

    def __init__(self, result: Any, plugins=("vision",), modules=("vision.observe",)):
        self.calls: list[str] = []
        self._result, self._plugins, self._modules = result, list(plugins), list(modules)

    def clear(self) -> None:
        """Discard whatever an earlier import registered."""
        self.calls.append("clear")

    def discover_plugins(self) -> None:
        """Load every `flyto.modules` entry point, as the engine does."""
        self.calls.append("discover_plugins")

    def get_plugins(self) -> list[str]:
        """The plugin names discovery found."""
        self.calls.append("get_plugins")
        return self._plugins

    def get_plugin_modules(self, name: str) -> list[str]:
        """The module ids one plugin registered."""
        return self._modules

    def capabilities(self) -> dict[str, list[str]]:
        """What the registry says each module provides."""
        return {"vision.observe": ["vision.observe"]}

    def execute(self, module_id: str, params: dict[str, Any]) -> Any:
        """Run a module by id, which is the only way this verifier runs one."""
        self.calls.append(f"execute:{module_id}:{params.get('zone')}")
        return self._result


def test_the_module_is_run_through_the_public_registry_only():
    """Never the class, never `execute()` directly — the host's own path."""
    registry = FakeRegistry(_result(_evidence()))
    outcome = verifier.execute_through_registry(registry, "arena")
    assert registry.calls[:2] == ["clear", "discover_plugins"]
    assert "execute:vision.observe:arena" in registry.calls
    assert outcome["capability"] == {"vision.observe": ["vision.observe"]}
    assert outcome["result"]["evidence"][0]["kind"] == "zone.overview"
    result, keys = verifier.unwrap_envelope({"result": {"data": _result(_evidence())}})
    assert keys == ["result", "data"] and result["evidence"][0]["zone"] == "arena"


@pytest.mark.parametrize("registry", [
    FakeRegistry(_result(), plugins=("community",)), FakeRegistry(_result(), modules=("x.y",))])
def test_a_plugin_that_did_not_register_fails_closed(registry):
    """No entry point, or the wrong module, means the wheel is not doing its job."""
    with pytest.raises(verifier.VerifierError):
        verifier.execute_through_registry(registry, "arena")


# -- what counts as a pass
def test_evidence_that_states_usable_true_for_the_zone_passes():
    """The one shape that is a closed loop, and unfamiliar kinds ride along."""
    summary = verifier.check_evidence(_result(_evidence(), _evidence(kind="zone.thermal")), "arena")
    assert summary["selected"] == 2 and summary["usable"] == 2
    assert summary["kinds"] == ["zone.overview", "zone.thermal"]


@pytest.mark.parametrize("result", [
    _result({"kind": "zone.overview", "zone": "arena"}), _result(_evidence(usable=False)),
    _result(_evidence(usable="true")), _result(_evidence(usable=1)),
    _result(_evidence(zone="corridor")), _result({"kind": "zone.overview", "usable": True}),
    _result({"usable": True, "zone": "arena"}), _result(),
    {"evidence": [], "error": "no vision gateway"}, {"observed": 0}, "evidence", None])
def test_anything_short_of_stated_usable_evidence_fails_closed(result):
    """An omitted boolean is false in most languages and is never read as true."""
    with pytest.raises(verifier.VerifierError):
        verifier.check_evidence(result, "arena")


# -- the report, in both generations of its shape
def _report(**overrides: Any) -> dict[str, Any]:
    """A report of a passing run, before a test spoils exactly one claim."""
    report = verifier.build_report(
        run_id="20260809T000000Z-abcdef01", zone="arena",
        gateway=verifier.validate_gateway_base("http://127.0.0.1:9010"),
        child={"requests": [{"method": "GET", "url": URL}], "connect_hosts": ["127.0.0.1"],
               "result": _result(_evidence()), "package_version": "0.1.0"},
        summary=verifier.check_evidence(_result(_evidence()), "arena"),
        wheel={"filename": WHEEL, "sha256": "a" * 64}, provenance={"clock": "UTC"})
    report.update(overrides)
    return report


def _v1_report(**overrides: Any) -> dict[str, Any]:
    """The first-generation shape: `outcome`, `requests_made`, and no `passed`.

    Deterministic, and field-for-field the run already recorded in this
    repository, so the read-only mode is held to reading that record too.
    """
    report = {
        "contract": verifier.CONTRACT, "outcome": "passed", "params": {"zone": "arena"},
        "run_id": "20260809T124233Z-f9e256cd",
        "evidence": [_evidence(detail="arena: view_ok (3.0s ago)")],
        "gateway": {"authority": "127.0.0.1:9010", "base_url": "http://127.0.0.1:9010",
                    "connect_hosts": ["127.0.0.1"], "credentials_present": False,
                    "loopback_only": True, "observation_url": URL, "scheme": "http",
                    "requests_made": [URL]},
        "package": {"name": "flyto-modules-vision", "version": "0.1.0", "wheel_filename": WHEEL,
                    "observation_path": verifier.OBSERVATION_PATH,
                    "observation_path_is_contract": True,
                    "wheel_sha256": "3f332cfd7cc4bb9632ab9ac0d3d09c74b3014e4774a4687ed306a6062"
                                    "9f9b211"},
        "boundaries": {"camera_capture": False, "gateway_read": True, "loopback_only": True,
                       "pixel_decode": False, "notes": ["What the gateway reported."]},
    }
    report.update(overrides)
    return report


def test_a_report_is_written_once_and_states_what_it_cannot_prove(tmp_path):
    """A record that can be overwritten is not a record, and it must own its limits."""
    report, bounds = _report(), _report()["boundaries"]
    assert report["passed"] is True and report["outcome"] == "passed"
    assert bounds["camera_capture"] is False and bounds["pixel_decode"] is False
    assert report["gateway"]["request_count"] == 1 and report["package"]["wheel_sha256"] == "a" * 64
    assert any("does not prove" in note for note in bounds["notes"])
    run_dir = verifier.create_run_dir(tmp_path, "20260809T000000Z-abcdef01")
    path = verifier.write_report(run_dir, report)
    assert json.loads(path.read_text())["contract"] == verifier.CONTRACT
    assert [p.name for p in run_dir.iterdir()] == ["report.json"]
    with pytest.raises(verifier.VerifierError):
        verifier.write_report(run_dir, report)
    with pytest.raises(verifier.VerifierError):
        verifier.create_run_dir(tmp_path, "20260809T000000Z-abcdef01")


def test_a_failed_write_leaves_no_partial_report(tmp_path, monkeypatch):
    """The file appears whole or not at all."""
    run_dir = verifier.create_run_dir(tmp_path, "20260809T000000Z-abcdef02")

    def boom(*args, **kwargs):
        """The rename failing, which is the only moment a report becomes real."""
        raise OSError("disk full")

    monkeypatch.setattr(verifier.os, "replace", boom)
    with pytest.raises(OSError):
        verifier.write_report(run_dir, _report())
    assert list(run_dir.iterdir()) == []


# -- reading a record back, without contacting anything
def _digest(path: Path) -> str:
    """The SHA-256 a reader would compute over the bytes on disk."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _written(tmp_path: Path, report: dict[str, Any]) -> tuple[Path, str]:
    """Write a report the way a run would, and return it with its digest."""
    return (path := verifier.write_report(
        verifier.create_run_dir(tmp_path, "20260809T0Z-abc"), report)), _digest(path)


@pytest.mark.parametrize("report", [_report(), _v1_report()])
def test_a_recorded_run_validates_against_its_digest(tmp_path, report):
    """Read-only, for both generations: no gateway, no build, nothing written."""
    path, digest = _written(tmp_path, report)
    before = sorted(p.name for p in path.parent.iterdir())
    assert verifier.validate_existing_report(path, digest)["contract"] == verifier.CONTRACT
    assert verifier.validate_existing_report(path, digest.upper())
    assert sorted(p.name for p in path.parent.iterdir()) == before


def test_the_repositorys_own_recorded_run_still_validates():
    """The record this verifier exists to make reproducible must stay readable."""
    recorded = sorted(REPO.glob("results/real-camera-closed-loop/*/report.json"))
    if not recorded:
        pytest.skip("no recorded run in this checkout")
    for path in recorded:
        assert verifier.validate_existing_report(path, _digest(path))["contract"] == CONTRACT


def test_a_tampered_or_mismatched_report_is_refused(tmp_path):
    """A digest is what makes "these are the bytes that were written" checkable."""
    path, digest = _written(tmp_path, _report())
    for bad in ("f" * 64, "not-a-digest"):
        with pytest.raises(verifier.VerifierError):
            verifier.validate_existing_report(path, bad)
    with pytest.raises(verifier.VerifierError):
        verifier.validate_existing_report(tmp_path / "absent.json", digest)
    path.write_text(path.read_text().replace("arena", "corridor"))
    with pytest.raises(verifier.VerifierError):
        verifier.validate_existing_report(path, digest)


@pytest.mark.parametrize("report", [
    _report(passed=False), _report(contract="something.else.v1"), _report(evidence=[]),
    _report(gateway={"base_url": "http://10.0.0.5:9010"}), _v1_report(outcome="failed"),
    _v1_report(gateway={"base_url": "http://127.0.0.1:9010", "requests_made": [URL, URL]})])
def test_a_report_failing_its_own_invariants_is_refused(report):
    """The digest says the bytes are unchanged; this says the bytes mean a pass."""
    with pytest.raises(verifier.VerifierError):
        verifier.check_report_invariants(report)


def test_the_command_line_refuses_a_bad_gateway_without_writing_anything(tmp_path, capsys):
    """A refusal exits nonzero and creates no run directory."""
    root = tmp_path / "results"
    (tmp_path / "core").mkdir()
    code = verifier.main(["--python", sys.executable, "--core-src", str(tmp_path), "--gateway",
                          "http://10.0.0.5:9010", "--zone", "arena", "--report-root", str(root)])
    assert code == 2 and not root.exists()
    assert "refused" in capsys.readouterr().err
