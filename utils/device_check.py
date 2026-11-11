"""Silent duplicate-device detection.

After a successful check-in the student's browser stores a cookie such as
    20261106_2012345_2012346
meaning: "on 2026-11-06 this device was used for student 2012345 and 2012346".

A new check-in is suspicious only when the cookie is from TODAY and does not
already contain the student ID being submitted. A cookie from another day is
ignored, and the same student checking in twice from their own phone is fine.
"""

import datetime
import hashlib

COOKIE_NAME_PREFIX = "attended_"
COOKIE_SEPARATOR = "_"
COOKIE_LIFETIME_SECONDS = 2 * 24 * 60 * 60


def get_today_date_code() -> str:
    return datetime.date.today().strftime("%Y%m%d")


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


def build_cookie_value(previous_cookie_value: str, today_date_code: str, student_id: str) -> str:
    recorded_student_ids = get_student_ids_recorded_today(previous_cookie_value, today_date_code)
    if student_id not in recorded_student_ids:
        recorded_student_ids.append(student_id)
    return COOKIE_SEPARATOR.join([today_date_code] + recorded_student_ids)
