# File: schemas.py — @2026 v1.0
# @2026 v1.0: Cập nhật TypedDict để khớp với dict thực tế trả về từ perform_reconciliation()
from typing import TypedDict, Set, Dict, Any, List, Optional
import pandas as pd


class SimpleReconResult(TypedDict):
    """Kết quả đối soát đơn giản (SourceKey-based)."""
    khop: Set[str]
    thieu: Set[str]
    thua: Set[str]


class ReconCounts(TypedDict, total=False):
    """Thống kê số lượng từ kết quả đối soát chính."""
    khop_chuan: int
    sai_thong_tin: int
    dao_chuyen_noi_bai: int
    chenh_lech_am: int
    chenh_lech_duong: int
    bien_dong_fe: int
    xuat_tau_van_ton: int
    ton_ly_thuyet: int
    ton_moi: int
    future_moves: int
    suspicious_dates: int
    duplicates_found: int
    # Legacy keys (kept for backward compatibility)
    van_ton: int
    van_ton_ok: int
    van_ton_thuc: int
    khop_sai: int
    thieu: int
    thua: int


class MainReconResult(TypedDict, total=False):
    """
    Kết quả đối soát chính từ perform_reconciliation().
    
    Keys bắt buộc (total=False vì một số key chỉ có khi có dữ liệu):
    - ton_chuan: Container khớp hoàn toàn
    - sai_thong_tin: Container khớp nhưng sai thông tin (F/E, ISO, Location)
    - dao_chuyen_noi_bai: Container chỉ thay đổi vị trí
    - chenh_lech_am: Container có lệnh nhưng chưa về (lý thuyết > thực tế)
    - chenh_lech_duong: Container tồn bãi chưa có lệnh (thực tế > lý thuyết)
    - bien_dong_fe: Container CFS - đổi F/E trong ngày (V5.1.1)
    - xuat_tau_van_ton: Container xuất tàu nhưng vẫn tồn - lỗi nghiêm trọng (V5.1.2)
    - master_log: Toàn bộ giao dịch đã sắp xếp
    - future_moves_report: Giao dịch có ngày tương lai
    - suspicious_dates: Giao dịch có ngày đáng ngờ (dd/mm bị đảo)
    - timeline: Timeline giao dịch theo container
    - pending_shifting: Container đang chờ Restow
    - raw_data: Dict các DataFrame gốc theo source key
    - duplicate_check_results: Kết quả kiểm tra trùng lặp (V4.3)
    - duplicate_summary: Tóm tắt trùng lặp
    - v51_checks: Kết quả kiểm tra V5.1
    - counts: Thống kê số lượng (ReconCounts)
    """
    ton_chuan: pd.DataFrame
    sai_thong_tin: pd.DataFrame
    dao_chuyen_noi_bai: pd.DataFrame
    chenh_lech_am: pd.DataFrame
    chenh_lech_duong: pd.DataFrame
    bien_dong_fe: pd.DataFrame
    xuat_tau_van_ton: pd.DataFrame
    master_log: pd.DataFrame
    future_moves_report: pd.DataFrame
    suspicious_dates: pd.DataFrame
    timeline: pd.DataFrame
    pending_shifting: pd.DataFrame
    raw_data: Dict[str, pd.DataFrame]
    duplicate_check_results: Dict[str, pd.DataFrame]
    duplicate_summary: str
    v51_checks: Dict[str, Any]
    counts: ReconCounts
    # Legacy keys (kept for backward compatibility)
    khop_sai_info: pd.DataFrame
    thieu: pd.DataFrame
    thua: pd.DataFrame
    van_ton: pd.DataFrame
