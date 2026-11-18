import html
import time
import logging

import streamlit as st

from utils import class_session, device_check, geo, gsheets_api, security
from utils.ui_helpers import force_light_inputs

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Điểm Danh Sinh Viên",
    layout="centered",
    initial_sidebar_state="collapsed"
)

STUDENT_ID_LENGTH = 7
STUDENT_NAME_MAX_LENGTH = 80

SESSION_DEFAULTS = {
    "checkin_step": "input",
    "draft_student_id": "",
    "draft_student_name": "",
    "verified_class_name": "",
    "submit_deadline": 0.0,
    "device_wait_warned": False,
    "done_student_name": "",
    "done_cookie_value": "",
    "verified_session_id": "",
    "screen_code_ok": False,
    "geo_nonce": 0,
    "locating": False,
    "location_received": True,
}
for session_key, default_value in SESSION_DEFAULTS.items():
    if session_key not in st.session_state:
        st.session_state[session_key] = default_value


def show_message(text: str):
    st.markdown(
        f'<div class="outlined-message">{html.escape(text)}</div>',
        unsafe_allow_html=True
    )


def render_success_card(
    student_id: str, student_name: str, cookie_name: str, cookie_value: str, auto_close: bool = True
):
    """Success card + cookie write + auto-close timer.

    Used right after sending AND on any later rerun (checkin_step == "done"),
    so a rerun can never bring the entry form back or allow a second send.
    """
    auto_close_html = """
        <div id="auto-exit-status" style="color: #1488DB; font-weight: 600; font-size: 0.95rem; margin-top: 12px;">
            Tự động đóng trang sau 2 giây...
        </div>
        <div class="countdown-track">
            <div class="countdown-bar"></div>
        </div>
    """ if auto_close else ""

    st.markdown(f"""
    <div class="confirm-card">
        <div class="confirm-card-title" style="font-size: 1.3rem;">
            ĐIỂM DANH THÀNH CÔNG
        </div>
        <div class="confirm-card-subtitle">
            Đã ghi nhận vào hệ thống
        </div>
        <div class="info-field-box" style="text-align: center;">
            <div class="info-field-value">
                {html.escape(student_id)} — {html.escape(student_name)}
            </div>
        </div>
        {auto_close_html}
    </div>
    """, unsafe_allow_html=True)

    if not auto_close:
        # Location was not received: keep the page open so the student can allow
        # location and press Send again (the entry is simply updated).
        st.markdown(
            '<div class="outlined-message">Chưa lấy được vị trí của bạn. Hãy cho phép trang này '
            'dùng vị trí (biểu tượng ổ khóa cạnh thanh địa chỉ) rồi bấm "Gửi lại".</div>',
            unsafe_allow_html=True,
        )
        if st.button("Gửi lại", use_container_width=True, key="resend_with_location"):
            st.session_state.checkin_step = "confirm"
            st.rerun()

    # Ghi nhớ thiết bị đã dùng cho mã sinh viên này hôm nay, rồi hẹn giờ đóng trang
    st.html(f"""
    <script>
        (function() {{
            const parentWindow = window;
            const parentDocument = parentWindow.document;

            parentDocument.cookie = "{cookie_name}={cookie_value}; max-age={device_check.COOKIE_LIFETIME_SECONDS}; path=/; SameSite=Lax";
            // Same value in localStorage: a browser may block one but not the other.
            try {{ parentWindow.localStorage.setItem("{cookie_name}", "{cookie_value}"); }} catch (error) {{}}

            if (!{str(auto_close).lower()}) {{
                return;
            }}

            // Only ever arm ONE exit timer, even if this script runs again.
            if (parentWindow._studentExitTimer) {{
                return;
            }}

            function triggerExit() {{
                const statusElement = parentDocument.getElementById('auto-exit-status');
                if (statusElement) {{
                    statusElement.innerText = "Đã hoàn tất điểm danh.";
                }}

                const userAgent = navigator.userAgent || "";
                const isAndroid = /Android/i.test(userAgent);

                // 1. Thử đóng cửa sổ/tab hiện tại
                try {{
                    parentWindow.open('', '_self', '');
                    parentWindow.close();
                }} catch (error) {{}}
                try {{
                    window.top.close();
                }} catch (error) {{}}

                // 2. Trên Android: thoát thẳng ra Màn hình chính
                if (isAndroid) {{
                    try {{
                        window.top.location.href = "intent:#Intent;action=android.intent.action.MAIN;category=android.intent.category.HOME;end";
                    }} catch (error) {{}}
                }}

                // 3. Lùi về tác vụ trước nếu có trong lịch sử trình duyệt
                setTimeout(function() {{
                    try {{
                        if (window.top.history.length > 1) {{
                            window.top.history.back();
                        }}
                    }} catch (error) {{}}
                }}, 250);
            }}

            parentWindow._studentExitTimer = parentWindow.setTimeout(triggerExit, 2000);
        }})();
    </script>
    """, unsafe_allow_javascript=True)


