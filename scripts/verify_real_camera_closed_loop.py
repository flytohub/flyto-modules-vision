#!/usr/bin/env python3
"""Re-run the real vision closed loop from this checkout, and record it.

The first recorded run named a verifier that was not in the repository, so the
record could be read but not reproduced. This builds this tree's wheel, installs
it into a throwaway directory with no resolution and no index, and runs
`vision.observe` through flyto-core's public registry in a child whose
``PYTHONPATH`` is replaced, so ``src/`` is never importable and what is tested is
what a user receives. A passing run makes exactly one HTTP GET, to the package's
own observation path on the configured loopback gateway; ``urlopen`` is wrapped
before the package is imported, because ``fetch_observations`` binds it as a
default argument at definition time. The address is an input, the path is
contract and is cross-checked against the installed package. Nothing here opens
a camera: the package holds no device handle, and the child refuses and records
camera device paths and capture libraries and holds every socket to loopback.
``usable`` must be stated, because an omitted boolean is false in most languages
across this wire; kinds are recorded, never filtered.

**A pass proves what the gateway reported through flyto-core**, not the identity
of any camera behind it, and every report says so in its own boundary notes.
Reports are written atomically into a new timestamped directory, only after every
check passes, never over an existing record. The read-only mode re-checks a
report on disk against its digest, contacting nothing — including
first-generation reports, whose shape is accepted exactly as written::

    python scripts/verify_real_camera_closed_loop.py --python PY \\
        --core-src /path/to/flyto-core/src --gateway http://127.0.0.1:9010 \\
        --zone arena
    python scripts/verify_real_camera_closed_loop.py \\
        --check-report results/.../report.json --expect-sha256 HEX
"""

from __future__ import annotations

import argparse
import asyncio
import builtins
import hashlib
import inspect
import ipaddress
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

CONTRACT = "flyto.modules-vision.real-camera-closed-loop.v1"
OBSERVATION_PATH = "/api/spaces/zone-camera/observation"
PACKAGE, DISTRIBUTION = "flyto_modules_vision", "flyto-modules-vision"
MODULE_ID, PLUGIN_NAME, ENTRY_POINT_GROUP = "vision.observe", "vision", "flyto.modules"
GATEWAY_URL_ENV = "FLYTO_VISION_GATEWAY_URL"
DEFAULT_REPORT_ROOT = "results/real-camera-closed-loop"
# One in-file child mode rather than a second script: a helper file's digest
# would have to be recorded separately to mean anything, and this way the
# verifier's own digest covers the code that ran.
CHILD_FLAG, SENTINEL = "--internal-child-run", "@@FLYTO_VISION_CHILD_RESULT@@"
CHILD_TIMEOUT_SECONDS, BUILD_TIMEOUT_SECONDS = 120.0, 900.0
CAMERA_PATHS = ("/dev/video", "/dev/camera", "/dev/media", "/dev/v4l", "/dev/vchiq")
CAMERA_MODULES = frozenset(
    "cv2 PIL Pillow picamera picamera2 imageio av vidgear pygame v4l2 v4l2py gphoto2".split()
)
HEX, MAX_URL_LENGTH, MAX_ZONE_LENGTH = "0123456789abcdef", 200, 64


class VerifierError(RuntimeError):
    """The run cannot be trusted, so it is not a run. Always fatal."""


def _require(condition: Any, message: str) -> None:
    """Refuse the run unless the condition holds. Every check below reads as one line."""
    if not condition:
        raise VerifierError(message)


def _is_digest(value: str) -> bool:
    """Whether a string is a lowercase SHA-256, the only digest form recorded here."""
    return len(value) == 64 and all(ch in HEX for ch in value)


