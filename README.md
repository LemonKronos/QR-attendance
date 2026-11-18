# Hệ Thống Điểm Danh Lớp Học bằng Mã QR (Phiên bản MVP)

Dự án MVP cho bài tập môn **Quản lý dự án (Project Management)**. Giảng viên trình chiếu một mã QR; sinh viên quét bằng điện thoại, nhập Mã SV + Họ tên; kết quả được ghi tự động vào Google Sheets (mỗi lớp một tab, mỗi ngày một cột). Hệ thống chạy được trên Streamlit Community Cloud (miễn phí), không cần mạng nội bộ hay phần cứng riêng.

---

## 🚀 Tính Năng

### Điểm danh
*   **Điểm danh một chạm:** quét QR, nhập Mã SV (7 chữ số) và Họ tên, bấm **Tiếp tục**, kiểm tra lại rồi **Gửi**.
*   **Lưu trữ đám mây:** ghi thẳng vào Google Sheets; sinh viên chưa có trong danh sách sẽ được tự thêm vào cuối.
*   **Kiểm tra họ tên thông minh:** Mã SV phải khớp tuyệt đối. Nếu mã đã có trong sheet, họ tên được so sánh không phân biệt hoa/thường và dấu: sai nhẹ sẽ **tự sửa theo tên trong sheet**, khác hẳn thì bị từ chối.
*   **Đường dẫn được bảo vệ:** trang sinh viên nằm ở đường dẫn ngẫu nhiên (`/checkin-xxxxxxxxxxxxxxxx`) và chỉ mở được qua mã QR hợp lệ. Trang giảng viên ở `/teacher`, có mật khẩu và chặn thử mật khẩu liên tục.

### Chống gian lận (âm thầm)
Hệ thống **không bao giờ chặn** sinh viên. Mọi trường hợp đáng ngờ chỉ được **gắn cờ kèm lý do** trong ô của Google Sheet (nhiều cờ cách nhau bằng xuống dòng) để giảng viên kiểm tra thủ công. Sinh viên không thấy thông báo gắn cờ.

| Lớp bảo vệ | Cách hoạt động |
|---|---|
| **QR xoay vòng** | QR đổi mỗi **20 giây**; server chấp nhận mã hiện tại và mã liền trước (quét được trong 20-40 giây). Ảnh chụp hoặc đường dẫn gửi muộn sẽ vô dụng. Chỉ cần quét kịp lúc **mở trang**; sau đó sinh viên có tối đa 10 phút để nhập thông tin, không bị áp lực thời gian. |
| **Mã xác nhận trên màn hình** | Cạnh QR có mã 4 chữ số đổi mỗi **10 giây** (chấp nhận mã hiện tại và mã liền trước). Sinh viên nhập mã này một lần, ở bước **Tiếp tục**. Người ở xa chỉ có đường dẫn sẽ không có mã. |
| **Cờ `Duplicate Device`** | Một thiết bị điểm danh cho Mã SV **khác** trong cùng ngày. Kết hợp: cookie, localStorage, và (cho tab ẩn danh) **cùng IP + cùng "chữ ký" thiết bị**. IP đứng một mình không phải dấu hiệu (cả lớp dùng chung IP Wi-Fi trường). Cả hai ô (người trước và người sau) đều được gắn cờ, kèm các tín hiệu khớp. |
| **Cờ GPS** | `OUT_OF_RANGE`, `GPS_DENIED`, `GPS_LOW_ACCURACY`: so vị trí sinh viên với vị trí giảng viên (bán kính 500 m, đã trừ sai số GPS của hai thiết bị). **Chỉ hoạt động sau khi giảng viên đặt vị trí**; trước đó không ai bị gắn cờ GPS. |

Ví dụ nội dung một ô có nhiều cờ:
```
Duplicate Device: previously by 2012345 - Nguyen Van A (cookie, browser storage)
GPS_DENIED: no location from the student's device (denied)
```

---

## 📖 Hướng Dẫn Sử Dụng

