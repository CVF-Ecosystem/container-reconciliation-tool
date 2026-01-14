# File: movement_summary.py
# Module tạo báo cáo biến động chi tiết theo kích cỡ container
# Version: 5.1

import pandas as pd
import logging
from typing import Dict, Optional, Tuple
from config import Col

# ============================================================================
# BẢNG TỔNG HỢP BIẾN ĐỘNG THEO KÍCH CỠ CONTAINER
# ============================================================================

def classify_container_size(iso_code: str) -> str:
    """
    Phân loại container thành 20/40 dựa trên ISO code.
    
    Args:
        iso_code: Mã kích cỡ ISO (ví dụ: 22G1, 45G1, 20GP, 40HC)
    
    Returns:
        '20' hoặc '40' hoặc 'Other'
    """
    if pd.isna(iso_code) or str(iso_code).strip() == '':
        return 'Other'
    
    iso_str = str(iso_code).upper().strip()
    
    # Lấy ký tự đầu tiên để xác định kích cỡ
    first_char = iso_str[0] if iso_str else ''
    
    if first_char == '2':
        return '20'
    elif first_char in ['4', '9', 'L', 'M']:  # 40, 45, L5 đều là 40ft
        return '40'
    elif iso_str.startswith('20'):
        return '20'
    elif iso_str.startswith('40') or iso_str.startswith('45'):
        return '40'
    else:
        return 'Other'


def classify_container_fe(fe_value: str) -> str:
    """
    Phân loại container Empty/Full.
    
    Args:
        fe_value: Giá trị F/E (Full, Empty, F, E, Hàng, Rỗng)
    
    Returns:
        'E' (Empty) hoặc 'F' (Full) hoặc 'Unknown'
    """
    if pd.isna(fe_value) or str(fe_value).strip() == '':
        return 'Unknown'
    
    fe_str = str(fe_value).upper().strip()
    
    # Empty
    if fe_str in ['E', 'EMPTY', 'RỖNG', 'RONG', 'R', 'MT']:
        return 'E'
    # Full
    elif fe_str in ['F', 'FULL', 'HÀNG', 'HANG', 'H', 'FL']:
        return 'F'
    else:
        return 'Unknown'


def get_size_fe_category(row: pd.Series) -> str:
    """
    Lấy category 20E/20F/40E/40F cho container.
    
    Returns:
        '20E', '20F', '40E', '40F' hoặc 'Other'
    """
    size = classify_container_size(row.get(Col.ISO, ''))
    fe = classify_container_fe(row.get(Col.FE, ''))
    
    if size in ['20', '40'] and fe in ['E', 'F']:
        return f"{size}{fe}"
    return 'Other'


def count_containers_by_category(df: pd.DataFrame) -> Dict[str, int]:
    """
    Đếm số container theo category 20E/20F/40E/40F.
    
    Returns:
        Dict với keys: '20E', '20F', '40E', '40F', 'Other', 'Total'
    """
    if df.empty:
        return {'20E': 0, '20F': 0, '40E': 0, '40F': 0, 'Other': 0, 'Total': 0}
    
    # Thêm cột phân loại
    df_temp = df.copy()
    df_temp['_SizeFE'] = df_temp.apply(get_size_fe_category, axis=1)
    
    counts = df_temp['_SizeFE'].value_counts().to_dict()
    
    result = {
        '20E': counts.get('20E', 0),
        '20F': counts.get('20F', 0),
        '40E': counts.get('40E', 0),
        '40F': counts.get('40F', 0),
        'Other': counts.get('Other', 0),
    }
    result['Total'] = sum(result.values())
    
    return result


def classify_phuong_an(phuong_an: str, source_key: str) -> str:
    """
    Phân loại phương án thành nhóm nghiệp vụ.
    
    Args:
        phuong_an: Tên phương án
        source_key: Key nguồn file (gate_in, gate_out, nhap_tau, xuat_tau)
    
    Returns:
        Tên nhóm nghiệp vụ
    """
    if pd.isna(phuong_an):
        return 'Khác'
    
    pa_upper = str(phuong_an).upper().strip()
    
    # GATE IN groups
    if source_key == 'gate_in':
        if any(k in pa_upper for k in ['HẠ BÃI', 'HA BAI']):
            return 'Hạ bãi (Nhập hàng)'
        elif any(k in pa_upper for k in ['TRẢ RỖNG', 'TRA RONG']):
            return 'Trả rỗng (Hạ rỗng)'
        elif any(k in pa_upper for k in ['ĐÓNG HÀNG', 'DONG HANG']):
            return 'Đóng hàng (CFS)'
        elif any(k in pa_upper for k in ['RÚT HÀNG', 'RUT HANG']):
            return 'Rút hàng (CFS)'
        else:
            return 'Gate In khác'
    
    # GATE OUT groups
    elif source_key == 'gate_out':
        if any(k in pa_upper for k in ['LẤY NGUYÊN', 'LAY NGUYEN']):
            return 'Lấy nguyên (Xuất hàng)'
        elif any(k in pa_upper for k in ['CẤP RỖNG', 'CAP RONG']):
            return 'Cấp rỗng'
        elif any(k in pa_upper for k in ['ĐÓNG HÀNG', 'DONG HANG']):
            return 'Đóng hàng (CFS)'
        elif any(k in pa_upper for k in ['RÚT HÀNG', 'RUT HANG']):
            return 'Rút hàng (CFS)'
        else:
            return 'Gate Out khác'
    
    # NHẬP TÀU
    elif source_key in ['nhap_tau', 'nhap_shifting']:
        return 'Nhập tàu'
    
    # XUẤT TÀU
    elif source_key in ['xuat_tau', 'xuat_shifting']:
        return 'Xuất tàu'
    
    return 'Khác'


