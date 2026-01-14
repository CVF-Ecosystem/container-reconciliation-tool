# Container Inventory Reconciliation Tool - V5.7

## 1. Giới Thiệu

Công cụ đối soát tồn kho container tự động giúp:
- So sánh **Tồn Cũ** (8H) vs **Tồn Mới** (15H) để tìm biến động
- Xác định nguồn gốc biến động (Gate In/Out, Tàu Nhập/Xuất, Shifting/Restow)
- Phát hiện container bất thường, trùng lặp, sai thông tin
- Xử lý container CFS (Đóng/Rút hàng đổi F/E)
- Xuất báo cáo theo hãng tàu với bộ lọc thời gian

---

## 2. Cấu Trúc Thư Mục

```
/CHECK LIST TON BAI V5.1/
├── data_input/           <- Đặt file Excel input tại đây
│   ├── N8.1.2026/        <- Có thể dùng subfolder theo ngày
│   │   ├── TON CU.xlsx   <- File không cần ngày trong tên
│   │   └── TON MOI.xlsx
│   └── TON CU N9.1.2026.xlsx  <- Hoặc file trực tiếp có ngày
├── data_output/          <- Kết quả báo cáo
│   └── Report_N12.01.2026_14h30/
├── logs/                 <- Log chi tiết
├── core/                 <- Module xử lý
├── app_gui.py            <- File GUI chính
└── USER_GUIDE_TEST.md    <- Hướng dẫn chi tiết
```

---

## 3. Tính Năng Chính

### 3.1 Đối Soát Tồn Kho
- So sánh tồn lý thuyết vs tồn thực tế
- Phân loại: Tồn chuẩn, Chênh lệch, Đảo chuyển nội bãi
- Xử lý container CFS (Đóng/Rút hàng)

### 3.2 Batch Mode - Xử Lý Nhiều Ngày
- Xử lý nhiều ngày liên tục với 1 lần click
- Tự động nhận diện ngày từ tên file/folder
- Logic: TON MOI ngày N = TON CU ngày N+1

### 3.3 Xuất Báo Cáo Theo Hãng Tàu
- Chọn ngày bằng calendar picker 📅
- Lọc theo hãng tàu (VMC, VFC, VOSCO...)
- Lọc theo ca: Sáng (8H-15H), Chiều (15H-8H), Cả ngày

### 3.4 So Sánh File App vs TOS ⭐ MỚI V5.4
- So sánh file BIẾN ĐỘNG/TỒN BÃI từ ứng dụng với file từ TOS Cảng
- Xác nhận 2 file khớp 100% hay có sai lệch
- Hiển thị chi tiết: container khớp, chỉ có trong App, chỉ có trong TOS
- Xuất báo cáo so sánh ra Excel

### 3.5 Hỗ Trợ Subfolder và Time Slots
- **Half-day mode**: `8H N7.1 - 15H N7.1` → slot 15H ngày 7/1
- **Full-day mode**: `8H N7.1 - 8H N8.1` → nguyên ngày 8/1
- Auto-detect mode từ tên folder
- Cảnh báo khi mix full-day và half-day cùng ngày

### 3.6 Nhận Diện File Input ⭐ MỚI V5.7

| Tên File | Loại | Mô tả |
|----------|------|--------|
| `TON CU.xlsx` | ton_cu | Tồn bãi cũ (baseline) |
| `TON MOI.xlsx` | ton_moi | Tồn bãi mới (thực tế) |
| `GATE IN OUT.xlsx` | gate_combined | Gate vào/ra (combined) |
| `NHAP XUAT.xlsx` | nhapxuat_combined | Nhập/xuất tàu (combined) |
| `SHIFTING.xlsx` | shifting_combined | Shifting tàu: Tàu→Bãi→Tàu |
| `RESTOW.xlsx` | shifting_combined | **Tương đương SHIFTING** |
| `N-RESTOW.xlsx` | nhap_shifting | Nhập shifting (Tàu→Bãi) |
| `X-RESTOW.xlsx` | xuat_shifting | Xuất shifting (Bãi→Tàu) |