### Giảng viên
1. Mở `https://<tên-app>.streamlit.app/teacher`, đăng nhập bằng mật khẩu giảng viên.
2. Nhập tên Lớp/Tab (ví dụ `L01`; không phân biệt hoa/thường, nhập sai sẽ báo kèm danh sách tab hiện có).
3. Bấm **Tạo mã QR** và trình chiếu lên màn hình lớn (nút **Hiển thị toàn màn hình**). **Giữ trang này mở:** QR và mã xác nhận tự đổi, và việc dọn dữ liệu vị trí cũng chạy từ trang này.
4. **Đặt vị trí lớp học (GPS):** GPS máy tính thường kém, nên làm bằng điện thoại:
   1. Dùng điện thoại quét chính mã QR vừa tạo, vào trang sinh viên.
   2. Kéo xuống cuối trang, bấm **Giảng viên? Mở trang giảng viên**, đăng nhập bằng mật khẩu (tên lớp được điền sẵn).
   3. Bấm **Đặt vị trí thiết bị này làm vị trí lớp học** và chọn **Cho phép** vị trí.
   
   Nút này cũng có trên máy tính. Vị trí mới kém chính xác hơn vị trí đã lưu sẽ **không ghi đè**, trừ khi giảng viên bấm xác nhận. Sinh viên điểm danh trước khi giảng viên đặt vị trí sẽ được kiểm tra lại ngay khi vị trí được đặt.
5. Một phiên kéo dài **10 phút** kể từ lúc tạo mã. **Làm mới mã QR** bắt đầu lại 10 phút (giữ nguyên dữ liệu vị trí). **Tắt mã QR** kết thúc phiên.
6. Mở Google Sheet, các ô có cờ là những dòng cần kiểm tra thủ công.

### Sinh viên
1. Quét mã QR trên bảng bằng Camera/Zalo; trang điểm danh tự mở.
2. Nhập Mã SV, Họ tên và **mã xác nhận 4 chữ số** đang hiển thị trên màn hình (nhập mã sau cùng, ngay trước khi bấm **Tiếp tục**), kiểm tra lại rồi bấm **Gửi**.
3. Cho phép vị trí khi trình duyệt hỏi (chỉ dùng để xác nhận đang ở lớp). Nếu lỡ từ chối, trang sẽ có nút **Gửi lại** để thử lại; bản ghi chỉ được cập nhật chứ không bị trùng.
4. Màn hình báo thành công và tự đóng sau 2 giây.

---

## 🔒 Dữ Liệu Vị Trí và Quyền Riêng Tư

*   Vị trí chỉ được hỏi **sau khi** sinh viên đã nhập tên và Mã SV, và chỉ trên trang điểm danh. Tọa độ **chỉ nằm trong bộ nhớ máy chủ**, không ghi vào Google Sheet; sheet chỉ nhận dòng cờ (ví dụ `OUT_OF_RANGE: about 1.8 km from the lecturer`).
*   Tọa độ **bị xóa** khi phiên hết hạn tự nhiên hoặc khi giảng viên bấm **Tắt mã QR** (không xóa khi bấm Làm mới). Các cờ đã ghi trong Google Sheet vẫn được giữ.
*   Streamlit không có bộ đếm thời gian nền, nên việc xóa chạy khi màn hình QR của giảng viên đang mở (kiểm tra mỗi giây) hoặc ở lần tải trang kế tiếp. Nếu không ai tải trang nào, tọa độ nằm trong bộ nhớ đến lần tải sau hoặc khi máy chủ khởi động lại.
*   Địa chỉ IP và chữ ký thiết bị chỉ giữ trong bộ nhớ trong ngày hôm đó, không ghi vào sheet.
*   Nếu trường có chính sách dữ liệu riêng, nên đối chiếu thêm.

---

## 🛠 Cài Đặt và Triển Khai

