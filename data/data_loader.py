# File: data_loader.py
import pandas as pd
from pathlib import Path
import logging
from typing import Dict, Optional
from config import Col
from utils.exceptions import DataLoadError, ValidationError, MissingColumnError
from data.data_transformer import (
    clean_column_names, 
    standardize_datetime_columns,
    assign_transaction_time,
    apply_business_rules,
    normalize_vietnamese_text
)


def ultimate_clean_series(series: pd.Series) -> pd.Series:
    if not isinstance(series, pd.Series):
        raise TypeError("Đầu vào phải là một pandas Series.")
    s = (series.dropna().astype(str).str.replace(r'\.0$', '', regex=True)
         .str.strip().str.upper().str.replace(r'[^A-Z0-9]', '', regex=True))
    s.replace('', pd.NA, inplace=True)
    return s

def load_and_transform_one_file(file_path: Path, file_name: str, file_key: str, cleaned_files_dir: Path, max_retries: int = 3) -> pd.DataFrame:
    """
    Load and transform one Excel file with retry mechanism.
    
    V5.0: Added retry logic for file loading failures.
    """
    logging.info(f"Đang xử lý file: {file_name} (key: {file_key})...")
    
    # V5.0: Retry mechanism
    import time
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
            break  # Success, exit retry loop
        except FileNotFoundError:
            logging.error(f"Không tìm thấy file: {file_name}")
            return pd.DataFrame()
        except PermissionError as e:
            last_error = e
            if attempt < max_retries:
                wait_time = attempt * 2  # Exponential backoff: 2s, 4s, 6s
                logging.warning(f"[Retry {attempt}/{max_retries}] File đang bị lock: {file_name}. Đợi {wait_time}s...")
                time.sleep(wait_time)
            else:
                logging.error(f"Không có quyền truy cập file sau {max_retries} lần thử: {file_name}")
                return pd.DataFrame()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait_time = attempt
                logging.warning(f"[Retry {attempt}/{max_retries}] Lỗi đọc file {file_name}: {e}. Thử lại sau {wait_time}s...")
                time.sleep(wait_time)
            else:
                logging.error(f"Lỗi khi đọc file {file_name} sau {max_retries} lần thử: {e}")
                return pd.DataFrame()
    else:
        # All retries exhausted
        logging.error(f"Không thể đọc file {file_name} sau {max_retries} lần thử: {last_error}")
        return pd.DataFrame()

    df = clean_column_names(df)
    df[Col.SOURCE_FILE] = file_name
    df[Col.SOURCE_KEY] = file_key

    possible_container_cols = ['Container', 'Số Container']
    found_col = next((col for col in possible_container_cols if col in df.columns), None)
    if not found_col:
        logging.warning(f"File {file_name} không có cột container. Bỏ qua...")
        return pd.DataFrame()
    
    df.rename(columns={found_col: Col.CONTAINER}, inplace=True)
    df[Col.CONTAINER] = ultimate_clean_series(df[Col.CONTAINER])
    df.dropna(subset=[Col.CONTAINER], inplace=True)
    if df.empty: return pd.DataFrame()

    for col in [Col.PHUONG_AN, Col.VAO_RA]:
        if col in df.columns:
            df[col] = normalize_vietnamese_text(df[col])

    df = standardize_datetime_columns(df)
    df = assign_transaction_time(df)
    df = apply_business_rules(df)
    
    # <<< NÂNG CẤP: Tối ưu hóa bộ nhớ với kiểu 'category' >>>
    for col in [Col.OPERATOR, Col.FE, Col.SOURCE_KEY, Col.MOVE_TYPE, Col.PHUONG_AN]:
        if col in df.columns:
            df[col] = df[col].astype('category')
    
    cleaned_output_path = cleaned_files_dir / f"cleaned_{file_key}.xlsx"
    df.to_excel(cleaned_output_path, index=False, engine='openpyxl')
    
    return df

def load_all_data(files_config: Dict[str, str], input_dir: Path, report_folder: Path) -> Dict[str, pd.DataFrame]:
    logging.info("--- GIAI ĐOẠN 1: TẢI VÀ BIẾN ĐỔI DỮ LIỆU ---")
    
    cleaned_files_dir = report_folder / "0a_Cleaned_Files"
    cleaned_files_dir.mkdir(exist_ok=True)
    
    file_dfs = {}
    for key, filename_or_list in files_config.items():
        # Bỏ qua các keys đặc biệt (như duplicate_warnings)
        if key == 'duplicate_warnings':
            continue
            
        # V5.2.1: Chỉ xử lý single file (không gộp list)
        if isinstance(filename_or_list, list):
            # Nếu là list, chỉ lấy file đầu tiên (đã có warning ở grouping stage)
            filename = filename_or_list[0]
            logging.warning(f"[{key}] Có {len(filename_or_list)} files, chỉ dùng file đầu: {filename}")
        else:
            filename = filename_or_list
            
        df = load_and_transform_one_file(input_dir / filename, filename, key, cleaned_files_dir)
        file_dfs[key] = df
    
    # V4.5.2: Tách file chung thành các phần riêng biệt
    file_dfs = _split_combined_files(file_dfs, cleaned_files_dir)
    
    return file_dfs


