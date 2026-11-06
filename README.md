# Hệ Thống Điểm Danh Lớp Học bằng Mã QR (Phiên bản MVP)

Dự án này là phiên bản Minimum Viable Product (MVP) được phát triển nhằm đáp ứng yêu cầu của bài tập nhóm môn học **Quản lý dự án (Project Management)**.
Hệ thống cung cấp giải pháp tự động ghi nhận giờ vào lớp của sinh viên thông qua ứng dụng di động, kết hợp xử lý dữ liệu tự động trên Google Sheets thông qua API, giúp giảng viên quản lý chuyên cần một cách chính xác và minh bạch.

---

## 🚀 Các Tính Năng Nổi Bật (MVP)

*   **Mã QR có thời hạn:** Mã QR chỉ mở được trang điểm danh trong 10 phút kể từ lúc tạo (giảng viên bấm **Làm mới mã QR** để tạo mã mới bất cứ lúc nào). Mã được ký bằng khóa bí mật nên không thể sửa hay làm giả.
*   **Điểm Danh Một Chạm:** Sinh viên chỉ cần dùng điện thoại (cùng mạng Wi-Fi với giảng viên) quét mã QR, nhập Mã Sinh Viên và Họ Tên để điểm danh.
*   **Lưu Trữ Đám Mây:** Dữ liệu điểm danh được đẩy tự động lên Google Sheets của giảng viên, mỗi ngày một cột.
*   **Đường dẫn được bảo vệ:**
    *   Trang sinh viên nằm ở một đường dẫn ngẫu nhiên, không đoán được (`/checkin-xxxxxxxxxxxxxxxx`), chỉ xuất hiện trong mã QR.
    *   Trang giảng viên ở `/teacher`, có mật khẩu, chặn thử mật khẩu liên tục, và **không có liên kết nào dẫn tới** từ các trang khác.
*   **Kiểm tra họ tên thông minh:** Mã sinh viên phải khớp tuyệt đối. Nếu mã đã có trong Google Sheets, họ tên nhập vào được so sánh không phân biệt hoa/thường và dấu: sai nhẹ (gõ sai chữ, thiếu dấu) sẽ được **tự sửa theo tên trong sheet** và chấp nhận; khác hẳn thì bị từ chối.
*   **Chống Gian Lận Âm Thầm (Anti-Cheat):** Hệ thống dùng Cookie để nhận diện thiết bị. Nếu **trong cùng một ngày** một thiết bị điểm danh cho một mã sinh viên **khác**, hệ thống vẫn ghi nhận nhưng gắn cờ `FLAG: Duplicate Device` trên Google Sheets. **Sinh viên không hề thấy thông báo nào về việc bị gắn cờ.** Sang ngày khác thì không gắn cờ.

---

## 🛠 Hướng Dẫn Cài Đặt (Dành cho Team Dev)

### 1. Yêu Cầu Hệ Thống
*   Máy tính đã cài đặt Python phiên bản 3.9 trở lên.
*   Máy tính đóng vai trò là Server (máy của giảng viên/nhóm trưởng chạy app) và điện thoại của sinh viên phải kết nối **CÙNG MỘT MẠNG WI-FI** (xem mục **Xử lý sự cố mạng** bên dưới nếu điện thoại không vào được).

### 2. Cài Đặt Môi Trường
Mở Terminal (hoặc Command Prompt) tại thư mục chứa mã nguồn dự án và chạy lệnh sau để cài đặt các thư viện cần thiết (cần Streamlit **1.46 trở lên**):
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
8. Mỗi lớp là một **Tab** trong Google Sheets (ví dụ `L01`, `L02`). Cột A là **Mã SV**, cột B là **Họ Tên**. Có thể nhập sẵn danh sách lớp; sinh viên chưa có trong danh sách sẽ được tự thêm vào cuối. Mỗi ngày hệ thống tự thêm một cột ngày mới.

### 4. Đặt Mật Khẩu Giảng Viên

Mật khẩu mặc định là `admin123` (trang giảng viên sẽ hiện cảnh báo khi còn dùng mật khẩu này). Hãy đổi bằng biến môi trường **trước khi chạy**:

