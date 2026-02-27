# File: core_logic.py — @2026 v1.0
import os
import pickle
from datetime import datetime
import logging
from pathlib import Path
import pandas as pd
from typing import Dict, Any, Callable, Optional

# Custom exceptions for better error handling
from utils.exceptions import (
    ReconciliationError,
    DataLoadError,
    ValidationError,
    ConfigurationError,
    ReportGenerationError
)

# Import tất cả các module xử lý của dự án
import config
from data.data_loader import load_all_data
from data.data_validator import validate_dataframes_structure, validate_dataframes_quality
from core.reconciliation_engine import perform_reconciliation
from core.advanced_checker import perform_simple_reconciliation
from core.inventory_checker import compare_inventories
from core.duplicate_checker import run_all_duplicate_checks
from reports.operator_analyzer import analyze_by_operator
from reports.report_generator import create_reports
from core.delta_checker import perform_delta_analysis
from reports.email_notifier import send_report_email
from config import Col, REQUIRED_COLUMNS_PER_FILE, DATA_VALIDATION_RULES
from utils.cache_utils import is_cache_valid, save_cache_metadata, get_input_files_hashes
from utils.history_db import HistoryDatabase

# --- HÀM LƯU VÀ TẢI KẾT QUẢ TRUNG GIAN ---
RESULTS_FILENAME = "latest_results.pkl"

def save_results(results: Dict[str, Any], output_dir: Path):
    """Lưu dictionary kết quả ra file pickle."""
    results_path = output_dir / RESULTS_FILENAME
    try:
        with open(results_path, 'wb') as f:
            pickle.dump(results, f)
        logging.info(f"Đã lưu kết quả trung gian vào: {results_path}")
    except (IOError, OSError) as e:
        logging.error(f"Lỗi khi lưu kết quả trung gian: {e}")
    except Exception as e:
        logging.error(f"Lỗi không xác định khi lưu kết quả: {e}")

def load_results(output_dir: Path) -> Dict[str, Any] | None:
    """
    Load previously saved reconciliation results from a pickle file.
    
    Args:
        output_dir: Directory where latest_results.pkl was saved.
    
    Returns:
        Dictionary containing all reconciliation results, or None if file not found.
    """
    results_path = output_dir / RESULTS_FILENAME
    if not results_path.exists():
        logging.warning("Không tìm thấy file kết quả trung gian (latest_results.pkl).")
        return None
    try:
        with open(results_path, 'rb') as f:
            results = pickle.load(f)
        logging.info(f"Đã tải thành công kết quả từ: {results_path}")
        return results
    except (IOError, OSError) as e:
        logging.error(f"Lỗi đọc file kết quả trung gian: {e}")
    except (pickle.UnpicklingError, EOFError) as e:
        logging.error(f"File kết quả bị lỗi hoặc không hợp lệ: {e}")
    except Exception as e:
        logging.error(f"Lỗi không xác định khi tải kết quả: {e}")
        return None

def find_input_files_from_dir(input_dir: Path) -> Dict[str, str]:
    """Quét một thư mục và tìm các file đầu vào dựa trên FILE_PATTERNS."""
    logging.info(f"--- BẮT ĐẦU QUÉT FILE TRONG: {input_dir} ---")
    found_files: Dict[str, str] = {}
    try:
        input_filenames = os.listdir(input_dir)
    except FileNotFoundError:
        logging.error(f"Thư mục đầu vào không tồn tại: {input_dir}")
        return {}

    for key, patterns in config.FILE_PATTERNS.items():
        file_found_for_key = False
        for fname in input_filenames:
            if any(fname.upper().startswith(pattern.upper()) for pattern in patterns):
                if key in found_files:
                    logging.warning(f"  -> Cảnh báo: Tìm thấy nhiều file cho key '{key}'. Đang sử dụng '{found_files[key]}' và bỏ qua '{fname}'.")
                else:
                    logging.info(f"  -> Đã chọn file cho '{key}': {fname}")
                    found_files[key] = fname
                    file_found_for_key = True
                    break
        if not file_found_for_key:
            # Chỉ log debug vì data đã được cleaned và tách riêng
            logging.debug(f"  -> Không tìm thấy file nào cho key '{key}'.")

    for req_key in config.REQUIRED_FILES:
        if req_key not in found_files:
            logging.error(f"Lỗi nghiêm trọng: Thiếu file bắt buộc '{req_key}'.")
            return {}
            
    logging.info("--- KẾT THÚC QUÉT FILE ---")
    return found_files

