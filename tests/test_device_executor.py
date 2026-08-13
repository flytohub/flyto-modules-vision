from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
import zipfile

import pytest

from flyto_modules_vision import device_executor as provider
from flyto_modules_vision.gateway import GatewayError


def request(params=None):
    return {
        "contract_version": provider.CONTRACT_VERSION,
        "module_id": provider.MODULE_ID,
        "params": {} if params is None else params,
    }


def fresh(**changes):
    item = {
        "kind": "future.kind",
        "usable": True,
        "source": {"provider": "camera-provider", "source_id": "camera-source"},
    }
    item.update(changes)
    return [item]


def run(monkeypatch, payload, params=None):
    monkeypatch.setattr(provider, "fetch_observations", lambda **kwargs: payload)
    return provider.executor.execute(provider.executor.prepare(request(params)))


def test_manifest_and_checkout_entry_point_are_exact():
    assert provider.executor.manifest() == {
        "contract_version": "device-executor-v1",
        "provider": "flyto-modules-vision",
        "module_ids": ["vision.observe"],
        "transport": "python_entry_point",
        "entry_point": "flyto_modules_vision.device_executor:executor",
    }
    project = Path(__file__).parents[1] / "pyproject.toml"
    assert 'vision = "flyto_modules_vision.device_executor:executor"' in project.read_text()


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"contract_version": "device-executor-v0", "module_id": "vision.observe", "params": {}},
        {"contract_version": "device-executor-v1", "module_id": "vision.other", "params": {}},
        {**request(), "extra": True},
        {**request(), "params": []},
        request({"zone": "x", "host": "example.test"}),
        request({"url": "http://example.test"}),
        request({"zone": "a/b"}),
        request({"zone": "x" * 129}),
    ],
)
def test_prepare_fails_closed_with_stable_content_free_error(bad):
    with pytest.raises(provider.ProviderRequestError) as exc:
        provider.executor.prepare(bad)
    assert str(exc.value) == "request_invalid"


def test_prepare_is_detached_and_execute_only_accepts_its_output(monkeypatch):
    original = request({"zone": "bay"})
    prepared = provider.executor.prepare(original)
    original["params"]["zone"] = "other"
    result = run(monkeypatch, fresh(zone="bay"), {"zone": "bay"})
    assert result["status"] == "succeeded"
    assert provider.executor.execute({"zone": "bay"}) == {
        "contract_version": "device-executor-v1",
        "status": "refused",
        "reason_code": "prepared_invalid",
        "detail": "prepared request refused",
        "evidence": [],
    }
    assert prepared == {
        "contract_version": "device-executor-v1",
        "module_id": "vision.observe",
        "params": {"zone": "bay"},
    }
    json.loads(json.dumps(prepared))


def test_prepared_payload_matches_registry_json_validator_semantics():
    prepared = provider.executor.prepare(request({"zone": "bay"}))
    detached = json.loads(json.dumps(prepared, allow_nan=False))
    assert detached == prepared
    assert provider.executor.execute({**detached, "extra": True})["reason_code"] == "prepared_invalid"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:9000",
        "http://localhost:9000",
        "http://127.0.0.1",
        "http://127.0.0.1:0",
        "http://user:secret@127.0.0.1:9000",
        "http://127.0.0.1:9000/",
        "http://127.0.0.1:9000/path?secret=x",
    ],
)
def test_invalid_gateway_is_refused_before_fetch(monkeypatch, url):
    monkeypatch.setenv("FLYTO_VISION_GATEWAY_URL", url)
    monkeypatch.setattr(provider, "fetch_observations", lambda **kwargs: pytest.fail("network used"))
    result = provider.executor.execute(provider.executor.prepare(request()))
    assert result["reason_code"] == "configuration_invalid"
    assert result["evidence"] == []
    assert url not in json.dumps(result)


@pytest.mark.parametrize(
    "values",
    [("one", None), (None, "two"), ("bad/value", "two"), ("one", "x" * 129)],
)
def test_partial_or_invalid_expected_identity_fails_before_fetch(monkeypatch, values):
    for name, value in zip(
        (provider.EXPECTED_PROVIDER_ENV, provider.EXPECTED_SOURCE_ID_ENV), values
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    monkeypatch.setattr(provider, "fetch_observations", lambda **kwargs: pytest.fail("network used"))
    result = provider.executor.execute(provider.executor.prepare(request()))
    assert result["reason_code"] == "configuration_invalid"


def test_gateway_fault_is_fixed_and_private_data_free(monkeypatch):
    def fail(**kwargs):
        raise GatewayError("http://127.0.0.1:9000/private?token=secret")

    monkeypatch.setattr(provider, "fetch_observations", fail)
    result = provider.executor.execute(provider.executor.prepare(request()))
    assert result["status"] == "failed"
    assert result["reason_code"] == "gateway_unavailable"
    assert "secret" not in json.dumps(result)
    assert result["evidence"] == []


class _Response(io.BytesIO):
    headers: dict[str, str]

    def __init__(self, body: bytes, content_length: str | None = None):
        super().__init__(body)
        self.headers = {} if content_length is None else {"Content-Length": content_length}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def test_guarded_opener_rejects_url_drift_and_second_request(monkeypatch):
    calls = []

    def urlopen(request, timeout=None):
        calls.append(request.full_url)
        return _Response(b"[]")

    monkeypatch.setattr(provider.urllib.request, "urlopen", urlopen)
    opener = provider._guarded_opener(
        "http://127.0.0.1:9000/api/spaces/zone-camera/observation"
    )
    wrong = provider.urllib.request.Request("http://127.0.0.1:9000/wrong")
    with pytest.raises(GatewayError):
        opener(wrong)
    assert calls == []
    right = provider.urllib.request.Request(
        "http://127.0.0.1:9000/api/spaces/zone-camera/observation"
    )
    with opener(right) as response:
        assert response.read() == b"[]"
    with pytest.raises(GatewayError):
        opener(right)
    assert calls == [right.full_url]


@pytest.mark.parametrize("declared", [None, str(provider.MAX_GATEWAY_RESPONSE_BYTES + 1)])
def test_gateway_response_bytes_are_bounded(monkeypatch, declared):
    body = b"x" * (provider.MAX_GATEWAY_RESPONSE_BYTES + 1)
    monkeypatch.setattr(
        provider.urllib.request,
        "urlopen",
        lambda request, timeout=None: _Response(body, declared),
    )
    url = "http://127.0.0.1:9000/api/spaces/zone-camera/observation"
    opener = provider._guarded_opener(url)
    if declared is None:
        with opener(provider.urllib.request.Request(url)) as response:
            with pytest.raises(GatewayError):
                response.read()
    else:
        with pytest.raises(GatewayError):
            opener(provider.urllib.request.Request(url))


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"not_evidence": "private"},
        [],
        fresh(usable=False),
        fresh(usable=False, detail="camera_frame_stale"),
        [{"kind": "future.kind", "usable": True}],
    ],
)
def test_malformed_empty_stale_or_unusable_never_returns_evidence(monkeypatch, payload):
    result = run(monkeypatch, payload)
    assert result["status"] == "refused"
    assert result["evidence"] == []
    assert "private" not in json.dumps(result)


