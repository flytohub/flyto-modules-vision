"""A narrow Python device-executor provider for ``vision.observe``.

The provider is deliberately an observation reader, not a camera driver.  Job
data cannot select an address or a source, and nothing returned by the gateway
crosses this boundary unless it is part of the closed evidence shape below.
"""

from __future__ import annotations

import os
import re
from typing import Any
import urllib.request
from urllib.parse import urlsplit

from .gateway import GATEWAY_URL_ENV, OBSERVATION_PATH, GatewayError, fetch_observations
from .observation import MAX_OBSERVATIONS, ObservationError, parse

CONTRACT_VERSION = "device-executor-v1"
PROVIDER = "flyto-modules-vision"
MODULE_ID = "vision.observe"
ENTRY_POINT = "flyto_modules_vision.device_executor:executor"

EXPECTED_PROVIDER_ENV = "FLYTO_VISION_EXPECTED_PROVIDER"
EXPECTED_SOURCE_ID_ENV = "FLYTO_VISION_EXPECTED_SOURCE_ID"
MAX_IDENTIFIER_LENGTH = 128
MAX_DETAIL_LENGTH = 500
MAX_GATEWAY_RESPONSE_BYTES = 256 * 1024

_IDENTIFIER = re.compile(
    rf"[A-Za-z0-9][A-Za-z0-9._-]{{0,{MAX_IDENTIFIER_LENGTH - 1}}}\Z"
)
_REQUEST_KEYS = frozenset({"contract_version", "module_id", "params"})
_PREPARED_KEYS = frozenset({"contract_version", "module_id", "params"})
_EVIDENCE_KEYS = frozenset({"kind", "usable", "detail", "zone", "source"})


class ProviderRequestError(ValueError):
    """The registry-validated request is not safe for this provider."""


class ProviderConfigError(RuntimeError):
    """Local provider configuration is not safe to use."""


def _safe_identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _manifest() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "provider": PROVIDER,
        "module_ids": [MODULE_ID],
        "transport": "python_entry_point",
        "entry_point": ENTRY_POINT,
    }


def _prepare(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != _REQUEST_KEYS:
        raise ProviderRequestError("request_invalid")
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ProviderRequestError("request_invalid")
    if request.get("module_id") != MODULE_ID:
        raise ProviderRequestError("request_invalid")
    params = request.get("params")
    if not isinstance(params, dict) or not set(params).issubset({"zone"}):
        raise ProviderRequestError("request_invalid")
    zone = params.get("zone")
    if zone is not None and not _safe_identifier(zone):
        raise ProviderRequestError("request_invalid")
    prepared_params = {} if zone is None else {"zone": zone}
    return {
        "contract_version": CONTRACT_VERSION,
        "module_id": MODULE_ID,
        "params": prepared_params,
    }


def _gateway_config() -> str:
    raw = os.environ.get(GATEWAY_URL_ENV, "http://127.0.0.1:9000")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ProviderConfigError("configuration_invalid") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or port is None
        or not 1 <= port <= 65535
        or parsed.path
        or parsed.query
        or parsed.fragment
        or raw != f"http://127.0.0.1:{port}"
    ):
        raise ProviderConfigError("configuration_invalid")
    return raw


def _identity_config() -> tuple[str, str] | None:
    provider = os.environ.get(EXPECTED_PROVIDER_ENV)
    source_id = os.environ.get(EXPECTED_SOURCE_ID_ENV)
    if provider is None and source_id is None:
        return None
    if not _safe_identifier(provider) or not _safe_identifier(source_id):
        raise ProviderConfigError("configuration_invalid")
    return provider, source_id


def _result(status: str, reason_code: str, detail: str, evidence: list[dict[str, Any]]):
    return {
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "reason_code": reason_code,
        "detail": detail,
        "evidence": evidence,
    }


def _raw_items(payload: Any) -> list[Any]:
    if isinstance(payload, dict):
        items = payload.get("evidence")
    else:
        items = payload
    if not isinstance(items, list):
        raise ObservationError("observation payload is invalid")
    return items


def _validate_raw_evidence(payload: Any) -> None:
    """Reject values the shared parser would otherwise trim or truncate."""
    for raw in _raw_items(payload):
        if not isinstance(raw, dict):
            raise ObservationError("observation payload is invalid")
        detail = raw.get("detail")
        if "detail" in raw and (
            not isinstance(detail, str)
            or not detail
            or len(detail) > MAX_DETAIL_LENGTH
            or not detail.isascii()
            or not detail.isprintable()
            or detail != detail.strip()
        ):
            raise ObservationError("observation evidence is invalid")


