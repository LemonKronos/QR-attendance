import streamlit as st
import streamlit.components.v1 as components
from utils import security
import socket
import io
import base64
import time

st.set_page_config(
    page_title="Cổng Giảng Viên",
    layout="centered",
    initial_sidebar_state="collapsed"
)

if "teacher_authenticated" not in st.session_state:
    st.session_state.teacher_authenticated = False
if "qr_active" not in st.session_state:
    st.session_state.qr_active = False
if "current_class" not in st.session_state:
    st.session_state.current_class = ""
if "qr_url" not in st.session_state:
    st.session_state.qr_url = ""
if "qr_b64" not in st.session_state:
    st.session_state.qr_b64 = ""
if "qr_created_at" not in st.session_state:
    st.session_state.qr_created_at = 0.0


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def pil_to_base64(img_obj):
    pil_img = img_obj.get_image() if hasattr(img_obj, "get_image") else img_obj
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def generate_new_qr(class_name: str):
    clean_class = class_name.strip().upper()
    token = security.generate_qr_token(clean_class)
    ip = get_local_ip()
    url = f"http://{ip}:8501/student?class={clean_class}&token={token}"
    img = security.make_qr_image(url)

    st.session_state.current_class = clean_class
    st.session_state.qr_url = url
    st.session_state.qr_b64 = pil_to_base64(img)
    st.session_state.qr_created_at = time.time()
    st.session_state.qr_active = True


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

# Đảm bảo khung nhập liệu luôn có nền trắng và viền #030391 trên mọi thiết bị
components.html("""
<script>
    (function() {
        const parentDoc = window.parent.document;
        let meta = parentDoc.querySelector('meta[name="color-scheme"]');
        if (!meta) {
            meta = parentDoc.createElement('meta');
            meta.name = 'color-scheme';
            parentDoc.head.appendChild(meta);
        }
        meta.content = 'only light';

        function enforceLightInputs() {
            const wrappers = parentDoc.querySelectorAll('[data-baseweb="input"]');
            wrappers.forEach(w => {
                w.style.setProperty('background-color', '#FFFFFF', 'important');
                w.style.setProperty('background', '#FFFFFF', 'important');
                w.style.setProperty('border', '2px solid #030391', 'important');
                w.style.setProperty('border-radius', '14px', 'important');
                w.style.setProperty('box-shadow', 'none', 'important');
            });
            const innerDivs = parentDoc.querySelectorAll('[data-baseweb="base-input"], [data-baseweb="input"] > div');
            innerDivs.forEach(d => {
                d.style.setProperty('background-color', '#FFFFFF', 'important');
                d.style.setProperty('background', '#FFFFFF', 'important');
                d.style.setProperty('border', 'none', 'important');
            });
            const inputs = parentDoc.querySelectorAll('input');
            inputs.forEach(inp => {
                inp.style.setProperty('background-color', '#FFFFFF', 'important');
                inp.style.setProperty('background', '#FFFFFF', 'important');
                inp.style.setProperty('color', '#000000', 'important');
                inp.style.setProperty('-webkit-text-fill-color', '#000000', 'important');
            });
        }
        enforceLightInputs();
        const obs = new MutationObserver(enforceLightInputs);
        obs.observe(parentDoc.body, { childList: true, subtree: true });
    })();
</script>
""", height=0)


# SIGN-IN

if not st.session_state.teacher_authenticated:
    with st.form("teacher_login_form"):
        password = st.text_input(
            "Mật khẩu",
            type="password",
            placeholder="Nhập mật khẩu"
        )
        login_submit = st.form_submit_button("Đăng nhập")

        if login_submit:
            if password == "admin123":
                st.session_state.teacher_authenticated = True
                st.rerun()
            else:
                st.markdown("""
                <div class="outlined-notice">
                    Mật khẩu không chính xác.
                </div>
                """, unsafe_allow_html=True)


# QR MN

