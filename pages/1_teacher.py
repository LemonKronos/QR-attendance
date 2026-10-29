import socket
import time

import streamlit as st
from utils import security


SESSION_SECONDS = 600


def get_local_ip():
    """Giữ cách xác định Network IP như dự án gốc."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        ip_address = sock.getsockname()[0]
    except Exception:
        ip_address = "127.0.0.1"
    finally:
        sock.close()
    return ip_address


def create_qr_session(class_name):
    """Dùng lại hàm tạo token/QR hiện có."""
    token = security.generate_qr_token(class_name)
    ip_address = get_local_ip()
    url = (
        f"http://{ip_address}:8501/student"
        f"?class={class_name}&token={token}"
    )
    qr_image = security.make_qr_image(url).get_image()
    now = time.time()

    st.session_state["teacher_qr_session"] = {
        "class_name": class_name,
        "url": url,
        "image": qr_image,
        "created_at": now,
        "expires_at": now + SESSION_SECONDS,
    }


# =========================================================
# CSS: Chỉ đổi màu nút Đăng xuất
# =========================================================

st.markdown(
    """
    <style>
    .st-key-teacher_logout_button button {
        background-color: #dc2626 !important;
        color: #ffffff !important;
        border: 1px solid #b91c1c !important;
        border-radius: 11px !important;
        font-weight: 650 !important;
        min-height: 44px !important;
    }

    .st-key-teacher_logout_button button:hover {
        background-color: #b91c1c !important;
        color: #ffffff !important;
        border-color: #991b1b !important;
    }

    .st-key-teacher_logout_button button p {
        color: #ffffff !important;
    }

    .st-key-teacher_logout_button button:focus:not(:active) {
        color: #ffffff !important;
        border-color: #991b1b !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Khởi tạo trạng thái
# =========================================================

if "teacher_authenticated" not in st.session_state:
    st.session_state["teacher_authenticated"] = False

if "teacher_login_error" not in st.session_state:
    st.session_state["teacher_login_error"] = ""


# =========================================================
# Tiêu đề trang
# =========================================================

st.title("Quản lý điểm danh")

st.markdown(
    '<p class="qa-muted">'
    "Tạo QR cho lớp học và theo dõi trạng thái phiên điểm danh."
    "</p>",
    unsafe_allow_html=True,
)


# =========================================================
# Đăng nhập giảng viên
# =========================================================

if not st.session_state["teacher_authenticated"]:
    spacer_l, login_col, spacer_r = st.columns([1, 1.6, 1])

    with login_col:
        with st.container(border=True):
            st.markdown("### Đăng nhập giảng viên")
            st.caption(
                "Sử dụng mật khẩu giảng viên để mở Teacher Portal."
            )

            with st.form("teacher_login_form"):
                password = st.text_input(
                    "Mật khẩu",
                    type="password",
                    placeholder="Nhập mật khẩu giảng viên",
                )

                login_clicked = st.form_submit_button(
                    "Đăng nhập",
                    type="primary",
                    use_container_width=True,
                )

            if login_clicked:
                if password.strip() == "admin123":
                    st.session_state["teacher_authenticated"] = True
                    st.session_state["teacher_login_error"] = ""
                    st.rerun()
                else:
                    st.session_state["teacher_login_error"] = (
                        "Mật khẩu chưa chính xác. Vui lòng thử lại."
                    )

            if st.session_state["teacher_login_error"]:
                st.error(st.session_state["teacher_login_error"])

            st.caption(
                "MVP hiện sử dụng mật khẩu mặc định đã thống nhất."
            )

    st.stop()


# =========================================================
# Trạng thái đăng nhập và nút đăng xuất
# =========================================================

header_col, action_col = st.columns([4, 1])

with header_col:
    st.success("Đã đăng nhập vào Teacher Portal")

with action_col:
    if st.button(
        "Đăng xuất",
        key="teacher_logout_button",
        use_container_width=True,
    ):
        st.session_state["teacher_authenticated"] = False
        st.session_state["teacher_login_error"] = ""
        st.rerun()


# =========================================================
# Kiểm tra phiên điểm danh
# =========================================================

session = st.session_state.get("teacher_qr_session")

is_expired = bool(
    session and time.time() >= session["expires_at"]
)


# =========================================================
# Chưa có phiên: tạo QR mới
# =========================================================

if not session:
    with st.container(border=True):
        st.markdown("### Tạo mã QR điểm danh")

        st.markdown(
            '<p class="qa-muted">'
            "Tên nhập vào phải trùng khớp chính xác với tên tab "
            "trên Google Sheets."
            "</p>",
            unsafe_allow_html=True,
        )

        with st.form("create_qr_form"):
            class_name = st.text_input(
                "Tên tab Google Sheets",
                placeholder="Ví dụ: L01 hoặc L02",
                help=(
                    "Nhập đúng tên tab đã tạo sẵn trên Google Sheets."
                ),
            )

            create_clicked = st.form_submit_button(
                "Tạo mã QR điểm danh",
                type="primary",
                use_container_width=True,
            )

        if create_clicked:
            if not class_name.strip():
                st.error("Vui lòng nhập tên tab Google Sheets.")
            else:
                try:
                    create_qr_session(class_name.strip())
                    st.rerun()
                except Exception:
                    st.error(
                        "Chưa thể tạo mã QR. Vui lòng kiểm tra cấu hình "
                        "ứng dụng hoặc thử lại."
                    )


# =========================================================
# Phiên đã hết hạn
# =========================================================

elif is_expired:
    with st.container(border=True):
        st.error("Mã QR đã hết hạn")

        st.markdown(
            f"Phiên điểm danh của lớp **{session['class_name']}** "
            "đã hết 10 phút. Sinh viên cần dùng mã mới để điểm danh."
        )

        if st.button(
            "Tạo mã QR mới",
            type="primary",
            use_container_width=True,
        ):
            try:
                create_qr_session(session["class_name"])
                st.rerun()
            except Exception:
                st.error("Chưa thể tạo mã mới. Vui lòng thử lại.")


# =========================================================
# Phiên đang hoạt động
# =========================================================

else:

    @st.fragment(run_every=1)
    def render_active_qr():
        current = st.session_state.get("teacher_qr_session")

        if not current:
            st.info("Chưa có phiên điểm danh.")
            return

        remaining = max(
            0,
            int(current["expires_at"] - time.time() + 0.999),
        )

        if remaining <= 0:
            st.error("Mã QR đã hết hạn")

            st.markdown(
                f"Phiên điểm danh của lớp **{current['class_name']}** "
                "đã hết 10 phút. Mã cũ không còn hiệu lực."
            )

            if st.button(
                "Tạo mã QR mới",
                type="primary",
                use_container_width=True,
                key="renew_qr_after_expiry",
            ):
                try:
                    create_qr_session(current["class_name"])
                    st.rerun()
                except Exception:
                    st.error("Chưa thể tạo mã mới. Vui lòng thử lại.")

            return

        minutes, seconds = divmod(remaining, 60)

        with st.container(border=True):
            top_col, status_col = st.columns([3, 1])

            with top_col:
                st.markdown("### Đang trình chiếu mã QR")
                st.markdown(f"## Lớp {current['class_name']}")
                st.caption(
                    "Tab Google Sheets được chọn cho phiên này."
                )

            with status_col:
                st.success("Đang mở")

            qr_col, detail_col = st.columns([1.15, 1], gap="large")

            with qr_col:
                st.image(current["image"], width=360)
                st.caption(
                    "Sinh viên dùng Camera hoặc Zalo để quét mã này."
                )

            with detail_col:
                st.markdown("#### Thời gian còn lại")

                st.markdown(
                    "<div style='font-size:2.7rem;"
                    "font-weight:750;letter-spacing:.03em'>"
                    f"{minutes:02d}:{seconds:02d}"
                    "</div>",
                    unsafe_allow_html=True,
                )

                st.progress(
                    min(1.0, remaining / SESSION_SECONDS)
                )

                st.caption("Mã QR tự hết hiệu lực sau 10 phút.")

                st.divider()

                st.metric("Lượt điểm danh đã ghi nhận", "—")

                st.caption(
                    "Vị trí thống kê đã được bố trí; dữ liệu thực cần "
                    "hàm đọc thống kê từ Google Sheets, chưa có trong "
                    "phần logic hiện tại."
                )

    render_active_qr()


# =========================================================
# Chân trang
# =========================================================

st.divider()

st.caption(
    "Lưu ý: QR và thời hạn được xử lý bởi module security hiện có. "
    "Đồng hồ trên giao diện chỉ giúp người dùng theo dõi thời gian "
    "còn lại."
)
