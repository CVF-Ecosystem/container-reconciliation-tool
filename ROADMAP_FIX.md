# 🗺️ Roadmap Fix Lỗi Code Quality

> Dựa trên kết quả đánh giá chất lượng code (điểm tổng thể: 7.0/10)  
> Cập nhật: 2026-02-27

---

## Phase 1 — Bảo mật & Runtime Errors (Ưu tiên KHẨN CẤP)
**Mục tiêu**: Vá các lỗi có thể gây crash hoặc lỗ hổng bảo mật ngay lập tức  
**Thời gian ước tính**: 1–2 ngày

### 1.1 Fix API endpoint gọi hàm không tồn tại
- **File**: [`api/server.py:192`](api/server.py:192)
- **Vấn đề**: `core_reconcile()` không tồn tại trong `core_logic.py`
- **Fix**: Thay bằng `run_full_reconciliation_process(input_dir, output_dir)`
- **Tác động**: Endpoint `/reconcile` hiện đang crash khi gọi

### 1.2 Fix ReportGenerator class không tồn tại
- **File**: [`api/server.py:349`](api/server.py:349)
- **Vấn đề**: `ReportGenerator()` được khởi tạo nhưng chỉ có function `create_reports()`
- **Fix**: Thay bằng gọi trực tiếp `create_reports(all_results)` hoặc tạo wrapper class
- **Tác động**: Endpoint `/reports/generate` crash khi gọi

### 1.3 Đổi default admin password
- **File**: [`utils/auth.py:441`](utils/auth.py:441)
- **Vấn đề**: Password mặc định `"admin123"` hardcode trong source code
- **Fix**: 
  - Đọc từ env var `ADMIN_DEFAULT_PASSWORD` 
  - Nếu không có env var, generate random password và log ra console lần đầu
  - Bắt buộc đổi password sau lần đăng nhập đầu tiên (flag `must_change_password`)

### 1.4 Giới hạn CORS
- **File**: [`api/server.py:106`](api/server.py:106)
- **Vấn đề**: `allow_origins=["*"]` cho phép mọi domain gọi API
- **Fix**: Đọc từ env var `ALLOWED_ORIGINS` (comma-separated), fallback về `["http://localhost:8501"]`

### 1.5 Vá Path Traversal trong download endpoint
- **File**: [`api/server.py:322`](api/server.py:322)
- **Vấn đề**: `file_path` từ URL không được validate, có thể truy cập file ngoài OUTPUT_DIR
- **Fix**: 
  ```python
  path = Path(file_path).resolve()
  if not str(path).startswith(str(OUTPUT_DIR.resolve())):
      raise HTTPException(status_code=403, detail="Access denied")
  ```

### 1.6 Bảo vệ email password
- **File**: [`config.py:224`](config.py:224)
- **Vấn đề**: Password email lưu plaintext trong `gui_settings.ini`
- **Fix**: Ưu tiên đọc từ env var `APP_EMAIL_PASSWORD`, cảnh báo nếu dùng INI file

---

## Phase 2 — Code Quality & Correctness (Quan trọng)
**Mục tiêu**: Sửa các lỗi logic, inconsistency, và code smell  
**Thời gian ước tính**: 3–5 ngày

### 2.1 Cập nhật `utils/schemas.py` cho khớp thực tế
- **File**: [`utils/schemas.py`](utils/schemas.py)
- **Vấn đề**: `MainReconResult` TypedDict thiếu các key mới (`dao_chuyen_noi_bai`, `bien_dong_fe`, `xuat_tau_van_ton`, `duplicate_check_results`, v.v.)
- **Fix**: Cập nhật TypedDict để phản ánh đúng dict trả về từ `perform_reconciliation()`

### 2.2 Thay `iterrows()` bằng `executemany()` trong SQLite
- **File**: [`utils/history_db.py:270`](utils/history_db.py:270), [`utils/history_db.py:368`](utils/history_db.py:368)
- **Vấn đề**: Insert từng row một vào SQLite — O(n) round trips, rất chậm với dữ liệu lớn
- **Fix**:
  ```python
  rows = [(date_str, row[Col.CONTAINER], ...) for _, row in df.iterrows()]
  cursor.executemany("INSERT OR REPLACE INTO container_snapshots ...", rows)
  ```