# After a failed send, put the "Gửi" button back to normal so the student can retry.
RESTORE_SEND_BUTTON_SCRIPT = """
<script>
    (function() {
        const parentDocument = document;
        parentDocument.querySelectorAll('button').forEach(button => {
            if (button.innerText.trim() === 'Đang điểm danh ...') {
                button.style.removeProperty('background-color');
                button.style.removeProperty('border-color');
                button.style.removeProperty('color');
                const labelElement = button.querySelector('p') || button;
                labelElement.innerText = 'Gửi';
            }
        });
    })();
</script>
"""

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap');

    :root, html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        color-scheme: only light !important;
        forced-color-adjust: none !important;
        --primary-dark: #030391;
        --primary-light: #1488DB;
        --text-black: #000000;
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif !important;
        background: #FFFFFF !important;
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-size-adjust: 100%;
    }

    * {
        box-sizing: border-box;
        -webkit-tap-highlight-color: transparent;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    .block-container {
        max-width: 480px !important;
        width: 100% !important;
        padding: 1.25rem 1rem 2.5rem 1rem !important;
        margin: 0 auto !important;
        animation: softFadeUp 0.25s ease-out forwards;
    }

    @keyframes softFadeUp {
        0% { opacity: 0; }
        100% { opacity: 1; }
    }

    @keyframes shrinkProgress {
        0% { width: 100%; }
        100% { width: 0%; }
    }

    /* Khung tiêu đề chỉ dùng viền bo góc, không màu nền */
    .student-header-box {
        background-color: transparent !important;
        border: 2px solid var(--primary-dark);
        border-radius: 18px;
        padding: 18px 16px;
        text-align: center;
        margin-bottom: 14px;
    }
    .student-header-box h1 {
        color: var(--primary-dark) !important;
        font-size: clamp(1.3rem, 4.8vw, 1.65rem) !important;
        font-weight: 700 !important;
        margin: 0 !important;
    }
    .student-header-box p {
        color: var(--primary-light) !important;
        font-size: clamp(0.9rem, 3.4vw, 1rem) !important;
        font-weight: 600 !important;
        margin: 4px 0 0 0 !important;
    }

    /* Khung hiển thị lớp chỉ có viền và bo góc, không màu nền */
    .class-status-box {
        background-color: transparent !important;
        border: 1.8px solid var(--primary-dark);
        border-radius: 14px;
        padding: 10px 16px;
        text-align: center;
        margin-bottom: 18px;
        color: var(--primary-dark);
        font-size: clamp(0.95rem, 3.8vw, 1.05rem);
        font-weight: 700;
    }

    /* Thiết kế khung nhập liệu độc lập với thiết bị: Nền trắng, chỉ có khung viền xanh dương đậm (#030391) */
    div[data-testid="stTextInput"] > div,
    div[data-testid="stTextInput"] div[data-baseweb="input"],
    div[data-testid="stTextInput"] div[data-baseweb="base-input"],
    div[data-testid="stTextInput"] div[data-baseweb="input"] > div {
        background: #FFFFFF !important;
        background-color: #FFFFFF !important;
        background-image: none !important;
        color: #000000 !important;
        box-shadow: none !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="input"] {
        border: 2px solid #030391 !important;
        border-radius: 14px !important;
        min-height: 60px !important;
        padding: 0 4px !important;
        transition: box-shadow 0.2s ease !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
        border: none !important;
        background-color: #FFFFFF !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border: 2px solid #030391 !important;
        box-shadow: 0 0 0 3px rgba(3, 3, 145, 0.14) !important;
    }

    div[data-testid="stTextInput"] input {
        -webkit-appearance: none !important;
        appearance: none !important;
        background: #FFFFFF !important;
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        caret-color: #030391 !important;
        font-size: clamp(1.15rem, 4.5vw, 1.32rem) !important;
        font-weight: 600 !important;
        padding: 14px 16px !important;
        line-height: 1.4 !important;
    }

    div[data-testid="stTextInput"] input::placeholder {
        color: #7A869A !important;
        -webkit-text-fill-color: #7A869A !important;
        font-weight: 400 !important;
        letter-spacing: normal !important;
    }

    div[data-testid="stTextInput"] input:-webkit-autofill,
    div[data-testid="stTextInput"] input:-webkit-autofill:hover,
    div[data-testid="stTextInput"] input:-webkit-autofill:focus {
        -webkit-box-shadow: 0 0 0 1000px #FFFFFF inset !important;
        -webkit-text-fill-color: #000000 !important;
    }

    /* Định dạng ô nhập Mã số sinh viên 7 chữ số */
    div[data-testid="stTextInput"]:first-of-type input {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        font-size: clamp(1.4rem, 5.8vw, 1.75rem) !important;
        font-weight: 700 !important;
        letter-spacing: 5px !important;
        text-align: center !important;
    }

    .stTextInput label p {
        color: var(--primary-dark) !important;
        font-size: clamp(0.95rem, 3.6vw, 1.02rem) !important;
        font-weight: 700 !important;
        margin-bottom: 4px !important;
    }

    /* Nút bấm chỉ có viền và bo góc, không màu nền */
    .stButton > button {
        background-color: #FFFFFF !important;
        color: var(--primary-dark) !important;
        border: 2px solid var(--primary-dark) !important;
        border-radius: 14px !important;
        min-height: 58px !important;
        font-size: clamp(1rem, 4vw, 1.12rem) !important;
        font-weight: 700 !important;
        width: 100% !important;
        margin-top: 6px !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        border-color: var(--primary-light) !important;
        color: var(--primary-light) !important;
    }
    .stButton > button:active {
        transform: scale(0.98) !important;
    }

    button[kind="secondary"] {
        border: 1.8px solid var(--primary-light) !important;
        color: var(--primary-light) !important;
    }

    /* Khung xác nhận và thông báo thành công: chỉ có viền bo góc, không màu nền */
    .confirm-card {
        background-color: transparent !important;
        border: 2px solid var(--primary-dark);
        border-radius: 18px;
        padding: 20px 16px;
        margin: 10px 0 16px 0;
        text-align: center;
        animation: softFadeUp 0.2s ease-out forwards;
    }
    .confirm-card-title {
        color: var(--primary-dark);
        font-size: clamp(1.1rem, 4.2vw, 1.25rem);
        font-weight: 700;
        margin-bottom: 4px;
    }
    .confirm-card-subtitle {
        color: var(--primary-light);
        font-size: 0.92rem;
        font-weight: 600;
        margin-bottom: 14px;
    }
    .info-field-box {
        background-color: transparent !important;
        border: 1.5px solid var(--primary-dark);
        border-radius: 14px;
        padding: 10px 14px;
        margin-bottom: 10px;
        text-align: left;
    }
    .info-field-label {
        color: var(--primary-light);
        font-size: 0.84rem;
        font-weight: 600;
    }
    .info-field-value {
        color: #000000;
        font-size: clamp(1.15rem, 4.5vw, 1.32rem);
        font-weight: 700;
        margin-top: 2px;
        word-break: break-word;
    }

    /* Khung thông báo chung: chỉ viền và bo góc, không màu nền */
    .outlined-message {
        background-color: transparent !important;
        border: 1.8px solid var(--primary-dark);
        border-radius: 14px;
        padding: 14px 16px;
        margin: 12px 0;
        text-align: center;
        color: var(--primary-dark);
        font-weight: 600;
        font-size: 0.96rem;
    }

    /* Thanh đếm ngược 2 giây không màu nền */
    .countdown-track {
        width: 100%;
        height: 6px;
        border: 1px solid var(--primary-light);
        border-radius: 99px;
        margin-top: 14px;
        overflow: hidden;
        background-color: transparent !important;
    }
    .countdown-bar {
        height: 100%;
        background-color: var(--primary-light);
        border-radius: 99px;
        animation: shrinkProgress 2s linear forwards;
    }

    @media screen and (max-width: 360px) {
        .block-container {
            padding: 0.8rem 0.65rem 1.8rem 0.65rem !important;
        }
        div[data-testid="stTextInput"]:first-of-type input {
            letter-spacing: 3px !important;
            font-size: 1.3rem !important;
        }
        .stButton > button {
            min-height: 52px !important;
        }
    }

    @media screen and (min-width: 768px) {
        .block-container {
            max-width: 500px !important;
            padding-top: 2.5rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="student-header-box">
    <h1>ĐIỂM DANH SINH VIÊN</h1>
    <p>Hệ thống ghi nhận chuyên cần</p>
</div>
""", unsafe_allow_html=True)

force_light_inputs()


# ====================================================
# KIỂM TRA MÃ QR (chỉ làm một lần cho mỗi phiên truy cập)
# ====================================================
# Mã QR chỉ cần còn hạn lúc sinh viên MỞ trang. Sau đó sinh viên có thêm
# một khoảng thời gian ngắn để nhập thông tin, nên đang nhập dở mà mã hết hạn
# thì không bị mất dữ liệu.
if not st.session_state.verified_class_name:
    token = st.query_params.get("token", "")

    if not token:
        show_message("Đường dẫn không hợp lệ. Vui lòng quét mã QR từ giảng viên.")
        st.stop()

    token_check = security.validate_token(token)
    if not token_check.is_valid:
        show_message(token_check.message)
        st.stop()

    if class_session.is_session_closed(token_check.session_id):
        show_message("Phiên điểm danh đã kết thúc. Vui lòng xin giảng viên mã mới.")
        st.stop()

    # The QR only had to be valid when the page was OPENED. From now on the
    # student has STUDENT_FORM_SECONDS to finish, with no time pressure.
    st.session_state.verified_class_name = token_check.class_name
    st.session_state.verified_session_id = token_check.session_id
    st.session_state.submit_deadline = time.time() + security.STUDENT_FORM_SECONDS

class_session.sweep_expired()  # lazy cleanup of expired sessions' GPS data

if time.time() > st.session_state.submit_deadline:
    show_message("Mã QR đã hết hạn! Vui lòng xin giảng viên mã mới.")
    st.stop()

class_name = st.session_state.verified_class_name

st.markdown(f"""
<div class="class-status-box">
    Lớp: {html.escape(class_name)}
</div>
""", unsafe_allow_html=True)

# Read this device's cookie from the browser as soon as the class is known.
# It stays at this fixed place on every run, so it is never re-created
# (re-creating it later is what made the page re-run after a successful send).
device_cookie_name = device_check.get_cookie_name(class_name)
device_info = device_check.load_device_info(device_cookie_name)

# Browser location. Idle until the student presses "Gửi" (geo_nonce goes up),
# so the permission prompt only ever appears after they entered name and ID.
geo_result = geo.locate("student_geo", st.session_state.geo_nonce)


def submit_attendance(draft_student_id: str, draft_student_name: str, location, step_placeholder):
    """Send the check-in. `location` is a GeoResult, or None when skipped."""
    status = location.status if location else "skipped"
    latitude = location.latitude if location else None
    longitude = location.longitude if location else None
    accuracy = location.accuracy if location else None

    # Silent checks. Nothing is blocked: suspicious entries get a flag in the sheet.
    fallback_cookie_value = "" if device_info.loaded else device_check.read_header_cookie(device_cookie_name)
    client_ip = device_check.get_client_ip()
    duplicate_signals = device_check.collect_duplicate_signals(
        class_name, draft_student_id, device_info, fallback_cookie_value, client_ip
    )
    gps_flags = class_session.preview_gps_flags(class_name, status, latitude, longitude, accuracy)
    logger.info(
        "Check-in signals: device_loaded=%s duplicate_candidates=%d gps_status=%s",
        device_info.loaded, len(duplicate_signals), status,
    )

    attendance_result = gsheets_api.mark_attendance(
        class_name, draft_student_id, draft_student_name, duplicate_signals, gps_flags
    )

    if not attendance_result.success:
        show_message(attendance_result.message)
        st.html(RESTORE_SEND_BUTTON_SCRIPT, unsafe_allow_javascript=True)
        return

    # Keep this student's latest location (replaces the previous one). If the
    # lecturer set their location in the meantime, fix this student's flags too.
    current_flags = class_session.record_student_location(
        class_name, draft_student_id, status, latitude, longitude, accuracy
    )
    if current_flags is not None and current_flags != gps_flags:
        gsheets_api.apply_gps_flags(class_name, {draft_student_id: current_flags})

    device_check.remember_checkin(class_name, draft_student_id, client_ip, device_info.fingerprint)
    new_cookie_value = device_check.build_device_value(device_info, fallback_cookie_value, draft_student_id)
    got_location = status == class_session.STATUS_OK

    # Từ đây trang ở trạng thái "done": nếu có rerun bất ngờ, form nhập
    # không bao giờ quay lại và không thể gửi lần hai.
    st.session_state.checkin_step = "done"
    st.session_state.done_student_name = attendance_result.student_name
    st.session_state.done_cookie_value = new_cookie_value
    st.session_state.location_received = got_location

    # Thay thế trực tiếp khung xác nhận bằng khung thông báo thành công
    # Không gọi st.rerun() để giữ nguyên phiên kích hoạt đóng trang của trình duyệt
    with step_placeholder.container():
        render_success_card(
            draft_student_id,
            attendance_result.student_name,
            device_cookie_name,
            new_cookie_value,
            auto_close=got_location,
        )


step_placeholder = st.empty()

# ====================================================
# BƯỚC 1: NHẬP LIỆU
# ====================================================
if st.session_state.checkin_step == "input":
    with step_placeholder.container():
        student_id_input = st.text_input(
            "Mã số sinh viên",
            value=st.session_state.draft_student_id,
            max_chars=STUDENT_ID_LENGTH,
            placeholder=f"{STUDENT_ID_LENGTH} chữ số"
        )

        student_name_input = st.text_input(
            "Họ và tên",
            value=st.session_state.draft_student_name,
            max_chars=STUDENT_NAME_MAX_LENGTH,
            placeholder="Nhập họ và tên"
        )

        if not st.session_state.screen_code_ok:
            screen_code_input = st.text_input(
                "Mã xác nhận trên màn hình",
                max_chars=security.SCREEN_CODE_LENGTH,
                placeholder=f"{security.SCREEN_CODE_LENGTH} chữ số hiển thị cạnh mã QR",
            )
        else:
            screen_code_input = ""

        st.html("""
        <script>
            function bindNumericKeypad() {
                const textInputs = document.querySelectorAll('input[type="text"], input[type="tel"]');
                if (textInputs.length > 0) {
                    const studentIdInput = textInputs[0];
                    studentIdInput.setAttribute('inputmode', 'numeric');
                    studentIdInput.setAttribute('pattern', '[0-9]*');
                    studentIdInput.setAttribute('type', 'tel');
                    studentIdInput.setAttribute('maxlength', '7');
                    studentIdInput.setAttribute('autocomplete', 'off');
                    if (!studentIdInput.dataset.boundNumeric) {
                        studentIdInput.dataset.boundNumeric = 'true';
                        studentIdInput.addEventListener('input', function() {
                            const digitsOnly = this.value.replace(/[^0-9]/g, '').slice(0, 7);
                            if (this.value !== digitsOnly) {
                                this.value = digitsOnly;
                            }
                        });
                    }
                }
                const codeInput = document.querySelector('input[aria-label="Mã xác nhận trên màn hình"]');
                if (codeInput) {
                    codeInput.setAttribute('inputmode', 'numeric');
                    codeInput.setAttribute('autocomplete', 'off');
                }
            }
            bindNumericKeypad();
            setTimeout(bindNumericKeypad, 200);
        </script>
        """, unsafe_allow_javascript=True)

        if st.button("Tiếp tục", use_container_width=True):
            clean_student_id = student_id_input.strip()
            clean_student_name = " ".join(student_name_input.strip().split())

            if not clean_student_id or not clean_student_name:
                show_message("Vui lòng nhập đầy đủ Mã số sinh viên và Họ tên.")
            elif not (
                clean_student_id.isascii()
                and clean_student_id.isdigit()
                and len(clean_student_id) == STUDENT_ID_LENGTH
            ):
                show_message(f"Mã số sinh viên phải gồm đúng {STUDENT_ID_LENGTH} chữ số.")
            elif not st.session_state.screen_code_ok and not security.check_screen_code(
                class_name, st.session_state.verified_session_id, screen_code_input
            ):
                show_message(
                    "Mã xác nhận không đúng hoặc đã đổi. Hãy nhập mã đang hiển thị "
                    "trên màn hình của giảng viên."
                )
            else:
                st.session_state.screen_code_ok = True
                st.session_state.draft_student_id = clean_student_id
                st.session_state.draft_student_name = clean_student_name
                st.session_state.checkin_step = "confirm"
                st.rerun()

# ====================================================
# BƯỚC 2: XÁC NHẬN ("SỬA" VÀ "GỬI")
# ====================================================
elif st.session_state.checkin_step == "confirm":
    draft_student_id = st.session_state.draft_student_id
    draft_student_name = st.session_state.draft_student_name

    with step_placeholder.container():
        st.markdown(f"""
        <div class="confirm-card">
            <div class="confirm-card-title">XÁC NHẬN THÔNG TIN</div>
            <div class="confirm-card-subtitle">
                Kiểm tra thông tin trước khi gửi
            </div>
            <div class="info-field-box">
                <div class="info-field-label">Mã số sinh viên</div>
                <div class="info-field-value" style="letter-spacing: 3px;">
                    {html.escape(draft_student_id)}
                </div>
            </div>
            <div class="info-field-box" style="margin-bottom: 4px;">
                <div class="info-field-label">Họ và tên</div>
                <div class="info-field-value">
                    {html.escape(draft_student_name)}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        edit_column, send_column = st.columns(2)

        with edit_column:
            edit_clicked = st.button("Sửa", type="secondary", use_container_width=True)

        with send_column:
            send_clicked = st.button("Gửi", use_container_width=True)

        # Khi bấm nút "Gửi": đổi ngay nút sang màu xám và cập nhật nội dung thành "Đang điểm danh ..."
        st.html("""
        <script>
            (function() {
                const parentDocument = document;
                const allButtons = parentDocument.querySelectorAll('button');
                allButtons.forEach(button => {
                    if (button.innerText.trim() === 'Gửi' && !button.dataset.sendBound) {
                        button.dataset.sendBound = 'true';
                        button.addEventListener('click', function() {
                            setTimeout(() => {
                                this.style.setProperty('background-color', '#E5E7EB', 'important');
                                this.style.setProperty('border-color', '#9CA3AF', 'important');
                                this.style.setProperty('color', '#6B7280', 'important');
                                const labelElement = this.querySelector('p') || this;
                                labelElement.innerText = 'Đang điểm danh ...';
                            }, 10);
                        });
                    }
                });
            })();
        </script>
        """, unsafe_allow_javascript=True)

    if edit_clicked:
        st.session_state.locating = False  # cancel a pending location request
        st.session_state.checkin_step = "input"
        st.rerun()

    if send_clicked:
        if not device_info.loaded and not st.session_state.device_wait_warned:
            # The browser has not reported this device's cookie yet (very rare:
            # the student would have to be faster than the page load). Ask for
            # ONE retry instead of silently skipping the duplicate check.
            st.session_state.device_wait_warned = True
            show_message("Đang kiểm tra thiết bị. Vui lòng bấm Gửi lại.")
            st.html(RESTORE_SEND_BUTTON_SCRIPT, unsafe_allow_javascript=True)
        else:
            # Step 1 of 2: ask the browser for the location (asked again on EVERY
            # press of Gửi, so a student who denied by accident can retry).
            st.session_state.geo_nonce += 1
            st.session_state.locating = True
            st.rerun()

    elif st.session_state.locating:
        # Step 2 of 2: the browser answers (or its 15 s timeout fires), then submit.
        if geo_result is not None:
            st.session_state.locating = False
            submit_attendance(draft_student_id, draft_student_name, geo_result, step_placeholder)
        else:
            show_message("Đang xác định vị trí... Hãy chọn Cho phép nếu trình duyệt hỏi.")
            # Safety net if the location component never answers: never block.
            if st.button("Gửi không cần vị trí", type="secondary", use_container_width=True):
                st.session_state.locating = False
                submit_attendance(draft_student_id, draft_student_name, None, step_placeholder)

# ====================================================
# BƯỚC 3: ĐÃ ĐIỂM DANH XONG (chỉ hiện lại khi trang bị chạy lại)
# ====================================================
elif st.session_state.checkin_step == "done":
    with step_placeholder.container():
        render_success_card(
            st.session_state.draft_student_id,
            st.session_state.done_student_name,
            device_cookie_name,
            st.session_state.done_cookie_value,
            auto_close=st.session_state.location_received,
        )

# Lecturer shortcut: reach the teacher page from the phone that scanned the QR
# (to set the classroom location). The teacher page asks for the password.
if st.session_state.checkin_step != "done":
    st.write("")
    if st.button("Giảng viên? Mở trang giảng viên", type="secondary", use_container_width=True, key="open_teacher_page"):
        st.session_state["current_class"] = class_name
        st.switch_page("views/teacher.py")