### Triển khai trên Streamlit Community Cloud (khuyến nghị)
Xem hướng dẫn từng bước trong **`DEPLOY_STREAMLIT_CLOUD.md`**. Tóm tắt: đưa mã lên GitHub (kho **private**), tạo app trên share.streamlit.io, dán nội dung Secrets, đặt app ở chế độ truy cập công khai (để sinh viên mở được trang điểm danh).

**Secrets** (Settings → Secrets). Mỗi khóa có thể đặt ở cấp cao nhất, hoặc trong bảng `[app]`, viết hoa hoặc thường:
```toml
PUBLIC_BASE_URL  = "https://ten-app.streamlit.app"   # phải khớp URL app
SHEET_URL        = "https://docs.google.com/spreadsheets/d/..."
TEACHER_PASSWORD = "mat-khau-manh-it-nhat-12-ky-tu"
APP_SECRET_KEY   = "64-ky-tu-hex"   # python -c "import secrets; print(secrets.token_hex(32))"

[gcp_service_account]
# ... toàn bộ nội dung file JSON của service account ...
```
Lưu ý: nếu **không** đặt mật khẩu, hệ thống dùng mật khẩu mặc định `admin123` (và cảnh báo trên trang giảng viên). Đổi mật khẩu rồi nên khởi động lại app.

