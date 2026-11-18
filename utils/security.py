import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

import qrcode
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRET_KEY_PATH = PROJECT_ROOT / "secret.key"

# One attendance session (from creating the QR until it stops) lasts this long.
# "Renew" restarts this clock.
QR_VALIDITY_SECONDS = 600
# The QR on the projector changes every QR_ROTATION_SECONDS. The server accepts
# the current slot and the previous one, so a scan stays valid for 10-20 s.
# The window only applies to OPENING the page; afterwards the student may take
# STUDENT_FORM_SECONDS to type their details (no time pressure).
QR_ROTATION_SECONDS = 30
QR_ACCEPTED_PREVIOUS_SLOTS = 1
STUDENT_FORM_SECONDS = 600

# The 4-digit code shown next to the QR on the teacher screen.
SCREEN_CODE_PERIOD_SECONDS = 13
SCREEN_CODE_ACCEPTED_PREVIOUS = 1
SCREEN_CODE_LENGTH = 4

SIGNATURE_BYTE_LENGTH = 16

DEFAULT_TEACHER_PASSWORD = "admin123"
TEACHER_PASSWORD_ENVIRONMENT_VARIABLE = "TEACHER_PASSWORD"
APP_SECRET_KEY_ENVIRONMENT_VARIABLE = "APP_SECRET_KEY"


def _get_configured_secret(name: str) -> str:
    """Read a setting from an environment variable or Streamlit secrets.

    Accepted spellings in secrets (first match wins):
        TEACHER_PASSWORD = "..."            (top level)
        teacher_password = "..."            (top level, lower case)
        [app] TEACHER_PASSWORD / teacher_password = "..."
    """
    environment_value = os.environ.get(name, "").strip()
    if environment_value:
        return environment_value
    try:
        secrets = st.secrets
        containers = [secrets]
        app_section = secrets.get("app")
        if app_section is not None and hasattr(app_section, "get"):
            containers.append(app_section)
        for container in containers:
            for key in (name, name.lower()):
                value = container.get(key)
                if value:
                    return str(value).strip()
    except Exception:
        # Streamlit raises when no secrets.toml exists in local development.
        pass
    return ""


