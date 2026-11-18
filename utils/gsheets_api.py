import difflib
import logging
import re
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


def _without_reasons(text: str) -> str:
    return re.sub(r"\s*\([^()]*\)", "", text)


def _merge_flag(existing_mark: str, note: str) -> str:
    """Turn a cell into a duplicate flag, or add one more note to an existing flag.

    An "X" becomes the flag (a flagged student is of course also present).
    The same note is never added twice, so re-submitting changes nothing.
    """
    existing_mark = existing_mark.strip()
    if existing_mark.startswith(DUPLICATE_DEVICE_MARK):
        # Compare without the "(reasons)" part, so re-sending from the same
        # device never adds the same note again just because the reasons differ.
        if _without_reasons(note) in _without_reasons(existing_mark):
            return existing_mark
        return f"{existing_mark}; {note}"
    return f"{DUPLICATE_DEVICE_MARK}: {note}"


# GPS flags are kept on their own lines of the cell (after the duplicate-device
# line, if any) so they can be replaced without touching the permanent flags.
GPS_FLAG_PREFIXES = ("OUT_OF_RANGE", "GPS_DENIED", "GPS_LOW_ACCURACY")


def _split_mark(mark: str):
    """Split a cell into (permanent text, [GPS flag lines])."""
    permanent_lines, gps_lines = [], []
    for line in mark.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        (gps_lines if line.startswith(GPS_FLAG_PREFIXES) else permanent_lines).append(line)
    return " ".join(permanent_lines), gps_lines


def _join_mark(permanent_text: str, gps_lines: list) -> str:
    """Build the cell: flags replace the plain \"X\", several flags are joined by a newline."""
    lines = []
    if permanent_text and not (permanent_text == PRESENT_MARK and gps_lines):
        lines.append(permanent_text)
    lines.extend(gps_lines)
    return "\n".join(lines) if lines else PRESENT_MARK


def _with_reasons(text: str, reasons: list) -> str:
    return f"{text} ({', '.join(reasons)})" if reasons else text


