"""In-memory attendance sessions and the GPS check.

Everything here lives in server memory only (the app has no database besides
the Google Sheet). It holds, per class:

  * the session id and its expiry (10 minutes; "Renew" restarts the clock),
  * the lecturer's location (set from the teacher page),
  * the location every student reported on their last "Gửi" press.

GPS FLAGS ARE DERIVED, NOT STORED WITH THE LOCATIONS.
The flag text ends up in the Google Sheet cell. Whenever a location changes
(student sends again, lecturer sets/updates the location) the GPS flags are
recomputed from the stored locations and replaced in the sheet. When the
session expires or is stopped, ALL coordinates are deleted from memory; the
flag text already written to the sheet stays.

Rules (agreed with the lecturer):
  * No lecturer location  -> nobody is flagged for GPS.
  * Nobody is ever blocked, only flagged with a plain-language reason.
  * Radius 500 m. The distance is reduced by both devices' reported accuracy,
    so a poor laptop fix does not produce false "out of range" flags.
  * Renew keeps locations. Stop / natural expiry deletes them.
  * Deleting happens lazily (Streamlit has no timer): sweep_expired() runs on
    every page load and every second from the lecturer's live QR display.
"""

import logging
import math
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from utils import gsheets_api, security

logger = logging.getLogger(__name__)

GPS_RADIUS_METERS = 500
# Above this accuracy radius a location is too vague to judge anything.
GPS_LOW_ACCURACY_METERS = 1000

FLAG_OUT_OF_RANGE = "OUT_OF_RANGE"
FLAG_GPS_DENIED = "GPS_DENIED"
FLAG_LOW_ACCURACY = "GPS_LOW_ACCURACY"

STATUS_OK = "ok"

OUTCOME_SET = "set"
OUTCOME_KEPT_BETTER = "kept_better"
OUTCOME_NO_SESSION = "no_session"


@dataclass
class GeoFix:
    latitude: float
    longitude: float
    accuracy: float
    taken_at: float


@dataclass
class StudentGeo:
    status: str  # "ok", "denied", "timeout", "unavailable", "unsupported", "skipped"
    fix: Optional[GeoFix] = None


@dataclass
class ClassSession:
    class_name: str  # real tab name, used to write the Google Sheet
    session_id: str
    expires_at: float
    teacher_fix: Optional[GeoFix] = None
    students: dict = field(default_factory=dict)  # student_id -> StudentGeo


_lock = threading.RLock()
_sessions = {}  # normalized class name -> ClassSession
# Ids only (no personal data): lets a stopped/expired session's old QR links die.
_closed_session_ids = set()


def _key(class_name: str) -> str:
    return " ".join(class_name.split()).casefold()


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def _close_locked(key: str) -> None:
    session = _sessions.pop(key, None)
    if session is not None:
        _closed_session_ids.add(session.session_id)
        logger.info("Attendance session closed; location data deleted (class=%r)", key)


def sweep_expired() -> int:
    """Delete every expired session together with all its coordinates."""
    with _lock:
        expired_keys = [key for key, s in _sessions.items() if s.expires_at <= _now()]
        for key in expired_keys:
            _close_locked(key)
        return len(expired_keys)


def start_session(class_name: str) -> ClassSession:
    """Create a session, or RENEW the running one (keeps all locations)."""
    with _lock:
        sweep_expired()
        key = _key(class_name)
        session = _sessions.get(key)
        new_expiry = _now() + security.QR_VALIDITY_SECONDS
        if session is None:
            session = ClassSession(
                class_name=class_name,
                session_id=secrets.token_urlsafe(9),
                expires_at=new_expiry,
            )
            _sessions[key] = session
        else:
            session.expires_at = new_expiry
        return session


def stop_session(class_name: str) -> None:
    with _lock:
        _close_locked(_key(class_name))


def get_open_session(class_name: str) -> Optional[ClassSession]:
    with _lock:
        sweep_expired()
        return _sessions.get(_key(class_name))


def is_session_closed(session_id: str) -> bool:
    with _lock:
        return session_id in _closed_session_ids


# ---------------------------------------------------------------------------
# Distance + flag rules
# ---------------------------------------------------------------------------

def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = phi2 - phi1
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * earth_radius * math.asin(math.sqrt(a))


def _format_distance(meters: float) -> str:
    return f"{meters:.0f} m" if meters < 1000 else f"{meters / 1000:.1f} km"


