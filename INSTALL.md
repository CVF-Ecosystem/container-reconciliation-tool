# 📦 HƯỚNG DẪN CÀI ĐẶT VÀ SỬ DỤNG
## Container Reconciliation Tool V5.4

---

## 🔧 Yêu Cầu Hệ Thống

| Thành phần | Yêu cầu |
|------------|---------|
| **Hệ điều hành** | Windows 10/11 (64-bit) |
| **Python** | 3.10 - 3.12 |
| **RAM** | Tối thiểu 4GB, khuyến nghị 8GB |
| **Ổ đĩa** | 500MB trống |

---

## 📥 Cài Đặt

### Cách 1: Chạy từ Source Code (Development)

```powershell
# 1. Cài đặt dependencies
pip install -r requirements.txt

# 2. Chạy ứng dụng
python app_gui.py        # GUI Desktop
python main.py           # CLI/Backend
streamlit run app.py     # Web Dashboard
```

### Cách 2: Build Single EXE (Production)

```powershell
# 1. Cài PyInstaller (nếu chưa có)
pip install pyinstaller

# 2. Build EXE từ spec file
pyinstaller app_gui.spec

# 3. File EXE sẽ được tạo tại:
#    dist/ContainerReconciliation_V5.4.exe
```

---

## 📁 Cấu Trúc Thư Mục Cần Thiết

```
📂 ContainerReconciliation_V5.4/
├── 📂 data_input/          # ← Đặt file Excel đầu vào
│   └── N12.1.2026/         # Subfolder theo ngày (tùy chọn)
│       ├── TON CU.xlsx
│       ├── TON MOI.xlsx
│       └── GATE.xlsx
├── 📂 data_output/         # ← Báo cáo sẽ xuất ra đây
├── 📂 logs/                # ← File log
├── 📂 locales/             # Ngôn ngữ VI/EN
│   ├── en.json
│   └── vi.json
├── 📄 config_mappings.json # Cấu hình mapping hãng tàu
├── 📄 email_config.json    # Cấu hình email (tùy chọn)
└── 📄 ContainerReconciliation_V5.4.exe
```

---

## 🚀 Hướng Dẫn Sử Dụng

### 1. Chuẩn Bị Dữ Liệu

Đặt các file Excel vào thư mục `data_input/`:

| File | Mô tả |
|------|-------|
| `TON CU.xlsx` | Tồn kho đầu kỳ |
| `TON MOI.xlsx` | Tồn kho cuối kỳ |
| `GATE.xlsx` | Giao dịch ra/vào cổng |
| `NHAPXUAT.xlsx` | Nhập xuất tàu (tùy chọn) |

### 2. Chạy Đối Soát

1. Mở ứng dụng `ContainerReconciliation_V5.4.exe`
2. Click **"Run Reconciliation"**
3. Đợi xử lý xong
4. Kết quả xuất trong `data_output/Report_N...`

### 3. Các Tính Năng Chính

| Nút | Chức năng |
|-----|-----------|
| **Run Reconciliation** | Chạy đối soát một ngày |
| **Batch Mode** | Xử lý nhiều ngày liên tục |
| **Xuất theo Hãng** | Export báo cáo theo từng hãng tàu |
| **So sánh File** | So sánh App vs TOS |
| **Web Dashboard** | Mở giao diện web |

---

## ⚠️ Xử Lý Sự Cố

### Ứng dụng không khởi động
- Kiểm tra Python đã cài đặt: `python --version`
- Cài lại dependencies: `pip install -r requirements.txt`

### Không tìm thấy file
- Đảm bảo file Excel có tên chứa từ khóa: `TON CU`, `TON MOI`, `GATE`
- Hoặc đặt trong subfolder có ngày: `N12.1.2026/`

### Lỗi "ModuleNotFoundError"
```powershell
pip install pandas openpyxl xlsxwriter ttkbootstrap tkcalendar
```

---

## 📞 Hỗ Trợ

- **Version:** 5.4
- **Cập nhật:** 13/01/2026
- **Tests:** 443/443 passed ✅

---

*Developed with ❤️ for Container Depot Operations*