def test_one_fetch_zone_filter_open_kind_source_and_closed_evidence(monkeypatch):
    calls = 0

    def fetch(**kwargs):
        nonlocal calls
        calls += 1
        return fresh(
            zone="bay",
            source={"provider": "future-provider.v9", "source_id": "logical-7"},
            pixels="private-pixels",
            frame={"secret": True},
        ) + fresh(zone="hall", source={"provider": "other", "source_id": "hall"})

    monkeypatch.setattr(provider, "fetch_observations", fetch)
    result = provider.executor.execute(provider.executor.prepare(request({"zone": "bay"})))
    assert calls == 1
    assert result["evidence"] == [
        {
            "kind": "future.kind",
            "usable": True,
            "zone": "bay",
            "source": {"provider": "future-provider.v9", "source_id": "logical-7"},
        }
    ]
    assert "pixels" not in json.dumps(result)


def test_required_identity_is_exact_and_mismatch_returns_nothing(monkeypatch):
    monkeypatch.setenv(provider.EXPECTED_PROVIDER_ENV, "future-provider")
    monkeypatch.setenv(provider.EXPECTED_SOURCE_ID_ENV, "source-1")
    matching = fresh(source={"provider": "future-provider", "source_id": "source-1"})
    assert run(monkeypatch, matching)["status"] == "succeeded"
    mismatching = fresh(source={"provider": "future-provider", "source_id": "source-2"})
    result = run(monkeypatch, mismatching)
    assert result["reason_code"] == "source_mismatch"
    assert result["evidence"] == []
    assert "source-2" not in json.dumps(result)


def test_required_identity_selects_match_among_unrelated_sources(monkeypatch):
    monkeypatch.setenv(provider.EXPECTED_PROVIDER_ENV, "future-provider")
    monkeypatch.setenv(provider.EXPECTED_SOURCE_ID_ENV, "source-1")
    payload = fresh(source={"provider": "other", "source_id": "other"}) + fresh(
        source={"provider": "future-provider", "source_id": "source-1"}
    )
    result = run(monkeypatch, payload)
    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["source"]["source_id"] == "source-1"


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "bad kind"},
        {"zone": "bad/zone"},
        {"detail": " x"},
        {"detail": "x" * 501},
        {"source": {"provider": "bad/provider", "source_id": "one"}},
    ],
)
def test_contract_incompatible_evidence_fails_closed(monkeypatch, change):
    assert run(monkeypatch, fresh(**change))["evidence"] == []


def test_loopback_http_integration_returns_fresh_metadata(monkeypatch):
    payload = fresh(zone="bay", detail="clear")
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = json.dumps({"evidence": payload}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("the execution sandbox forbids binding a loopback socket")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("FLYTO_VISION_GATEWAY_URL", f"http://127.0.0.1:{server.server_port}")
    try:
        result = provider.executor.execute(provider.executor.prepare(request()))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert result["status"] == "succeeded"
    assert requests == ["/api/spaces/zone-camera/observation"]
    assert result["evidence"] == [
        {
            "kind": "future.kind",
            "usable": True,
            "detail": "clear",
            "zone": "bay",
            "source": {"provider": "camera-provider", "source_id": "camera-source"},
        }
    ]


def test_built_wheel_exposes_loadable_entry_point_without_src(tmp_path):
    root = Path(__file__).parents[1]
    out = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(out)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(out.glob("*.whl"))
    target = tmp_path / "target"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(target)
    script = """
import importlib.metadata, json, pathlib, sys
target = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))
eps = [ep for dist in importlib.metadata.distributions(path=[target])
       for ep in dist.entry_points if ep.group == 'flyto.device_executors']
assert len(eps) == 1
loaded = eps[0].load()
assert all(callable(getattr(loaded, name, None)) for name in ('manifest', 'prepare', 'execute'))
assert '/src' not in pathlib.Path(sys.modules[loaded.__class__.__module__].__file__).as_posix()
print(json.dumps(loaded.manifest(), sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script, str(target)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"contract_version": "device-executor-v1"' in completed.stdout
