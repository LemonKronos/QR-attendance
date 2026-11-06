import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

import qrcode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRET_KEY_PATH = PROJECT_ROOT / "secret.key"

# A QR code can only be used to OPEN the check-in page for this long.
QR_VALIDITY_SECONDS = 600
# A student who opened the page just before the QR expired still gets this much
# extra time to type their details and press the send button.
SUBMIT_GRACE_SECONDS = 300

SIGNATURE_BYTE_LENGTH = 16

DEFAULT_TEACHER_PASSWORD = "admin123"
TEACHER_PASSWORD_ENVIRONMENT_VARIABLE = "TEACHER_PASSWORD"


def _load_or_create_secret_key() -> bytes:
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
    expires_at: float
    message: str


def generate_qr_token(class_name: str) -> str:
    expires_at = int(time.time()) + QR_VALIDITY_SECONDS
    # A random nonce ensures two QR generations in the same second still
    # produce different links, even for the same class.
    nonce = secrets.token_urlsafe(8)
    payload = f"{expires_at}|{nonce}|{class_name}"
    encoded_payload = _encode_base64_url(payload.encode("utf-8"))
    return f"{encoded_payload}.{_sign(encoded_payload)}"


def validate_token(token: str) -> TokenCheckResult:
    broken_token_result = TokenCheckResult(
        is_valid=False,
        class_name="",
        expires_at=0.0,
        message="Mã QR không hợp lệ hoặc đã bị hỏng.",
    )

    try:
        encoded_payload, received_signature = token.split(".")
        expected_signature = _sign(encoded_payload)
        signature_matches = hmac.compare_digest(
            received_signature.encode("utf-8"),
            expected_signature.encode("utf-8"),
        )
        if not signature_matches:
            return broken_token_result

        payload = _decode_base64_url(encoded_payload).decode("utf-8")
        payload_parts = payload.split("|", 2)
        if len(payload_parts) == 3:
            # Current format: expiry | random nonce | class name.
            expires_at_text, _nonce, class_name = payload_parts
        elif len(payload_parts) == 2:
            # Accept tokens from the previous format during a short transition.
            expires_at_text, class_name = payload_parts
        else:
            return broken_token_result
        expires_at = float(expires_at_text)
    except (ValueError, UnicodeError):
        return broken_token_result

    if time.time() > expires_at:
        return TokenCheckResult(
            is_valid=False,
            class_name=class_name,
            expires_at=expires_at,
            message="Mã QR đã hết hạn! Vui lòng xin giảng viên mã mới.",
        )

    return TokenCheckResult(
        is_valid=True,
        class_name=class_name,
        expires_at=expires_at,
        message="Hợp lệ",
    )


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
    return os.environ.get(TEACHER_PASSWORD_ENVIRONMENT_VARIABLE, DEFAULT_TEACHER_PASSWORD)


def is_using_default_teacher_password() -> bool:
    return _get_expected_teacher_password() == DEFAULT_TEACHER_PASSWORD


def check_teacher_password(candidate_password: str) -> bool:
    # compare_digest avoids leaking how many leading characters were correct.
    return hmac.compare_digest(
        candidate_password.encode("utf-8"),
        _get_expected_teacher_password().encode("utf-8"),
    )