def _closed_evidence(item: dict[str, Any]) -> dict[str, Any]:
    if not set(item).issubset(_EVIDENCE_KEYS):
        raise ObservationError("observation evidence is invalid")
    kind = item.get("kind")
    if not _safe_identifier(kind):
        raise ObservationError("observation evidence is invalid")
    if item.get("usable") is not True:
        raise ObservationError("observation is unusable")
    out: dict[str, Any] = {"kind": kind, "usable": True}
    if "detail" in item:
        detail = item["detail"]
        if (
            not isinstance(detail, str)
            or not detail
            or len(detail) > MAX_DETAIL_LENGTH
            or not detail.isascii()
            or not detail.isprintable()
            or detail != detail.strip()
        ):
            raise ObservationError("observation evidence is invalid")
        out["detail"] = detail
    if "zone" in item:
        if not _safe_identifier(item["zone"]):
            raise ObservationError("observation evidence is invalid")
        out["zone"] = item["zone"]
    source = item.get("source")
    if not isinstance(source, dict) or set(source) != {"provider", "source_id"}:
        raise ObservationError("observation evidence is invalid")
    if not all(_safe_identifier(source.get(key)) for key in ("provider", "source_id")):
        raise ObservationError("observation evidence is invalid")
    out["source"] = dict(source)
    return out


class _BoundedResponse:
    def __init__(self, response: Any):
        self._response = response

    def __enter__(self):
        self._response.__enter__()
        return self

    def __exit__(self, *args):
        return self._response.__exit__(*args)

    def read(self) -> bytes:
        value = self._response.read(MAX_GATEWAY_RESPONSE_BYTES + 1)
        if not isinstance(value, bytes) or len(value) > MAX_GATEWAY_RESPONSE_BYTES:
            raise GatewayError("gateway_response_invalid")
        return value


def _guarded_opener(expected_url: str):
    used = False

    def open_once(request: Any, timeout: float | None = None):
        nonlocal used
        if used or request.full_url != expected_url:
            raise GatewayError("gateway_request_invalid")
        used = True
        response = urllib.request.urlopen(request, timeout=timeout)
        content_length = response.headers.get("Content-Length")
        try:
            oversized = content_length is not None and int(content_length) > MAX_GATEWAY_RESPONSE_BYTES
        except (TypeError, ValueError) as exc:
            response.close()
            raise GatewayError("gateway_response_invalid") from exc
        if oversized:
            response.close()
            raise GatewayError("gateway_response_invalid")
        return _BoundedResponse(response)

    return open_once


def _prepared_zone(prepared: Any) -> str | None:
    if not isinstance(prepared, dict) or set(prepared) != _PREPARED_KEYS:
        raise ProviderRequestError("prepared_invalid")
    if prepared.get("contract_version") != CONTRACT_VERSION or prepared.get("module_id") != MODULE_ID:
        raise ProviderRequestError("prepared_invalid")
    params = prepared.get("params")
    if not isinstance(params, dict) or not set(params).issubset({"zone"}):
        raise ProviderRequestError("prepared_invalid")
    zone = params.get("zone")
    if zone is not None and not _safe_identifier(zone):
        raise ProviderRequestError("prepared_invalid")
    return zone


def _execute(prepared: Any) -> dict[str, Any]:
    try:
        zone = _prepared_zone(prepared)
    except ProviderRequestError:
        return _result("refused", "prepared_invalid", "prepared request refused", [])
    try:
        gateway = _gateway_config()
        expected = _identity_config()
    except ProviderConfigError:
        return _result("refused", "configuration_invalid", "provider configuration refused", [])

    try:
        expected_url = gateway + OBSERVATION_PATH
        payload = fetch_observations(opener=_guarded_opener(expected_url))
        _validate_raw_evidence(payload)
        observations = parse(payload)
        evidence = [_closed_evidence(item) for item in observations if item["usable"]]
    except GatewayError:
        return _result("failed", "gateway_unavailable", "observation gateway unavailable", [])
    except (ObservationError, TypeError, ValueError):
        return _result("refused", "observation_invalid", "observation refused", [])

    if zone is not None:
        evidence = [item for item in evidence if item.get("zone") == zone]
    if expected is not None:
        wanted_provider, wanted_source_id = expected
        evidence = [
            item
            for item in evidence
            if item["source"]
            == {"provider": wanted_provider, "source_id": wanted_source_id}
        ]
        if not evidence:
            return _result("refused", "source_mismatch", "observation source refused", [])
    if not evidence:
        return _result("refused", "no_usable_evidence", "no usable observation", [])
    if len(evidence) > MAX_OBSERVATIONS:
        return _result("refused", "observation_invalid", "observation refused", [])
    return _result("succeeded", "ok", "observation accepted", evidence)


class _Executor:
    manifest = staticmethod(_manifest)
    prepare = staticmethod(_prepare)
    execute = staticmethod(_execute)


executor = _Executor()

__all__ = ["ProviderConfigError", "ProviderRequestError", "executor"]
