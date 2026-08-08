"""The address is configuration, and a step may never carry one.

This is the rule the sibling robotics package guards with a test and states in
its AGENTS.md, and it is the rule the interim `http.get` approach broke: the
gateway URL lived in an operator-authored command in Firestore, so two rooms
with identical hardware needed two different workflows, and moving the backend
to another port meant editing every template that had ever mentioned it.
"""

from __future__ import annotations

import asyncio
import io
import json
import urllib.error

import pytest

from flyto_modules_vision.gateway import (
    DEFAULT_GATEWAY_URL,
    GATEWAY_URL_ENV,
    OBSERVATION_PATH,
    GatewayError,
    fetch_observations,
    gateway_url,
)
from flyto_modules_vision.modules import build_modules
from flyto_modules_vision.steps import MODULE_OBSERVE
from tests.test_registration import StandInBase


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _opener(payload, *, capture=None):
    def open_it(request, timeout=None):
        if capture is not None:
            capture.append(request.full_url)
        body = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
        return _Response(body.encode() if isinstance(body, str) else body)

    return open_it


def test_the_default_gateway_is_loopback(monkeypatch):
    """The job was dispatched to the machine with the camera; it is here."""
    monkeypatch.delenv(GATEWAY_URL_ENV, raising=False)
    assert gateway_url() == DEFAULT_GATEWAY_URL
    assert gateway_url().startswith("http://127.0.0.1")


def test_the_address_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv(GATEWAY_URL_ENV, "http://10.0.0.9:9100/")
    assert gateway_url() == "http://10.0.0.9:9100"


def test_the_path_is_contract_not_configuration(monkeypatch):
    """An operator who can set the path can point a step at any JSON at all."""
    monkeypatch.setenv(GATEWAY_URL_ENV, "http://10.0.0.9:9100")
    seen: list[str] = []
    fetch_observations(opener=_opener([], capture=seen))
    assert seen == [f"http://10.0.0.9:9100{OBSERVATION_PATH}"]


def test_no_parameter_can_name_a_host(monkeypatch):
    """The rule, enforced: the step ignores anything that looks like an address.

    A workflow carrying a host is bound to one machine, which is the exact
    duplication the capability model exists to remove.
    """
    monkeypatch.setenv(GATEWAY_URL_ENV, "http://127.0.0.1:9000")
    seen: list[str] = []
    monkeypatch.setattr(
        "flyto_modules_vision.modules.fetch_observations",
        lambda: fetch_observations(opener=_opener([], capture=seen)),
    )
    captured: dict[str, type] = {}

    def register_module(**meta):
        def decorate(cls):
            captured[meta["module_id"]] = cls
            return cls

        return decorate

    build_modules(StandInBase, register_module)
    hostile = {
        "url": "http://evil.example/steal",
        "gateway": "http://evil.example",
        "host": "evil.example",
        "base_url": "http://evil.example",
    }
    asyncio.run(captured[MODULE_OBSERVE](hostile, {}).run())
    assert seen == ["http://127.0.0.1:9000" + OBSERVATION_PATH]
    assert not any("evil.example" in url for url in seen)


def test_an_unreachable_gateway_says_where_it_looked():
    def refuse(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    with pytest.raises(GatewayError, match="no vision gateway at"):
        fetch_observations(opener=refuse)


def test_an_http_error_is_reported_with_its_code():
    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    with pytest.raises(GatewayError, match="HTTP 404"):
        fetch_observations(opener=refuse)


def test_an_html_error_page_is_not_mistaken_for_an_answer():
    """The failure the generic http.get approach could not catch."""
    with pytest.raises(GatewayError, match="did not return JSON"):
        fetch_observations(opener=_opener("<html><body>404</body></html>"))


def test_a_real_answer_comes_back_parsed():
    payload = [{"kind": "zone.overview", "usable": True}]
    assert fetch_observations(opener=_opener(payload)) == payload