else:
    col_status, col_logout = st.columns([3.2, 1])
    with col_status:
        st.markdown("""
        <div class="outlined-notice" style="margin: 0; padding: 12px 16px;">
            Đã đăng nhập
        </div>
        """, unsafe_allow_html=True)
    with col_logout:
        if st.button("Đăng xuất", type="secondary", use_container_width=True):
            st.session_state.teacher_authenticated = False
            st.session_state.qr_active = False
            st.rerun()

    st.write("")
    class_input = st.text_input(
        "Tên lớp",
        value=st.session_state.current_class,
        placeholder="VD: L01, L02"
    )

    components.html("""
    <script>
        function bindUppercaseInput() {
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            if (inputs.length > 0) {
                const classInput = inputs[0];
                classInput.style.textTransform = 'uppercase';
                if (!classInput.dataset.upperBound) {
                    classInput.dataset.upperBound = 'true';
                    classInput.addEventListener('input', function() {
                        const start = this.selectionStart;
                        const end = this.selectionEnd;
                        const upper = this.value.toUpperCase();
                        if (this.value !== upper) {
                            this.value = upper;
                            this.setSelectionRange(start, end);
                        }
                    });
                }
            }
        }
        bindUppercaseInput();
        setTimeout(bindUppercaseInput, 200);
    </script>
    """, height=0)

    normalized_class = class_input.strip().upper()

    if st.session_state.qr_active:
        col_create, col_refresh, col_stop = st.columns(3)
        with col_create:
            if st.button("Tạo mã QR", use_container_width=True):
                if normalized_class:
                    generate_new_qr(normalized_class)
                    st.rerun()
                else:
                    st.markdown('<div class="outlined-notice">Vui lòng nhập tên lớp.</div>', unsafe_allow_html=True)
        with col_refresh:
            if st.button("Làm mới mã QR", type="secondary", use_container_width=True):
                target_class = normalized_class or st.session_state.current_class
                if target_class:
                    generate_new_qr(target_class)
                    st.rerun()
        with col_stop:
            if st.button("Tắt mã QR", type="secondary", use_container_width=True):
                st.session_state.qr_active = False
                st.session_state.qr_b64 = ""
                st.session_state.qr_url = ""
                st.rerun()
    else:
        if st.button("Tạo mã QR", use_container_width=True):
            if normalized_class:
                generate_new_qr(normalized_class)
                st.rerun()
            else:
                st.markdown('<div class="outlined-notice">Vui lòng nhập tên lớp.</div>', unsafe_allow_html=True)

    # Hiển thị QR khi đang kích hoạt
    if st.session_state.qr_active and st.session_state.qr_b64:
        elapsed = int(time.time() - st.session_state.qr_created_at)
        remaining = max(0, 600 - elapsed)

        st.markdown(f"""
        <button id="btn-open-fs" class="fs-open-btn" type="button">
            Hiển thị toàn màn hình
        </button>

        <div class="qr-container-box">
            <div class="qr-class-title">Lớp: {st.session_state.current_class}</div>
            <div class="qr-sub-text" id="normal-qr-timer">
                Thời gian còn lại: 10:00
            </div>
            <div class="qr-image-frame">
                <img src="data:image/png;base64,{st.session_state.qr_b64}" width="350" height="350" alt="QR Code" />
            </div>
            <div class="url-outline-box">
                <span style="color: #030391; font-weight: 700; font-size: 0.92rem;">
                    Đường dẫn kiểm thử:
                </span><br/>
                <a href="{st.session_state.qr_url}" target="_blank" rel="opener" style="color: #1488DB; font-weight: 600; text-decoration: none; font-size: 0.92rem;">
                    {st.session_state.qr_url}
                </a>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Gắn lớp phủ Toàn màn hình trực tiếp vào thẻ <body> gốc và căn giữa tuyệt đối
        components.html(f"""
        <script>
            (function() {{
                const parentDoc = window.parent.document;
                const openBtn = parentDoc.getElementById('btn-open-fs');
                const normalTimer = parentDoc.getElementById('normal-qr-timer');

                // Xóa overlay cũ nếu có và tạo mới trực tiếp trong document.body
                let oldOverlay = parentDoc.getElementById('teacher-fs-overlay');
                if (oldOverlay) {{
                    oldOverlay.remove();
                }}

                const overlay = parentDoc.createElement('div');
                overlay.id = 'teacher-fs-overlay';
                overlay.style.cssText = [
                    'display: none',
                    'position: fixed',
                    'top: 0',
                    'left: 0',
                    'right: 0',
                    'bottom: 0',
                    'width: 100vw',
                    'height: 100vh',
                    'background-color: #FFFFFF',
                    'z-index: 2147483647',
                    'flex-direction: column',
                    'align-items: center',
                    'justify-content: center',
                    'padding: 24px',
                    'box-sizing: border-box',
                    'margin: 0'
                ].join(' !important; ') + ' !important;';

                overlay.innerHTML = `
                    <div style="
                        background-color: #FFFFFF;
                        border: 2px solid #030391;
                        border-radius: 20px;
                        padding: 28px 40px;
                        text-align: center;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        margin: auto;
                        max-width: 90vw;
                        max-height: 92vh;
                        box-sizing: border-box;
                        font-family: 'Segoe UI', sans-serif;
                    ">
                        <button id="btn-close-fs" type="button" style="
                            background-color: #FFFFFF;
                            color: #030391;
                            border: 2px solid #030391;
                            border-radius: 14px;
                            padding: 12px 28px;
                            font-size: 1rem;
                            font-weight: 700;
                            cursor: pointer;
                            margin-bottom: 16px;
                        ">
                            Dừng toàn màn hình
                        </button>
                        <div style="color: #030391; font-size: 2rem; font-weight: 700; margin-bottom: 4px;">
                            LỚP: {st.session_state.current_class}
                        </div>
                        <div id="fs-qr-timer" style="color: #1488DB; font-size: 1.2rem; font-weight: 600; margin-bottom: 16px;">
                            Thời gian còn lại: 10:00
                        </div>
                        <div style="
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            padding: 14px;
                            border: 2px solid #030391;
                            border-radius: 18px;
                            background-color: #FFFFFF;
                            margin: 0 auto;
                        ">
                            <img src="data:image/png;base64,{st.session_state.qr_b64}"
                                 style="width: min(62vh, 500px); height: min(62vh, 500px); display: block; margin: 0 auto; image-rendering: pixelated;"
                                 alt="Fullscreen QR" />
                        </div>
                    </div>
                `;
                parentDoc.body.appendChild(overlay);

                const closeBtn = overlay.querySelector('#btn-close-fs');
                const fsTimer = overlay.querySelector('#fs-qr-timer');

                function showOverlay() {{
                    overlay.style.setProperty('display', 'flex', 'important');
                    try {{
                        if (!parentDoc.fullscreenElement) {{
                            if (overlay.requestFullscreen) {{
                                overlay.requestFullscreen().catch(() => {{}});
                            }} else if (parentDoc.documentElement.requestFullscreen) {{
                                parentDoc.documentElement.requestFullscreen().catch(() => {{}});
                            }}
                        }}
                    }} catch (e) {{}}
                }}

                function hideOverlay() {{
                    overlay.style.setProperty('display', 'none', 'important');
                    try {{
                        if (parentDoc.fullscreenElement && parentDoc.exitFullscreen) {{
                            parentDoc.exitFullscreen().catch(() => {{}});
                        }}
                    }} catch (e) {{}}
                }}

                if (openBtn) {{
                    openBtn.onclick = showOverlay;
                }}
                if (closeBtn) {{
                    closeBtn.onclick = hideOverlay;
                }}

                parentDoc.addEventListener('fullscreenchange', function() {{
                    if (!parentDoc.fullscreenElement) {{
                        overlay.style.setProperty('display', 'none', 'important');
                    }}
                }});

                let rem = {remaining};
                if (window.parent._qrTimerInterval) {{
                    clearInterval(window.parent._qrTimerInterval);
                }}
                function updateTimers() {{
                    if (rem <= 0) {{
                        if (normalTimer) normalTimer.innerText = "Đã hết hạn";
                        if (fsTimer) fsTimer.innerText = "Đã hết hạn";
                        return;
                    }}
                    const m = String(Math.floor(rem / 60)).padStart(2, '0');
                    const s = String(rem % 60).padStart(2, '0');
                    const text = "Thời gian còn lại: " + m + ":" + s;
                    if (normalTimer) normalTimer.innerText = text;
                    if (fsTimer) fsTimer.innerText = text;
                    rem--;
                }}
                updateTimers();
                window.parent._qrTimerInterval = setInterval(updateTimers, 1000);
            }})();
        </script>
        """, height=0)