# -- Inputs, checked before anything is built, installed or contacted. Each
# -- refusal is a way to aim a report saying "loopback" at something else.
def validate_gateway_base(raw: str) -> dict[str, Any]:
    """The loopback gateway base URL, or raise saying why it was refused."""
    _require(isinstance(raw, str) and raw.strip(), "gateway base URL is required")
    text = raw.strip().rstrip("/")
    _require(len(text) <= MAX_URL_LENGTH, "gateway base URL is implausibly long")
    printable = not any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text)
    _require(printable, "gateway base URL has whitespace or control characters")
    _require("%" not in text and "\\" not in text, "gateway base URL contains escapes")
    parts = urlsplit(text)
    _require(parts.scheme == "http", f"gateway scheme {parts.scheme!r} is refused; http only")
    anonymous = not (parts.username or parts.password or "@" in parts.netloc)
    _require(anonymous, "gateway base URL must carry no credentials")
    _require(not parts.query and not parts.fragment, "gateway URL must carry no query or fragment")
    _require(parts.path in ("", "/"), "gateway URL must carry no path; the path is contract")
    loopback = bool(parts.hostname) and _is_loopback(parts.hostname or "")
    _require(loopback, f"gateway host {parts.hostname!r} is missing or not loopback")
    try:
        port = parts.port
    except ValueError as exc:
        raise VerifierError(f"gateway port is not a number: {exc}") from exc
    _require(port is None or 1 <= port <= 65535, f"gateway port {port} is out of range")
    return {
        "base_url": text,
        "scheme": parts.scheme,
        "authority": parts.netloc,
        "observation_url": f"{text}{OBSERVATION_PATH}",
    }


def _is_loopback(host: str) -> bool:
    """Whether a host name or literal can only mean this machine."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def validate_zone(raw: str) -> str:
    """A zone taken literally; a repaired one would match the wrong evidence."""
    _require(isinstance(raw, str) and raw, "zone is required")
    _require(raw == raw.strip() and raw.strip(), "zone must not be blank or padded")
    _require(len(raw) <= MAX_ZONE_LENGTH, "zone is implausibly long")
    single = not any(ord(ch) < 0x20 or ord(ch) == 0x7F or ch.isspace() for ch in raw)
    _require(single, "zone must be a single token without control characters")
    return raw


def validate_toolchain(python_raw: str, core_raw: str) -> tuple[Path, Path]:
    """The interpreter and the flyto-core source directory, both explicit, or raise."""
    _require(python_raw and core_raw, "both --python and --core-src are required")
    python = Path(python_raw).expanduser()
    python = python if python.is_absolute() else python.resolve()
    runnable = python.is_file() and os.access(python, os.X_OK)
    _require(runnable, f"--python {python_raw!r} is not an executable file")
    core = Path(core_raw).expanduser().resolve()
    holds_core = core.is_dir() and (core / "core").is_dir()
    _require(holds_core, f"--core-src {core_raw!r} is not a directory holding 'core'")
    return python, core


def wheel_build_argv(python: Path, repo: Path, outdir: Path) -> list[str]:
    """The wheel build command. Isolation is off, so no index is consulted."""
    flags = ["-m", "build", "--wheel", "--no-isolation", "--outdir"]
    return [str(python), *flags, str(outdir), str(repo)]


def wheel_install_argv(python: Path, wheel: Path, target: Path) -> list[str]:
    """The install command: this wheel, that directory, nothing resolved or fetched."""
    flags = ["--no-deps", "--no-index", "--no-build-isolation", "--no-cache-dir"]
    return [str(python), "-m", "pip", "install", *flags, "--target", str(target), str(wheel)]


def offline_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """An environment in which a build or install cannot reach an index."""
    env = dict(os.environ if base is None else base)
    env.pop("PYTHONPATH", None)
    env.update(PIP_NO_INDEX="1", PIP_NO_INPUT="1", PYTHONNOUSERSITE="1")
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def child_env(
    target: Path, core_src: Path, gateway_base: str, base: dict[str, str] | None = None
) -> dict[str, str]:
    """The wheel and flyto-core and nothing else; PYTHONPATH is replaced, not extended.

    With ``PYTHONSAFEPATH`` stopping the interpreter adding the script's own
    directory, that replacement is what makes "the wheel was tested, not the
    working tree" true rather than merely intended.
    """
    env = dict(os.environ if base is None else base)
    env.pop("PYTHONPATH", None)
    env["PYTHONPATH"] = os.pathsep.join([str(target), str(core_src)])
    env.update(PYTHONSAFEPATH="1", PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    env["PIP_NO_INDEX"], env[GATEWAY_URL_ENV] = "1", gateway_base
    return env


def _run(
    argv: list[str], *, env: dict[str, str], timeout: float, what: str, allow_nonzero: bool = False
) -> subprocess.CompletedProcess:
    """Run a subprocess, or raise naming what failed and what it said."""
    try:
        done = subprocess.run(
            argv, env=env, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerifierError(f"{what} could not run: {exc}") from exc
    tail = (done.stderr or done.stdout or "").strip()[-800:]
    _require(done.returncode == 0 or allow_nonzero, f"{what} failed ({done.returncode}): {tail}")
    return done


def build_and_install(python: Path, repo: Path, scratch: Path) -> tuple[Path, Path]:
    """Build this checkout's wheel and install it in isolation; return both paths."""
    outdir, target = scratch / "wheel", scratch / "target"
    common = {"env": offline_env(), "timeout": BUILD_TIMEOUT_SECONDS}
    _run(wheel_build_argv(python, repo, outdir), what="wheel build", **common)
    wheels = sorted(outdir.glob("*.whl"))
    _require(len(wheels) == 1, f"expected exactly one built wheel, found {len(wheels)}")
    target.mkdir(parents=True, exist_ok=True)
    _run(wheel_install_argv(python, wheels[0], target), what="wheel install", **common)
    _require((target / PACKAGE).is_dir(), f"the wheel did not install {PACKAGE} into {target}")
    return wheels[0], target