def _load_or_create_secret_key() -> bytes:
    configured_key = _get_configured_secret(APP_SECRET_KEY_ENVIRONMENT_VARIABLE)
    if configured_key:
        # Require exactly 32 random bytes represented as 64 hexadecimal chars.
        if len(configured_key) != 64:
            raise RuntimeError(
                "APP_SECRET_KEY must be exactly 64 hexadecimal characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        try:
            return bytes.fromhex(configured_key)
        except ValueError as error:
            raise RuntimeError("APP_SECRET_KEY must contain only hexadecimal characters.") from error

    # Local-development fallback. On Community Cloud, configure APP_SECRET_KEY
    # in App settings -> Secrets; the writable container filesystem is not the
    # source of truth for a signing key that must survive app restarts.
    if not SECRET_KEY_PATH.exists():
        try:
            with open(SECRET_KEY_PATH, "xb") as secret_key_file:
                secret_key_file.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
    return SECRET_KEY_PATH.read_bytes()


SECRET_KEY = _load_or_create_secret_key()


def _encode_base64_url(raw_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")


def _decode_base64_url(encoded_text: str) -> bytes:
    padding = "=" * (-len(encoded_text) % 4)
    return base64.urlsafe_b64decode(encoded_text + padding)


def _sign(message: str) -> str:
    full_digest = hmac.new(SECRET_KEY, message.encode("utf-8"), hashlib.sha256).digest()
    return _encode_base64_url(full_digest[:SIGNATURE_BYTE_LENGTH])


# ---------------------------------------------------------------------------
# QR tokens
#
# The token is only SIGNED (not encrypted): the class name and expiry time are
# not secret, but nobody can change them without the secret key. Keeping the
# token short makes the QR code much less dense and easier to scan from the
# back of a classroom.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TokenCheckResult:
    is_valid: bool
    class_name: str
    session_id: str
    session_expires_at: float
    message: str


def current_qr_slot(now: float = None) -> int:
    """Index of the current QR_ROTATION_SECONDS-long time slot."""
    return int((time.time() if now is None else now) // QR_ROTATION_SECONDS)


def generate_qr_token(class_name: str, session_id: str, session_expires_at: float) -> str:
    """Token for the CURRENT time slot. The teacher page calls this every slot."""
    payload = f"{int(session_expires_at)}|{current_qr_slot()}|{session_id}|{class_name}"
    encoded_payload = _encode_base64_url(payload.encode("utf-8"))
    return f"{encoded_payload}.{_sign(encoded_payload)}"


def validate_token(token: str) -> TokenCheckResult:
    def failure(message, class_name="", session_id="", expires_at=0.0):
        return TokenCheckResult(False, class_name, session_id, expires_at, message)

    broken_message = "Mã QR không hợp lệ hoặc đã bị hỏng."
    try:
        encoded_payload, received_signature = token.split(".")
        expected_signature = _sign(encoded_payload)
        if not hmac.compare_digest(
            received_signature.encode("utf-8"), expected_signature.encode("utf-8")
        ):
            return failure(broken_message)

        payload = _decode_base64_url(encoded_payload).decode("utf-8")
        payload_parts = payload.split("|", 3)
        if len(payload_parts) != 4:
            return failure(broken_message)
        expires_at_text, slot_text, session_id, class_name = payload_parts
        expires_at = float(expires_at_text)
        token_slot = int(slot_text)
    except (ValueError, UnicodeError):
        return failure(broken_message)

    if time.time() > expires_at:
        return failure(
            "Mã QR đã hết hạn! Vui lòng xin giảng viên mã mới.",
            class_name, session_id, expires_at,
        )

    slots_old = current_qr_slot() - token_slot
    if slots_old < 0 or slots_old > QR_ACCEPTED_PREVIOUS_SLOTS:
        return failure(
            "Mã QR này đã được thay đổi. Hãy quét lại mã QR đang hiển thị trên màn hình.",
            class_name, session_id, expires_at,
        )

    return TokenCheckResult(True, class_name, session_id, expires_at, "Hợp lệ")


# ---------------------------------------------------------------------------
# On-screen code (second secret, typed by the student after scanning)
# ---------------------------------------------------------------------------

def _screen_code_for_slot(class_name: str, session_id: str, slot: int) -> str:
    message = f"screen-code|{class_name}|{session_id}|{slot}".encode("utf-8")
    digest = hmac.new(SECRET_KEY, message, hashlib.sha256).digest()
    number = int.from_bytes(digest[:4], "big") % (10 ** SCREEN_CODE_LENGTH)
    return str(number).zfill(SCREEN_CODE_LENGTH)


def get_screen_code(class_name: str, session_id: str):
    """Return (current code, seconds until it changes) for the teacher screen."""
    now = time.time()
    slot = int(now // SCREEN_CODE_PERIOD_SECONDS)
    seconds_left = int((slot + 1) * SCREEN_CODE_PERIOD_SECONDS - now) + 1
    return _screen_code_for_slot(class_name, session_id, slot), seconds_left


def check_screen_code(class_name: str, session_id: str, entered_code: str) -> bool:
    entered_code = entered_code.strip()
    current_slot = int(time.time() // SCREEN_CODE_PERIOD_SECONDS)
    for slots_back in range(SCREEN_CODE_ACCEPTED_PREVIOUS + 1):
        expected = _screen_code_for_slot(class_name, session_id, current_slot - slots_back)
        if hmac.compare_digest(entered_code.encode("utf-8"), expected.encode("utf-8")):
            return True
    return False


def get_student_page_path() -> str:
    """Return the fixed, secret route registered for the student page.

    Streamlit registers page routes at app startup, so this path stays the same
    until secret.key changes. Never share this bare route as an attendance link:
    each teacher-generated QR must append a fresh signed, expiring token.
    """
    digest = hmac.new(SECRET_KEY, b"student-page-path", hashlib.sha256).hexdigest()
    return f"checkin-{digest[:16]}"


def make_qr_image(url: str):
    qr_code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr_code.add_data(url)
    qr_code.make(fit=True)
    return qr_code.make_image(fill_color="black", back_color="white")


# ---------------------------------------------------------------------------
# Teacher password
# ---------------------------------------------------------------------------

def _get_expected_teacher_password() -> str:
    configured_password = _get_configured_secret(TEACHER_PASSWORD_ENVIRONMENT_VARIABLE)
    return configured_password or DEFAULT_TEACHER_PASSWORD


def is_using_default_teacher_password() -> bool:
    return _get_expected_teacher_password() == DEFAULT_TEACHER_PASSWORD


def check_teacher_password(candidate_password: str) -> bool:
    # compare_digest avoids leaking how many leading characters were correct.
    return hmac.compare_digest(
        candidate_password.encode("utf-8"),
        _get_expected_teacher_password().encode("utf-8"),
    )
