import streamlit as st
from utils import security
import socket

st.set_page_config(page_title="Teacher Portal", page_icon="👨‍🏫")
st.title("Teacher Portal 👨‍🏫")

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

password = st.text_input("Mật khẩu Giảng viên", type="password")

if password == "admin123":
    st.success("Đăng nhập thành công.")
    
    class_name = st.text_input("Nhập tên Lớp/Tab trên Google Sheet (VD: L01, L02)")
    
    if st.button("Tạo mã QR Điểm danh"):
        if class_name:
            token = security.generate_qr_token(class_name)
            ip = get_local_ip()
            url = f"http://{ip}:8501/student?class={class_name}&token={token}"
            img = security.make_qr_image(url)
            
            st.image(img.get_image(), caption=f"Lớp: {class_name} | Hết hạn sau 10 phút", width=400)
            st.info(f"Link trực tiếp (dùng để test): {url}")
        else:
            st.error("Vui lòng nhập tên lớp.")
