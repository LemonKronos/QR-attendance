import html
import io
import logging
import math
import time
import socket

import streamlit as st

from utils import class_session, geo, gsheets_api, security
from utils.ui_helpers import force_light_inputs

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Cổng Giảng Viên",
    layout="centered",
    initial_sidebar_state="collapsed"
)

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 60
FAILED_LOGIN_DELAY_SECONDS = 1.5

SESSION_DEFAULTS = {
    "teacher_authenticated": False,
    "failed_login_attempts": 0,
    "login_locked_until": 0.0,
    "qr_active": False,
    "current_class": "",
    "qr_url": "",
    "qr_image_bytes": b"",
    "qr_base_url": "",
    "qr_slot": -1,
    # Teacher GPS (see render_location_panel)
    "geo_nonce": 0,
    "geo_wait_nonce": 0,
    "location_message": "",
    "pending_location": None,
}
for session_key, default_value in SESSION_DEFAULTS.items():
    if session_key not in st.session_state:
        st.session_state[session_key] = default_value


def show_notice(text: str):
    st.markdown(
        f'<div class="outlined-notice">{html.escape(text)}</div>',
        unsafe_allow_html=True
    )


@st.fragment(run_every=1)
def render_live_qr():
    """The QR display. Reruns every second WITHOUT rerunning the whole page.

    Every second it: deletes expired sessions (and their GPS data), updates the
    countdown, and builds a new QR image when the 10-second slot has changed.
    The 4-digit on-screen code is shown here too.
    """
    if not st.session_state.get("qr_active"):
        return

    class_session.sweep_expired()
    class_name = st.session_state.current_class
    escaped_class_name = html.escape(class_name)
    session = class_session.get_open_session(class_name)

    if session is None:
        st.markdown(
            f"""
            <div class="qr-container-box">
                <div class="qr-class-title">Lớp: {escaped_class_name}</div>
                <div class="qr-sub-text" style="color: #B42318;">
                    Phiên điểm danh đã kết thúc. Hãy tạo mã mới để tiếp tục điểm danh.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if security.current_qr_slot() != st.session_state.qr_slot or not st.session_state.qr_image_bytes:
        try:
            build_qr_for_current_slot(session)
        except Exception:
            logger.exception("[QR] Could not rebuild the rotating QR image")

    remaining_seconds = max(0, math.ceil(session.expires_at - time.time()))
    minutes, seconds = divmod(remaining_seconds, 60)
    screen_code, code_seconds_left = security.get_screen_code(session.class_name, session.session_id)

    st.markdown(
        f"""
        <div class="qr-container-box">
            <div class="qr-class-title">Lớp: {escaped_class_name}</div>
            <div class="qr-sub-text" style="margin-bottom: 0;">
                Thời gian còn lại: {minutes:02d}:{seconds:02d}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, qr_column, _ = st.columns([1, 3, 1])
    with qr_column:
        if st.session_state.qr_image_bytes:
            st.image(io.BytesIO(st.session_state.qr_image_bytes), width=350)

    st.markdown(
        f"""
        <div class="screen-code-box">
            <div class="qr-sub-text" style="margin-bottom: 4px;">
                Mã xác nhận (sinh viên nhập sau khi quét QR) — đổi sau {code_seconds_left} giây
            </div>
            <div class="screen-code">{html.escape(screen_code)}</div>
        </div>
        <div class="url-outline-box">
            <span style="color: #030391; font-weight: 700; font-size: 0.92rem;">
                Đường dẫn kiểm thử của mã QR hiện tại (đổi mỗi {security.QR_ROTATION_SECONDS} giây):
            </span><br/>
            <a href="{html.escape(st.session_state.qr_url, quote=True)}" target="_blank" rel="noopener noreferrer"
               style="color: #1488DB; font-weight: 600; text-decoration: none; font-size: 0.92rem;">
                {html.escape(st.session_state.qr_url)}
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_local_ip_address() -> str:
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp_socket.connect(("10.255.255.255", 1))
        return udp_socket.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        udp_socket.close()


def get_default_base_url() -> str:
    # 1. Try the configured public URL (Streamlit Cloud)
    try:
        public_url = st.secrets["PUBLIC_BASE_URL"]
        if public_url:
            return public_url.rstrip("/")
    except (FileNotFoundError, KeyError):
        pass
    except st.errors.StreamlitSecretNotFoundError:
        pass

    # 2. Local development fallback
    server_port = st.get_option("server.port")
    return f"http://{get_local_ip_address()}:{server_port}"


def normalize_base_url(typed_base_url: str) -> str:
    base_url = typed_base_url.strip().rstrip("/")
    if not base_url:
        return get_default_base_url()
    if not base_url.lower().startswith(("http://", "https://")):
        looks_like_local_address = base_url[0].isdigit() or base_url.lower().startswith("localhost")
        scheme = "http" if looks_like_local_address else "https"
        base_url = f"{scheme}://{base_url}"
    return base_url


def make_qr_png_bytes(url: str) -> bytes:
    """Generate a PNG in memory for Streamlit's native image renderer."""
    qr_image = security.make_qr_image(url)
    pil_image = qr_image.get_image() if hasattr(qr_image, "get_image") else qr_image

    image_buffer = io.BytesIO()
    pil_image.save(image_buffer, format="PNG")
    png_bytes = image_buffer.getvalue()
    if not png_bytes:
        raise RuntimeError("QR image generation returned an empty PNG.")
    return png_bytes


def build_qr_for_current_slot(session) -> None:
    """Build the QR image for the current 10-second slot (a fresh signed token)."""
    token = security.generate_qr_token(session.class_name, session.session_id, session.expires_at)
    student_path = security.get_student_page_path()
    url = f"{st.session_state.qr_base_url}/{student_path}?token={token}"
    qr_png_bytes = make_qr_png_bytes(url)

    # Replace the current QR atomically only after both URL and image are ready.
    st.session_state.qr_url = url
    st.session_state.qr_image_bytes = qr_png_bytes
    st.session_state.qr_slot = security.current_qr_slot()


def generate_new_qr(tab_name: str, base_url: str):
    # Starts a session, or RENEWS the running one: the 10-minute clock restarts
    # and the stored GPS locations are kept.
    session = class_session.start_session(tab_name)
    st.session_state.current_class = session.class_name
    st.session_state.qr_base_url = base_url.rstrip("/")
    st.session_state.qr_slot = -1
    build_qr_for_current_slot(session)
    st.session_state.qr_active = True


def request_new_qr(typed_class_name: str, typed_base_url: str) -> str:
    """Create a QR code for the class. Returns an error message, or "" on success."""
    started_at = time.monotonic()
    class_name = typed_class_name.strip()
    logger.info("[QR] Request started for class=%r", class_name)

    if not class_name:
        logger.warning("[QR] Rejected request: class name is empty")
        return "Vui lòng nhập tên lớp."

    try:
        logger.info("[QR] Stage 1/3: checking class tab in Google Sheets")
        lookup_result = gsheets_api.lookup_class_tab(class_name)
        if not lookup_result.success:
            logger.warning("[QR] Class lookup failed: %s", lookup_result.message)
            return lookup_result.message

        logger.info("[QR] Stage 2/3: generating signed session URL")
        base_url = normalize_base_url(typed_base_url)
        generate_new_qr(lookup_result.tab_name, base_url)

        image_size = len(st.session_state.qr_image_bytes)
        logger.info(
            "[QR] Stage 3/3: success; class=%r image_bytes=%d elapsed=%.2fs",
            lookup_result.tab_name,
            image_size,
            time.monotonic() - started_at,
        )
        return ""
    except Exception as error:
        logger.exception("[QR] Failed during QR generation after %.2fs", time.monotonic() - started_at)
        return f"Không thể tạo mã QR ({type(error).__name__}): {error}"


def handle_teacher_location_result(class_name: str, result) -> None:
    """Store the lecturer's location (once per button press) and refresh the flags."""
    if result.status != "ok":
        if result.status == "denied":
            st.session_state.location_message = (
                "Trình duyệt từ chối quyền vị trí. Hãy cho phép vị trí cho trang này "
                "(biểu tượng ổ khóa cạnh thanh địa chỉ) rồi bấm lại."
            )
        else:
            st.session_state.location_message = (
                "Không lấy được vị trí. Máy tính thường có GPS kém hoặc bị tắt; "
                "hãy thử bằng điện thoại."
            )
        return

    accuracy = float(result.accuracy or 0.0)
    old_accuracy = class_session.get_teacher_status(class_name).get("accuracy", 0.0)
    outcome = class_session.set_teacher_location(class_name, result.latitude, result.longitude, accuracy)

    if outcome == class_session.OUTCOME_NO_SESSION:
        st.session_state.location_message = "Phiên điểm danh của lớp này đã kết thúc. Hãy tạo mã QR mới."
    elif outcome == class_session.OUTCOME_KEPT_BETTER:
        st.session_state.pending_location = (class_name, result.latitude, result.longitude, accuracy)
        st.session_state.location_message = (
            f"Vị trí mới kém chính xác hơn (±{accuracy:.0f} m) so với vị trí đã lưu "
            f"(±{old_accuracy:.0f} m) nên vẫn giữ vị trí cũ."
        )
    else:
        st.session_state.pending_location = None
        st.session_state.location_message = apply_new_teacher_location_message(class_name, accuracy)


def apply_new_teacher_location_message(class_name: str, accuracy: float) -> str:
    with st.spinner("Đang cập nhật cờ GPS cho sinh viên..."):
        update_result = class_session.recompute_all_gps_flags(class_name)
    if update_result.success:
        return f"Đã đặt vị trí lớp học (±{accuracy:.0f} m) và cập nhật cờ GPS."
    return (
        f"Đã đặt vị trí lớp học (±{accuracy:.0f} m) nhưng chưa cập nhật được Google Sheet: "
        f"{update_result.message}"
    )


def render_location_panel(typed_class_name: str) -> None:
    """Button that stores THIS device's location as the classroom location."""
    st.markdown('<div class="section-title">Vị trí lớp học (GPS)</div>', unsafe_allow_html=True)
    class_name = typed_class_name or st.session_state.current_class

    # Fixed place on every run. Idle until the button raises geo_nonce.
    geo_result = geo.locate("teacher_geo", st.session_state.geo_nonce, timeout_ms=20000)
    waiting = st.session_state.geo_wait_nonce == st.session_state.geo_nonce > 0
    if waiting and geo_result is not None:
        st.session_state.geo_wait_nonce = 0
        waiting = False
        handle_teacher_location_result(class_name, geo_result)

    status = class_session.get_teacher_status(class_name) if class_name else {"session_open": False}

    if status.get("session_open") and status.get("has_location"):
        show_notice(
            f"Đã đặt vị trí lớp học (±{status['accuracy']:.0f} m). "
            f"Sinh viên đã gửi vị trí: {status['students_with_location']}/{status['students_total']}."
        )
    elif status.get("session_open"):
        show_notice("Chưa đặt vị trí lớp học. Khi chưa đặt, không ai bị gắn cờ GPS.")
    else:
        st.caption(
            "Tạo mã QR trước, rồi bấm nút bên dưới trên điện thoại (GPS điện thoại chính xác hơn "
            "máy tính). Nút này dùng được trên cả máy tính lẫn điện thoại."
        )

    if st.button("Đặt vị trí thiết bị này làm vị trí lớp học", key="set_teacher_location", use_container_width=True):
        if not class_name:
            st.session_state.location_message = "Vui lòng nhập tên lớp."
        elif not status.get("session_open"):
            st.session_state.location_message = (
                "Lớp này chưa có phiên điểm danh đang chạy. Hãy tạo mã QR trước."
            )
        else:
            st.session_state.geo_nonce += 1
            st.session_state.geo_wait_nonce = st.session_state.geo_nonce
            st.session_state.location_message = ""
            st.session_state.pending_location = None
            st.rerun()

    if waiting:
        show_notice("Đang xác định vị trí... Hãy chọn Cho phép nếu trình duyệt hỏi.")

    pending = st.session_state.pending_location
    if pending and pending[0] == class_name:
        if st.button("Vẫn dùng vị trí kém chính xác hơn này", type="secondary", use_container_width=True):
            _, latitude, longitude, accuracy = pending
            class_session.set_teacher_location(class_name, latitude, longitude, accuracy, force=True)
            st.session_state.pending_location = None
            st.session_state.location_message = apply_new_teacher_location_message(class_name, accuracy)
            st.rerun()

    if st.session_state.location_message:
        show_notice(st.session_state.location_message)


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
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    .block-container {
        max-width: 720px !important;
        padding-top: 2.2rem !important;
        padding-bottom: 3rem !important;
        margin: 0 auto !important;
    }

    /* Khung tiêu đề chỉ dùng viền bo góc, không màu nền */
    .header-box {
        background-color: transparent !important;
        border: 2px solid var(--primary-dark);
        border-radius: 18px;
        padding: 20px 24px;
        margin-bottom: 22px;
        text-align: center;
    }
    .header-box h1 {
        color: var(--primary-dark) !important;
        font-weight: 700 !important;
        font-size: 1.85rem !important;
        margin: 0 !important;
        letter-spacing: 0.5px;
    }
    .header-box p {
        color: var(--primary-light) !important;
        font-size: 0.98rem !important;
        font-weight: 600 !important;
        margin: 6px 0 0 0 !important;
    }

    /* Khung thông báo chỉ có viền và bo góc, không màu nền */
    .outlined-notice {
        background-color: transparent !important;
        border: 1.8px solid var(--primary-dark);
        border-radius: 14px;
        padding: 12px 18px;
        margin: 10px 0 16px 0;
        text-align: center;
        color: var(--primary-dark);
        font-weight: 600;
        font-size: 0.98rem;
    }

    /* Khung Form trong suốt */
    div[data-testid="stForm"] {
        border: 1.8px solid var(--primary-dark) !important;
        border-radius: 18px !important;
        padding: 22px !important;
        background-color: #FFFFFF !important;
    }

    /* Thiết kế khung nhập liệu độc lập với thiết bị: Nền trắng, chỉ có viền xanh dương đậm (#030391) */
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
        min-height: 56px !important;
        padding: 0 4px !important;
        transition: box-shadow 0.2s ease !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
        border: none !important;
        background-color: #FFFFFF !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border: 2px solid #030391 !important;
        box-shadow: 0 0 0 3px rgba(3, 3, 145, 0.12) !important;
    }

    div[data-testid="stTextInput"] input {
        -webkit-appearance: none !important;
        appearance: none !important;
        background: #FFFFFF !important;
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        caret-color: #030391 !important;
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        padding: 12px 14px !important;
    }

    div[data-testid="stTextInput"] input::placeholder {
        color: #7A869A !important;
        -webkit-text-fill-color: #7A869A !important;
        font-weight: 400 !important;
    }

    div[data-testid="stTextInput"] input:-webkit-autofill,
    div[data-testid="stTextInput"] input:-webkit-autofill:hover,
    div[data-testid="stTextInput"] input:-webkit-autofill:focus {
        -webkit-box-shadow: 0 0 0 1000px #FFFFFF inset !important;
        -webkit-text-fill-color: #000000 !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="input"] button {
        background: #FFFFFF !important;
        background-color: #FFFFFF !important;
        color: #030391 !important;
        border: none !important;
    }

    .stTextInput label p {
        color: var(--primary-dark) !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        margin-bottom: 4px !important;
    }

    /* Nút bấm viền bo góc, nền trắng */
    .stButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #FFFFFF !important;
        color: var(--primary-dark) !important;
        border: 2px solid var(--primary-dark) !important;
        border-radius: 14px !important;
        min-height: 52px !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        border-color: var(--primary-light) !important;
        color: var(--primary-light) !important;
    }
    .stButton > button:active,
    div[data-testid="stFormSubmitButton"] > button:active {
        transform: scale(0.985) !important;
    }

    button[kind="secondary"] {
        border: 1.8px solid var(--primary-light) !important;
        color: var(--primary-light) !important;
    }
    button[kind="secondary"]:hover {
        border-color: var(--primary-dark) !important;
        color: var(--primary-dark) !important;
    }

    /* Khung hiển thị mã QR */
    .qr-container-box {
        background-color: transparent !important;
        border: 2px solid var(--primary-dark);
        border-radius: 18px;
        padding: 24px 20px;
        margin-top: 16px;
        text-align: center;
    }
    .qr-class-title {
        color: var(--primary-dark);
        font-size: 1.55rem;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .qr-sub-text {
        color: var(--primary-light);
        font-size: 0.98rem;
        font-weight: 600;
        margin-bottom: 16px;
    }
    .qr-image-frame {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 12px;
        border: 1.8px solid var(--primary-dark);
        border-radius: 16px;
        background-color: #FFFFFF;
        margin: 0 auto;
    }
    .qr-image-frame img {
        image-rendering: pixelated;
        image-rendering: crisp-edges;
        display: block;
        margin: 0 auto;
    }
    .screen-code-box {
        background-color: transparent !important;
        border: 2px solid var(--primary-dark);
        border-radius: 18px;
        padding: 14px 20px;
        margin-top: 12px;
        text-align: center;
    }
    .screen-code {
        color: var(--primary-dark);
        font-size: 3.2rem;
        font-weight: 700;
        letter-spacing: 14px;
        padding-left: 14px;
        line-height: 1.1;
    }
    .section-title {
        color: var(--primary-dark);
        font-size: 1.15rem;
        font-weight: 700;
        margin: 22px 0 8px 0;
    }
    .url-outline-box {
        background-color: transparent !important;
        border: 1.5px solid var(--primary-light);
        border-radius: 14px;
        padding: 10px 14px;
        margin-top: 18px;
        text-align: center;
        word-break: break-all;
    }

    .fs-open-btn {
        background-color: #FFFFFF;
        color: var(--primary-dark);
        border: 2px solid var(--primary-dark);
        border-radius: 14px;
        min-height: 52px;
        width: 100%;
        font-size: 1rem;
        font-weight: 700;
        cursor: pointer;
        margin-top: 8px;
        transition: all 0.2s ease;
    }
    .fs-open-btn:hover {
        border-color: var(--primary-light);
        color: var(--primary-light);
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-box">
    <h1>CỔNG GIẢNG VIÊN</h1>
    <p>Quản lý điểm danh bằng mã QR</p>
</div>
""", unsafe_allow_html=True)

force_light_inputs()

# Lazy cleanup: delete expired attendance sessions (and their GPS data).
class_session.sweep_expired()


# SIGN-IN

if not st.session_state.teacher_authenticated:
    with st.form("teacher_login_form"):
        password = st.text_input(
            "Mật khẩu",
            type="password",
            placeholder="Nhập mật khẩu"
        )
        login_submitted = st.form_submit_button("Đăng nhập")

        if login_submitted:
            seconds_until_unlock = math.ceil(st.session_state.login_locked_until - time.time())

            if seconds_until_unlock > 0:
                show_notice(f"Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau {seconds_until_unlock} giây.")
            elif security.check_teacher_password(password):
                st.session_state.failed_login_attempts = 0
                st.session_state.teacher_authenticated = True
                st.rerun()
            else:
                # The pause makes guessing passwords by trial and error very slow.
                time.sleep(FAILED_LOGIN_DELAY_SECONDS)
                st.session_state.failed_login_attempts += 1

                if st.session_state.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                    st.session_state.failed_login_attempts = 0
                    st.session_state.login_locked_until = time.time() + LOGIN_LOCK_SECONDS
                    show_notice(f"Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau {LOGIN_LOCK_SECONDS} giây.")
                else:
                    show_notice("Mật khẩu không chính xác.")


# QR MANAGEMENT

else:
    status_column, logout_column = st.columns([3.2, 1])
    with status_column:
        st.markdown("""
        <div class="outlined-notice" style="margin: 0; padding: 12px 16px;">
            Đã đăng nhập
        </div>
        """, unsafe_allow_html=True)
    with logout_column:
        if st.button("Đăng xuất", type="secondary", use_container_width=True):
            st.session_state.teacher_authenticated = False
            st.session_state.qr_active = False
            st.rerun()

    st.write("")

    if security.is_using_default_teacher_password():
        show_notice(
            "Đang dùng mật khẩu mặc định. Hãy đặt "
            f"{security.TEACHER_PASSWORD_ENVIRONMENT_VARIABLE} trong Streamlit Secrets "
            "(hoặc biến môi trường khi chạy local) để đổi mật khẩu."
        )

    escaped_sheet_url = html.escape(gsheets_api.SHEET_URL, quote=True)
    st.markdown(f"""
    <div class="url-outline-box" style="margin: 0 0 16px 0;">
        <span style="color: #030391; font-weight: 700; font-size: 0.92rem;">
            Google Sheet điểm danh:
        </span><br/>
        <a href="{escaped_sheet_url}" target="_blank" rel="noopener noreferrer" style="color: #1488DB; font-weight: 600; text-decoration: none; font-size: 0.92rem;">
            {escaped_sheet_url}
        </a>
    </div>
    """, unsafe_allow_html=True)

    class_input = st.text_input(
        "Tên lớp",
        value=st.session_state.current_class,
        placeholder="VD: L01, L02"
    )
    typed_class_name = class_input.strip()

    with st.expander("Tùy chọn nâng cao"):
        base_url_input = st.text_input(
            "Địa chỉ máy chủ (không bắt buộc)",
            key="base_url_input",
            placeholder=get_default_base_url()
        )
        st.caption(
            "Để deploy cloud, đặt PUBLIC_BASE_URL trong Streamlit Secrets thành URL "
            "https://...streamlit.app. Ô này chỉ dùng để ghi đè tạm thời; để trống "
            "sẽ tự dùng PUBLIC_BASE_URL (hoặc IP LAN khi chạy local)."
        )

    qr_error_message = ""

    if st.session_state.qr_active:
        create_column, refresh_column, stop_column = st.columns(3)
        with create_column:
            if st.button("Tạo mã QR", use_container_width=True):
                with st.spinner("Đang kiểm tra lớp và tạo mã QR..."):
                    qr_error_message = request_new_qr(typed_class_name, base_url_input)
                if not qr_error_message:
                    st.rerun()
        with refresh_column:
            if st.button("Làm mới mã QR", type="secondary", use_container_width=True):
                with st.spinner("Đang kiểm tra lớp và tạo mã QR mới..."):
                    qr_error_message = request_new_qr(
                        typed_class_name or st.session_state.current_class,
                        base_url_input
                    )
                if not qr_error_message:
                    st.rerun()
        with stop_column:
            if st.button("Tắt mã QR", type="secondary", use_container_width=True):
                # Stopping deletes this session's GPS data (flags stay in the sheet).
                class_session.stop_session(st.session_state.current_class)
                st.session_state.qr_active = False
                st.session_state.qr_image_bytes = b""
                st.session_state.qr_url = ""
                st.rerun()
    else:
        if st.button("Tạo mã QR", use_container_width=True):
            with st.spinner("Đang kiểm tra lớp và tạo mã QR..."):
                qr_error_message = request_new_qr(typed_class_name, base_url_input)
            if not qr_error_message:
                st.rerun()

    if qr_error_message:
        show_notice(qr_error_message)

    # The live QR (rotating token + on-screen code). It refreshes by itself.
    if st.session_state.qr_active:
        render_live_qr()

    render_location_panel(typed_class_name)