```bash
# Windows (PowerShell)
$env:TEACHER_PASSWORD = "mat-khau-cua-ban"

# Windows (Command Prompt)
set TEACHER_PASSWORD=mat-khau-cua-ban

# macOS / Linux
export TEACHER_PASSWORD="mat-khau-cua-ban"
```

### 5. Khởi Động Máy Chủ (Server)

Tại thư mục chứa dự án, chạy lệnh:

```bash
streamlit run app.py
```
hoặc

```bash
python -m streamlit run app.py
```

Terminal sẽ hiển thị 2 đường link. Giảng viên mở trang quản lý bằng `http://localhost:8501/teacher`.

---

## 📖 Hướng Dẫn Sử Dụng (Luồng Hoạt Động)

### Đối Với Giảng Viên (Teacher Portal):

1. Trên máy chạy server, mở trình duyệt và gõ `http://localhost:8501/teacher` (trang này không có liên kết nào dẫn tới, phải gõ trực tiếp).
2. Nhập mật khẩu giảng viên.
3. Trang giảng viên hiển thị đường dẫn tới Google Sheets điểm danh. Nhập tên Lớp/Tab (ví dụ `L01`). Hệ thống kiểm tra tab có tồn tại không (không phân biệt hoa/thường) và báo lỗi kèm danh sách tab hiện có nếu gõ sai.
4. Bấm **Tạo mã QR** và trình chiếu mã QR (nút **Hiển thị toàn màn hình**) lên màn hình lớn cho sinh viên.
5. *Mã QR tự hết hạn sau 10 phút. Bấm **Làm mới mã QR** để tạo mã mới.*

### Đối Với Sinh Viên (Student Check-In):

1. Dùng ứng dụng Camera hoặc Zalo trên điện thoại (đã kết nối chung mạng Wi-Fi với giảng viên) để quét mã QR trên bảng.
2. Điện thoại tự động mở trang điểm danh.
3. Nhập Mã Sinh Viên (7 chữ số) và Họ Tên, bấm **Tiếp tục**, kiểm tra lại rồi bấm **Gửi**.
4. Màn hình báo thành công. Dòng của sinh viên (ở cột ngày hôm nay) sẽ tự động xuất hiện trên Google Sheets của giảng viên.

Sinh viên đã mở được trang trước khi mã hết hạn vẫn có thêm 5 phút để nhập và gửi.

---

## 🌐 Xử Lý Sự Cố Mạng (Điện Thoại Không Vào Được)

Streamlit **có hỗ trợ** truy cập từ thiết bị khác trong cùng mạng (mặc định nó lắng nghe trên mọi card mạng). Nếu điện thoại không vào được, thường là do mạng/tường lửa chứ không phải do code. Cách kiểm tra nhanh nhất: trên điện thoại (đang dùng Wi-Fi), mở trình duyệt và gõ thẳng `http://<IP máy chạy server>:8501`. Nếu cũng không vào được thì lỗi nằm ở mạng, theo thứ tự thường gặp:

1. **Wi-Fi của trường bật "cô lập thiết bị" (client/AP isolation)**: các thiết bị trên Wi-Fi không nhìn thấy nhau, rất phổ biến ở Wi-Fi trường/quán cà phê. Cũng xảy ra khi laptop cắm dây LAN còn điện thoại dùng Wi-Fi (khác phân đoạn mạng). Cách thử: dùng một laptop/điện thoại thứ hai cùng Wi-Fi để vào địa chỉ trên.
2. **Tường lửa của máy chạy server chặn cổng 8501** (hay gặp nhất trên Windows khi mạng đang đặt là *Public*). Cho phép Python/Streamlit qua tường lửa, hoặc mở cổng bằng lệnh (chạy Command Prompt bằng quyền Administrator):
   ```
   netsh advfirewall firewall add rule name="Streamlit" dir=in action=allow protocol=TCP localport=8501
   ```