def sha256_file(path: Path) -> str:
    """The SHA-256 of a file, as lowercase hex."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision(path: Path) -> str | None:
    """The checked-out commit at ``path``, or None where git cannot say."""
    argv = ["git", "-C", str(path), "rev-parse", "HEAD"]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (done.stdout.strip() or None) if done.returncode == 0 else None


def utc_stamp() -> str:
    """The current UTC time, in the form run directories are named with."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# -- What counts as a pass: one request to one URL, and evidence that states
# -- what it claims. These two functions are the whole judgement.
def check_requests(requests: list[Any], expected_url: str) -> None:
    """Exactly one HTTP GET, exactly to the contract URL, or raise.

    A second request means something reached past the step; another URL means
    the path stopped being contract; a non-GET means this stopped being a read.
    """
    _require(len(requests) == 1, f"expected exactly 1 HTTP request, the run made {len(requests)}")
    only = requests[0]
    _require(isinstance(only, dict), f"the recorded request is {type(only).__name__}, not an object")
    _require(only.get("method") == "GET", f"the one request was {only.get('method')!r}, not GET")
    url = only.get("url")
    _require(url == expected_url, f"the one request went to {url!r}, not {expected_url!r}")


def check_evidence(result: Any, zone: str) -> dict[str, Any]:
    """Selected evidence stating boolean ``usable`` true for this zone, or raise.

    Absent is refused, not guessed: an omitted boolean is false in most
    languages across this wire and would invert the field deciding whether a
    mission counts as proven. Kinds are recorded, never filtered.
    """
    _require(isinstance(result, dict), f"the module returned {type(result).__name__}, not an object")
    _require(not result.get("error"), f"the module refused: {str(result.get('error'))[:300]}")
    evidence = result.get("evidence")
    _require(isinstance(evidence, list), "the module returned no evidence list")
    _require(evidence, f"no usable evidence for zone {zone!r}; nothing here closed a loop")
    for index, item in enumerate(evidence):
        _require(isinstance(item, dict), f"evidence {index} is not an object")
        kind = item.get("kind") if isinstance(item, dict) else None
        _require(isinstance(kind, str) and kind.strip(), f"evidence {index} has no kind")
        _require("usable" in item, f"evidence {index} does not state usable; absent is not true")
        _require(item["usable"] is True, f"evidence {index} is not usable: {item['usable']!r}")
        seen = item.get("zone")
        _require(seen == zone, f"evidence {index} names zone {seen!r}, not {zone!r}")
    return {
        "zone": zone,
        "selected": len(evidence),
        "usable": sum(1 for item in evidence if item.get("usable") is True),
        "observed": result.get("observed"),
        "kinds": sorted({str(item["kind"]) for item in evidence}),
    }

# -- The report: built after validation, written once, never over anything.
BOUNDARY_NOTES = [
    "This run never opened a camera and never read image bytes or pixels. It made "
    "exactly one HTTP GET, to the configured loopback gateway, through flyto-core's "
    "public module registry. No credential value is read or recorded.",
    "The wheel built from this checkout was installed into a throwaway directory; the "
    "working tree was not importable. The gateway address is configuration, no step "
    "parameter can name a host, and the observation path is contract.",
    "A gateway-derived observation proves the gateway reported it. It does not prove "
    "the identity of any camera device behind that gateway, nor that a camera exists.",
]
REGISTRY_KEYS = ("plugins_discovered", "vision_plugin_modules", "capability",
                 "public_apis_used", "envelope_keys_unwrapped", "registry_import_path")
