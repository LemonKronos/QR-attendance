import html
import urllib.parse

import extra_streamlit_components as stx
import streamlit as st
from utils import gsheets_api, security


# Không dùng cache cho CookieManager.
cookie_manager = stx.CookieManager(key="attendance_cookie_manager")


# =========================================================
# CSS: Tối ưu giao diện sinh viên trên điện thoại
# =========================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 720px;
        padding: 1.5rem 1.15rem 2.5rem 1.15rem;
    }

    .student-muted {
        color: #68758a;
        font-size: .94rem;
        line-height: 1.5;
    }

    .student-class-card {
        border: 1px solid #dbe4f0;
        background: #f1f6ff;
        border-radius: 15px;
        padding: 1rem 1.05rem;
        margin: .8rem 0 1rem 0;
    }

    .student-class-label {
        color: #64748b;
        font-size: .8rem;
        margin-bottom: .2rem;
    }

    .student-class-name {
        color: #14213d;
        font-size: 1.35rem;
        font-weight: 750;
        line-height: 1.3;
        overflow-wrap: anywhere;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px;
        border-color: #dce4ef;
    }

    div[data-baseweb="input"] > div {
        border-radius: 11px;
        min-height: 47px;
    }

    div[data-baseweb="input"] input {
        font-size: 16px !important;
    }

    .stFormSubmitButton > button,
    .stButton > button {
        width: 100%;
        min-height: 48px;
        border-radius: 12px;
        font-weight: 700;
    }

    div[data-testid="stAlert"] {
        border-radius: 13px;
        overflow-wrap: anywhere;
    }

    @media (max-width: 640px) {
        .block-container {
            max-width: 100%;
            padding: 1rem .85rem 2rem .85rem;
        }

        h1 {
            font-size: 1.65rem !important;
            line-height: 1.2 !important;
            letter-spacing: -.025em;
        }

        h2, h3 {
            line-height: 1.25 !important;
        }

        .student-class-card {
            padding: .9rem;
        }

        .student-class-name {
            font-size: 1.2rem;
        }

        .stFormSubmitButton > button,
        .stButton > button {
            min-height: 52px;
            font-size: 1rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding-left: .15rem;
            padding-right: .15rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Tiêu đề trang
# Đã bỏ nhãn STUDENT CHECK-IN phía trên tiêu đề.
# =========================================================

st.title("Điểm danh sinh viên")

st.markdown(
    '<div class="student-muted">'
    "Nhập MSSV và họ tên, sau đó nhấn Điểm danh. "
    "Hãy kiểm tra lớp đang hiển thị trước khi gửi."
    "</div>",
    unsafe_allow_html=True,
)


# =========================================================
# Đọc thông tin phiên từ URL QR
# =========================================================

query_params = st.query_params

class_name = query_params.get("class", None)
token_encoded = query_params.get("token", None)

current_context = (
    str(class_name or ""),
    str(token_encoded or ""),
)

# Chỉ xóa kết quả cũ khi chuyển sang QR/phiên khác.
if st.session_state.get("student_feedback_context") != current_context:
    st.session_state["student_feedback_context"] = current_context
    st.session_state.pop("student_feedback", None)
    st.session_state.pop("student_feedback_technical_detail", None)


# =========================================================
# Lưu và hiển thị thông báo
# =========================================================

def save_feedback(
    kind,
    title,
    detail="",
    student_id="",
    student_name="",
    flagged=False,
):
    st.session_state["student_feedback"] = {
        "kind": kind,
        "title": title,
        "detail": detail,
        "student_id": student_id,
        "student_name": student_name,
        "class_name": class_name or "",
        "flagged": bool(flagged),
    }


def render_feedback():
    feedback = st.session_state.get("student_feedback")

    if not feedback:
        return

    kind = feedback.get("kind", "info")
    title = feedback.get("title", "")
    detail = feedback.get("detail", "")

    if kind == "success":
        st.success(title)
    elif kind == "warning":
        st.warning(title)
    elif kind == "error":
        st.error(title)
    else:
        st.info(title)

    if detail:
        st.caption(detail)

    if kind == "success":
        with st.container(border=True):
            st.markdown("#### Thông tin đã gửi")
            st.text(f"MSSV: {feedback.get('student_id', '')}")
            st.text(f"Họ tên: {feedback.get('student_name', '')}")
            st.text(f"Lớp: {feedback.get('class_name', '')}")

            if feedback.get("flagged"):
                st.caption(
                    "Ghi chú: Thiết bị đã được sử dụng trước đó; "
                    "lượt gửi đã được gắn cờ."
                )


# =========================================================
# Kiểm tra QR và hiển thị biểu mẫu
# =========================================================

if class_name and token_encoded:

    token = urllib.parse.unquote(str(token_encoded))

    valid, validation_message = security.validate_token(
        token,
        class_name,
    )

    if valid:

        # Thẻ thông tin lớp
        st.markdown(
            '<div class="student-class-card">'
            '<div class="student-class-label">'
            "LỚP ĐANG ĐIỂM DANH"
            "</div>"
            '<div class="student-class-name">'
            f"{html.escape(str(class_name))}"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        # Biểu mẫu sinh viên
        with st.container(border=True):

            st.subheader("Thông tin sinh viên")

            st.markdown(
                '<div class="student-muted">'
                "Hai trường bên dưới là bắt buộc."
                "</div>",
                unsafe_allow_html=True,
            )

            with st.form(
                "checkin_form",
                clear_on_submit=False,
            ):

                student_id = st.text_input(
                    "Mã số sinh viên (MSSV)",
                    placeholder="Nhập MSSV của bạn",
                    help=(
                        "Nhập MSSV dưới dạng văn bản, "
                        "kể cả khi mã bắt đầu bằng số 0."
                    ),
                    key="student_id_input",
                )

                student_name = st.text_input(
                    "Họ và tên",
                    placeholder="Nhập họ tên đầy đủ",
                    key="student_name_input",
                )

                submit = st.form_submit_button(
                    "Điểm danh",
                    type="primary",
                    use_container_width=True,
                )

        # =================================================
        # Xử lý gửi điểm danh
        # Giữ nguyên hàm Google Sheets hiện có.
        # =================================================

        if submit:

            st.session_state.pop(
                "student_feedback_technical_detail",
                None,
            )

            student_id = student_id.strip()
            student_name = " ".join(
                student_name.strip().split()
            )

            if not student_id or not student_name:

                save_feedback(
                    "error",
                    "Vui lòng nhập đầy đủ MSSV và họ tên.",
                    student_id=student_id,
                    student_name=student_name,
                )

            else:

                cookie_name = f"attended_{class_name}"
                cookie_value = cookie_manager.get(cookie_name)

                is_flagged = bool(cookie_value)

                try:
                    with st.spinner(
                        "Đang gửi thông tin điểm danh..."
                    ):

                        success, result_message = (
                            gsheets_api.mark_attendance(
                                class_name,
                                student_id,
                                student_name,
                                is_flagged,
                            )
                        )

                    # MSSV đã điểm danh trước đó.
                    if result_message == "ALREADY_ATTENDED":

                        save_feedback(
                            "info",
                            "MSSV này đã được điểm danh rồi.",
                            "Hệ thống không ghi nhận lượt trùng.",
                            student_id,
                            student_name,
                        )

                    # Gửi thành công.
                    elif success:

                        flagged = (
                            is_flagged
                            or result_message == "FLAGGED_DEVICE"
                        )

                        if flagged:

                            save_feedback(
                                "warning",
                                "Điểm danh đã được gửi thành công; "
                                "thiết bị này đã được sử dụng trước đó.",
                                "Lượt gửi vẫn được ghi nhận. "
                                "Thiết bị được gắn cờ để giảng viên xem xét.",
                                student_id,
                                student_name,
                                flagged=True,
                            )

                        else:

                            save_feedback(
                                "success",
                                "Điểm danh thành công!",
                                "Thông tin của bạn đã được gửi đến hệ thống.",
                                student_id,
                                student_name,
                            )

                        # Chỉ đặt cookie sau khi API xác nhận thành công.
                        cookie_manager.set(
                            cookie_name,
                            "true",
                            max_age=86400,
                        )

                    # Gửi thất bại.
                    else:

                        result_text = str(result_message)

                        if "Không tìm thấy Tab" in result_text:

                            friendly_error = (
                                "Không tìm thấy tab lớp trên "
                                "Google Sheets. Vui lòng kiểm tra tên lớp."
                            )

                        elif (
                            "credentials.json" in result_text
                            or "credentials" in result_text.lower()
                        ):

                            friendly_error = (
                                "Hệ thống chưa được cấu hình quyền "
                                "truy cập dữ liệu. Vui lòng báo giảng viên."
                            )

                        else:

                            friendly_error = (
                                "Chưa thể ghi nhận điểm danh. "
                                "Kiểm tra kết nối rồi thử lại."
                            )

                        save_feedback(
                            "error",
                            friendly_error,
                            "Hãy thử lại sau khi kiểm tra kết nối.",
                            student_id,
                            student_name,
                        )

                        st.session_state[
                            "student_feedback_technical_detail"
                        ] = result_text

                except Exception as exc:

                    save_feedback(
                        "error",
                        "Đã xảy ra lỗi khi gửi điểm danh. Vui lòng thử lại.",
                        "Thông báo sẽ được giữ lại trên màn hình "
                        "cho đến lần gửi tiếp theo hoặc khi mở QR khác.",
                        student_id,
                        student_name,
                    )

                    st.session_state[
                        "student_feedback_technical_detail"
                    ] = str(exc)

        # Hiển thị thông báo ngoài khối submit để giữ kết quả
        # qua các lần rerun thông thường.
        render_feedback()

        technical_detail = st.session_state.get(
            "student_feedback_technical_detail"
        )

        if (
            technical_detail
            and st.session_state.get("student_feedback")
        ):
            with st.expander("Chi tiết lỗi kỹ thuật"):
                st.code(technical_detail)

    else:

        st.error("Mã QR không hợp lệ hoặc đã hết hạn.")
        st.write(validation_message)

        st.info(
            "Vui lòng quét mã QR mới do giảng viên trình chiếu."
        )

else:

    st.warning("Chưa tìm thấy thông tin phiên điểm danh.")

    st.write(
        "Mở Camera hoặc Zalo trên điện thoại và quét mã QR "
        "do giảng viên cung cấp."
    )


# =========================================================
# Chân trang
# =========================================================

st.divider()

st.caption(
    "MVP · Kết quả điểm danh phụ thuộc vào phản hồi "
    "từ hệ thống Google Sheets."
)