def _split_combined_files(file_dfs: Dict[str, pd.DataFrame], cleaned_files_dir: Path) -> Dict[str, pd.DataFrame]:
    """
    V4.5.2: Tách các file chung (GATE, SHIFTING, NHAPXUAT) thành các phần riêng biệt.
    Dựa trên cột Vào/Ra hoặc Hướng công việc.
    """
    # Các cột có thể chứa thông tin vào/ra
    vao_keywords = ['VÀO', 'VAO', 'Vào', 'IN', 'In', 'NHẬP', 'Nhập', 'NHAP']
    ra_keywords = ['RA', 'Ra', 'OUT', 'Out', 'XUẤT', 'Xuất', 'XUAT']
    
    # 1. Tách GATE (nếu có gate_combined)
    if 'gate_combined' in file_dfs and not file_dfs['gate_combined'].empty:
        df_gate = file_dfs['gate_combined']
        logging.info(f"  -> Đang tách GATE file ({len(df_gate)} records)...")
        
        # Tìm cột vào/ra
        vao_ra_col = _find_vao_ra_column(df_gate)
        if vao_ra_col:
            mask_vao = df_gate[vao_ra_col].astype(str).str.upper().str.strip().isin([k.upper() for k in vao_keywords])
            mask_ra = df_gate[vao_ra_col].astype(str).str.upper().str.strip().isin([k.upper() for k in ra_keywords])
            
            df_gate_in = df_gate[mask_vao].copy()
            df_gate_out = df_gate[mask_ra].copy()
            
            if not df_gate_in.empty:
                df_gate_in[Col.SOURCE_KEY] = 'gate_in'
                df_gate_in.to_excel(cleaned_files_dir / "cleaned_gate_in.xlsx", index=False)
                file_dfs['gate_in'] = pd.concat([file_dfs.get('gate_in', pd.DataFrame()), df_gate_in], ignore_index=True)
                logging.info(f"    + Gate IN: {len(df_gate_in)} containers")
                
            if not df_gate_out.empty:
                df_gate_out[Col.SOURCE_KEY] = 'gate_out'
                df_gate_out.to_excel(cleaned_files_dir / "cleaned_gate_out.xlsx", index=False)
                file_dfs['gate_out'] = pd.concat([file_dfs.get('gate_out', pd.DataFrame()), df_gate_out], ignore_index=True)
                logging.info(f"    + Gate OUT: {len(df_gate_out)} containers")
        
        del file_dfs['gate_combined']
    
    # 2. Tách SHIFTING (nếu có shifting_combined)  
    if 'shifting_combined' in file_dfs and not file_dfs['shifting_combined'].empty:
        df_shift = file_dfs['shifting_combined']
        logging.info(f"  -> Đang tách SHIFTING file ({len(df_shift)} records)...")
        
        # Tìm cột chứa thông tin loại shifting (có thể là 'Hướng công việc' hoặc tương tự)
        shift_col = _find_shifting_type_column(df_shift)
        if shift_col:
            # V4.5.2: Sửa regex - tránh 'SHIFTING' khớp với 'IN'
            # Discharge = Tàu đưa container xuống bãi (nhập bãi)
            mask_discharge = df_shift[shift_col].astype(str).str.upper().str.contains('DISCHARGE', regex=False, na=False)
            # Loading = Bãi đưa container lên tàu (xuất bãi)
            mask_loading = df_shift[shift_col].astype(str).str.upper().str.contains('LOADING', regex=False, na=False)
            
            df_nhap_shift = df_shift[mask_discharge].copy()
            df_xuat_shift = df_shift[mask_loading].copy()
            
            if not df_nhap_shift.empty:
                df_nhap_shift[Col.SOURCE_KEY] = 'nhap_shifting'
                df_nhap_shift.to_excel(cleaned_files_dir / "cleaned_nhap_shifting.xlsx", index=False)
                file_dfs['nhap_shifting'] = pd.concat([file_dfs.get('nhap_shifting', pd.DataFrame()), df_nhap_shift], ignore_index=True)
                logging.info(f"    + Shifting Discharge: {len(df_nhap_shift)} containers")
                
            if not df_xuat_shift.empty:
                df_xuat_shift[Col.SOURCE_KEY] = 'xuat_shifting'
                df_xuat_shift.to_excel(cleaned_files_dir / "cleaned_xuat_shifting.xlsx", index=False)
                file_dfs['xuat_shifting'] = pd.concat([file_dfs.get('xuat_shifting', pd.DataFrame()), df_xuat_shift], ignore_index=True)
                logging.info(f"    + Shifting Loading: {len(df_xuat_shift)} containers")
        
        del file_dfs['shifting_combined']
    
    # 3. Tách NHAPXUAT (nếu có nhapxuat_combined)
    if 'nhapxuat_combined' in file_dfs and not file_dfs['nhapxuat_combined'].empty:
        df_nx = file_dfs['nhapxuat_combined']
        logging.info(f"  -> Đang tách NHAPXUAT file ({len(df_nx)} records)...")
        
        # V4.5.3: Sử dụng cột Hướng (Import/Export) làm key phân biệt
        huong_col = _find_huong_column(df_nx)
        
        if huong_col:
            # Export = Xuất tàu (container từ bãi lên tàu)
            mask_export = df_nx[huong_col].astype(str).str.upper().str.contains('EXPORT|XUẤT|XUAT', regex=True, na=False)
            # Import = Nhập tàu (container từ tàu xuống bãi)
            mask_import = df_nx[huong_col].astype(str).str.upper().str.contains('IMPORT|NHẬP|NHAP', regex=True, na=False)
            
            df_xuat = df_nx[mask_export].copy()
            df_nhap = df_nx[mask_import].copy()
            
            if not df_nhap.empty:
                df_nhap[Col.SOURCE_KEY] = 'nhap_tau'
                df_nhap.to_excel(cleaned_files_dir / "cleaned_nhap_tau.xlsx", index=False)
                file_dfs['nhap_tau'] = pd.concat([file_dfs.get('nhap_tau', pd.DataFrame()), df_nhap], ignore_index=True)
                logging.info(f"    + Nhập tàu (Import): {len(df_nhap)} containers")
            
            if not df_xuat.empty:
                df_xuat[Col.SOURCE_KEY] = 'xuat_tau'
                df_xuat.to_excel(cleaned_files_dir / "cleaned_xuat_tau.xlsx", index=False)
                file_dfs['xuat_tau'] = pd.concat([file_dfs.get('xuat_tau', pd.DataFrame()), df_xuat], ignore_index=True)
                logging.info(f"    + Xuất tàu (Export): {len(df_xuat)} containers")
        else:
            logging.warning("    ! Không tìm thấy cột Hướng trong file NHAPXUAT")
        
        del file_dfs['nhapxuat_combined']
    
    return file_dfs


