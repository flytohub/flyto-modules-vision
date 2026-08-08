"""Asking the vision gateway on this machine what it can see.

A step never names a machine. The job it belongs to was already dispatched to a
device, so this code runs on the host holding the camera, and the gateway is on
loopback. That is what lets two rooms with identical hardware share one authored
workflow instead of two copies differing only by address.

The address is configuration rather than a parameter for the same reason it is
in the robotics package: a workflow carrying a host is bound to one machine,
which is the duplication the capability model exists to remove, just wearing a
URL instead of a device id. It is also what makes the robot's own camera a
setting rather than a rewrite — the same step, pointed at a different gateway.

**This never opens a camera.** It reads what a gateway already observed. A
mission cannot make a lens fire by asking twice, and a package that cannot
drive hardware cannot be talked into driving it.

Only the standard library is used, so installing this package pulls nothing in.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_GATEWAY_URL = "http://127.0.0.1:9000"
GATEWAY_URL_ENV = "FLYTO_VISION_GATEWAY_URL"

# The path is contract, not configuration. An operator who can point a step at
# an arbitrary path can point it at anything that returns JSON, and the step
# would report whatever came back as evidence.
OBSERVATION_PATH = "/api/spaces/zone-camera/observation"

# A loopback request answers immediately or not at all. Long enough to survive
# a busy event loop, short enough that a wedged gateway fails the step rather
# than holding the job open.
REQUEST_TIMEOUT_SECONDS = 5.0


class GatewayError(RuntimeError):
    """The vision gateway could not be reached, or answered unusably."""


def gateway_url() -> str:
    return (os.environ.get(GATEWAY_URL_ENV) or DEFAULT_GATEWAY_URL).rstrip("/")


def fetch_observations(*, opener=urllib.request.urlopen) -> Any:
    """Whatever the gateway said, parsed but not yet trusted.

    Returned raw so the caller decides what counts. Validation lives in
    :mod:`observation` because "could we reach it" and "did it answer with
    evidence" are different failures and an operator needs to tell them apart.
    """
    url = f"{gateway_url()}{OBSERVATION_PATH}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise GatewayError(f"vision gateway at {url} answered HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise GatewayError(f"no vision gateway at {url}: {exc.reason}") from exc

    try:
        return json.loads(payload)
    except (ValueError, TypeError) as exc:
        # An HTML error page parses as neither, and this is where that is
        # caught. Reported as the gateway's fault rather than the step's,
        # because the step did exactly what it was told.
        raise GatewayError(f"vision gateway at {url} did not return JSON") from exc
