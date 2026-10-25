import time
import json
import qrcode
from cryptography.fernet import Fernet
import os
import urllib.parse

if not os.path.exists("secret.key"):
    with open("secret.key", "wb") as f:
        f.write(Fernet.generate_key())

with open("secret.key", "rb") as f:
    cipher = Fernet(f.read())

def generate_qr_token(class_name):
    data = {"class": class_name, "time": time.time()}
    token = cipher.encrypt(json.dumps(data).encode()).decode()
    return urllib.parse.quote(token)

def validate_token(token, class_name):
    try:
        decrypted = cipher.decrypt(token.encode()).decode()
        data = json.loads(decrypted)
        
        if data["class"] != class_name:
            return False, "QR code này không dành cho lớp học này."
        
        # Hết hạn sau 10 phút (600 giây)
        if time.time() - data["time"] > 600:
            return False, "Mã QR đã hết hạn! Vui lòng xin giảng viên mã mới."
            
        return True, "Hợp lệ"
    except Exception:
        return False, "Mã QR không hợp lệ hoặc đã bị hỏng."

def make_qr_image(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")