def create_summary_dataframe(main_results: Dict, simple_results: Dict, inventory_change_results: Dict) -> pd.DataFrame:
    """Tạo DataFrame summary từ các kết quả đối soát để tái sử dụng."""
    main_counts = main_results.get('counts', {})
    raw_data = main_results.get('raw_data', {})
    main_thieu_set = set(main_results.get('thieu', pd.DataFrame({Col.CONTAINER: []}))[Col.CONTAINER])
    simple_thieu_set = simple_results.get('thieu', set())
    df_da_roi_bai = inventory_change_results.get('da_roi_bai', pd.DataFrame())
    
    df_xuat_chung_tu = pd.concat([raw_data.get(key, pd.DataFrame()) for key in config.OUTBOUND_KEYS])
    set_xuat_chung_tu = set()
    if not df_xuat_chung_tu.empty and Col.CONTAINER in df_xuat_chung_tu.columns:
        set_xuat_chung_tu = set(df_xuat_chung_tu[Col.CONTAINER])
    
    cont_roi_bai_khong_chung_tu = []
    if Col.CONTAINER in df_da_roi_bai.columns:
        cont_roi_bai_khong_chung_tu = list(set(df_da_roi_bai[Col.CONTAINER]).difference(set_xuat_chung_tu))

    def get_len(key: str) -> int:
        return len(raw_data.get(key, pd.DataFrame()))

    # Tính toán các giá trị
    khop_chuan = main_counts.get('khop_chuan', 0)
    dao_chuyen = main_counts.get('dao_chuyen_noi_bai', 0)
    sai_thong_tin = main_counts.get('sai_thong_tin', 0)
    chenh_lech_am = main_counts.get('chenh_lech_am', 0)
    chenh_lech_duong = main_counts.get('chenh_lech_duong', 0)
    van_ton = main_counts.get('van_ton', 0)
    
    # Tính TỔNG để verify với Tồn Mới
    # Công thức: Khớp + Đảo chuyển + Sai thông tin + Thừa = Tồn Mới
    tong_ket_qua = khop_chuan + dao_chuyen + sai_thong_tin + chenh_lech_duong
    
    # Gộp "Đổi F/E hợp lệ" vào "Khớp hoàn toàn" vì đây là biến động hợp lệ
    khop_hoan_toan_total = khop_chuan + main_counts.get('van_ton_ok', 0)
    
    # Chỉ hiện CẢNH BÁO nếu có lỗi thật
    van_ton_thuc_count = main_counts.get('van_ton_thuc', 0)
    
    # Chỉ giữ lại các chỉ số quan trọng cho nghiệp vụ
    
    dao_chuyen_total = dao_chuyen + sai_thong_tin
    
    tong_ton_bai = khop_hoan_toan_total + dao_chuyen_total + chenh_lech_duong
    
    data_rows = [
        ('Ton cu (baseline)', get_len('ton_cu')),
        ('Ton moi (thoi diem kiem tra)', get_len('ton_moi')),
        ('Tong giao dich NHAP', get_len('gate_in') + get_len('nhap_tau') + get_len('nhap_shifting')),
        ('Tong giao dich XUAT', get_len('gate_out') + get_len('xuat_tau') + get_len('xuat_shifting')),
        ('Container da roi bai', len(df_da_roi_bai)),
        ('Container moi vao bai', len(inventory_change_results.get('moi_vao_bai', pd.DataFrame()))),
        ('Roi bai khong co chung tu', len(cont_roi_bai_khong_chung_tu)),
        ('Khop hoan toan', khop_hoan_toan_total),
        ('Dao chuyen vi tri', dao_chuyen_total),
        ('Ton bai chua co du lieu nguon', chenh_lech_duong),
        ('TONG TON BAI', get_len('ton_moi')),
    ]
    
    future_moves = main_counts.get('future_moves', 0)
    suspicious_dates = main_counts.get('suspicious_dates', 0)
    if future_moves > 0:
        data_rows.append(('Ngay tuong lai (CANH BAO)', future_moves))
    if suspicious_dates > 0:
        data_rows.append(('Ngay thang dang ngo (CANH BAO)', suspicious_dates))
    
    # Thêm CẢNH BÁO nếu có lỗi
    if van_ton_thuc_count > 0:
        data_rows.insert(13, ('CANH BAO: XUAT VAN TON', van_ton_thuc_count))
    
    # Lọc bỏ các dòng có giá trị = 0 nếu muốn gọn hơn (optional)
    # data_rows = [(k, v) for k, v in data_rows if v != 0]
    
    hang_muc = [r[0] for r in data_rows]
    so_luong = [r[1] for r in data_rows]
    
    return pd.DataFrame({'Hang muc': hang_muc, 'So luong': so_luong})