PACKAGE_KEYS = ("package_version", "installed_location", "imported_from")


def build_report(*, run_id: str, gateway: dict[str, Any], zone: str, child: dict[str, Any],
                 summary: dict[str, Any], wheel: dict[str, Any],
                 provenance: dict[str, Any]) -> dict[str, Any]:
    """The record of a run that already passed every check."""
    result = child.get("result") or {}
    return {
        "contract": CONTRACT, "run_id": run_id, "passed": True, "outcome": "passed",
        "params": {"zone": zone},
        "gateway": dict(
            gateway, observation_path=OBSERVATION_PATH, observation_path_is_contract=True,
            loopback_only=True, credentials_present=False, requests=child["requests"],
            request_count=len(child["requests"]),
            connect_hosts=sorted(set(child.get("connect_hosts", []))),
        ),
        "package": dict(
            {key: child.get(key) for key in PACKAGE_KEYS}, name=DISTRIBUTION,
            observation_path=OBSERVATION_PATH, imported_from_working_tree=False,
            wheel_filename=wheel["filename"], wheel_sha256=wheel["sha256"],
        ),
        "registry": dict(
            {key: child.get(key) for key in REGISTRY_KEYS},
            entry_point_group=ENTRY_POINT_GROUP, entry_point_name=PLUGIN_NAME,
        ),
        "result": result, "evidence": result.get("evidence", []), "summary": summary,
        "boundaries": {
            "camera_capture": False, "pixel_decode": False, "gateway_read": True,
            "loopback_only": True, "notes": list(BOUNDARY_NOTES),
            "camera_access_attempts": child.get("camera_attempts", []),
        },
        "provenance": provenance,
    }


def create_run_dir(root: Path, run_id: str) -> Path:
    """A new directory for this run, or raise rather than touch an old one."""
    run_dir = root / run_id
    _require(not run_dir.exists(), f"run directory {run_dir} already exists; refusing to reuse it")
    root.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(exist_ok=False)
    return run_dir


def write_report(run_dir: Path, report: dict[str, Any]) -> Path:
    """Write ``report.json`` atomically, only where none exists: a half-written
    report is indistinguishable from a report about a half-run loop."""
    final = run_dir / "report.json"
    _require(not final.exists(), f"{final} already exists; refusing to overwrite a record")
    body = json.dumps(report, indent=2, sort_keys=True) + "\n"
    kwargs = {"dir": run_dir, "prefix": ".report-", "suffix": ".tmp", "delete": False}
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", **kwargs)
    try:
        with handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, final)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
    return final


