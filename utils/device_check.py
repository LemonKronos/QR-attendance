"""Silent duplicate-device detection.

After a successful check-in the student's browser stores a cookie such as
    20261106_2012345_2012346
meaning: "on 2026-11-06 this device was used for student 2012345 and 2012346".

A new check-in is suspicious only when the cookie is from TODAY and does not
already contain the student ID being submitted. A cookie from another day is
ignored, and the same student checking in twice from their own phone is fine.
"""

import hashlib

import streamlit as st

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


def load_browser_cookies() -> dict:
    """Read the browser's cookies from inside the browser.

    st.context.cookies only sees cookies sent when the page's websocket opens,
    and on Streamlit Community Cloud it often misses cookies that were set by
    JavaScript (it works on a local run, which is why the flag worked locally
    but not online). Reading document.cookie in the browser avoids that.

    Call this while the page is being drawn (not inside a button handler). The
    first run returns an empty dict; the browser answers a moment later and
    Streamlit re-runs the script automatically with the real cookies.
    """
    try:
        import extra_streamlit_components as stx

        cookies = stx.CookieManager(key="device_cookie_reader").get_all(key="device_cookie_reader_all")
        return dict(cookies) if cookies else {}
    except Exception:
        return {}


def read_device_cookie(cookie_name: str, browser_cookies: dict) -> str:
    """Browser value first; the old server-side header is only a fallback."""
    browser_value = browser_cookies.get(cookie_name)
    if browser_value:
        return str(browser_value)
    return st.context.cookies.get(cookie_name, "")