def _mark_attendance_while_locked(
    class_name: str, student_id: str, student_name: str, duplicate_signals: dict, gps_flags
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

    # ---- who else looks like this device today? (A, when this entry is B)
    other_students = []
    for other_id, reasons in duplicate_signals.items():
        other_row_number, other_row_values = _find_student_row(all_rows, other_id)
        other_name = other_row_values[1].strip() if len(other_row_values) > 1 else ""
        other_students.append((other_id, other_name, reasons, other_row_number, other_row_values))

    # ---- this student's own cell:  "Duplicate Device: previously by A-id - A-name (cookie, ...)"
    own_note = ""
    if other_students:
        previous_text = ", ".join(
            _with_reasons(_describe(i, n), reasons) for i, n, reasons, _r, _v in other_students
        )
        own_note = f"previously by {previous_text}"

    if student_row_number is None:
        permanent_text = _merge_flag("", own_note) if own_note else PRESENT_MARK
        mark = _join_mark(permanent_text, list(gps_flags or []))
        blank_cells_before_today = [""] * (today_column_number - 3)
        new_row = [student_id, official_name] + blank_cells_before_today + [mark]
        _call_with_retry(lambda: worksheet.append_row(new_row, value_input_option="RAW"))
    else:
        existing_mark = _get_cell_text(student_row_values, today_column_number)
        existing_permanent, existing_gps = _split_mark(existing_mark)
        if own_note:
            new_permanent = _merge_flag(existing_permanent, own_note)
        else:
            # A re-submit can never erase an existing flag.
            new_permanent = existing_permanent or PRESENT_MARK
        # GPS flags are always recomputed by the caller: replace the old ones.
        new_gps = existing_gps if gps_flags is None else list(gps_flags)
        new_mark = _join_mark(new_permanent, new_gps)
        if new_mark != existing_mark:
            _write_cell(worksheet, student_row_number, today_column_number, new_mark)

    # ---- the earlier students' cells (A): "... also registered for B-id - B-name (cookie, ...)"
    new_student_text = _describe(student_id, official_name)
    for _other_id, _other_name, reasons, other_row_number, other_row_values in other_students:
        if other_row_number is None:
            continue
        other_existing_mark = _get_cell_text(other_row_values, today_column_number)
        other_permanent, other_gps = _split_mark(other_existing_mark)
        other_new_permanent = _merge_flag(
            other_permanent, f"also registered for {_with_reasons(new_student_text, reasons)}"
        )
        other_new_mark = _join_mark(other_new_permanent, other_gps)
        if other_new_mark != other_existing_mark:
            _write_cell(worksheet, other_row_number, today_column_number, other_new_mark)

    return AttendanceResult(True, "Thành công", official_name)


def _run_sheet_operation(description: str, operation) -> AttendanceResult:
    """Run an operation under the sheet lock and turn failures into a result."""
    try:
        with _sheet_lock:
            return operation()
    except UserFacingError as error:
        return AttendanceResult(False, str(error))
    except gspread.exceptions.APIError as error:
        logger.exception("Google Sheets API error while %s", description)
        _reset_cache()
        if _get_http_status_code(error) == RATE_LIMIT_HTTP_STATUS_CODE:
            return AttendanceResult(False, SYSTEM_BUSY_MESSAGE)
        return AttendanceResult(False, CONNECTION_ERROR_MESSAGE)
    except Exception:
        logger.exception("Unexpected error while %s", description)
        _reset_cache()
        return AttendanceResult(False, CONNECTION_ERROR_MESSAGE)


def mark_attendance(
    class_name: str,
    student_id: str,
    student_name: str,
    duplicate_signals: dict = None,
    gps_flags: list = None,
) -> AttendanceResult:
    """Record attendance.

    duplicate_signals: {other_student_id: [reasons]} from device_check.
    gps_flags: the student's GPS flag lines (replaces any older GPS flags);
               None leaves the cell's GPS flags untouched.
    """
    return _run_sheet_operation(
        "marking attendance",
        lambda: _mark_attendance_while_locked(
            class_name, student_id, student_name, dict(duplicate_signals or {}), gps_flags
        ),
    )


def _apply_gps_flags_while_locked(class_name: str, flags_by_student: dict) -> AttendanceResult:
    worksheet = _get_worksheet(class_name)
    all_rows = _call_with_retry(worksheet.get_all_values)
    header_row = list(all_rows[0]) if all_rows else []
    today_label = clock.now().strftime("%d-%b-%Y")
    if today_label not in header_row:
        return AttendanceResult(True, "0")
    today_column_number = header_row.index(today_label) + 1

    cell_updates = []
    for student_id, gps_lines in flags_by_student.items():
        row_number, row_values = _find_student_row(all_rows, student_id)
        if row_number is None:
            continue
        existing_mark = _get_cell_text(row_values, today_column_number)
        if not existing_mark:
            continue  # not marked present today: nothing to flag
        permanent_text, _old_gps = _split_mark(existing_mark)
        new_mark = _join_mark(permanent_text, list(gps_lines))
        if new_mark != existing_mark:
            cell_updates.append(
                {
                    "range": gspread.utils.rowcol_to_a1(row_number, today_column_number),
                    "values": [[new_mark]],
                }
            )

    if cell_updates:
        # One request for all changed cells keeps us far from the API rate limit.
        _call_with_retry(lambda: worksheet.batch_update(cell_updates, raw=True))
    return AttendanceResult(True, str(len(cell_updates)))


def apply_gps_flags(class_name: str, flags_by_student: dict) -> AttendanceResult:
    """Replace the GPS flag lines of many students' cells for today (one read, one write)."""
    if not flags_by_student:
        return AttendanceResult(True, "0")
    return _run_sheet_operation(
        "updating GPS flags",
        lambda: _apply_gps_flags_while_locked(class_name, dict(flags_by_student)),
    )
