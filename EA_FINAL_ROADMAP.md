# EA Final Roadmap

Ngay lap: 2026-04-23

Muc tieu: dua `container-reconciliation-tool` tu trang thai internal tool co gia tri nghiep vu len muc san sang van hanh on dinh. Roadmap nay da dung hoa giua `EA_INDEPENDENT_ASSESSMENT.md` va `ea_counter_assessment.md`.

## Trang Thai Thuc Hien

Cap nhat: 2026-04-23.

Quyet dinh van hanh: tool chi dung noi bo, khong can Docker/K8s/API production trong giai doan nay.

- Phase 0: Hoan tat. `pytest -q --collect-only` collect thanh cong; Hypothesis optional dependency khong lam fail collect.
- Phase 1: Hoan tat cho internal/API local. Health check da co `run_health_checks()` canonical va `/health` dung contract moi. Docker healthcheck khong con la gate bat buoc do Docker khong su dung.
- Phase 2: Hoan tat neu bat REST API noi bo. Auth router da include; endpoint write/job/audit da co auth/rate limit; upload da sanitize filename, gioi han size, validate extension/MIME/signature va chan overwrite.
- Phase 3: Hoan tat theo quyet dinh internal. Queue mac dinh la in-memory single-node; Celery/Redis chi con optional trong `requirements-enterprise.txt`, khong nam trong dependency mac dinh.
- Phase 4: Hoan tat muc on dinh. `core_logic.run_full_reconciliation_process()` da thanh wrapper goi `core.pipeline.ReconciliationPipeline`; business rule catalog toi thieu da co tai `BUSINESS_RULE_CATALOG.md`.
- Phase 5: Hoan tat muc internal/server-safe. Pickle legacy duoc giu cho desktop/local, nhung co atomic write va JSON/SQLite metadata; `APP_MODE=api-server` khong load pickle lam state chinh.
- Phase 6: Hoan tat. CI cai dependency tu file chuan, khong ignore API tests, bo Docker build khoi gate noi bo.
- Phase 7: Khong ap dung hien tai. Chi mo lai neu co quyet dinh deploy API/K8s production.

Ket qua xac minh hien tai: `pytest -q` pass voi 502 passed, 5 skipped.

## Dinh Vi Cuoi

- Internal desktop/web readiness: 6.5/10.
- Enterprise API/K8s readiness: 5.5/10.
- Ket luan: khong can xu ly cac khac biet danh gia mang tinh tieu chuan hoa truoc; chi uu tien loi ky thuat co anh huong truc tiep den crash, bao mat API, CI va drift nghiep vu.

## Nguyen Tac Uu Tien

- P0: loi gay crash, health check sai, test/CI khong dang tin.
- P1: bao mat API neu bat REST API cho user khac hoac deploy server.
- P2: giam drift kien truc, on dinh nghiep vu, cai thien maintainability.
- P3: nang cap enterprise production chi lam khi co quyet dinh deploy API/K8s that.

## Phase 0 - Stabilize Baseline

Thoi gian: 1-2 ngay.

Muc tieu: tao baseline test/CI dang tin truoc khi refactor.

- Sua dependency/test environment de `pytest -q` khong fail o collect.
- Sua `tests/test_property_based.py` de skip dung khi Hypothesis khong available hoac dam bao Hypothesis duoc cai trong CI/dev.
- Cai day du dependency test tu `requirements.txt` trong CI, hoac tach `requirements-dev.txt` ro rang.
- Phan loai test API: test nao can optional dependency thi mark ro, khong de import app fail ca module.
- Cap nhat CI de khong ignore API server test neu API la deployment target.

Exit criteria:

- `pytest -q` collect thanh cong.
- CI unit test chay duoc voi dependency dung.
- Khong co loi import app do thieu dependency da khai bao.

## Phase 1 - Fix Runtime And Health

Thoi gian: 1 ngay.

Muc tieu: sua cac loi van hanh ro rang, khong tranh cai.

- Chuan hoa health check thanh mot API duy nhat, vi du `run_health_checks()` tra ve `dict[str, bool]`.
- Sua `api/server.py` de goi dung health function, khong fallback "healthy" khi health check import fail.
- Sua `Dockerfile` healthcheck de goi dung function hoac endpoint thuc te.
- Dam bao Docker image co tool can cho healthcheck neu dung `curl`, hoac dung Python HTTP client/no-op phu hop.
- Kiem tra lai `/health` bang test API.

Exit criteria:

- `/health` phan anh dung filesystem/database/module checks.
- Docker healthcheck khong fail do import sai.
- Health test pass.

## Phase 2 - Secure API Mode

Thoi gian: 2-4 ngay.

Muc tieu: chi bat REST API khi endpoint quan trong duoc bao ve toi thieu.

- Include `auth_router` vao FastAPI app.
- Gan `Depends(require_permission(...))` cho `/reconcile`, `/files/upload`, `/reports/generate`, `/audit/logs`, `/audit/statistics`.
- Gan `check_rate_limit` cho API routes hoac global dependency.
- Sua `AuthManager` de doc `JWT_SECRET_KEY` tu env/secrets manager thay vi random theo process trong server mode.
- Sua test auth dang fail; xac dinh ro loi do PyJWT/fallback hay secret lifecycle.
- Sanitize upload filename bang `Path(file.filename).name`, gioi han size, validate MIME/content can ban.
- Khong cho upload ghi de file neu chua co policy ro rang.

Exit criteria:

