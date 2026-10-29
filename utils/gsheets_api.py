import gspread
from google.oauth2.service_account import Credentials
import datetime
import os

SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def get_client():
    if not os.path.exists("credentials.json"):
        return None, "Thiếu file credentials.json. Vui lòng xem README.md"
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
    return gspread.authorize(creds), "OK"

# URL Google Sheet để chạy thử
SHEET_URL = "https://docs.google.com/spreadsheets/d/11or8N-px_ac1bggLJlCaRMllQch3MCcXMF_DDZfhr3c/edit?usp=sharing"

def mark_attendance(class_name, student_id, student_name, is_flagged=False):
    client, msg = get_client()
    if not client:
        return False, msg
        
    try:
        doc = client.open_by_url(SHEET_URL)
    except Exception as e:
        return False, f"Không thể mở Google Sheet. Lỗi: {str(e)}"
        
    try:
        sheet = doc.worksheet(class_name)
    except gspread.exceptions.WorksheetNotFound:
        return False, f"Không tìm thấy Tab '{class_name}'. Vui lòng tạo tab này trên Google Sheet."

    today_date = datetime.datetime.now().strftime("%d-%b-%Y")
    records = sheet.get_all_values()
    headers = records[0] if records else ["Mã SV", "Họ Tên"]
    
    if not records:
         sheet.append_row(headers)
         records = [headers]

    if today_date not in headers:
        headers.append(today_date)
        sheet.update(range_name=f"A1:{gspread.utils.rowcol_to_a1(1, len(headers))}", values=[headers])
        col_idx = len(headers)
    else:
        col_idx = headers.index(today_date) + 1

    student_row = None
    for idx, row in enumerate(records):
        if len(row) > 0 and row[0] == student_id:
            student_row = idx + 1
            break

    mark = "FLAG: Duplicate Device" if is_flagged else "X"

    if student_row:
        sheet.update_cell(student_row, col_idx, mark)
    else:
        new_row = [student_id, student_name] + [""] * (col_idx - 3) + [mark]
        sheet.append_row(new_row)

    return True, "Thành công"
