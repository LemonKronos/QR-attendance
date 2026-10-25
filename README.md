# Hệ Thống Điểm Danh Lớp Học bằng Mã QR Động (Phiên bản MVP)

Dự án này là phiên bản Minimum Viable Product (MVP) được phát triển nhằm đáp ứng yêu cầu của bài tập nhóm môn học **Quản lý dự án (Project Management)**. 
Hệ thống cung cấp giải pháp tự động ghi nhận giờ vào lớp của sinh viên thông qua ứng dụng di động, kết hợp xử lý dữ liệu tự động trên Google Sheets thông qua API, giúp giảng viên quản lý chuyên cần một cách chính xác và minh bạch.

---

## 🚀 Các Tính Năng Nổi Bật (MVP)

*   **Tạo QR Động (Dynamic QR):** Giảng viên tạo mã QR thay đổi liên tục, giới hạn thời gian quét (10 phút) để tránh việc sinh viên gửi mã cho nhau.
*   **Điểm Danh Một Chạm:** Sinh viên chỉ cần dùng điện thoại (cùng mạng Wi-Fi với giảng viên) quét mã QR, nhập Mã Sinh Viên và Họ Tên để điểm danh.
*   **Lưu Trữ Đám Mây:** Dữ liệu điểm danh được đẩy tự động theo thời gian thực lên Google Sheets của giảng viên.
*   **Chống Gian Lận (Anti-Cheat):** Hệ thống sử dụng Cookie để nhận diện thiết bị. Nếu một sinh viên cố tình dùng cùng một thiết bị để điểm danh cho nhiều người, hệ thống sẽ vẫn ghi nhận nhưng tự động gắn cờ `FLAG: Duplicate Device` trên Google Sheets để giảng viên kiểm tra lại.

---

## 🛠 Hướng Dẫn Cài Đặt (Dành cho Team Dev)

### 1. Yêu Cầu Hệ Thống
*   Máy tính đã cài đặt Python phiên bản 3.9 trở lên.
*   Máy tính đóng vai trò là Server (máy của giảng viên/nhóm trưởng chạy app) và điện thoại của sinh viên phải kết nối **CÙNG MỘT MẠNG WI-FI** (Ví dụ: Wifi HCMUT2).

### 2. Cài Đặt Môi Trường
Mở Terminal (hoặc Command Prompt) tại thư mục chứa mã nguồn dự án và chạy lệnh sau để cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt

```

### 3. Cấu Hình Google Sheets API

Để hệ thống có thể ghi dữ liệu tự động, bạn cần cấu hình tài khoản dịch vụ của Google:

1. Truy cập [Google Cloud Console](https://console.cloud.google.com/) và tạo một Project mới.
2. Bật (Enable) 2 API: **Google Sheets API** và **Google Drive API**.
3. Tạo thông tin xác thực (Credentials) dạng **Service Account**.
4. Tạo khóa (Key) mới định dạng JSON và tải về máy.
5. Đổi tên file vừa tải thành `credentials.json` và **đặt vào thư mục gốc** của dự án này.
6. **QUAN TRỌNG:** Mở file `credentials.json`, copy địa chỉ email (`client_email`). Mở file Google Sheets mà bạn muốn dùng để lưu dữ liệu, nhấn **Share** và cấp quyền **Editor** cho địa chỉ email vừa copy.
7. Mở file `utils/gsheets_api.py`, tìm biến `SHEET_URL` và thay bằng đường link (URL) thực tế của file Google Sheets đó.

### 4. Khởi Động Máy Chủ (Server)

Tại thư mục chứa dự án, chạy lệnh:

```bash
streamlit run app.py

```

Terminal sẽ hiển thị 2 đường link. Hãy sử dụng **Network URL** (ví dụ: `http://192.168.1.15:8501`) để có thể truy cập từ các thiết bị khác trong mạng.

---

## 📖 Hướng Dẫn Sử Dụng (Luồng Hoạt Động)

### Đối Với Giảng Viên (Teacher Portal):

1. Mở trình duyệt, truy cập vào đường link ứng dụng (Network URL).
2. Chọn mục **Teacher Portal** ở menu bên trái.
3. Nhập mật khẩu (Mặc định bản MVP: `admin123`).
4. Nhập tên Lớp/Tab tương ứng trên Google Sheets (Ví dụ: `L01`, `L02`). **Lưu ý: Tên này phải trùng khớp chính xác với tên Sheet (Tab) đã tạo sẵn trên Google Sheets.**
5. Bấm **Tạo mã QR Điểm danh** và trình chiếu mã QR này lên màn hình lớn cho sinh viên.
* *Mã QR có chứa mã hóa an toàn và sẽ tự động hết hạn sau 10 phút.*



### Đối Với Sinh Viên (Student Check-In):

1. Sử dụng ứng dụng Camera hoặc Zalo trên điện thoại (đã kết nối chung mạng Wi-Fi với giảng viên) để quét mã QR trên bảng.
2. Điện thoại sẽ tự động mở trang **Student Check-In**.
3. Nhập Mã Sinh Viên và Họ Tên.
4. Bấm **Điểm danh**.
5. Màn hình báo thành công. Thông tin của sinh viên (bao gồm cột ngày tháng) sẽ tự động xuất hiện trên Google Sheets của giảng viên.

---

## 📁 Cấu Trúc Mã Nguồn (Folder Structure)

* `app.py`: Trang chủ điều hướng của ứng dụng.
* `pages/`: Chứa các trang giao diện của Streamlit.
* `1_teacher.py`: Giao diện quản lý dành cho Giảng viên.
* `2_student.py`: Giao diện điểm danh dành cho Sinh viên.


* `utils/`: Chứa các hàm xử lý logic Backend.
* `gsheets_api.py`: Quản lý kết nối và thao tác đọc/ghi dữ liệu với Google Sheets API.
* `security.py`: Xử lý mã hóa, giải mã token, thời gian hết hạn và tạo hình ảnh mã QR.


* `requirements.txt`: Danh sách các thư viện Python phụ thuộc.
* `credentials.json`: File chứa khóa bảo mật của Google (không đưa lên Github).
* `secret.key`: Khóa mã hóa token cục bộ (tự động tạo khi chạy lần đầu).

---

*Dự án được xây dựng phục vụ mục đích học thuật và thử nghiệm. Vui lòng không sử dụng cho các hệ thống yêu cầu bảo mật cấp doanh nghiệp nếu chưa nâng cấp cơ chế xác thực.*

```

```