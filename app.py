import streamlit as st

st.set_page_config(
    page_title="QR Attendance",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_global_styles():
    st.markdown(
        """
        <style>
        :root {
            --qa-ink: #16243a;
            --qa-muted: #64748b;
            --qa-blue: #285bdd;
            --qa-border: #e2e8f0;
            --qa-bg: #f5f7fb;
        }

        [data-testid="stAppViewContainer"] {
            background: var(--qa-bg);
        }

        /* Header trong suốt */
        [data-testid="stHeader"] {
            background: transparent !important;
            backdrop-filter: none !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--qa-border);
        }

        .block-container {
            max-width: 1120px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        /* Tiêu đề màu đen */
        .stApp h1,
        .stApp h2,
        .stApp h3,
        .stApp h4,
        .stApp h5,
        .stApp h6 {
            color: #000000 !important;
            letter-spacing: -0.025em;
        }

        h1 {
            font-size: clamp(1.8rem, 3vw, 2.45rem);
        }

        h2 {
            font-size: clamp(1.3rem, 2vw, 1.7rem);
        }

        p, label, .stMarkdown {
            color: var(--qa-ink);
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--qa-border);
            border-radius: 18px;
            background: rgba(255,255,255,.86);
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--qa-border);
            border-radius: 15px;
            padding: 14px 16px;
        }

        div[data-testid="stAlert"] {
            border-radius: 13px;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div {
            border-radius: 11px;
            border-color: #d8e0ed;
            background: #ffffff;
        }

        .stButton > button,
        .stFormSubmitButton > button,
        div[data-testid="stPageLink"] a {
            border-radius: 11px;
            min-height: 44px;
            font-weight: 650;
        }

        .qa-eyebrow {
            color: var(--qa-blue);
            font-size: .78rem;
            font-weight: 750;
            letter-spacing: .12em;
            text-transform: uppercase;
            margin-bottom: .45rem;
        }

        .qa-muted {
            color: var(--qa-muted);
        }

        .qa-small {
            color: var(--qa-muted);
            font-size: .88rem;
        }

        .qa-hero {
            padding: 1.4rem 0 .8rem 0;
        }

        @media (max-width: 700px) {
            .block-container {
                padding: 1.1rem 1rem 2rem 1rem;
            }

            h1 {
                font-size: 1.75rem;
            }

            h2 {
                font-size: 1.35rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_global_styles()


def home_page():
    # Đã bỏ dòng QR ATTENDANCE · MVP.
    # Giữ lại tiêu đề chính.
    st.title("Điểm danh lớp học, đơn giản hơn.")

    st.markdown(
        "Một luồng thao tác ngắn gọn cho giảng viên và sinh viên — "
        "từ tạo mã QR đến gửi thông tin điểm danh."
    )

    st.write("")

    teacher_col, student_col = st.columns(2, gap="large")

    with teacher_col:
        with st.container(border=True):
            st.markdown("### 🎓 Teacher Portal")
            st.markdown(
                "Tạo mã QR cho tab Google Sheets của lớp và trình chiếu "
                "để sinh viên quét."
            )
            st.markdown("- Đăng nhập bằng mật khẩu giảng viên")
            st.markdown("- Nhập đúng tên tab, ví dụ `L01`")
            st.markdown("- QR có hiệu lực 10 phút")
            st.write("")

            st.page_link(
                "pages/1_teacher.py",
                label="Mở Teacher Portal",
                icon="🎓",
            )

    with student_col:
        with st.container(border=True):
            st.markdown("### 📱 Student Check-In")
            st.markdown(
                "Sinh viên quét QR bằng Camera hoặc Zalo, nhập MSSV và họ tên, "
                "rồi gửi điểm danh."
            )
            st.markdown("- Không cần tạo tài khoản sinh viên")
            st.markdown("- Trang mở trực tiếp từ QR")
            st.markdown("- Có thông báo kết quả gửi")
            st.write("")

            st.page_link(
                "pages/2_student.py",
                label="Mở Student Check-In",
                icon="📱",
            )

    st.write("")

    with st.container(border=True):
        st.markdown("#### Trước khi bắt đầu")

        tip1, tip2, tip3 = st.columns(3)

        with tip1:
            st.markdown("**1. Giảng viên**")
            st.caption("Chạy ứng dụng và mở Network URL.")

        with tip2:
            st.markdown("**2. Sinh viên**")
            st.caption("Quét mã QR đang được trình chiếu.")

        with tip3:
            st.markdown("**3. Hoàn tất**")
            st.caption("Chờ hệ thống xác nhận kết quả điểm danh.")

    st.caption(
        "Bản MVP. Trạng thái ghi dữ liệu phụ thuộc vào cấu hình Google Sheets "
        "và phần xử lý hiện có của dự án."
    )


navigation = st.navigation(
    {
        "QR Attendance": [
            st.Page(
                home_page,
                title="Trang chủ",
                icon="🏠",
                default=True,
            ),
            st.Page(
                "pages/1_teacher.py",
                title="Teacher Portal",
                icon="🎓",
                url_path="teacher",
            ),
            st.Page(
                "pages/2_student.py",
                title="Student Check-In",
                icon="📱",
                url_path="student",
            ),
        ]
    }
)

navigation.run()
