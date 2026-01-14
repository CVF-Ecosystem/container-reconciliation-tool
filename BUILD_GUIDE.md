# Hướng Dẫn Đóng Gói (Build Guide)

## Đóng gói thành file EXE duy nhất

### Yêu cầu
- Python 3.8+
- PyInstaller (`pip install pyinstaller`)

### Cách 1: Dùng script tự động (Khuyến nghị)
```batch
# Chạy file build.bat
build.bat
```

### Cách 2: Dùng lệnh thủ công
```bash
# Clean và build
pyinstaller app_gui.spec --clean --noconfirm

# Output
dist/ContainerReconciliation_V5.7.exe
```

### Cách 3: Build từ command line (không cần spec file)
```bash
pyinstaller --onefile --windowed --name "ContainerReconciliation_V5.7" ^
    --add-data "locales;locales" ^
    --add-data "config_mappings.json;." ^
    --add-data "email_config.json;." ^
    app_gui.py
```

---

## Cấu trúc output

```
dist/
└── ContainerReconciliation_V5.7.exe   # File EXE duy nhất (~50-100 MB)
```

---

## Phân phối cho người dùng

### Các file cần gửi cho user:
1. `ContainerReconciliation_V5.7.exe` - File chương trình (chỉ cần file này!)
2. `USER_GUIDE.md` hoặc PDF - Hướng dẫn sử dụng (tùy chọn)

### ✨ Tự động tạo folder:
Khi chạy EXE lần đầu, chương trình sẽ **tự động tạo**:
- `data_input/` - Folder chứa file Excel đầu vào
- `data_output/` - Folder chứa kết quả báo cáo
- `logs/` - Folder chứa log file
- `gui_settings.ini` - File lưu cài đặt

### Cấu trúc folder sau khi chạy EXE:
```
📁 Container Reconciliation/
├── ContainerReconciliation_V5.7.exe   <- File duy nhất cần copy
├── 📁 data_input/                     <- Tự động tạo
├── 📁 data_output/                    <- Tự động tạo
├── 📁 logs/                           <- Tự động tạo
└── gui_settings.ini                   <- Tự động tạo
```

---

## Troubleshooting

### Lỗi "Missing module"
Thêm module vào `hiddenimports` trong file `app_gui.spec`

### EXE quá lớn
- Thêm module không cần vào `excludes` trong spec file
- Sử dụng UPX compression (đã bật mặc định)

### Antivirus block EXE
- Đây là false positive phổ biến với PyInstaller
- Thêm exception trong antivirus hoặc ký code với certificate

### EXE khởi động chậm
- Lần đầu chạy sẽ chậm do giải nén temp files
- Các lần sau sẽ nhanh hơn

---

## Thông tin Build

| Thông số | Giá trị |
|----------|---------|
| Version | V5.7 |
| Entry point | app_gui.py |
| Output type | Single EXE (onefile) |
| Console | No (windowed) |
| UPX compression | Yes |
| Expected size | ~50-100 MB |

---

*Cập nhật: 2026-01-14*
