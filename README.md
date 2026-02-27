# Container Inventory Reconciliation Tool — v1.0 @2026

[![CI/CD](https://github.com/Blackbird081/container-reconciliation-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/Blackbird081/container-reconciliation-tool/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Công cụ đối soát tồn kho container tự động cho cảng biển. Hỗ trợ GUI desktop, web dashboard (Streamlit), và REST API.

---

## 🚀 Tính Năng Chính

### Đối Soát Tồn Kho
- So sánh **Tồn Cũ** (baseline) vs **Tồn Mới** (thực tế) để tìm biến động
- Phân loại: Tồn chuẩn, Chênh lệch (+/-), Đảo chuyển nội bãi, CFS
- Phát hiện container bất thường, trùng lặp, sai thông tin
- Xử lý container CFS (Đóng/Rút hàng đổi F/E)

### Batch Mode
- Xử lý nhiều ngày liên tục với 1 lần click
- Tự động nhận diện ngày từ tên file/folder
- Logic: TON MOI ngày N = TON CU ngày N+1
- Hỗ trợ Time Slots: Ca sáng (8H-15H), Ca chiều (15H-8H), Cả ngày

### Báo Cáo & Xuất Dữ Liệu
- Báo cáo Excel đa sheet với format chuyên nghiệp
- Xuất theo template hãng tàu (VIMC, Vinafco, VOSCO...)
- Gửi email tự động cho từng hãng
- Export Power BI

### Web Dashboard (Streamlit)
- Multi-page app: Tổng quan, Hãng tàu, Analytics, F/E, Export
- Auto-refresh với countdown timer
- Caching `@st.cache_data` (TTL 5 phút)
- Hỗ trợ tiếng Việt / English

### REST API (FastAPI)
- `POST /reconcile` — Submit job async, trả về `task_id`
- `GET /tasks/{task_id}` — Theo dõi tiến độ (0-100%)
- `GET /files/input|output` — Quản lý file
- `POST /files/upload` — Upload Excel
- JWT authentication + API key support
- Rate limiting, CORS configurable

---

## 🏗️ Kiến Trúc

```
container-reconciliation-tool/
├── app.py                    # Streamlit dashboard (legacy single-page)
├── app_gui.py                # Desktop GUI (tkinter/ttkbootstrap)
├── main.py                   # CLI entry point
├── config.py                 # Cấu hình ứng dụng
├── config_business_rules.py  # Business rules (Rule Engine)
├── core_logic.py             # Orchestrator chính
│
├── core/                     # Business logic
│   ├── pipeline.py           # ReconciliationPipeline (12 steps)
│   ├── reconciliation_engine.py
│   ├── advanced_checker.py
│   ├── inventory_checker.py
│   ├── duplicate_checker.py
│   ├── delta_checker.py
│   ├── batch_processor.py
│   └── anomaly_detector.py   # ML anomaly detection
│
├── data/                     # Data layer
│   ├── data_loader.py        # Load + retry + parallel
│   ├── data_transformer.py   # Clean + normalize
│   ├── data_validator.py
│   └── parallel_loader.py
│
├── api/                      # REST API
│   ├── server.py             # FastAPI endpoints
│   └── auth_middleware.py    # JWT + API key auth
│
├── pages/                    # Streamlit multi-page app
│   ├── _shared.py            # Shared utilities + caching
│   ├── 1_Overview.py
│   └── 2_Operator.py
│
├── reports/                  # Report generation
│   ├── report_generator.py
│   ├── operator_analyzer.py
│   ├── email_notifier.py
│   ├── email_sender.py
│   ├── email_template_exporter.py
│   ├── movement_summary.py
│   └── pdf_generator.py
│
├── utils/                    # Utilities
│   ├── auth.py               # JWT + RBAC
│   ├── db_models.py          # SQLAlchemy ORM
│   ├── user_store_db.py      # DB-backed UserStore
│   ├── history_db.py         # SQLite history
│   ├── cache_utils.py        # File hash caching
│   ├── task_queue.py         # Async task queue
│   ├── secrets.py            # Secrets management
│   ├── observability.py      # OpenTelemetry + Prometheus
│   ├── display_helpers.py    # UI helper functions
│   ├── exceptions.py         # Custom exceptions
│   ├── validators.py         # Data validation
│   └── ...
│
├── tests/                    # Test suite (~7000 lines)
│   ├── conftest.py           # Shared fixtures
│   ├── test_reconciliation_engine.py
│   ├── test_api_server.py
│   ├── test_report_generator.py
│   ├── test_display_helpers.py
│   ├── test_property_based.py  # Hypothesis property tests
│   └── ...
│
└── .github/workflows/ci.yml  # CI/CD pipeline
```

---

## ⚡ Cài Đặt Nhanh

### Yêu Cầu
- Python 3.10+
- pip

### Cài Đặt

```bash
# Clone repo
git clone https://github.com/Blackbird081/container-reconciliation-tool.git
cd container-reconciliation-tool

# Cài dependencies
pip install -r requirements.txt

# Cấu hình môi trường (tùy chọn)
cp .env.example .env
# Chỉnh sửa .env với thông tin của bạn
```

### Biến Môi Trường

| Biến | Mô tả | Mặc định |
|------|-------|---------|
| `ADMIN_DEFAULT_PASSWORD` | Password admin lần đầu | Random (xem log) |
| `APP_EMAIL_USER` | Email gửi báo cáo | - |
| `APP_EMAIL_PASSWORD` | Password email | - |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:8501` |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./data/app.db` |
| `CELERY_BROKER_URL` | Redis URL cho Celery | - (dùng ThreadPool) |
| `VAULT_ADDR` | HashiCorp Vault URL | - |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry endpoint | - |

---

## 🖥️ Chạy Ứng Dụng

### Desktop GUI
```bash
python app_gui.py
```

### Web Dashboard (Streamlit)
```bash
# Single-page (legacy)
streamlit run app.py

# Multi-page (mới)
streamlit run app.py  # pages/ được tự động load
```

### REST API
```bash
uvicorn api.server:app --reload --port 8000
# Docs: http://localhost:8000/docs
```

### CLI (Backend only)
```bash
python main.py
```

### Docker
```bash
docker-compose up -d
```

---

## 📁 Chuẩn Bị Dữ Liệu

### Cách 1: File trực tiếp
```
data_input/
├── TON CU N8.1.2026.xlsx
├── TON MOI N8.1.2026.xlsx
└── GATE IN OUT N8.1.2026.xlsx
```

### Cách 2: Subfolder theo ngày (khuyến nghị)
```
data_input/
└── N8.1.2026/
    ├── TON CU.xlsx
    ├── TON MOI.xlsx
    └── GATE IN OUT.xlsx
```

### Cách 3: Time Slots
```
data_input/
├── 8H N7.1 - 15H N7.1/     ← Ca chiều ngày 7/1
│   ├── TON CU.xlsx
│   └── TON MOI.xlsx
└── 15H N7.1 - 8H N8.1/     ← Ca sáng ngày 8/1
    ├── TON CU.xlsx
    └── TON MOI.xlsx
```

### Tên File Được Nhận Diện

| Tên File | Loại | Mô tả |
|----------|------|--------|
| `TON CU.xlsx` | ton_cu | Tồn bãi cũ (baseline) |
| `TON MOI.xlsx` | ton_moi | Tồn bãi mới (thực tế) |
| `GATE IN OUT.xlsx` | gate_combined | Gate vào/ra |
| `NHAP XUAT.xlsx` | nhapxuat_combined | Nhập/xuất tàu |
| `SHIFTING.xlsx` / `RESTOW.xlsx` | shifting_combined | Shifting tàu |
| `N-RESTOW.xlsx` | nhap_shifting | Nhập shifting |
| `X-RESTOW.xlsx` | xuat_shifting | Xuất shifting |

---

## 📊 Báo Cáo Đầu Ra

| File | Nội dung |
|------|----------|
| `1. SUMMARY.xlsx` | Tổng hợp tất cả chỉ số |
| `2. TON_BAI_CHUAN.xlsx` | Container khớp hoàn toàn |
| `3. CHENH_LECH.xlsx` | Container chênh lệch (+/-) |
| `4. DAO_CHUYEN_NOI_BAI.xlsx` | Container đảo chuyển vị trí |
| `5. BIEN_DONG_CHI_TIET.xlsx` | Chi tiết biến động VÀO/RA |
| `6_Ton_Theo_Hang/` | Báo cáo riêng từng hãng tàu |
| `7_Email_Templates/` | Templates gửi email hãng tàu |
| `8. MASTER_LOG.xlsx` | Log tra cứu toàn bộ giao dịch |
| `9. MOVEMENT_SUMMARY.xlsx` | Tổng hợp biến động |
| `10. ERRORS_V51.xlsx` | Lỗi cần kiểm tra |

---

## 🧪 Chạy Tests

```bash
# Tất cả tests
pytest tests/ -v

# Với coverage
pytest tests/ --cov=. --cov-report=html

# Property-based tests (cần hypothesis)
pip install hypothesis
pytest tests/test_property_based.py -v

# API tests (cần fastapi + httpx)
pip install fastapi httpx
pytest tests/test_api_server.py -v
```

---

## 🔒 Bảo Mật

- **Passwords**: Đọc từ env vars, không hardcode
- **JWT tokens**: Revocation list persist vào SQLite
- **API keys**: Random token 32 bytes, hash SHA256 trước khi lưu
- **CORS**: Configurable qua `ALLOWED_ORIGINS` env var
- **Path traversal**: Download endpoint validate path trong OUTPUT_DIR
- **Secrets**: Hỗ trợ HashiCorp Vault, AWS Secrets Manager, env vars

---

## 📈 Observability

```python
from utils.observability import setup_logging, setup_tracing, get_metrics

# Structured JSON logging
setup_logging(service_name="reconciliation", json_format=True)

# OpenTelemetry tracing (cần opentelemetry-sdk)
setup_tracing(otlp_endpoint="http://jaeger:4317")

# Prometheus metrics (cần prometheus-client)
metrics = get_metrics()
metrics.start_metrics_server(port=9090)
```

---

## 🤝 Đóng Góp

1. Fork repo
2. Tạo branch: `git checkout -b feature/ten-tinh-nang`
3. Commit: `git commit -m "feat: mô tả thay đổi"`
4. Push: `git push origin feature/ten-tinh-nang`
5. Tạo Pull Request

---

## 📝 Changelog

### v1.0 @2026 (2026-02-27)
- **Security**: Fix CORS wildcard, path traversal, hardcoded passwords
- **Architecture**: Pipeline pattern, multi-page Streamlit, async task queue
- **Database**: SQLAlchemy ORM thay thế JSON file storage
- **Observability**: OpenTelemetry tracing, Prometheus metrics, structured logging
- **Testing**: Property-based tests (Hypothesis), CI/CD pipeline (GitHub Actions)
- **Anomaly Detection**: IQR + Z-score based anomaly detection
- **Secrets**: Vault/AWS/Env fallback chain

### V5.7 (2026-01-14)
- Thêm pattern RESTOW = SHIFTING
- Cải thiện nhận diện file conflict
- Hiển thị thời gian xử lý

---

*Xem chi tiết tại: [USER_GUIDE.md](USER_GUIDE.md) | [ROADMAP_FIX.md](ROADMAP_FIX.md)*