### Cấu hình Google Sheets
1. Tạo Project trong [Google Cloud Console](https://console.cloud.google.com/), bật **Google Sheets API** và **Google Drive API**.
2. Tạo **Service Account**, tạo khóa JSON và tải về (`credentials.json`, **không đưa lên GitHub**).
3. Mở Google Sheet, nhấn **Share**, cấp quyền **Editor** cho `client_email` trong file JSON.
4. Mỗi lớp là một **Tab** (ví dụ `L01`). Cột A là **Mã SV**, cột B là **Họ Tên**; có thể nhập sẵn danh sách lớp. Hệ thống tự thêm cột ngày mới mỗi ngày.

Có thể dùng `python scripts/make_cloud_secrets.py` để tạo sẵn file secrets từ `credentials.json`.

### Chạy thử trên máy cá nhân
```bash
pip install -r requirements.txt        # cần Streamlit 1.46 trở lên
streamlit run app.py                   # giảng viên mở http://localhost:8501/teacher
```
Khi chạy cục bộ có thể đặt mật khẩu bằng biến môi trường `TEACHER_PASSWORD`, và dùng `credentials.json` + `secret.key` thay cho Secrets. **Lưu ý:** trình duyệt chỉ cho phép lấy vị trí trên HTTPS hoặc `localhost`; nếu chạy qua địa chỉ IP LAN bằng `http://`, tính năng GPS sẽ không hoạt động (bản trên Streamlit Cloud là HTTPS nên không bị ảnh hưởng).

---

## ⚙️ Tinh Chỉnh Thông Số

| Thông số | File | Mặc định |
|---|---|---|
| Chu kỳ đổi QR / số khung cũ được chấp nhận | `utils/security.py`: `QR_ROTATION_SECONDS`, `QR_ACCEPTED_PREVIOUS_SLOTS` | 30 s / 1 |
| Chu kỳ đổi mã xác nhận / số mã cũ được chấp nhận | `SCREEN_CODE_PERIOD_SECONDS`, `SCREEN_CODE_ACCEPTED_PREVIOUS` | 13 s / 1 |
| Thời lượng một phiên; thời gian sinh viên được nhập thông tin | `QR_VALIDITY_SECONDS`, `STUDENT_FORM_SECONDS` | 600 s |
| Bán kính GPS; ngưỡng độ chính xác "quá mờ" | `utils/class_session.py`: `GPS_RADIUS_METERS`, `GPS_LOW_ACCURACY_METERS` | 500 m / 1000 m |

Nếu sinh viên hay gặp lỗi "mã xác nhận đã đổi", tăng `SCREEN_CODE_ACCEPTED_PREVIOUS` lên 2.

---

## 📁 Cấu Trúc Mã Nguồn

* `app.py`: điểm vào, khai báo các trang (`/teacher` và đường dẫn ngẫu nhiên của sinh viên).
* `views/teacher.py`: giao diện giảng viên (đăng nhập, QR trực tiếp, mã xác nhận, đặt vị trí GPS).
* `views/student.py`: giao diện điểm danh (mã xác nhận, hỏi vị trí, gửi, thông báo thành công).
* `utils/security.py`: ký và kiểm tra token QR xoay vòng, mã xác nhận, mật khẩu giảng viên, đọc Secrets, tạo ảnh QR.
* `utils/class_session.py`: phiên điểm danh trong bộ nhớ, vị trí giảng viên/sinh viên, quy tắc cờ GPS, dọn dữ liệu khi hết phiên.
* `utils/device_check.py`: tín hiệu thiết bị trùng (cookie, localStorage, IP + chữ ký thiết bị).
* `utils/geo.py`: lấy vị trí từ trình duyệt (component tự viết, không cần thư viện thêm).
* `utils/gsheets_api.py`: đọc/ghi Google Sheets (khóa chống ghi chồng, tự thử lại khi quá tải, so khớp họ tên, ghi cờ nhiều dòng, cập nhật cờ GPS hàng loạt).
* `components/device_cookie/`, `components/geo_locator/`: hai component JavaScript nhỏ chạy trong trình duyệt.
* `scripts/make_cloud_secrets.py`: tạo file secrets từ `credentials.json`.
* `credentials.json`, `secret.key`, `.streamlit/secrets.toml`: **không đưa lên GitHub**.

---

## ⚠️ Rủi Ro Còn Lại và Giới Hạn

*   **Chuyển tiếp trực tiếp (live relay):** một bạn trong lớp chụp ảnh QR + mã xác nhận gửi ngay cho người ở nhà trong vài chục giây vẫn có thể qua được lớp QR/mã. Lớp GPS sẽ gắn cờ người đó (xa lớp) trừ khi họ giả lập vị trí. Hệ thống **làm khó và để lại dấu vết cho giảng viên kiểm tra**, chứ không chứng minh tuyệt đối sinh viên có mặt trong phòng.
*   **Giả lập GPS:** công cụ giả vị trí (Chrome DevTools, ứng dụng mock location) có thể qua mặt kiểm tra GPS nếu biết tọa độ lớp.
*   **Gắn cờ có thể nhầm:** hai điện thoại giống hệt nhau trong cùng Wi-Fi có thể bị gắn `Duplicate Device`; GPS trong nhà có thể sai vài chục đến hàng trăm mét. Vì vậy cờ chỉ để **tham khảo**, giảng viên quyết định cuối cùng.
*   **Dữ liệu trong bộ nhớ:** nếu máy chủ miễn phí ngủ hoặc khởi động lại giữa buổi, phiên và vị trí bị mất; giảng viên đăng nhập lại và bấm Tạo mã QR.
*   **Tải lại trình duyệt:** sinh viên tải lại trang bằng đường dẫn QR cũ sẽ bị từ chối (QR đã đổi) và cần quét lại. Giảng viên tải lại `/teacher` sẽ mất phiên đăng nhập và QR đang hiển thị.
*   **Giới hạn Google Sheets API:** khoảng 60 lượt đọc và 60 lượt ghi mỗi phút. Nếu cả lớp đông gửi cùng lúc, một số em có thể thấy "Hệ thống đang quá tải" và chỉ cần bấm **Gửi** lại.
*   **Trang `/teacher` truy cập được từ Internet** (và có nút dẫn từ trang sinh viên), nên bắt buộc dùng mật khẩu mạnh.
*   Streamlit Community Cloud phù hợp cho MVP/demo; hãy thử với số lượng sinh viên dự kiến trước khi dùng thật.

---

*Dự án phục vụ mục đích học thuật và thử nghiệm. Vui lòng không dùng cho hệ thống yêu cầu bảo mật cấp doanh nghiệp nếu chưa nâng cấp cơ chế xác thực.*