def create_movement_summary(
    file_dfs: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Tạo bảng tổng hợp biến động chi tiết theo 20E/20F/40E/40F.
    
    Args:
        file_dfs: Dict chứa các DataFrame theo source_key
    
    Returns:
        DataFrame bảng tổng hợp:
        | Hạng mục       | 20E | 20F | 40E | 40F | Other | Tổng |
        |----------------|-----|-----|-----|-----|-------|------|
        | TỒN CŨ         | ... | ... | ... | ... | ...   | ...  |
        | GATE IN        | ... | ... | ... | ... | ...   | ...  |
        | - Nhập hàng    | ... | ... | ... | ... | ...   | ...  |
        | ...            |     |     |     |     |       |      |
    """
    logging.info("=" * 60)
    logging.info("TẠO BẢNG TỔNG HỢP BIẾN ĐỘNG (MOVEMENT SUMMARY)")
    logging.info("=" * 60)
    
    summary_rows = []
    
    # ----- TỒN CŨ -----
    df_ton_cu = file_dfs.get('ton_cu', pd.DataFrame())
    counts = count_containers_by_category(df_ton_cu)
    summary_rows.append({
        'Hạng mục': 'TON CU (Dau ky)',
        'Level': 0,
        **counts
    })
    logging.info(f"[TON CU] Total: {counts['Total']}")
    
    # ----- GATE IN -----
    df_gate_in = file_dfs.get('gate_in', pd.DataFrame())
    gate_in_counts = count_containers_by_category(df_gate_in)
    summary_rows.append({
        'Hạng mục': 'GATE IN (Vao)',
        'Level': 0,
        **gate_in_counts
    })
    
    # Chi tiết Gate In theo phương án
    if not df_gate_in.empty and Col.PHUONG_AN in df_gate_in.columns:
        df_gi = df_gate_in.copy()
        df_gi['_Group'] = df_gi[Col.PHUONG_AN].apply(lambda x: classify_phuong_an(x, 'gate_in'))
        
        for group in ['Hạ bãi (Nhập hàng)', 'Trả rỗng (Hạ rỗng)', 'Đóng hàng (CFS)', 'Rút hàng (CFS)', 'Gate In khác']:
            df_group = df_gi[df_gi['_Group'] == group]
            if not df_group.empty:
                counts = count_containers_by_category(df_group)
                summary_rows.append({
                    'Hạng mục': f'  - {group}',
                    'Level': 1,
                    **counts
                })
    
    # ----- GATE OUT -----
    df_gate_out = file_dfs.get('gate_out', pd.DataFrame())
    gate_out_counts = count_containers_by_category(df_gate_out)
    summary_rows.append({
        'Hạng mục': 'GATE OUT (Ra)',
        'Level': 0,
        **gate_out_counts
    })
    
    # Chi tiết Gate Out theo phương án
    if not df_gate_out.empty and Col.PHUONG_AN in df_gate_out.columns:
        df_go = df_gate_out.copy()
        df_go['_Group'] = df_go[Col.PHUONG_AN].apply(lambda x: classify_phuong_an(x, 'gate_out'))
        
        for group in ['Lấy nguyên (Xuất hàng)', 'Cấp rỗng', 'Đóng hàng (CFS)', 'Rút hàng (CFS)', 'Gate Out khác']:
            df_group = df_go[df_go['_Group'] == group]
            if not df_group.empty:
                counts = count_containers_by_category(df_group)
                summary_rows.append({
                    'Hạng mục': f'  - {group}',
                    'Level': 1,
                    **counts
                })
    
    # ----- NHẬP TÀU -----
    df_nhap_tau = file_dfs.get('nhap_tau', pd.DataFrame())
    df_nhap_shift = file_dfs.get('nhap_shifting', pd.DataFrame())
    
    nhap_tau_list = [df for df in [df_nhap_tau, df_nhap_shift] if not df.empty]
    if nhap_tau_list:
        df_all_nhap = pd.concat(nhap_tau_list, ignore_index=True)
        counts = count_containers_by_category(df_all_nhap)
    else:
        counts = count_containers_by_category(pd.DataFrame())
    summary_rows.append({
        'Hạng mục': 'NHAP TAU (Discharge)',
        'Level': 0,
        **counts
    })
    
    # ----- XUẤT TÀU -----
    df_xuat_tau = file_dfs.get('xuat_tau', pd.DataFrame())
    df_xuat_shift = file_dfs.get('xuat_shifting', pd.DataFrame())
    
    xuat_tau_list = [df for df in [df_xuat_tau, df_xuat_shift] if not df.empty]
    if xuat_tau_list:
        df_all_xuat = pd.concat(xuat_tau_list, ignore_index=True)
        counts = count_containers_by_category(df_all_xuat)
    else:
        counts = count_containers_by_category(pd.DataFrame())
    summary_rows.append({
        'Hạng mục': 'XUAT TAU (Loading)',
        'Level': 0,
        **counts
    })
    
    # ----- SHIFTING -----
    df_shifting = file_dfs.get('shifting_combined', pd.DataFrame())
    counts = count_containers_by_category(df_shifting)
    if counts['Total'] > 0:
        summary_rows.append({
            'Hạng mục': 'SHIFTING',
            'Level': 0,
            **counts
        })
    
    # ----- TỒN MỚI -----
    df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
    counts = count_containers_by_category(df_ton_moi)
    summary_rows.append({
        'Hạng mục': 'TON MOI (Cuoi ky)',
        'Level': 0,
        **counts
    })
    logging.info(f"[TON MOI] Total: {counts['Total']}")
    
    # ----- TẠO DATAFRAME -----
    df_summary = pd.DataFrame(summary_rows)
    
    # Sắp xếp cột - LOẠI BỎ CỘT LEVEL (chỉ dùng nội bộ)
    col_order = ['Hạng mục', '20E', '20F', '40E', '40F', 'Other', 'Total']
    df_summary = df_summary[[c for c in col_order if c in df_summary.columns]]
    
    logging.info("=" * 60)
    logging.info("HOÀN THÀNH BẢNG TỔNG HỢP BIẾN ĐỘNG")
    logging.info("=" * 60)
    
    return df_summary


def calculate_movement_balance(
    file_dfs: Dict[str, pd.DataFrame]
) -> Dict[str, any]:
    """
    Tính toán cân đối biến động để kiểm tra.
    
    Công thức: TỒN CŨ + NHẬP - XUẤT = TỒN MỚI
    - NHẬP = Gate In + Nhập tàu
    - XUẤT = Gate Out + Xuất tàu
    
    Returns:
        Dict chứa thông tin cân đối và chênh lệch
    """
    # Đếm tồn cũ
    df_ton_cu = file_dfs.get('ton_cu', pd.DataFrame())
    ton_cu = len(df_ton_cu) if not df_ton_cu.empty else 0
    
    # Đếm tồn mới
    df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
    ton_moi = len(df_ton_moi) if not df_ton_moi.empty else 0
    
    # Đếm nhập
    nhap = 0
    for key in ['gate_in', 'nhap_tau', 'nhap_shifting']:
        df = file_dfs.get(key, pd.DataFrame())
        nhap += len(df) if not df.empty else 0
    
    # Đếm xuất
    xuat = 0
    for key in ['gate_out', 'xuat_tau', 'xuat_shifting']:
        df = file_dfs.get(key, pd.DataFrame())
        xuat += len(df) if not df.empty else 0
    
    # Tính cân đối
    expected_ton_moi = ton_cu + nhap - xuat
    chenh_lech = ton_moi - expected_ton_moi
    
    balance_info = {
        'ton_cu': ton_cu,
        'nhap': nhap,
        'xuat': xuat,
        'ton_moi_thuc_te': ton_moi,
        'ton_moi_du_kien': expected_ton_moi,
        'chenh_lech': chenh_lech,
        'cong_thuc': f"{ton_cu} + {nhap} - {xuat} = {expected_ton_moi}",
        'can_doi': chenh_lech == 0
    }
    
    if chenh_lech != 0:
        logging.warning(f"[BALANCE] Chênh lệch: {chenh_lech} container")
        logging.warning(f"[BALANCE] Công thức: {balance_info['cong_thuc']}")
        logging.warning(f"[BALANCE] Tồn mới thực tế: {ton_moi}")
    else:
        logging.info(f"[BALANCE] Cân đối OK: {balance_info['cong_thuc']} = {ton_moi}")
    
    return balance_info


def create_balance_summary_row(balance_info: Dict) -> pd.DataFrame:
    """
    Tạo dòng tổng kết cân đối để thêm vào bảng summary.
    """
    rows = [
        {
            'Hạng mục': '-' * 30,
            '20E': '-', '20F': '-', '40E': '-', '40F': '-', 'Other': '-', 'Total': '-'
        },
        {
            'Hạng mục': 'KIEM TRA CAN DOI',
            '20E': '', '20F': '', '40E': '', '40F': '', 'Other': '',
            'Total': ''
        },
        {
            'Hạng mục': f"  Cong thuc: {balance_info['cong_thuc']}",
            '20E': '', '20F': '', '40E': '', '40F': '', 'Other': '',
            'Total': balance_info['ton_moi_du_kien']
        },
        {
            'Hạng mục': f"  Ton moi thuc te:",
            '20E': '', '20F': '', '40E': '', '40F': '', 'Other': '',
            'Total': balance_info['ton_moi_thuc_te']
        },
        {
            'Hạng mục': f"  {'CAN DOI' if balance_info['can_doi'] else 'CHENH LECH: ' + str(balance_info['chenh_lech'])}",
            '20E': '', '20F': '', '40E': '', '40F': '', 'Other': '',
            'Total': balance_info['chenh_lech']
        }
    ]
    
    return pd.DataFrame(rows)


def generate_full_movement_report(
    file_dfs: Dict[str, pd.DataFrame]
) -> Tuple[pd.DataFrame, Dict]:
    """
    Tạo báo cáo biến động đầy đủ bao gồm cả kiểm tra cân đối.
    
    Returns:
        Tuple[DataFrame summary, Dict balance_info]
    """
    # Tạo bảng tổng hợp
    df_summary = create_movement_summary(file_dfs)
    
    # Tính cân đối
    balance_info = calculate_movement_balance(file_dfs)
    
    # Thêm phần cân đối vào bảng
    df_balance = create_balance_summary_row(balance_info)
    df_full = pd.concat([df_summary, df_balance], ignore_index=True)
    
    return df_full, balance_info


def create_vosco_movement_summary(
    file_dfs: Dict[str, pd.DataFrame],
    exclude_soc: bool = True
) -> pd.DataFrame:
    """
    Tạo bảng tổng hợp biến động riêng cho VOSCO.
    
    Args:
        file_dfs: Dict chứa các DataFrame theo source_key
        exclude_soc: Nếu True, loại bỏ container SOC (mã SVC), chỉ tính COC (mã VOC)
        
    Returns:
        DataFrame bảng tổng hợp biến động cho VOSCO (chỉ COC)
    """
    logging.info("=" * 60)
    logging.info("TẠO BẢNG TỔNG HỢP BIẾN ĐỘNG VOSCO (CHỈ COC - LOẠI TRỪ SOC)")
    logging.info("=" * 60)
    
    # Define VOSCO operator codes
    # VOC = Container do hãng sở hữu (COC - Carrier-Owned Container)
    # SVC = Container của chủ hàng (SOC - Shipper-Owned Container)
    vosco_codes = ['VOC']
    if not exclude_soc:
        vosco_codes.append('SVC')
    
    logging.info(f"[VOSCO] Filter theo mã: {vosco_codes}")
    
    # Create filtered file_dfs for Vosco only
    vosco_dfs = {}
    for key, df in file_dfs.items():
        if df.empty:
            vosco_dfs[key] = df
            continue
        
        # Find operator column
        operator_col = None
        for col in [Col.OPERATOR, 'Hãng khai thác', 'Hãng KT', 'Lines']:
            if col in df.columns:
                operator_col = col
                break
        
        if operator_col:
            # Filter for VOSCO operator codes only
            filtered = df[df[operator_col].isin(vosco_codes)].copy()
            vosco_dfs[key] = filtered
            if not filtered.empty:
                logging.info(f"  [{key}] VOSCO COC: {len(filtered)} containers")
        else:
            vosco_dfs[key] = pd.DataFrame()  # No operator column = empty
    
    # Generate movement summary using filtered data
    df_vosco_summary = create_movement_summary(vosco_dfs)
    
    # Add header row to indicate this is VOSCO-specific
    header_row = pd.DataFrame([{
        'Hạng mục': '=== VOSCO - CHỈ TÍNH COC (LOẠI TRỪ SOC) ===',
        '20E': '', '20F': '', '40E': '', '40F': '', 'Other': '', 'Total': ''
    }])
    
    df_result = pd.concat([header_row, df_vosco_summary], ignore_index=True)
    
    logging.info("=" * 60)
    logging.info("HOÀN THÀNH BẢNG TỔNG HỢP VOSCO")
    logging.info("=" * 60)
    
    return df_result
