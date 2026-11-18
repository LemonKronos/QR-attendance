"""Silent duplicate-device detection.

After a successful check-in the student's browser stores a cookie such as
    20261106_2012345_2012346
meaning: "on 2026-11-06 this device was used for student 2012345 and 2012346".

COMBINED SIGNALS. The same "date_id_id" value is kept in two places (cookie and
localStorage), because a browser may block one and not the other. A third,
server-side signal catches private/incognito windows: the same IP address AND
the same device signature already used for a different student ID today.
The IP address alone is never a signal (a whole classroom shares the campus
Wi-Fi's public IP). Nothing here blocks anyone; the sheet gets a flag.

A new check-in is suspicious only when the cookie is from TODAY and does not
already contain the student ID being submitted. A cookie from another day is
ignored, and the same student checking in twice from their own phone is fine.
"""

import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils import clock

COOKIE_NAME_PREFIX = "attended_"
COOKIE_SEPARATOR = "_"
COOKIE_LIFETIME_SECONDS = 2 * 24 * 60 * 60


def get_today_date_code() -> str:
    return clock.now().strftime("%Y%m%d")


def get_cookie_name(class_name: str) -> str:
    # Class names may contain spaces or accents, which are not valid in cookie
    # names, so the name is built from a hash of the class name instead.
    class_name_hash = hashlib.sha1(class_name.encode("utf-8")).hexdigest()[:10]
    return f"{COOKIE_NAME_PREFIX}{class_name_hash}"


def get_student_ids_recorded_today(cookie_value: str, today_date_code: str) -> list:
    if not cookie_value:
        return []

    cookie_parts = cookie_value.split(COOKIE_SEPARATOR)
    recorded_date_code, recorded_student_ids = cookie_parts[0], cookie_parts[1:]

    if recorded_date_code != today_date_code:
        return []
    return [student_id for student_id in recorded_student_ids if student_id]


def should_flag_duplicate_device(cookie_value: str, today_date_code: str, student_id: str) -> bool:
    recorded_student_ids = get_student_ids_recorded_today(cookie_value, today_date_code)
    if not recorded_student_ids:
        return False
    return student_id not in recorded_student_ids


def get_other_student_ids_today(cookie_value: str, today_date_code: str, student_id: str) -> list:
    """IDs that already checked in from this device today, excluding this student."""
    return [
        recorded_id
        for recorded_id in get_student_ids_recorded_today(cookie_value, today_date_code)
        if recorded_id != student_id
    ]


def build_cookie_value(previous_cookie_value: str, today_date_code: str, student_id: str) -> str:
    recorded_student_ids = get_student_ids_recorded_today(previous_cookie_value, today_date_code)
    if student_id not in recorded_student_ids:
        recorded_student_ids.append(student_id)
    return COOKIE_SEPARATOR.join([today_date_code] + recorded_student_ids)


_COMPONENT_DIRECTORY = Path(__file__).resolve().parent.parent / "components" / "device_cookie"
_device_cookie_component = components.declare_component(
    "device_cookie", path=str(_COMPONENT_DIRECTORY)
)


@dataclass(frozen=True)
class DeviceInfo:
    loaded: bool
    cookie_value: str = ""
    storage_value: str = ""
    fingerprint: str = ""


def load_device_info(cookie_name: str) -> DeviceInfo:
    """Read this device's cookie, localStorage item and signature in the browser.

    st.context.cookies only sees cookies sent when the page's websocket opens,
    and on Streamlit Community Cloud it often misses cookies set by JavaScript
    (it works on a local run, which is why the flag worked locally but not
    online). Reading document.cookie in the browser avoids that.

    Call this ONCE per run, at the same place on the page, as soon as the
    class is known (before the student types anything). The first run returns
    loaded=False; the browser answers a moment later, Streamlit re-runs the
    script once, and from then on the values are available. Because the
    student spends many seconds typing, it is always loaded by the time they
    press send.
    """
    result = _device_cookie_component(
        cookie_name=cookie_name, key="device_cookie_reader", default=None
    )
    if isinstance(result, dict) and result.get("loaded"):
        return DeviceInfo(
            loaded=True,
            cookie_value=str(result.get("value", "")),
            storage_value=str(result.get("storage_value", "")),
            fingerprint=str(result.get("fingerprint", "")),
        )
    return DeviceInfo(loaded=False)


def read_header_cookie(cookie_name: str) -> str:
    """Old server-side way. Only a fallback: unreliable on Streamlit Cloud."""
    return st.context.cookies.get(cookie_name, "")


def get_client_ip() -> str:
    """Public IP of the student's connection (first X-Forwarded-For entry)."""
    try:
        forwarded_for = st.context.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return str(getattr(st.context, "ip_address", "") or "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Server-side memory of today's check-ins (IP + device signature).
# Kept only for the current day and never written to the Google Sheet.
# ---------------------------------------------------------------------------

_log_lock = threading.Lock()
_todays_checkins = {}  # (class key, date code) -> list of (student_id, ip, fingerprint)


def _class_key(class_name: str) -> str:
    return " ".join(class_name.split()).casefold()


def remember_checkin(class_name: str, student_id: str, ip: str, fingerprint: str) -> None:
    if not ip or not fingerprint:
        return
    today = get_today_date_code()
    with _log_lock:
        for stale_key in [k for k in _todays_checkins if k[1] != today]:
            del _todays_checkins[stale_key]
        entries = _todays_checkins.setdefault((_class_key(class_name), today), [])
        if (student_id, ip, fingerprint) not in entries:
            entries.append((student_id, ip, fingerprint))


def _students_with_same_ip_and_signature(class_name: str, student_id: str, ip: str, fingerprint: str) -> list:
    if not ip or not fingerprint:
        return []
    key = (_class_key(class_name), get_today_date_code())
    with _log_lock:
        entries = list(_todays_checkins.get(key, []))
    matches = []
    for other_id, other_ip, other_fingerprint in entries:
        if other_id != student_id and other_ip == ip and other_fingerprint == fingerprint:
            if other_id not in matches:
                matches.append(other_id)
    return matches


def collect_duplicate_signals(
    class_name: str, student_id: str, device: DeviceInfo, fallback_cookie_value: str, ip: str
) -> dict:
    """Which OTHER student IDs does this device look like, and why?

    Returns {other_student_id: [reasons]}; empty when nothing is suspicious.
    """
    today = get_today_date_code()
    signals = {}

    def add(other_id: str, reason: str) -> None:
        reasons = signals.setdefault(other_id, [])
        if reason not in reasons:
            reasons.append(reason)

    cookie_value = device.cookie_value if device.loaded else fallback_cookie_value
    for other_id in get_other_student_ids_today(cookie_value, today, student_id):
        add(other_id, "cookie")
    for other_id in get_other_student_ids_today(device.storage_value, today, student_id):
        add(other_id, "browser storage")
    for other_id in _students_with_same_ip_and_signature(class_name, student_id, ip, device.fingerprint):
        add(other_id, "same IP + device signature")
    return signals


def build_device_value(device: DeviceInfo, fallback_cookie_value: str, student_id: str) -> str:
    """New value to save (in BOTH cookie and localStorage) after a successful check-in."""
    today = get_today_date_code()
    cookie_base = device.cookie_value if device.loaded else fallback_cookie_value
    known_ids = get_student_ids_recorded_today(cookie_base, today)
    for stored_id in get_student_ids_recorded_today(device.storage_value, today):
        if stored_id not in known_ids:
            known_ids.append(stored_id)
    if student_id not in known_ids:
        known_ids.append(student_id)
    return COOKIE_SEPARATOR.join([today] + known_ids)
