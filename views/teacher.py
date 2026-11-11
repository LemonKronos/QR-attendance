import html
import io
import logging
import math
import time
import socket

import streamlit as st

from utils import gsheets_api, security
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
    "qr_created_at": 0.0,
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
def render_qr_countdown():
    """Refresh only the countdown every second without rerunning the whole page."""
    if not st.session_state.get("qr_active"):
        return

    created_at = float(st.session_state.get("qr_created_at", 0.0) or 0.0)
    if created_at <= 0:
        return

    elapsed_seconds = max(0.0, time.time() - created_at)
    remaining_seconds = max(
        0,
        math.ceil(security.QR_VALIDITY_SECONDS - elapsed_seconds),
    )
    minutes, seconds = divmod(remaining_seconds, 60)
    escaped_class_name = html.escape(st.session_state.current_class)

    if remaining_seconds > 0:
        timer_text = f"Thời gian còn lại: {minutes:02d}:{seconds:02d}"
        timer_color = "#1488DB"
    else:
        timer_text = "Mã QR đã hết hạn. Hãy tạo mã mới để tiếp tục điểm danh."
        timer_color = "#B42318"

    st.markdown(
        f"""
        <div class="qr-container-box">
            <div class="qr-class-title">Lớp: {escaped_class_name}</div>
            <div class="qr-sub-text" style="color: {timer_color};">
                {timer_text}
            </div>
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


def generate_new_qr(tab_name: str, base_url: str):
    # Start the countdown when the signed token is created, not after PNG rendering.
    created_at = float(int(time.time()))
    token = security.generate_qr_token(tab_name)
    student_path = security.get_student_page_path()
    url = f"{base_url.rstrip('/')}/{student_path}?token={token}"
    qr_png_bytes = make_qr_png_bytes(url)

    # Replace the current QR atomically only after both URL and image are ready.
    st.session_state.current_class = tab_name
    st.session_state.qr_url = url
    st.session_state.qr_image_bytes = qr_png_bytes
    st.session_state.qr_created_at = created_at
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

    # Display only the complete, per-session attendance link generated above.
    if st.session_state.qr_active and st.session_state.qr_image_bytes:
        # The fragment updates the timer every second; the QR image and URL stay still.
        render_qr_countdown()
        escaped_qr_url = html.escape(st.session_state.qr_url, quote=True)

        # Use Streamlit's image element. Avoid HTML data: URLs and iframe scripts
        # for the actual QR image; those were the fragile part of the old display.
        _, qr_column, _ = st.columns([1, 3, 1])
        with qr_column:
            try:
                # st.image accepts a BytesIO stream for encoded PNG data.
                st.image(io.BytesIO(st.session_state.qr_image_bytes), width=350)
            except Exception:
                logger.exception("[QR] PNG was generated but Streamlit failed to display it")
                st.error(
                    "Mã QR đã được tạo nhưng không thể hiển thị. "
                    "Hãy xem terminal để biết lỗi chi tiết."
                )

        st.markdown(
            f"""
            <div class="url-outline-box">
                <span style="color: #030391; font-weight: 700; font-size: 0.92rem;">
                    Đường dẫn kiểm thử của mã QR hiện tại:
                </span><br/>
                <a href="{escaped_qr_url}" target="_blank" rel="noopener noreferrer"
                   style="color: #1488DB; font-weight: 600; text-decoration: none; font-size: 0.92rem;">
                    {escaped_qr_url}
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