### 2.3 Xóa dead imports trong `main.py`
- **File**: [`main.py:10-18`](main.py:10)
- **Vấn đề**: Import `perform_reconciliation`, `perform_simple_reconciliation`, `compare_inventories`, v.v. nhưng không dùng
- **Fix**: Xóa các import không dùng, chỉ giữ `run_full_reconciliation_process`

### 2.4 Sửa `import time` bên trong vòng lặp
- **File**: [`data/data_loader.py:34`](data/data_loader.py:34)
- **Vấn đề**: `import time` được gọi mỗi lần retry thay vì một lần ở đầu file
- **Fix**: Chuyển `import time` lên đầu file

### 2.5 Thay magic string `'1970-01-01'` bằng constant
- **File**: [`data/data_transformer.py:33`](data/data_transformer.py:33)
- **Vấn đề**: Fallback date hardcode, không có giải thích
- **Fix**: Định nghĩa `DEFAULT_FALLBACK_DATE = pd.Timestamp('1970-01-01')` trong `config.py` với comment giải thích

### 2.6 Tách business logic ra khỏi `app.py`
- **File**: [`app.py`](app.py) (850 dòng)
- **Vấn đề**: Hàm `calculate_teus()`, `add_teus_columns_to_operator_table()`, v.v. là business logic nằm trong UI file
- **Fix**: Tạo `utils/display_helpers.py` chứa các hàm helper, `app.py` chỉ giữ UI code

### 2.7 Chuẩn hóa TEU estimation
- **File**: [`app.py:100`](app.py:100), [`app.py:130`](app.py:130), [`app.py:288`](app.py:288)
- **Vấn đề**: Hardcode `* 1.5` làm hệ số TEU ở nhiều nơi, không nhất quán
- **Fix**: Định nghĩa `DEFAULT_TEU_FACTOR = 1.5` trong `config.py`, dùng constant này ở mọi nơi

### 2.8 Persist token revocation list
- **File**: [`utils/auth.py:189`](utils/auth.py:189)
- **Vấn đề**: `_revoked_tokens` là in-memory set, mất khi restart server
- **Fix**: Lưu revoked tokens vào SQLite với TTL bằng expiry time của token

### 2.9 Sửa `except Exception: pass` nuốt lỗi
- **File**: [`app.py:236`](app.py:236), [`config.py:217`](config.py:217)
- **Vấn đề**: Lỗi bị nuốt im lặng, khó debug
- **Fix**: Thay bằng `except Exception as e: logging.debug(f"Non-critical: {e}")` hoặc log ở level phù hợp

---

## Phase 3 — Test Coverage (Quan trọng)
**Mục tiêu**: Tăng coverage cho các module chưa có test  
**Thời gian ước tính**: 3–4 ngày

### 3.1 Thêm test cho API layer
- **File mới**: `tests/test_api_server.py`
- **Nội dung**:
  - Test `/health` endpoint
  - Test `/reconcile` với mock `run_full_reconciliation_process`
  - Test `/files/download` với path traversal attempt
  - Test authentication flow

### 3.2 Thêm test cho `reports/report_generator.py`
- **File mới**: `tests/test_report_generator.py`
- **Nội dung**:
  - Test `_add_total_row()` với DataFrame có/không có numeric columns
  - Test `_create_phuong_an_breakdown()` với dữ liệu mẫu
  - Test `create_reports()` với mock data (không ghi file thật)

### 3.3 Cập nhật test bị skip
- **File**: [`tests/test_reconciliation_engine.py:66`](tests/test_reconciliation_engine.py:66)
- **Vấn đề**: 2 test case bị `@unittest.skip` từ V4.7.1
- **Fix**: Xóa hoặc cập nhật test để phản ánh logic hiện tại (dùng `Col.FE`, `Col.ISO`, `Col.LOCATION`)

### 3.4 Thêm shared fixtures vào `conftest.py`
- **File**: [`tests/conftest.py`](tests/conftest.py)
- **Vấn đề**: Chỉ có 10 dòng, mỗi test file tự tạo fixture riêng
- **Fix**: Thêm fixtures dùng chung: `sample_ton_cu`, `sample_ton_moi`, `sample_gate_in`, `temp_output_dir`

---

## Phase 4 — Performance & Maintainability (Cải thiện dài hạn)
**Mục tiêu**: Tối ưu hiệu năng và dễ bảo trì  
**Thời gian ước tính**: 5–7 ngày