# <<< NÂNG CẤP: Thêm các hàm callback để giao tiếp với GUI >>>
def run_full_reconciliation_process(
    input_dir: Path, 
    output_dir: Path,
    update_status: Optional[Callable[[str], None]] = None,
    update_progress: Optional[Callable[[int], None]] = None,
    confirm_missing_ton_cu: Optional[Callable[[str], bool]] = None
) -> Path:
    """
    Execute the complete container inventory reconciliation workflow.
    
    This is the main entry point for the reconciliation process. It orchestrates
    all data loading, validation, reconciliation, and reporting steps.
    
    Args:
        input_dir: Directory containing input Excel files (TON CU, TON MOI, etc.)
        output_dir: Directory where reports and results will be saved.
        update_status: Optional callback function to receive status messages (for GUI).
        update_progress: Optional callback function to receive progress (0-100) updates.
        confirm_missing_ton_cu: Optional callback to ask user when TON CU is missing.
            Should return True to continue (load from DB), False to abort.
    
    Returns:
        Path: The directory path where all generated reports are saved.
    
    Raises:
        ValueError: If required input files are not found or data structure is invalid.
        RuntimeError: If the reconciliation process fails unexpectedly.
    
    Example:
        >>> from core_logic import run_full_reconciliation_process
        >>> report_path = run_full_reconciliation_process(
        ...     Path('./data_input'),
        ...     Path('./data_output')
        ... )
        >>> print(f"Reports saved to: {report_path}")
    """
    def _update_status(message):
        logging.info(message)
        if update_status:
            update_status(message)

    def _update_progress(value):
        if update_progress:
            update_progress(value)

    # 1. Thiết lập môi trường
    _update_status("Bắt đầu quy trình đối soát...")
    _update_progress(0)
    run_time = datetime.now()
    date_part = run_time.strftime("N%d.%m.%Y")
    time_part = run_time.strftime("%Hh%M")
    report_folder = output_dir / f"Report_{date_part}_{time_part}"
    report_folder.mkdir(parents=True, exist_ok=True)

    # 2. Tìm và tải dữ liệu
    _update_status("Đang tìm kiếm file đầu vào...")
    files_to_process = find_input_files_from_dir(input_dir)
    if not files_to_process:
        raise DataLoadError(
            "Không tìm thấy các file đầu vào cần thiết.",
            {"input_dir": str(input_dir)}
        )
    _update_progress(10)
    
    ton_cu_from_db = None
    if 'ton_cu' not in files_to_process:
        _update_status("⚠️ CẢNH BÁO: Không tìm thấy file TON CU!")
        
        # Kiểm tra database có snapshot không
        history_db = HistoryDatabase(output_dir)
        available_dates = history_db.get_available_dates(limit=1)
        
        if available_dates:
            msg = f"Không tìm thấy file TON CU.\nCó snapshot ngày {available_dates[0]} trong database.\nBạn muốn sử dụng snapshot này làm TON CU?"
        else:
            msg = "Không tìm thấy file TON CU và không có snapshot trong database.\nBạn có muốn tiếp tục mà không có TON CU?"
        
        # Gọi callback hỏi user
        if confirm_missing_ton_cu:
            user_confirmed = confirm_missing_ton_cu(msg)
            if not user_confirmed:
                raise DataLoadError(
                    "Người dùng hủy vì thiếu file TON CU.",
                    {"action": "user_cancelled"}
                )
            # User chọn tiếp tục - lấy từ database
            if available_dates:
                ton_cu_from_db = history_db.get_yesterday_as_ton_cu()
                if ton_cu_from_db.empty:
                    # Thử lấy snapshot gần nhất
                    from datetime import datetime as dt
                    latest_date = dt.strptime(available_dates[0], '%Y-%m-%d')
                    ton_cu_from_db = history_db.get_snapshot_for_date(latest_date)
                _update_status(f"Đã tải {len(ton_cu_from_db)} container từ database làm TON CU")
        else:
            # Không có callback, log warning và tiếp tục
            logging.warning("Thiếu file TON CU, tiếp tục mà không có confirm callback")

    _update_status("Đang tải và làm sạch dữ liệu...")
    file_dfs = load_all_data(files_to_process, input_dir, report_folder)
    
    if ton_cu_from_db is not None and not ton_cu_from_db.empty:
        file_dfs['ton_cu'] = ton_cu_from_db
        logging.info(f"Đã sử dụng {len(ton_cu_from_db)} container từ database làm TON CU")
    
    _update_progress(30)

    # 3. Kiểm tra chất lượng dữ liệu
    _update_status("Đang kiểm tra chất lượng dữ liệu...")
    if not validate_dataframes_structure(file_dfs, REQUIRED_COLUMNS_PER_FILE):
        raise ValidationError(
            "Dữ liệu không đủ cấu trúc tối thiểu.",
            {"missing_files": [k for k, v in file_dfs.items() if v.empty]}
        )
    quality_warnings = validate_dataframes_quality(file_dfs, DATA_VALIDATION_RULES)
    
    try:
        history_db = HistoryDatabase(output_dir)
        dup_results = history_db.check_all_files_duplicate(file_dfs)
        warnings_found = 0
        for dup_check in dup_results:
            if dup_check['warning_level'] == 'warning':
                _update_status(dup_check['message'])
                logging.warning(dup_check['message'])
                warnings_found += 1
            elif dup_check['warning_level'] == 'info':
                logging.info(dup_check['message'])
        if warnings_found > 0:
            _update_status(f"⚠️ Phát hiện {warnings_found} file có thể bị dùng nhầm!")
    except Exception as e:
        logging.debug(f"Could not check file duplicates: {e}")
    
    _update_progress(40)

    # 4. Chạy các module phân tích và đối soát
    _update_status("Đang chạy đối soát chính (Rule Engine)...")
    main_results = perform_reconciliation(file_dfs, report_folder, run_time)
    _update_progress(60)

    _update_status("Đang chạy kiểm tra chéo (SourceKey)...")
    simple_results = perform_simple_reconciliation(file_dfs)
    _update_progress(70)

    _update_status("Đang phân tích biến động tồn bãi...")
    inventory_change_results = compare_inventories(file_dfs)
    operator_analysis_result = analyze_by_operator(file_dfs)
    _update_progress(75)
    
    _update_status("Đang chạy kiểm tra lỗi V5.1...")
    v51_check_results = run_all_duplicate_checks(file_dfs)
    _update_progress(80)

    if not main_results:
        raise ReconciliationError(
            "Quá trình đối soát chính không thành công.",
            {"step": "perform_reconciliation", "run_time": str(run_time)}
        )

    # 5. Tạo Summary và chạy Delta Analysis
    _update_status("Đang tạo tóm tắt và phân tích Delta...")
    current_summary_df = create_summary_dataframe(main_results, simple_results, inventory_change_results)
    
    # <<< SỬA LỖI: set_index được thực hiện ở đây, chỉ một lần >>>
    delta_analysis_result = perform_delta_analysis(
        current_summary_df.set_index('Hang muc'), 
        config.OUTPUT_DIR, 
        report_folder.name
    )
    _update_progress(90)
    # 6. Gộp kết quả
    main_results['v51_checks'] = v51_check_results
    
    final_results = {
        "main_results": main_results, "simple_results": simple_results,
        "inventory_change_results": inventory_change_results,
        "operator_analysis_result": operator_analysis_result,
        "delta_analysis_result": delta_analysis_result,
        "summary_df": current_summary_df,
        "quality_warnings": quality_warnings,
        "report_folder": report_folder,
        "run_timestamp": run_time
    }

    # 7. Tạo báo cáo
    _update_status("Đang tạo các file báo cáo...")
    create_reports(final_results)
    
    # 8. Gửi email và lưu kết quả
    _update_status("Đang gửi email và lưu kết quả dashboard...")
    send_report_email(report_folder, current_summary_df)
    save_results(final_results, output_dir)
    
    # 9. Lưu vào history database + Daily Snapshot + Transactions
    try:
        history_db = HistoryDatabase(output_dir)
        history_db.save_run(final_results)
        
        df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
        if not df_ton_moi.empty:
            snapshot_count = history_db.save_daily_snapshot(df_ton_moi, run_time)
            _update_status(f"Đã lưu snapshot {snapshot_count} container...")
        
        df_master_log = main_results.get('master_log', pd.DataFrame())
        if not df_master_log.empty:
            trans_count = history_db.save_transactions(df_master_log, run_time)
            _update_status(f"Đã lưu {trans_count} giao dịch vào lịch sử...")
        
        save_cache_metadata(output_dir, get_input_files_hashes(input_dir))
    except Exception as e:
        logging.warning(f"Could not save to history database: {e}")
    
    _update_progress(100)
    
    _update_status("Hoàn tất!")
    return report_folder