- Khong endpoint ghi/chay job/audit nao public khong auth.
- Auth tests pass.
- Upload path traversal va overwrite case co test.

## Phase 3 - Align Task Queue And Deployment Modes

Thoi gian: 2-3 ngay.

Muc tieu: lam ro mode nao la internal, mode nao la production server.

- Doi `docker-compose.yml` tu `REDIS_URL` sang `CELERY_BROKER_URL` neu dung Celery.
- Neu chua dung Celery, bo worker/Redis khoi compose mac dinh de tranh misleading.
- Tach config theo mode: desktop, streamlit internal, api-server.
- Ghi ro trong README: in-memory queue chi dung single-process/single-node.
- Neu API deploy multi-replica, bat buoc dung Celery + Redis va shared database.

Exit criteria:

- Compose file khong quang cao worker/Redis neu app van dung in-memory queue.
- Runtime mode duoc document ro.
- Task status khong mat khi chay theo mode da cong bo.

## Phase 4 - Reduce Architecture Drift

Thoi gian: 3-5 ngay.

Muc tieu: giam rui ro nghiep vu bi lech giua GUI, API, dashboard va legacy code.

- Chon `core/pipeline.py` lam orchestrator chinh.
- Bien `core_logic.run_full_reconciliation_process()` thanh wrapper goi pipeline, hoac loai bo dan cac luong duplicate.
- Dam bao GUI, API, CLI cung goi mot orchestration path.
- Chuyen cac helper con can dung chung ra module rieng, tranh UI file chua business logic.
- Lap "business rule catalog" toi thieu: rule name, input, output, exception, test fixture lien quan.

Exit criteria:

- Mot duong chay chinh cho reconciliation.
- Test integration xac nhan GUI/API/CLI dung cung pipeline contract.
- Business rule critical co test fixture.

## Phase 5 - Data And State Hardening

Thoi gian: 2-4 ngay.

Muc tieu: on dinh state va bao cao khi chay server/shared runtime.

- Giu `pickle` cho desktop/internal local neu can, nhung khong dung lam state chinh cho API multi-user.
- Với API/server mode, thay `latest_results.pkl` bang SQLite/PostgreSQL record hoac Parquet/JSON co schema va checksum.
- Them locking/atomic write cho file output neu van dung file state.
- Chuan hoa retention policy cho `data_output`, logs, report folders.

Exit criteria:

- Server mode khong phu thuoc vao pickle mutable shared state.
- Latest result co schema/version metadata.
- Khong co race condition ro rang khi nhieu task cung ghi output.

## Phase 6 - CI Quality Gate

Thoi gian: 1-2 ngay.

Muc tieu: CI phan anh dung tinh trang release.

- Bo `continue-on-error` cho integration tests neu integration la release gate.
- Bo hoac giam `continue-on-error` cho Ruff/Bandit o muc loi nghiem trong.
- Coverage threshold phai fail that neu duoc dung lam gate; neu khong thi bo khoi gate.
- CI cai dependencies tu file chuan thay vi list thu cong lech voi `requirements.txt`.
- Tao matrix nho hon neu can toc do, nhung gate phai dang tin.

Exit criteria:

- PR fail khi unit/integration/security critical fail.
- Khong co test quan trong bi ignore ma khong co ly do/documentation.

## Phase 7 - Enterprise Production Track

Chi lam khi co quyet dinh deploy API/K8s production.

- Chuyen database sang PostgreSQL.
- Bat Celery + Redis that cho async jobs.
- Dung external secret manager hoac K8s sealed/external secrets; khong commit placeholder secret trong manifest production.
- Thay SQLite + `ReadWriteOnce` PVC cho multi-replica API bang DB/object storage phu hop.
- Gan observability vao runtime: structured logs, Prometheus metrics, OpenTelemetry tracing neu can.
- Hardening K8s: image tag immutable, resource sizing theo load test, pod disruption budget, backup/restore, network policy refined.

Exit criteria:

- API co the scale horizontal ma khong mat task state/result.
- Secret/config khong nam trong repo production.
- Co runbook backup, restore, incident, rollback.

## Thu Tu Thuc Hien Khuyen Nghi

1. Phase 0 - Stabilize Baseline.
2. Phase 1 - Fix Runtime And Health.
3. Phase 2 - Secure API Mode, neu REST API duoc dung.
4. Phase 3 - Align Task Queue And Deployment Modes.
5. Phase 4 - Reduce Architecture Drift.
6. Phase 6 - CI Quality Gate.
7. Phase 5 - Data And State Hardening.
8. Phase 7 - Enterprise Production Track khi co nhu cau thuc te.

## Khong Lam Ngay

- Khong ep PostgreSQL/Celery/K8s neu chi dung desktop/internal single-node.
- Khong loai bo pickle ngay neu no chi phuc vu local session va khong nhan input tu user khong tin cay.
- Khong refactor lon UI/GUI truoc khi baseline test va pipeline contract on dinh.
- Khong sua cac khac biet thuan "style assessment" neu khong gay crash, security issue, hoac drift nghiep vu.

## Definition Of Done Cho Ban On Dinh Tiep Theo

- `pytest -q` pass trong moi truong chuan.
- `/health` dung. Docker healthcheck khong phai gate vi Docker khong dung cho internal mode.
- API mode co auth cho endpoint write/job/audit.
- Upload khong path traversal, khong overwrite tuy tien, co size limit.
- README noi ro 3 mode: desktop, internal Streamlit, API server.
- CI fail khi co loi unit/integration/security critical.
- Mot orchestration path chinh cho reconciliation duoc document.