### 4.1 Bổ sung `requirements.txt`
- **File**: [`requirements.txt`](requirements.txt)
- **Vấn đề**: Thiếu nhiều dependency thực tế
- **Fix**: Thêm đầy đủ:
  ```
  unidecode>=1.3.0        # data_transformer.py
  fastapi>=0.100.0        # api/server.py
  uvicorn>=0.23.0         # api/server.py
  python-multipart>=0.0.6 # file upload
  pyjwt>=2.8.0            # utils/auth.py
  bcrypt>=4.0.0           # utils/auth.py
  schedule>=1.2.0         # scheduler.py
  reportlab>=4.0.0        # reports/pdf_generator.py
  ```

### 4.2 Tách `BUSINESS_RULES` ra file riêng
- **File**: [`config.py:123`](config.py:123)
- **Vấn đề**: 40+ business rules làm `config.py` phình to
- **Fix**: Tạo `config_business_rules.py` hoặc đọc từ `config_mappings.json`

### 4.3 Dọn dẹp version comments lịch sử
- **Vấn đề**: Comment `# V4.3`, `# V4.5.2`, `# V5.1.1` tích lũy nhiều, làm khó đọc
- **Fix**: Xóa comment version cũ, giữ lại trong git history. Chỉ giữ comment giải thích WHY, không giải thích WHAT

### 4.4 Tối ưu nested loop trong `app.py`
- **File**: [`app.py:369`](app.py:369)
- **Vấn đề**: O(n×m) loop tính TEU theo operator × dwell category trong UI render
- **Fix**: Pre-compute bằng `groupby` + `apply` một lần, cache kết quả

### 4.5 Thêm API key validation đúng cách
- **File**: [`api/auth_middleware.py:81`](api/auth_middleware.py:81)
- **Vấn đề**: API key = username, không an toàn
- **Fix**: Tạo bảng `api_keys` trong database, API key là random token 32 bytes, map đến user_id

---

## Tóm tắt Timeline

| Phase | Nội dung | Thời gian | Ưu tiên |
|-------|----------|-----------|---------|
| **Phase 1** | Bảo mật & Runtime Errors | 1–2 ngày | 🔴 Khẩn cấp |
| **Phase 2** | Code Quality & Correctness | 3–5 ngày | 🟡 Quan trọng |
| **Phase 3** | Test Coverage | 3–4 ngày | 🟡 Quan trọng |
| **Phase 4** | Performance & Maintainability | 5–7 ngày | 🟢 Dài hạn |
| **Tổng** | | **12–18 ngày** | |

---

## Checklist theo dõi tiến độ

### Phase 1 — Bảo mật & Runtime
- [ ] 1.1 Fix `core_reconcile` → `run_full_reconciliation_process` trong `api/server.py`
- [ ] 1.2 Fix `ReportGenerator` class không tồn tại trong `api/server.py`
- [ ] 1.3 Đổi default admin password sang env var
- [ ] 1.4 Giới hạn CORS origins
- [ ] 1.5 Vá path traversal trong download endpoint
- [ ] 1.6 Bảo vệ email password

### Phase 2 — Code Quality
- [ ] 2.1 Cập nhật `utils/schemas.py`
- [ ] 2.2 Thay `iterrows()` bằng `executemany()` trong `history_db.py`
- [ ] 2.3 Xóa dead imports trong `main.py`
- [ ] 2.4 Chuyển `import time` lên đầu file trong `data_loader.py`
- [ ] 2.5 Thay magic string `'1970-01-01'` bằng constant
- [ ] 2.6 Tách business logic ra khỏi `app.py`
- [ ] 2.7 Chuẩn hóa TEU estimation với constant
- [ ] 2.8 Persist token revocation list
- [ ] 2.9 Sửa `except Exception: pass`

### Phase 3 — Test Coverage
- [ ] 3.1 Thêm `tests/test_api_server.py`
- [ ] 3.2 Thêm `tests/test_report_generator.py`
- [ ] 3.3 Cập nhật/xóa test bị skip
- [ ] 3.4 Thêm shared fixtures vào `conftest.py`

### Phase 4 — Performance & Maintainability
- [ ] 4.1 Bổ sung `requirements.txt` đầy đủ
- [ ] 4.2 Tách `BUSINESS_RULES` ra file riêng
- [ ] 4.3 Dọn dẹp version comments lịch sử
- [ ] 4.4 Tối ưu nested loop trong `app.py`
- [ ] 4.5 Thêm API key validation đúng cách
