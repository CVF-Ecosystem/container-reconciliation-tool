# Internal Operation Runbook

Ngay cap nhat: 2026-04-23

Pham vi: van hanh noi bo single-node, khong Docker, khong K8s, khong Celery/Redis.

## Cai dat

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Chay ung dung

```powershell
python app_gui.py
```

Hoac chay backend khong GUI:

```powershell
python main.py
```

Dashboard noi bo:

```powershell
streamlit run app.py
```

## Thu muc can backup

- `data_input`: file nguon da xu ly.
- `data_output`: report, latest result metadata, history database.
- `logs`: log van hanh.
- `email_config.json` hoac `gui_settings.ini` neu co cau hinh email.

## State

- Desktop/internal local van co `latest_results.pkl` cho tuong thich dashboard cu.
- He thong cung ghi `latest_results.json` va `latest_results.sqlite3` co schema metadata de giam rui ro corrupt/read unsafe.
- File state duoc ghi atomic de giam rui ro hong file khi task bi dung giua chung.

## Khi co loi

1. Chay `pytest -q` de xac nhan baseline.
2. Kiem tra `logs/app_log.txt` hoac log moi nhat trong `logs`.
3. Chay health local qua Python:

```powershell
python -c "from utils.health_check import run_health_checks; print(run_health_checks())"
```

4. Neu dashboard khong co du lieu, chay lai `python main.py` de tao latest result.

## Khong can cho mode nay

- Docker/Docker Compose.
- Celery/Redis.
- PostgreSQL.
- Kubernetes.
- External secret manager.