def _find_vao_ra_column(df: pd.DataFrame) -> Optional[str]:
    """Tìm cột chứa thông tin Vào/Ra trong DataFrame."""
    possible_cols = ['Vào/ Ra', 'Vào/Ra', 'VAO/RA', 'VaoRa', 'Direction', Col.VAO_RA]
    for col in possible_cols:
        if col in df.columns:
            return col
    # Tìm theo pattern
    for col in df.columns:
        if 'vào' in col.lower() or 'ra' in col.lower():
            return col
    return None


def _find_huong_column(df: pd.DataFrame) -> Optional[str]:
    """Tìm cột chứa thông tin Hướng (Import/Export) trong DataFrame."""
    possible_cols = ['Hướng', 'Huong', 'Direction', 'HƯỚNG', 'HUONG']
    for col in possible_cols:
        if col in df.columns:
            return col
    # Tìm theo pattern
    for col in df.columns:
        if 'hướng' in col.lower() and 'công' not in col.lower():  # Tránh nhầm với 'Hướng công việc'
            return col
    return None


def _find_shifting_type_column(df: pd.DataFrame) -> Optional[str]:
    """Tìm cột chứa loại Shifting (Discharge/Loading)."""
    possible_cols = ['Hướng công việc', 'Huong cong viec', 'ShiftType', 'Type', 'Loại']
    for col in possible_cols:
        if col in df.columns:
            return col
    for col in df.columns:
        if 'hướng' in col.lower() or 'việc' in col.lower() or 'shift' in col.lower():
            return col
    return None


def _find_phuong_an_column(df: pd.DataFrame, direction: str) -> Optional[str]:
    """Tìm cột phương án vào hoặc ra."""
    if direction == 'vào':
        possible_cols = ['Phương án vào', 'Phuong an vao', 'PA_Vao', Col.PHUONG_AN]
    else:
        possible_cols = ['Phương án ra', 'Phuong an ra', 'PA_Ra']
    
    for col in possible_cols:
        if col in df.columns:
            return col
    return None