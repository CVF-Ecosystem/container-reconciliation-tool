# Business Rule Catalog

Ngay cap nhat: 2026-04-23

Muc dich: ghi lai cac rule nghiep vu critical dang duoc pipeline reconciliation su dung, input/output ky vong, exception va test fixture lien quan. Source chinh: `config_business_rules.py`, `core/reconciliation_engine.py`, `core/inventory_checker.py`, `core/duplicate_checker.py`.

| Rule | Input | Output | Exception/Canh bao | Test fixture lien quan |
|---|---|---|---|---|
| SourceKey move direction | `SourceKey` in `xuat_tau`, `xuat_shifting`, `gate_out`, `nhap_tau`, `nhap_shifting`, `gate_in`, `ton_cu` | `MoveType` = `OUT` hoac `IN` | SourceKey khong nhan dien thi fallback sang `Phuong an`/`Vao Ra` | `tests/test_reconciliation_engine.py`, `tests/conftest.py::sample_gate_in`, `sample_gate_out` |
| Phuong an OUT | `Phuong an` nhu `LAY NGUYEN`, `CAP RONG`, `XUAT TAU`, `SHIFTING LOADING` | `MoveType` = `OUT` | Gia tri khong nam trong catalog can duoc review khi phat sinh | `tests/test_basic.py`, `tests/test_reconciliation_engine.py` |
| Phuong an IN | `Phuong an` nhu `HA BAI`, `TRA RONG`, `NHAP TAU`, `SHIFTING DISCHARGE` | `MoveType` = `IN` | Gia tri khong nam trong catalog can duoc review khi phat sinh | `tests/test_basic.py`, `tests/test_reconciliation_engine.py` |
| Rule phu thuoc Vao/Ra | `Phuong an` lap lung nhu `LUU RONG`, `CHUYEN TAU`, `DONG HANG`, `RUT HANG` kem cot `Vao/Ra` | `MoveType` theo `Vao/Ra` | Thieu `Vao/Ra` thi khong du bang chung xac dinh huong | `tests/test_reconciliation_engine.py` |
| Ton cu vs Ton moi | `ton_cu`, `ton_moi`, transaction sources | `ton_chuan`, `chenh_lech_am`, `chenh_lech_duong`, `dao_chuyen_noi_bai`, `sai_thong_tin` | Thieu required columns thi fail validation | `tests/test_reconciliation_engine.py`, `tests/test_integration.py` |
| Future/suspicious date | `TransactionTime` trong transaction sources | Warning report, khong crash pipeline | Ngay tuong lai/ngay dang ngo phai la warning co dem so | `tests/test_basic.py`, `tests/test_reconciliation_engine.py` |
| Duplicate and missing transaction checks | DataFrames da normalize co `Container`, `SourceKey`, time/location | `v51_checks`, duplicate reports | Empty/missing optional source khong duoc crash | `tests/test_duplicate_checker.py` |

Quy tac bao tri: khi them/sua business rule, cap nhat file nay va them fixture/test khang dinh input/output. GUI, CLI va API phai di qua `core.pipeline.ReconciliationPipeline` de khong tao drift rule.
