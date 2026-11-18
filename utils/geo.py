"""Browser geolocation for Streamlit (a tiny custom component, no extra package).

Usage (two-step, because the browser answers asynchronously):

    1. A button handler does   st.session_state.geo_nonce += 1   and reruns.
    2. On every run, call      result = geo.locate(key, st.session_state.geo_nonce)
       It returns None until the browser has answered THAT request, then a
       GeoResult. Compare against the nonce you are waiting for.

Call it at the same place on every run (fixed key), like the device component.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components

_COMPONENT_DIRECTORY = Path(__file__).resolve().parent.parent / "components" / "geo_locator"
_geo_component = components.declare_component("geo_locator", path=str(_COMPONENT_DIRECTORY))

DEFAULT_TIMEOUT_MS = 15000


@dataclass(frozen=True)
class GeoResult:
    status: str  # "ok", "denied", "timeout", "unavailable", "unsupported"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None


def locate(key: str, nonce: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Optional[GeoResult]:
    raw = _geo_component(nonce=nonce, timeout_ms=timeout_ms, key=key, default=None)
    if nonce <= 0 or not isinstance(raw, dict):
        return None
    try:
        if int(raw.get("nonce", -1)) != nonce:
            return None  # an older answer; still waiting for the current one
    except (TypeError, ValueError):
        return None
    return GeoResult(
        status=str(raw.get("status", "unavailable")),
        latitude=raw.get("lat"),
        longitude=raw.get("lon"),
        accuracy=raw.get("accuracy"),
    )