def _flags_for(teacher_fix: Optional[GeoFix], student_geo: StudentGeo) -> list:
    if teacher_fix is None:
        return []  # no reference point: GPS is ignored for everybody

    if student_geo.status != STATUS_OK or student_geo.fix is None:
        return [f"{FLAG_GPS_DENIED}: no location from the student's device ({student_geo.status})"]

    fix = student_geo.fix
    if fix.accuracy > GPS_LOW_ACCURACY_METERS:
        return [f"{FLAG_LOW_ACCURACY}: ±{fix.accuracy:.0f} m, location too vague to verify"]

    distance = distance_meters(teacher_fix.latitude, teacher_fix.longitude, fix.latitude, fix.longitude)
    # Definitely outside only when even the best case (both errors in the
    # student's favour) is still beyond the radius.
    if distance - fix.accuracy - teacher_fix.accuracy > GPS_RADIUS_METERS:
        return [f"{FLAG_OUT_OF_RANGE}: about {_format_distance(distance)} from the lecturer (±{fix.accuracy:.0f} m)"]
    return []


def _build_student_geo(status: str, latitude, longitude, accuracy) -> StudentGeo:
    if status == STATUS_OK and latitude is not None and longitude is not None:
        fix = GeoFix(float(latitude), float(longitude), float(accuracy or 0.0), _now())
        return StudentGeo(STATUS_OK, fix)
    return StudentGeo(status if status != STATUS_OK else "unavailable", None)


# ---------------------------------------------------------------------------
# Student locations
# ---------------------------------------------------------------------------

def preview_gps_flags(class_name: str, status: str, latitude, longitude, accuracy) -> list:
    """The flags a student WOULD get right now. Changes nothing."""
    with _lock:
        session = get_open_session(class_name)
        if session is None:
            return []
        return _flags_for(session.teacher_fix, _build_student_geo(status, latitude, longitude, accuracy))


def record_student_location(
    class_name: str, student_id: str, status: str, latitude, longitude, accuracy
) -> Optional[list]:
    """Remember the student's latest location (replacing the previous one).

    Returns the student's current GPS flags, or None when no session is open
    (then nothing is stored).
    """
    with _lock:
        session = get_open_session(class_name)
        if session is None:
            return None
        student_geo = _build_student_geo(status, latitude, longitude, accuracy)
        session.students[student_id] = student_geo
        return _flags_for(session.teacher_fix, student_geo)


# ---------------------------------------------------------------------------
# Lecturer location
# ---------------------------------------------------------------------------

def set_teacher_location(
    class_name: str, latitude: float, longitude: float, accuracy: float, force: bool = False
) -> str:
    """Store the lecturer's location.

    A new fix replaces the old one only if it is at least as accurate (so a
    poor laptop fix cannot overwrite a good phone fix), unless force=True.
    """
    with _lock:
        session = get_open_session(class_name)
        if session is None:
            return OUTCOME_NO_SESSION
        old_fix = session.teacher_fix
        if old_fix is not None and accuracy > old_fix.accuracy and not force:
            return OUTCOME_KEPT_BETTER
        session.teacher_fix = GeoFix(float(latitude), float(longitude), float(accuracy), _now())
        return OUTCOME_SET


def get_teacher_status(class_name: str) -> dict:
    """Non-sensitive summary for the teacher page (no coordinates)."""
    with _lock:
        session = get_open_session(class_name)
        if session is None:
            return {"session_open": False}
        fix = session.teacher_fix
        return {
            "session_open": True,
            "has_location": fix is not None,
            "accuracy": fix.accuracy if fix else 0.0,
            "set_at": fix.taken_at if fix else 0.0,
            "students_with_location": sum(1 for g in session.students.values() if g.status == STATUS_OK),
            "students_total": len(session.students),
        }


def recompute_all_gps_flags(class_name: str):
    """Recompute every stored student's GPS flags and write them to the sheet."""
    with _lock:
        session = get_open_session(class_name)
        if session is None:
            return gsheets_api.AttendanceResult(True, "Không có phiên đang chạy")
        sheet_class_name = session.class_name
        flags_by_student = {
            student_id: _flags_for(session.teacher_fix, student_geo)
            for student_id, student_geo in session.students.items()
        }
    # The (slow) Google Sheets call happens outside the lock.
    return gsheets_api.apply_gps_flags(sheet_class_name, flags_by_student)
