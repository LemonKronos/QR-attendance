import streamlit as st
import streamlit.components.v1 as components
import extra_streamlit_components as stx
from utils import security
from utils import gsheets_api
import urllib.parse

st.set_page_config(
    page_title="Điểm Danh Sinh Viên",
    layout="centered",
    initial_sidebar_state="collapsed"
)

cookie_manager = stx.CookieManager(key="student_cookie_manager")

if "checkin_step" not in st.session_state:
    st.session_state.checkin_step = "input"
if "draft_student_id" not in st.session_state:
    st.session_state.draft_student_id = ""
if "draft_student_name" not in st.session_state:
    st.session_state.draft_student_name = ""

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

# Đảm bảo mọi khung nhập liệu luôn có nền trắng và viền #030391 độc lập với thiết bị
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

        function enforceCustomInputs() {
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
        enforceCustomInputs();
        const obs = new MutationObserver(enforceCustomInputs);
        obs.observe(parentDoc.body, { childList: true, subtree: true });
    })();
</script>
""", height=0)

query_params = st.query_params
class_name_raw = query_params.get("class", None)
token_encoded = query_params.get("token", None)

if class_name_raw and token_encoded:
    class_name = class_name_raw.strip().upper()
    token = urllib.parse.unquote(token_encoded)
    valid, msg = security.validate_token(token, class_name)

    if valid:
        st.markdown(f"""
        <div class="class-status-box">
            Lớp: {class_name}
        </div>
        """, unsafe_allow_html=True)

        step_placeholder = st.empty()

        # ====================================================
        # BƯỚC 1: NHẬP LIỆU
        # ====================================================
        if st.session_state.checkin_step == "input":
            with step_placeholder.container():
                student_id_input = st.text_input(
                    "Mã số sinh viên",
                    value=st.session_state.draft_student_id,
                    max_chars=7,
                    placeholder="7 chữ số"
                )

                student_name_input = st.text_input(
                    "Họ và tên",
                    value=st.session_state.draft_student_name,
                    placeholder="Nhập họ và tên"
                )

                components.html("""
                <script>
                    function bindNumericKeypad() {
                        const inputs = window.parent.document.querySelectorAll('input[type="text"], input[type="tel"]');
                        if (inputs.length > 0) {
                            const idInput = inputs[0];
                            idInput.setAttribute('inputmode', 'numeric');
                            idInput.setAttribute('pattern', '[0-9]*');
                            idInput.setAttribute('type', 'tel');
                            idInput.setAttribute('maxlength', '7');
                            idInput.setAttribute('autocomplete', 'off');
                            if (!idInput.dataset.boundNumeric) {
                                idInput.dataset.boundNumeric = 'true';
                                idInput.addEventListener('input', function() {
                                    const digitsOnly = this.value.replace(/[^0-9]/g, '').slice(0, 7);
                                    if (this.value !== digitsOnly) {
                                        this.value = digitsOnly;
                                    }
                                });
                            }
                        }
                    }
                    bindNumericKeypad();
                    setTimeout(bindNumericKeypad, 200);
                </script>
                """, height=0)

                if st.button("Tiếp tục", use_container_width=True):
                    clean_id = student_id_input.strip()
                    clean_name = " ".join(student_name_input.strip().split())

                    if not clean_id or not clean_name:
                        st.markdown("""
                        <div class="outlined-message">
                            Vui lòng nhập đầy đủ Mã số sinh viên và Họ tên.
                        </div>
                        """, unsafe_allow_html=True)
                    elif not (clean_id.isdigit() and len(clean_id) == 7):
                        st.markdown("""
                        <div class="outlined-message">
                            Mã số sinh viên phải gồm đúng 7 chữ số.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.session_state.draft_student_id = clean_id
                        st.session_state.draft_student_name = clean_name
                        st.session_state.checkin_step = "confirm"
                        st.rerun()

        # ====================================================
        # BƯỚC 2: XÁC NHẬN ("SỬA" VÀ "GỬI")
        # ====================================================
        elif st.session_state.checkin_step == "confirm":
            cookie_name = f"attended_{class_name}"
            cookie_val = cookie_manager.get(cookie_name)

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
                            {st.session_state.draft_student_id}
                        </div>
                    </div>
                    <div class="info-field-box" style="margin-bottom: 4px;">
                        <div class="info-field-label">Họ và tên</div>
                        <div class="info-field-value">
                            {st.session_state.draft_student_name}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if cookie_val:
                    st.markdown("""
                    <div class="outlined-message">
                        Thiết bị này đã điểm danh trước đó. Dữ liệu vẫn được ghi nhận kèm đánh dấu kiểm tra.
                    </div>
                    """, unsafe_allow_html=True)

                col_edit, col_send = st.columns(2)

                with col_edit:
                    edit_clicked = st.button("Sửa", type="secondary", use_container_width=True)

                with col_send:
                    send_clicked = st.button("Gửi", use_container_width=True)

                # Khi bấm nút "Gửi": đổi ngay nút sang màu xám và cập nhật nội dung thành "Đang điểm danh ..."
                components.html("""
                <script>
                    (function() {
                        const parentDoc = window.parent.document;
                        const buttons = parentDoc.querySelectorAll('button');
                        buttons.forEach(btn => {
                            if (btn.innerText.trim() === 'Gửi' && !btn.dataset.sendBound) {
                                btn.dataset.sendBound = 'true';
                                btn.addEventListener('click', function() {
                                    setTimeout(() => {
                                        this.style.setProperty('background-color', '#E5E7EB', 'important');
                                        this.style.setProperty('border-color', '#9CA3AF', 'important');
                                        this.style.setProperty('color', '#6B7280', 'important');
                                        const textNode = this.querySelector('p') || this;
                                        textNode.innerText = 'Đang điểm danh ...';
                                    }, 10);
                                });
                            }
                        });
                    })();
                </script>
                """, height=0)

            if edit_clicked:
                st.session_state.checkin_step = "input"
                st.rerun()

            if send_clicked:
                is_flagged = True if cookie_val else False
                success, g_msg = gsheets_api.mark_attendance(
                    class_name,
                    st.session_state.draft_student_id,
                    st.session_state.draft_student_name,
                    is_flagged
                )

                if success:
                    # Thay thế trực tiếp khung xác nhận bằng khung thông báo thành công
                    # Không gọi st.rerun() để giữ nguyên phiên kích hoạt đóng trang của trình duyệt
                    with step_placeholder.container():
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
                                    {st.session_state.draft_student_id} — {st.session_state.draft_student_name}
                                </div>
                            </div>
                            <div id="auto-exit-status" style="color: #1488DB; font-weight: 600; font-size: 0.95rem; margin-top: 12px;">
                                Tự động đóng trang sau 2 giây...
                            </div>
                            <div class="countdown-track">
                                <div class="countdown-bar"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Đặt cookie và hẹn giờ đóng trang trực tiếp trên window.parent
                        components.html(f"""
                        <script>
                            (function() {{
                                const parentWin = window.parent;
                                const parentDoc = parentWin.document;

                                // Lưu cookie đánh dấu thiết bị đã điểm danh (24 giờ)
                                parentDoc.cookie = "{cookie_name}=true; max-age=86400; path=/; SameSite=Lax";

                                if (parentWin._studentExitTimer) {{
                                    parentWin.clearTimeout(parentWin._studentExitTimer);
                                }}

                                function triggerExit() {{
                                    const ua = navigator.userAgent || "";
                                    const isAndroid = /Android/i.test(ua);

                                    // 1. Thử đóng cửa sổ/tab hiện tại
                                    try {{
                                        parentWin.open('', '_self', '');
                                        parentWin.close();
                                    }} catch (e) {{}}
                                    try {{
                                        window.top.close();
                                    }} catch (e) {{}}

                                    // 2. Trên Android: thoát thẳng ra Màn hình chính
                                    if (isAndroid) {{
                                        try {{
                                            window.top.location.href = "intent:#Intent;action=android.intent.action.MAIN;category=android.intent.category.HOME;end";
                                        }} catch (e) {{}}
                                    }}

                                    // 3. Lùi về tác vụ trước nếu có trong lịch sử trình duyệt
                                    setTimeout(function() {{
                                        try {{
                                            if (window.top.history.length > 1) {{
                                                window.top.history.back();
                                            }}
                                        }} catch (e) {{}}

                                        const statusEl = parentDoc.getElementById('auto-exit-status');
                                        if (statusEl) {{
                                            statusEl.innerText = "Đã hoàn tất điểm danh.";
                                        }}
                                    }}, 250);
                                }}

                                parentWin._studentExitTimer = parentWin.setTimeout(triggerExit, 2000);
                            }})();
                        </script>
                        """, height=0)
                else:
                    st.markdown(f"""
                    <div class="outlined-message">
                        Lỗi: {g_msg}
                    </div>
                    """, unsafe_allow_html=True)

    else:
        st.markdown(f"""
        <div class="outlined-message">
            {msg}
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="outlined-message">
        Đường dẫn không hợp lệ. Vui lòng quét mã QR từ giảng viên.
    </div>
    """, unsafe_allow_html=True)
