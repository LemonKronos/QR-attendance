import streamlit as st
import extra_streamlit_components as stx
from utils import security
from utils import gsheets_api
import urllib.parse

st.set_page_config(page_title="Student Check-In", page_icon="📱")
st.title("Điểm danh Sinh viên 📱")

@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

query_params = st.query_params
class_name = query_params.get("class", None)
token_encoded = query_params.get("token", None)

if class_name and token_encoded:
    token = urllib.parse.unquote(token_encoded)
    valid, msg = security.validate_token(token, class_name)
    
    if valid:
        st.success(f"Đã kết nối tới Lớp: **{class_name}**")
        
        with st.form("checkin_form"):
            student_id = st.text_input("Mã SV (Student ID)")
            student_name = st.text_input("Họ Tên (Full Name)")
            submit = st.form_submit_button("Điểm danh")
            
            if submit:
                if not student_id or not student_name:
                    st.error("Vui lòng nhập đầy đủ Mã SV và Họ Tên.")
                else:
                    cookie_name = f"attended_{class_name}"
                    cookie_val = cookie_manager.get(cookie_name)
                    is_flagged = False
                    
                    if cookie_val:
                        st.warning("Thiết bị này đã được sử dụng để điểm danh! Dữ liệu của bạn vẫn được gửi nhưng sẽ bị gắn cờ (Flag) nghi ngờ gian lận.")
                        is_flagged = True
                        
                    with st.spinner("Đang lưu dữ liệu..."):
                        success, g_msg = gsheets_api.mark_attendance(class_name, student_id, student_name, is_flagged)
                        
                        if success:
                            st.success("Điểm danh thành công! Bạn có thể đóng trang này.")
                            cookie_manager.set(cookie_name, "true", max_age=86400)
                        else:
                            st.error(f"Lỗi: {g_msg}")
    else:
        st.error(f"❌ {msg}")
else:
    st.error("Link không hợp lệ. Vui lòng quét mã QR do giảng viên cung cấp.")