**Lưu ý:** Nếu có cả file RESTOW và SHIFTING trong cùng slot, hệ thống sẽ cảnh báo và chọn file có time range lớn hơn.

### 3.7 Kiểm Tra Tính Liên Tục ⭐ MỚI V5.7
- Tự động phát hiện thiếu slot trong chuỗi thời gian
- Cảnh báo khi dữ liệu đã tồn tại trong database
- So sánh TON MOI slot N với TON CU slot N+1
- Xử lý cuối tuần thông minh: 15H Thứ 6 → 8H Thứ 2 là hợp lệ
- Hiển thị thời gian xử lý khi hoàn tất

---

## 4. Hướng Dẫn Nhanh

### Chạy Ứng Dụng
```bash
python app_gui.py
```

### Chuẩn Bị Dữ Liệu

**Cách 1: File trực tiếp**
```
data_input/
├── TON CU N8.1.2026.xlsx
├── TON MOI N8.1.2026.xlsx
└── GATE IN OUT N8.1.2026.xlsx
```

**Cách 2: Subfolder theo ngày (khuyến nghị)**
```
data_input/
└── N8.1.2026/
    ├── TON CU.xlsx
    ├── TON MOI.xlsx
    └── GATE IN OUT.xlsx
```

**Cách 3: Subfolder với Time Slots (⭐ MỚI V5.2)**
```
data_input/
├── 8H N7.1 - 15H N7.1/     ← Slot 15H ngày 7/1
│   ├── TON CU.xlsx
│   └── TON MOI.xlsx
├── 15H N7.1 - 8H N8.1/     ← Slot 8H ngày 8/1
│   ├── TON CU.xlsx
│   └── TON MOI.xlsx
└── 8H N7.1 - 8H N8.1/      ← Full-day ngày 8/1
    ├── TON CU.xlsx
    └── TON MOI.xlsx
```

### Xem Kết Quả
- Báo cáo lưu tại: `data_output/Report_N{DD}.{MM}.{YYYY}_{HH}h{MM}/`

---

## 5. Các File Báo Cáo

| File/Folder | Nội dung |
|------|----------|
| `1. SUMMARY.xlsx` | Tổng hợp tất cả chỉ số |
| `2. TON_BAI_CHUAN.xlsx` | Container khớp hoàn toàn |
| `3. CHENH_LECH.xlsx` | Container chênh lệch |
| `4. DAO_CHUYEN_NOI_BAI.xlsx` | Container đảo chuyển |
| `5. BIEN_DONG_CHI_TIET.xlsx` | Chi tiết biến động |
| `6_Ton_Theo_Hang/` | Thống kê theo hãng tàu (internal) |
| `7_Email_Templates/` | **MỚI V5.2**: Files gửi email hãng tàu |
| `8. MASTER_LOG.xlsx` | Log tra cứu container |
| `9. MOVEMENT_SUMMARY.xlsx` | Tổng hợp biến động |
| `10. ERRORS_V51.xlsx` | Các lỗi cần kiểm tra |

### Folder 7_Email_Templates (V5.4)
Xuất theo đúng template hãng tàu để gửi email:
```
7_Email_Templates/
├── BIEN DONG - VIMC Lines - N12.1.2026.xlsx   (49 cột - full mapping)
├── TON BAI - VIMC Lines - N12.1.2026.xlsx     (46 cột - full mapping)
├── BIEN DONG - Vinafco - N12.1.2026.xlsx
└── ...
```

**Column Mapping Coverage:**
- BIEN DONG: 55 source variants → 49 template columns (100%)
- TON BAI: 51 source variants → 46 template columns (100%)

---

## 6. Yêu Cầu Hệ Thống

- Python 3.8+
- Thư viện: pandas, openpyxl, ttkbootstrap

```bash
pip install -r requirements.txt
```

---

*Phiên bản: V5.7 - Cập nhật: 2026-01-14*
*Xem chi tiết tại: USER_GUIDE.md*