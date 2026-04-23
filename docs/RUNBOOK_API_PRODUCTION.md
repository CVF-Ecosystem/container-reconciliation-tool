# API Production Runbook

Ngay cap nhat: 2026-04-23

Chi dung track nay khi co quyet dinh deploy REST API/K8s production.

## Dieu kien bat buoc

- `JWT_SECRET_KEY` den tu external secret manager hoac K8s Secret duoc quan ly ngoai repo.
- API multi-replica phai dung Celery + Redis va shared database/object storage; khong dung in-memory queue cho scale horizontal.
- Database production uu tien PostgreSQL. SQLite/PVC `ReadWriteOnce` chi dung single-node.
- Image tag production phai immutable, vi du git SHA hoac semver tag.

## Backup

- Backup database hang ngay va truoc moi release.
- Backup object/report storage theo retention policy van hanh.
- Luu checksum backup va test restore dinh ky.

## Restore

- Dung deploy moi vao maintenance mode hoac scale API worker ve 0 neu can tranh ghi moi.
- Restore database vao instance moi truoc, kiem tra schema/version.
- Restore report/object storage, doi chieu checksum.
- Chay smoke test: `/health`, login, submit reconciliation test voi data fixture, xem task status/result.

## Incident

- Neu `/health` degraded: kiem tra filesystem/database/module checks trong response.
- Neu task bi mat status: kiem tra backend queue dang dung. In-memory queue khong duoc dung cho multi-replica.
- Neu auth token invalid sau restart: xac nhan `JWT_SECRET_KEY` khong bi rotate ngoai ke hoach.
- Neu upload bat thuong: kiem tra audit logs, file size, filename sanitized, va overwrite policy.

## Rollback

- Rollback image ve immutable tag truoc do.
- Khong rollback database schema khi chua co migration rollback da test.
- Neu secret bi rotate loi, khoi phuc secret version truoc va revoke token neu nghi ngo compromise.
- Sau rollback, chay smoke test va kiem tra queue worker khop version voi API.