3. **Mã QR chứa sai địa chỉ IP** (khi máy có VPN, WSL, Docker, VirtualBox...). So sánh địa chỉ trong "Đường dẫn kiểm thử" trên trang giảng viên với kết quả lệnh `ipconfig` (Windows) hoặc `ifconfig` (macOS/Linux). Nếu sai, nhập địa chỉ đúng vào **Tùy chọn nâng cao** trên trang giảng viên.
4. Điện thoại đang dùng 4G/5G thay vì Wi-Fi, hoặc trình duyệt bật chế độ "chỉ dùng kết nối bảo mật (HTTPS)" nên chặn địa chỉ `http://`.

**Nếu Wi-Fi của trường chặn hẳn, có 2 cách thay thế:**

*   **Phát Wi-Fi riêng:** bật Mobile Hotspot trên laptop (hoặc điện thoại) của giảng viên, sinh viên kết nối vào đó rồi quét mã QR.
*   **Đường hầm (tunnel):** chạy `cloudflared tunnel --url http://localhost:8501` (hoặc `ngrok http 8501`), rồi dán địa chỉ `https://...` nhận được vào **Tùy chọn nâng cao** trên trang giảng viên và tạo lại mã QR. Sinh viên dùng được cả 4G. **Lưu ý:** khi đó trang `/teacher` cũng truy cập được từ Internet, vì vậy bắt buộc phải đặt `TEACHER_PASSWORD` mạnh.

---

## 📁 Cấu Trúc Mã Nguồn (Folder Structure)

* `app.py`: Điểm vào của ứng dụng, khai báo các đường dẫn (URL) của từng trang.
* `views/`: Chứa các trang giao diện của Streamlit.
    * `landing.py`: Trang chủ trung lập (không tiết lộ đường dẫn nào).
    * `teacher.py`: Giao diện quản lý dành cho Giảng viên (`/teacher`).
    * `student.py`: Giao diện điểm danh dành cho Sinh viên (đường dẫn ngẫu nhiên).
* `utils/`: Chứa các hàm xử lý logic Backend.
    * `gsheets_api.py`: Kết nối và ghi dữ liệu Google Sheets (có khóa chống ghi chồng, tự thử lại khi Google báo quá tải, so khớp họ tên).
    * `security.py`: Ký và kiểm tra token, đường dẫn trang sinh viên, kiểm tra mật khẩu giảng viên, tạo hình ảnh mã QR.
    * `device_check.py`: Nhận diện thiết bị trùng bằng Cookie (theo ngày).
    * `ui_helpers.py`: Đoạn script dùng chung cho giao diện.
* `requirements.txt`: Danh sách các thư viện Python phụ thuộc.
* `credentials.json`: File chứa khóa bảo mật của Google (không đưa lên Github).
* `secret.key`: Khóa bí mật cục bộ (tự động tạo khi chạy lần đầu, không đưa lên Github). Đường dẫn trang sinh viên được suy ra từ file này; xóa file để đổi sang đường dẫn mới.

---

## ⚠️ Giới Hạn Đã Biết

*   Google Sheets API giới hạn khoảng 60 lượt đọc và 60 lượt ghi mỗi phút (theo tài liệu của Google, có thể thay đổi). Mỗi lượt điểm danh dùng 1 lượt đọc và 1 lượt ghi, nên nếu cả lớp đông quét cùng lúc, một số em có thể thấy "Hệ thống đang quá tải" và chỉ cần bấm **Gửi** lại.
*   Nhận diện thiết bị bằng Cookie chỉ ngăn được việc dùng chung điện thoại thông thường; sinh viên xóa Cookie hoặc dùng tab ẩn danh sẽ không bị phát hiện.
*   Nếu giảng viên tải lại trang `/teacher`, phiên đăng nhập và mã QR đang hiển thị sẽ mất (đăng nhập và tạo lại là được).

---

*Dự án được xây dựng phục vụ mục đích học thuật và thử nghiệm. Vui lòng không sử dụng cho các hệ thống yêu cầu bảo mật cấp doanh nghiệp nếu chưa nâng cấp cơ chế xác thực.*
