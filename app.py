import streamlit as st

from utils import security

# Streamlit registers page routes when the app starts. This secret path is only
# the hidden student-page entry point; it is NOT a complete attendance link.
# Each teacher-generated QR adds a fresh, signed, expiring ?token=... parameter.
pages = [
    st.Page("views/landing.py", title="Điểm danh lớp học", default=True),
    st.Page("views/teacher.py", title="Cổng giảng viên", url_path="teacher"),
    st.Page(
        "views/student.py",
        title="Điểm danh sinh viên",
        url_path=security.get_student_page_path(),
    ),
]

navigation = st.navigation(pages, position="hidden")
navigation.run()
