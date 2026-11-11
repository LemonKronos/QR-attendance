import difflib
import logging
import threading
import time
import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

from utils import clock

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# URL Google Sheet để chạy thử
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/11or8N-px_ac1bggLJlCaRMllQch3MCcXMF_DDZfhr3c/edit?usp=sharing"


def _get_setting(name: str, default: str = "") -> str:
    """Read an environment variable or top-level Streamlit secret."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


SHEET_URL = _get_setting("SHEET_URL", DEFAULT_SHEET_URL)

# Column A holds the student ID and column B the student name.
# Every attendance date gets its own column after those two.
HEADER_STUDENT_ID = "Mã SV"
HEADER_STUDENT_NAME = "Họ Tên"
PRESENT_MARK = "X"
DUPLICATE_DEVICE_MARK = "Duplicate Device"

# 1.0 means identical. Names are compared without accents and upper/lower case.
NAME_SIMILARITY_THRESHOLD = 0.8

MAX_RETRY_ATTEMPTS = 4
FIRST_RETRY_DELAY_SECONDS = 1.5
# Bound every Google API request so a missing network route cannot freeze the
# Streamlit script indefinitely. Requests accepts (connect, read) seconds.
GOOGLE_API_TIMEOUT = (3.05, 5.0)
RETRYABLE_HTTP_STATUS_CODES = (429, 500, 502, 503)
RATE_LIMIT_HTTP_STATUS_CODE = 429

NAME_MISMATCH_MESSAGE = (
    "Mã số sinh viên này đã có trong danh sách nhưng họ tên không khớp. "
    "Vui lòng kiểm tra lại."
)
SYSTEM_BUSY_MESSAGE = "Hệ thống đang quá tải. Vui lòng bấm Gửi lại sau vài giây."
CONNECTION_ERROR_MESSAGE = (
    "Không thể kết nối với Google Sheet. Vui lòng báo giảng viên kiểm tra lại hệ thống."
)


class UserFacingError(Exception):
    """An error whose message is safe and useful to show on screen."""


@dataclass(frozen=True)
class AttendanceResult:
    success: bool
    message: str
    student_name: str = ""


@dataclass(frozen=True)
class ClassTabLookupResult:
    success: bool
    tab_name: str
    message: str


# Streamlit runs every browser session in its own thread. One lock makes sure
# "read the sheet, then write the sheet" is never interleaved between students,
# which would otherwise create duplicate rows or overwrite each other.
_sheet_lock = threading.Lock()
_cached_spreadsheet = None
_cached_worksheets = {}


def _reset_cache() -> None:
    global _cached_spreadsheet
    _cached_spreadsheet = None
    _cached_worksheets.clear()


def _get_http_status_code(error: Exception):
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)


def _call_with_retry(operation, max_attempts: int = MAX_RETRY_ATTEMPTS):
    """Run a Google API call with bounded retries when Google is busy."""
    delay_seconds = FIRST_RETRY_DELAY_SECONDS
    for attempt_number in range(1, max_attempts + 1):
        try:
            return operation()
        except gspread.exceptions.APIError as error:
            is_retryable = _get_http_status_code(error) in RETRYABLE_HTTP_STATUS_CODES
            if not is_retryable or attempt_number == max_attempts:
                raise
            time.sleep(delay_seconds)
            delay_seconds *= 2


def _get_spreadsheet():
    global _cached_spreadsheet
    if _cached_spreadsheet is None:
        logger.info("Loading Google service-account credentials")
        service_account_info = None
        try:
            configured_account = st.secrets.get("gcp_service_account")
            if configured_account:
                service_account_info = dict(configured_account)
        except Exception:
            # No local secrets.toml: continue to the credentials.json fallback.
            pass

        if service_account_info:
            private_key = service_account_info.get("private_key", "")
            if isinstance(private_key, str):
                # Accommodate either TOML-decoded newlines or escaped JSON newlines.
                service_account_info["private_key"] = private_key.replace("\\n", "\n")
            credentials = Credentials.from_service_account_info(
                service_account_info,
                scopes=SCOPES,
            )
        elif CREDENTIALS_PATH.exists():
            credentials = Credentials.from_service_account_file(
                str(CREDENTIALS_PATH),
                scopes=SCOPES,
            )
        else:
            raise UserFacingError(
                "Thiếu Google credentials. Hãy cấu hình [gcp_service_account] "
                "trong Streamlit Secrets hoặc đặt credentials.json ở thư mục gốc."
            )
        client = gspread.authorize(credentials)
        # gspread defaults to no request timeout. Without this, a stalled
        # Google API connection can leave the teacher page loading forever.
        client.set_timeout(GOOGLE_API_TIMEOUT)
        logger.info("Google Sheets client ready; request timeout=%s", GOOGLE_API_TIMEOUT)
        logger.info("Opening attendance spreadsheet")
        _cached_spreadsheet = _call_with_retry(
            lambda: client.open_by_url(SHEET_URL),
            max_attempts=2,
        )
        logger.info("Attendance spreadsheet opened successfully")
    return _cached_spreadsheet


def _get_worksheet(class_name: str):
    if class_name not in _cached_worksheets:
        spreadsheet = _get_spreadsheet()
        try:
            _cached_worksheets[class_name] = _call_with_retry(
                lambda: spreadsheet.worksheet(class_name)
            )
        except gspread.exceptions.WorksheetNotFound:
            raise UserFacingError(
                f"Không tìm thấy Tab '{class_name}'. Vui lòng tạo tab này trên Google Sheet."
            )
    return _cached_worksheets[class_name]


# ---------------------------------------------------------------------------
# Class (tab) lookup, used by the teacher page before a QR code is created
# ---------------------------------------------------------------------------

def lookup_class_tab(typed_class_name: str) -> ClassTabLookupResult:
    """Find the real tab name for what the teacher typed (ignoring upper/lower case)."""
    typed_name = typed_class_name.strip()

    try:
        with _sheet_lock:
            spreadsheet = _get_spreadsheet()
            logger.info("Reading Google Sheet worksheet list for class lookup")
            # Only two attempts here: QR creation should fail promptly instead
            # of appearing to hang while a teacher is waiting in class.
            worksheets = _call_with_retry(spreadsheet.worksheets, max_attempts=2)
            logger.info("Read %d worksheet(s) from Google Sheets", len(worksheets))
            for worksheet in worksheets:
                _cached_worksheets[worksheet.title] = worksheet
    except UserFacingError as error:
        return ClassTabLookupResult(False, "", str(error))
    except Exception:
        logger.exception("Could not read the list of tabs from Google Sheets")
        _reset_cache()
        return ClassTabLookupResult(False, "", CONNECTION_ERROR_MESSAGE)

    tab_names = [worksheet.title for worksheet in worksheets]

    if typed_name in tab_names:
        return ClassTabLookupResult(True, typed_name, "OK")
    for tab_name in tab_names:
        if tab_name.casefold() == typed_name.casefold():
            return ClassTabLookupResult(True, tab_name, "OK")

    available_tabs_text = ", ".join(tab_names) if tab_names else "(chưa có tab nào)"
    return ClassTabLookupResult(
        False,
        "",
        f"Không tìm thấy tab '{typed_name}' trên Google Sheet. "
        f"Các tab hiện có: {available_tabs_text}",
    )


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------

def _normalize_name_for_comparison(name: str) -> str:
    name_with_plain_d = name.replace("đ", "d").replace("Đ", "D")
    decomposed_name = unicodedata.normalize("NFD", name_with_plain_d)
    name_without_accents = "".join(
        character for character in decomposed_name if unicodedata.category(character) != "Mn"
    )
    return " ".join(name_without_accents.lower().split())


def names_are_similar(entered_name: str, stored_name: str) -> bool:
    """True when the names differ only by case, accents or a small typo."""
    entered_name_normalized = _normalize_name_for_comparison(entered_name)
    stored_name_normalized = _normalize_name_for_comparison(stored_name)

    if entered_name_normalized == stored_name_normalized:
        return True

    similarity = difflib.SequenceMatcher(
        None, entered_name_normalized, stored_name_normalized
    ).ratio()
    return similarity >= NAME_SIMILARITY_THRESHOLD


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

def _ensure_column_count(worksheet, required_column_count: int) -> None:
    if worksheet.col_count < required_column_count:
        missing_column_count = required_column_count - worksheet.col_count
        _call_with_retry(lambda: worksheet.add_cols(missing_column_count))


def _write_cell(worksheet, row_number: int, column_number: int, value: str) -> None:
    cell_address = gspread.utils.rowcol_to_a1(row_number, column_number)
    # raw=True stores the text exactly as given, so a name such as "=1+1"
    # can never be turned into a formula by Google Sheets.
    _call_with_retry(
        lambda: worksheet.update(range_name=cell_address, values=[[value]], raw=True)
    )


def _find_student_row(all_rows, student_id: str):
    for row_number, row_values in enumerate(all_rows[1:], start=2):
        if row_values and row_values[0].strip() == student_id:
            return row_number, row_values
    return None, []


def _get_cell_text(row_values, column_number: int) -> str:
    if len(row_values) >= column_number:
        return row_values[column_number - 1].strip()
    return ""


def _describe(student_id: str, student_name: str) -> str:
    return f"{student_id} - {student_name}" if student_name else student_id


def _merge_flag(existing_mark: str, note: str) -> str:
    """Turn a cell into a duplicate flag, or add one more note to an existing flag.

    An "X" becomes the flag (a flagged student is of course also present).
    The same note is never added twice, so re-submitting changes nothing.
    """
    existing_mark = existing_mark.strip()
    if existing_mark.startswith(DUPLICATE_DEVICE_MARK):
        if note in existing_mark:
            return existing_mark
        return f"{existing_mark}; {note}"
    return f"{DUPLICATE_DEVICE_MARK}: {note}"


def _mark_attendance_while_locked(
    class_name: str, student_id: str, student_name: str, other_student_ids: list
) -> AttendanceResult:
    worksheet = _get_worksheet(class_name)
    all_rows = _call_with_retry(worksheet.get_all_values)

    # ---- header row: make sure the two fixed columns and today's column exist
    header_row = list(all_rows[0]) if all_rows else []
    while header_row and not header_row[-1].strip():
        header_row.pop()

    header_was_changed = False
    for required_position, required_title in enumerate((HEADER_STUDENT_ID, HEADER_STUDENT_NAME)):
        if len(header_row) <= required_position:
            header_row.append(required_title)
            header_was_changed = True

    today_label = clock.now().strftime("%d-%b-%Y")
    if today_label in header_row:
        today_column_number = header_row.index(today_label) + 1
    else:
        header_row.append(today_label)
        today_column_number = len(header_row)
        header_was_changed = True

    if header_was_changed:
        _ensure_column_count(worksheet, len(header_row))
        last_header_cell = gspread.utils.rowcol_to_a1(1, len(header_row))
        _call_with_retry(
            lambda: worksheet.update(
                range_name=f"A1:{last_header_cell}", values=[header_row], raw=True
            )
        )

    # ---- find the student: the ID must match exactly
    student_row_number, student_row_values = _find_student_row(all_rows, student_id)

    # ---- known student: check the name, fix small typos, reject different names.
    # This happens BEFORE anything is written, so a rejected name never flags anybody.
    if student_row_number is None:
        official_name = student_name
    else:
        stored_name = student_row_values[1].strip() if len(student_row_values) > 1 else ""
        if stored_name:
            if not names_are_similar(student_name, stored_name):
                return AttendanceResult(False, NAME_MISMATCH_MESSAGE)
            official_name = stored_name
        else:
            official_name = student_name
            _write_cell(worksheet, student_row_number, 2, official_name)

    # ---- who else used this device today? (A, when this entry is B)
    other_students = []
    for other_id in other_student_ids:
        other_row_number, other_row_values = _find_student_row(all_rows, other_id)
        other_name = other_row_values[1].strip() if len(other_row_values) > 1 else ""
        other_students.append((other_id, other_name, other_row_number, other_row_values))

    # ---- this student's own cell:  "Duplicate Device: previously by A-id - A-name"
    own_note = ""
    if other_students:
        previous_text = ", ".join(_describe(i, n) for i, n, _r, _v in other_students)
        own_note = f"previously by {previous_text}"

    if student_row_number is None:
        mark = _merge_flag("", own_note) if own_note else PRESENT_MARK
        blank_cells_before_today = [""] * (today_column_number - 3)
        new_row = [student_id, official_name] + blank_cells_before_today + [mark]
        _call_with_retry(lambda: worksheet.append_row(new_row, value_input_option="RAW"))
    else:
        existing_mark = _get_cell_text(student_row_values, today_column_number)
        if own_note:
            new_mark = _merge_flag(existing_mark, own_note)
        else:
            # A re-submit can never erase an existing mark.
            new_mark = existing_mark or PRESENT_MARK
        if new_mark != existing_mark:
            _write_cell(worksheet, student_row_number, today_column_number, new_mark)

    # ---- the earlier students' cells (A): "... also registered for B-id - B-name"
    new_student_text = _describe(student_id, official_name)
    for _other_id, _other_name, other_row_number, other_row_values in other_students:
        if other_row_number is None:
            continue
        other_existing_mark = _get_cell_text(other_row_values, today_column_number)
        other_new_mark = _merge_flag(other_existing_mark, f"also registered for {new_student_text}")
        if other_new_mark != other_existing_mark:
            _write_cell(worksheet, other_row_number, today_column_number, other_new_mark)

    return AttendanceResult(True, "Thành công", official_name)


def mark_attendance(
    class_name: str, student_id: str, student_name: str, other_student_ids: list = ()
) -> AttendanceResult:
    try:
        with _sheet_lock:
            return _mark_attendance_while_locked(
                class_name, student_id, student_name, list(other_student_ids)
            )
    except UserFacingError as error:
        return AttendanceResult(False, str(error))
    except gspread.exceptions.APIError as error:
        logger.exception("Google Sheets API error while marking attendance")
        _reset_cache()
        if _get_http_status_code(error) == RATE_LIMIT_HTTP_STATUS_CODE:
            return AttendanceResult(False, SYSTEM_BUSY_MESSAGE)
        return AttendanceResult(False, CONNECTION_ERROR_MESSAGE)
    except Exception:
        logger.exception("Unexpected error while marking attendance")
        _reset_cache()
        return AttendanceResult(False, CONNECTION_ERROR_MESSAGE)