def validate_existing_report(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Check a report on disk against a digest, reading only and contacting nothing."""
    expected = (expected_sha256 or "").strip().lower()
    _require(_is_digest(expected), "--expect-sha256 must be 64 hexadecimal characters")
    _require(path.is_file(), f"no report at {path}")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    _require(actual == expected, f"report digest is {actual}, not the expected {expected}")
    try:
        report = json.loads(raw)
    except ValueError as exc:
        raise VerifierError(f"report at {path} is not JSON: {exc}") from exc
    check_report_invariants(report)
    return report


def report_requests(gateway: dict[str, Any]) -> list[Any]:
    """The requests a report records, in either generation's spelling.

    The first reports recorded ``requests_made`` as URL strings, GETs by
    construction. Reading that is not a weaker check — the same
    one-GET-to-the-contract-URL rule is applied — and refusing it would leave
    this repository's own record unauditable by the tool that audits records.
    """
    if isinstance(gateway.get("requests"), list):
        return list(gateway["requests"])
    made = gateway.get("requests_made")
    urls = isinstance(made, list) and all(isinstance(url, str) for url in made)
    _require(urls, "report records no requests, or not as URL strings")
    return [{"method": "GET", "url": url} for url in made]


def check_report_invariants(report: Any) -> None:
    """The claims a report must make about itself to be readable as a pass."""
    _require(isinstance(report, dict), "report is not an object")
    _require(report.get("contract") == CONTRACT, f"report states {report.get('contract')!r}")
    # A report carrying the boolean must state it true; one written before that
    # field existed must still say it passed, in the field it had.
    if "passed" in report:
        _require(report["passed"] is True, "report does not state passed: true")
    else:
        _require(report.get("outcome") == "passed", "report states neither passed nor outcome")
    gateway, package = report.get("gateway"), report.get("package")
    sections = isinstance(gateway, dict) and isinstance(package, dict)
    _require(sections, "report has no gateway or package section")
    stated = gateway.get("observation_path", package.get("observation_path"))
    _require(stated == OBSERVATION_PATH, f"report names observation path {stated!r}")
    base = str(gateway.get("base_url", ""))
    validate_gateway_base(base)
    requests = report_requests(gateway)
    count = gateway.get("request_count")
    _require(count is None or count == len(requests), "report's request count disagrees")
    check_requests(requests, f"{base}{OBSERVATION_PATH}")
    zone = (report.get("params") or {}).get("zone")
    _require(isinstance(zone, str) and zone, "report names no zone")
    check_evidence({"evidence": report.get("evidence")}, zone)
    _require(_is_digest(str(package.get("wheel_sha256", "")).lower()), "no wheel SHA-256")
    boundaries = report.get("boundaries") or {}
    for flag, value in (("camera_capture", False), ("pixel_decode", False),
                        ("gateway_read", True), ("loopback_only", True)):
        _require(boundaries.get(flag) is value, f"report's boundary {flag} is not {value}")
    _require(not boundaries.get("camera_access_attempts"), "report records a camera attempt")


# -- The child: the only code touching flyto-core, the wheel or the network.
def is_camera_path(target: Any) -> bool:
    """Whether a path being opened would be a camera or video device."""
    try:
        text = os.fspath(target)
    except TypeError:
        return False
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    return any(marker in str(text).lower() for marker in CAMERA_PATHS)


def is_camera_module(name: str) -> bool:
    """Whether an import would pull in a capture or pixel-decoding library."""
    return str(name).split(".", 1)[0] in CAMERA_MODULES


def _is_inside(candidate: str, directory: str) -> bool:
    """Whether a file really lives under a directory, symlinks resolved."""
    try:
        return Path(candidate).resolve().is_relative_to(Path(directory).resolve())
    except (OSError, ValueError):
        return False


def install_guards(state: dict[str, Any]) -> None:
    """Make "this cannot open a camera" observable, not merely documented."""
    real_import, real_connect = builtins.__import__, socket.socket.connect

    def refuse_devices(real: Any, label: str) -> Any:
        """Wrap an opener so a camera device is recorded and refused."""
        def guarded(path: Any, *args: Any, **kwargs: Any) -> Any:
            if is_camera_path(path):
                state["camera_attempts"].append(f"{label}:{path}")
                raise PermissionError(f"this verifier refuses camera device {path!r}")
            return real(path, *args, **kwargs)

        return guarded

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        """import, except that a capture library is recorded and refused."""
        if is_camera_module(name):
            state["camera_attempts"].append(f"import:{name}")
            raise ImportError(f"this verifier refuses the capture library {name!r}")
        return real_import(name, *args, **kwargs)

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        """connect(), recording the host and refusing anything but loopback."""
        host = address[0] if isinstance(address, tuple) and address else ""
        state["connect_hosts"].append(str(host))
        if not _is_loopback(str(host)):
            raise PermissionError(f"this verifier refuses a connection to {host!r}")
        return real_connect(self, address)

    builtins.open = refuse_devices(builtins.open, "open")
    os.open = refuse_devices(os.open, "os.open")
    builtins.__import__, socket.socket.connect = guarded_import, guarded_connect


def recording_opener(real_urlopen: Any, state: dict[str, Any], allowed_url: str) -> Any:
    """Wrap urlopen so every request is recorded and only the contract one runs."""

    def opener(request: Any, *args: Any, **kwargs: Any) -> Any:
        """urlopen(), for the one URL this run is allowed to ask for."""
        url = getattr(request, "full_url", None) or str(request)
        method = request.get_method() if hasattr(request, "get_method") else "GET"
        state["requests"].append({"method": method, "url": url})
        if method != "GET" or url != allowed_url:
            raise PermissionError(f"this verifier refuses {method} {url}")
        return real_urlopen(request, *args, **kwargs)

    return opener


def resolve_registry(module: Any) -> Any:
    """flyto-core's public module registry, however that build exposes it."""
    for attribute in ("module_registry", "registry", "MODULE_REGISTRY"):
        candidate = getattr(module, attribute, None)
        if candidate is not None and hasattr(candidate, "execute"):
            return candidate
    factory = getattr(module, "ModuleRegistry", None)
    _require(factory is not None, "core.modules.registry exposes no ModuleRegistry")
    return factory()


def execute_through_registry(registry: Any, zone: str) -> dict[str, Any]:
    """Run `vision.observe` the way a host runs it, and report what happened."""
    used: list[str] = []

    def call(name: str, *args: Any) -> Any:
        """Reach one named public method, recording that the run used it."""
        method = getattr(registry, name, None)
        _require(method is not None, f"flyto-core's registry has no public {name}()")
        used.append(name)
        return method(*args)

    if hasattr(registry, "clear"):
        call("clear")
    call("discover_plugins")
    plugins = sorted(str(name) for name in (call("get_plugins") or []))
    _require(PLUGIN_NAME in plugins, f"discovered {plugins}; no {ENTRY_POINT_GROUP} entry point "
             f"registered {PLUGIN_NAME!r}")
    modules = sorted(str(name) for name in (call("get_plugin_modules", PLUGIN_NAME) or []))
    _require(MODULE_ID in modules, f"the {PLUGIN_NAME!r} plugin registered {modules}")
    capabilities = call("capabilities") or {}
    params: tuple[Any, ...] = (MODULE_ID, {"zone": zone})
    raw = call("execute", *(params + ({},) if _wants_context(registry) else params))
    if inspect.iscoroutine(raw):
        raw = asyncio.run(raw)
    result, unwrapped = unwrap_envelope(raw)
    return {
        "plugins_discovered": plugins, "vision_plugin_modules": modules,
        "capability": {MODULE_ID: list(capabilities.get(MODULE_ID, []) or [])},
        "public_apis_used": used, "envelope_keys_unwrapped": unwrapped, "result": result,
    }


def _wants_context(registry: Any) -> bool:
    """Whether ``registry.execute`` also takes a job context, asked not assumed."""
    try:
        return len(inspect.signature(registry.execute).parameters) >= 3
    except (TypeError, ValueError, AttributeError):
        return False


def unwrap_envelope(raw: Any) -> tuple[Any, list[str]]:
    """The step's own dict, out of whatever envelope the engine wrapped it in."""
    unwrapped: list[str] = []
    current = raw
    for _ in range(4):
        if not isinstance(current, dict) or "evidence" in current:
            break
        inner = [k for k in ("result", "data", "output", "value") if isinstance(current.get(k), dict)]
        if not inner:
            break
        unwrapped.append(inner[0])
        current = current[inner[0]]
    return current, unwrapped


def child_main(config_path: str) -> int:
    """Do the one real thing: the installed wheel, flyto-core, and one GET."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    state: dict[str, Any] = {"requests": [], "connect_hosts": [], "camera_attempts": []}
    payload: dict[str, Any] = {"ok": False}
    try:
        import urllib.request

        install_guards(state)
        # Patched before the package is imported: fetch_observations binds urlopen
        # as a default argument at definition time, so a later patch counts nothing.
        urllib.request.urlopen = recording_opener(
            urllib.request.urlopen, state, config["observation_url"]
        )

        import flyto_modules_vision as installed

        imported = getattr(installed, "__file__", "") or ""
        wheel_only = _is_inside(imported, config["target"])
        _require(wheel_only, f"{PACKAGE} was imported from {imported}, not the wheel")
        path_is_contract = installed.OBSERVATION_PATH == OBSERVATION_PATH
        _require(path_is_contract, f"installed path is {installed.OBSERVATION_PATH!r}")

        import core.modules.registry as registry_module

        payload = {
            "ok": True, "package_version": getattr(installed, "__version__", None),
            "installed_location": str(config["target"]), "imported_from": imported,
            "registry_import_path": "core.modules.registry",
            **execute_through_registry(resolve_registry(registry_module), config["zone"]),
        }
    except BaseException as exc:  # reported to the parent, which decides
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    payload.update(state)
    # default=str so a child that cannot serialise its answer still reports:
    # that is a different failure from a child that never ran.
    sys.stdout.write(SENTINEL + json.dumps(payload, default=str) + "\n")
    sys.stdout.flush()
    return 0 if payload.get("ok") else 1


def read_child_payload(stdout: str, stderr: str = "", returncode: int = 0) -> dict[str, Any]:
    """The child's one JSON line, or raise saying it did not report."""
    for line in reversed(stdout.splitlines()):
        if line.startswith(SENTINEL):
            try:
                return json.loads(line[len(SENTINEL) :])
            except ValueError as exc:
                raise VerifierError(f"the child's result was not JSON: {exc}") from exc
    tail = (stderr or stdout or "").strip()[-800:]
    raise VerifierError(f"the child reported no result (exit {returncode}): {tail}")


def build_parser() -> argparse.ArgumentParser:
    """The command line. Every input is explicit; none has a host default."""
    description = "Run vision.observe from this tree's wheel through flyto-core."
    parser = argparse.ArgumentParser(prog=Path(__file__).name, description=description)
    add = parser.add_argument
    add("--python", default="", help="interpreter used to build, install and run")
    add("--core-src", default="", help="flyto-core 'src' directory")
    add("--gateway", default="", help="loopback base URL, e.g. http://127.0.0.1:9010")
    add("--zone", default="", help="zone the observation must name")
    add("--report-root", default=DEFAULT_REPORT_ROOT, help="where run directories are created")
    add("--check-report", default="", help="validate an existing report, read only")
    add("--expect-sha256", default="", help="the digest that report must have")
    add(CHILD_FLAG, dest="child", default="", help=argparse.SUPPRESS)
    return parser


def run_verification(args: argparse.Namespace) -> Path:
    """One live run, from wheel build to a written report; returns the report path."""
    repo = Path(__file__).resolve().parent.parent
    python, core_src = validate_toolchain(args.python, args.core_src)
    gateway, zone = validate_gateway_base(args.gateway), validate_zone(args.zone)
    started = utc_stamp()
    scratch = Path(tempfile.mkdtemp(prefix="flyto-vision-verify-")).resolve()
    try:
        wheel, target = build_and_install(python, repo, scratch)
        config = scratch / "child.json"
        config.write_text(json.dumps({
            "zone": zone, "observation_url": gateway["observation_url"], "target": str(target),
        }), encoding="utf-8")
        done = _run(
            [str(python), str(Path(__file__).resolve()), CHILD_FLAG, str(config)],
            env=child_env(target, core_src, gateway["base_url"]),
            timeout=CHILD_TIMEOUT_SECONDS, what="the closed-loop child run", allow_nonzero=True,
        )
        child = read_child_payload(done.stdout, done.stderr, done.returncode)
        wheel_info = {"filename": wheel.name, "sha256": sha256_file(wheel)}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    attempts = child.get("camera_attempts")
    _require(not attempts, f"the run tried to reach a camera: {attempts}")
    _require(child.get("ok"), f"the closed loop did not complete: {child.get('error')}")
    check_requests(child.get("requests", []), gateway["observation_url"])
    summary = check_evidence(child.get("result"), zone)
    run_id = f"{started}-{secrets.token_hex(4)}"
    report = build_report(
        run_id=run_id, gateway=gateway, zone=zone, child=child, summary=summary, wheel=wheel_info,
        provenance={
            "checkout": str(repo), "checkout_revision": git_revision(repo),
            "core_src": str(core_src), "core_revision": git_revision(core_src.parent),
            "verifier": "scripts/verify_real_camera_closed_loop.py",
            "verifier_sha256": sha256_file(Path(__file__).resolve()),
            "python_executable": str(python), "python_version": sys.version,
            "platform": platform.platform(), "clock": "UTC",
            "started_utc": started, "finished_utc": utc_stamp(),
        },
    )
    return write_report(create_run_dir(Path(args.report_root), run_id), report)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Nonzero on any refusal, and nothing written on a refusal."""
    args = build_parser().parse_args(argv)
    if args.child:
        return child_main(args.child)
    try:
        if args.check_report:
            validate_existing_report(Path(args.check_report), args.expect_sha256)
            print(f"report {args.check_report} matches its digest and its contract")
            return 0
        print(f"passed; report written to {run_verification(args)}")
        return 0
    except VerifierError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
