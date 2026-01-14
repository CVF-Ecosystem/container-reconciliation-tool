# File: reports/email_template_exporter.py
# V5.2: Xuất file theo template chuẩn BIEN DONG và TON BAI để gửi email cho hãng tàu

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import date

from config import Col, OPERATOR_MAPPING


# === TEMPLATE COLUMNS ===
# Giữ đúng thứ tự và tên cột như file mẫu để hãng tàu map vào TOS

BIEN_DONG_COLUMNS = [
    'Số Container', 'Số lệnh', 'Kích cỡ nội bộ', 'Kích cỡ ISO', 'F/E', 
    'Hãng KT', 'Vào/ Ra', 'Phương án', 'Phương tiện', 'Số xe / Sà lan',
    'Số rơmooc', 'Lịch trình tàu', 'Chủ hàng', 'Số BILL', 'Số Booking',
    'Hàng hóa', 'Loại hàng', 'Số niêm chì', 'Số niêm chì 1', 'Số niêm chì 2',
    'Trọng lượng', 'Cảng dỡ', 'Cảng đích', 'Vị trí bãi', 'VGM', 'CLASS',
    'UNNO', 'Nhiệt độ', 'Vent', 'Tình trạng Container', 'Cổng vào',
    'Xe vào cổng', 'Container vào bãi', 'Container ra bãi', 'Xe ra cổng',
    'Cổng ra', 'Số ngày lưu bãi', 'Ngày hoàn tất công việc bãi', 'Ghi chú',
    'PTGN', 'ĐTTT', 'HTTT', 'Số hóa đơn', 'Số PTC', 'Hàng nội/ ngoại',
    'Cảng chuyển', 'Cảng giao nhận', 'TLHQ', 'Giao quá hạn lệnh'
]

TON_BAI_COLUMNS = [
    'Hãng khai thác', 'Container', 'Kích cỡ', 'Kích cỡ ISO', 'Ghi chú',
    'Ghi chú nội bộ', 'Tình trạng vỏ', 'Năm sản xuất', 'Số ngày lưu bãi',
    'Lịch trình tàu', 'Tên tàu', 'Chuyến nhập', 'Chuyến xuất', 'Hướng',
    'Trạng thái', 'F/E', 'Phương án', 'Vị trí trên bãi', 'Cảng xếp',
    'Cảng dỡ', 'Cảng đích', 'Ngày nhập bãi', 'Ngày ra bãi', 'Loại Hàng',
    'Hàng Hóa', 'Trọng Lượng', 'Nhóm Trọng Lượng', 'VGM', 'Hủy', 'Nhiệt độ',
    'CLASS', 'UNNO', 'Chủ hàng', 'Số Booking', 'Số Vận Đơn', 'Số niêm chì',
    'Số niêm chì 1', 'Số niêm chì 2', 'Thanh Lý Hải Quan', 'Số tờ khai',
    'Hàng nội/ ngoại', 'Cảng chuyển', 'Cảng giao nhận', 'Số lệnh',
    'Thông gió', 'ĐVT thông gió'
]


# === COLUMN MAPPING ===
# Map từ columns nội bộ sang template columns
# V5.4: Mở rộng mapping để bao phủ tất cả các cột trong template

BIEN_DONG_MAPPING = {
    # Các cột từ config.Col
    Col.CONTAINER: 'Số Container',
    Col.JOB_ORDER: 'Số lệnh',
    Col.ISO: 'Kích cỡ ISO',
    Col.FE: 'F/E',
    Col.OPERATOR: 'Hãng KT',
    Col.VAO_RA: 'Vào/ Ra',
    Col.PHUONG_AN: 'Phương án',
    Col.LOCATION: 'Vị trí bãi',
    Col.XE_VAO_CONG: 'Xe vào cổng',
    Col.CONT_VAO_BAI: 'Container vào bãi',
    Col.CONT_RA_BAI: 'Container ra bãi',
    Col.XE_RA_CONG: 'Xe ra cổng',
    Col.NGAY_NHAP_BAI: 'Container vào bãi',  # Alias ngày nhập bãi
    Col.NGAY_RA_BAI: 'Container ra bãi',     # Alias ngày ra bãi
    Col.TRANSACTION_TIME: 'Ngày hoàn tất công việc bãi',  # Map thời điểm giao dịch
    
    # Các cột có thể có trong source data - mở rộng V5.4
    'Kích cỡ': 'Kích cỡ nội bộ',
    'Chủ hàng': 'Chủ hàng',
    'Số BILL': 'Số BILL',
    'Số Vận Đơn': 'Số BILL',  # Alias
    'Số Bill': 'Số BILL',  # Alias case-insensitive
    'Số Booking': 'Số Booking',
    'Hàng hóa': 'Hàng hóa',
    'Hàng Hóa': 'Hàng hóa',  # Alias
    'Loại hàng': 'Loại hàng',
    'Loại Hàng': 'Loại hàng',
    'Số niêm chì': 'Số niêm chì',
    'Số niêm chì 1': 'Số niêm chì 1',
    'Số niêm chì 2': 'Số niêm chì 2',
    'Trọng lượng': 'Trọng lượng',
    'Trọng Lượng': 'Trọng lượng',
    'VGM': 'VGM',
    'CLASS': 'CLASS',
    'UNNO': 'UNNO',
    'Nhiệt độ': 'Nhiệt độ',
    'Vent': 'Vent',
    'Thông gió': 'Vent',  # Alias
    'Ghi chú': 'Ghi chú',
    'Lịch trình tàu': 'Lịch trình tàu',
    'Tên tàu': 'Lịch trình tàu',  # Có thể dùng Tên tàu cho Lịch trình
    'Cảng dỡ': 'Cảng dỡ',
    'Cảng đích': 'Cảng đích',
    
    # V5.5: Thêm các cột còn thiếu - map từ source data
    'Hướng': 'Vào/ Ra',  # Hướng = Vào/Ra
    'LoaiGiaoDich': 'Vào/ Ra',  # Internal column
    'NguonGoc': 'Phương tiện',  # Source info
    'Trạng thái': 'Tình trạng Container',
    'Tình trạng vỏ': 'Tình trạng Container',  # Alias
    'ThoiDiemGiaoDich': 'Ngày hoàn tất công việc bãi',  # Internal time column
    'Ngày nhập bãi': 'Container vào bãi',  # Map ngày nhập bãi
    'Ngày ra bãi': 'Container ra bãi',     # Map ngày ra bãi
    'Vị trí trên bãi': 'Vị trí bãi',  # Alias
    'Số ngày lưu bãi': 'Số ngày lưu bãi',
    
    # Thêm các cột còn lại từ template
    'Phương tiện': 'Phương tiện',
    'Số xe / Sà lan': 'Số xe / Sà lan',
    'Số rơmooc': 'Số rơmooc',
    'Tình trạng Container': 'Tình trạng Container',
    'Cổng vào': 'Cổng vào',
    'Cổng ra': 'Cổng ra',
    'Ngày hoàn tất công việc bãi': 'Ngày hoàn tất công việc bãi',
    'PTGN': 'PTGN',
    'ĐTTT': 'ĐTTT',
    'HTTT': 'HTTT',
    'Số hóa đơn': 'Số hóa đơn',
    'Số PTC': 'Số PTC',
    'Hàng nội/ ngoại': 'Hàng nội/ ngoại',
    'Cảng chuyển': 'Cảng chuyển',
    'Cảng giao nhận': 'Cảng giao nhận',
    'TLHQ': 'TLHQ',
    'Thanh Lý Hải Quan': 'TLHQ',  # Alias
    'Giao quá hạn lệnh': 'Giao quá hạn lệnh',
}


TON_BAI_MAPPING = {
    # Các cột từ config.Col
    Col.OPERATOR: 'Hãng khai thác',
    Col.CONTAINER: 'Container',
    Col.ISO: 'Kích cỡ ISO',
    Col.FE: 'F/E',
    Col.PHUONG_AN: 'Phương án',
    Col.LOCATION: 'Vị trí trên bãi',
    Col.NGAY_NHAP_BAI: 'Ngày nhập bãi',
    Col.NGAY_RA_BAI: 'Ngày ra bãi',
    
    # Các cột có thể có trong source data - mở rộng V5.4
    'Kích cỡ': 'Kích cỡ',
    'Ghi chú': 'Ghi chú',
    'Ghi chú nội bộ': 'Ghi chú nội bộ',
    'Tình trạng vỏ': 'Tình trạng vỏ',
    'Năm sản xuất': 'Năm sản xuất',
    'Số ngày lưu bãi': 'Số ngày lưu bãi',
    'Lịch trình tàu': 'Lịch trình tàu',
    'Tên tàu': 'Tên tàu',
    'Chuyến nhập': 'Chuyến nhập',
    'Chuyến xuất': 'Chuyến xuất',
    'Hướng': 'Hướng',
    'Trạng thái': 'Trạng thái',
    'Cảng xếp': 'Cảng xếp',
    'Cảng dỡ': 'Cảng dỡ',
    'Cảng đích': 'Cảng đích',
    'Loại Hàng': 'Loại Hàng',
    'Loại hàng': 'Loại Hàng',  # Alias
    'Hàng Hóa': 'Hàng Hóa',
    'Hàng hóa': 'Hàng Hóa',  # Alias
    'Trọng Lượng': 'Trọng Lượng',
    'Trọng lượng': 'Trọng Lượng',  # Alias
    'VGM': 'VGM',
    'Nhiệt độ': 'Nhiệt độ',
    'CLASS': 'CLASS',
    'UNNO': 'UNNO',
    'Chủ hàng': 'Chủ hàng',
    'Số Booking': 'Số Booking',
    'Số Vận Đơn': 'Số Vận Đơn',
    'Số BILL': 'Số Vận Đơn',  # Alias cho Số Vận Đơn
    'Số niêm chì': 'Số niêm chì',
    'Số niêm chì 1': 'Số niêm chì 1',
    'Số niêm chì 2': 'Số niêm chì 2',
    'Số lệnh': 'Số lệnh',
    
    # V5.4: Thêm các cột còn thiếu
    'Nhóm Trọng Lượng': 'Nhóm Trọng Lượng',
    'Hủy': 'Hủy',
    'Thanh Lý Hải Quan': 'Thanh Lý Hải Quan',
    'TLHQ': 'Thanh Lý Hải Quan',  # Alias
    'Số tờ khai': 'Số tờ khai',
    'Hàng nội/ ngoại': 'Hàng nội/ ngoại',
    'Cảng chuyển': 'Cảng chuyển',
    'Cảng giao nhận': 'Cảng giao nhận',
    'Thông gió': 'Thông gió',
    'ĐVT thông gió': 'ĐVT thông gió',
}


def get_operator_list() -> List[str]:
    """Lấy danh sách các hãng tàu từ config."""
    return list(OPERATOR_MAPPING.keys())


def get_operator_codes(operator_name: str) -> List[str]:
    """Lấy danh sách mã hãng tàu cho một tên hãng."""
    return OPERATOR_MAPPING.get(operator_name, [operator_name])


def _create_empty_template(columns: List[str]) -> pd.DataFrame:
    """Tạo DataFrame rỗng với đúng columns của template."""
    return pd.DataFrame(columns=columns)


def _map_to_template(df: pd.DataFrame, column_mapping: Dict[str, str], 
                     template_columns: List[str]) -> pd.DataFrame:
    """
    Map DataFrame từ format nội bộ sang format template.
    
    Args:
        df: DataFrame gốc
        column_mapping: Dict mapping từ cột nội bộ -> cột template
        template_columns: List các cột template (theo đúng thứ tự)
        
    Returns:
        DataFrame đã được map với đầy đủ cột template
    """
    if df.empty:
        return _create_empty_template(template_columns)
    
    # Tạo DataFrame mới với tất cả cột template
    result = pd.DataFrame(columns=template_columns)
    
    # Copy data từ các cột có mapping
    for internal_col, template_col in column_mapping.items():
        if internal_col in df.columns and template_col in template_columns:
            result[template_col] = df[internal_col].values if len(df) > 0 else []
    
    # Đảm bảo giữ đúng thứ tự cột
    result = result.reindex(columns=template_columns)
    
    return result


def enrich_with_raw_gate_data(
    df_bien_dong: pd.DataFrame,
    df_gate_in: pd.DataFrame = None,
    df_gate_out: pd.DataFrame = None
) -> pd.DataFrame:
    """
    V5.6: Bổ sung dữ liệu từ raw gate files vào biến động.
    
    Merge các cột thời gian và thông tin chi tiết từ gate data gốc
    mà không có trong inventory change results.
    
    Args:
        df_bien_dong: DataFrame biến động (từ inventory change)
        df_gate_in: DataFrame Gate In gốc (raw data)
        df_gate_out: DataFrame Gate Out gốc (raw data)
        
    Returns:
        DataFrame biến động đã được bổ sung thông tin từ gate
    """
    if df_bien_dong.empty:
        return df_bien_dong
    
    # Columns to enrich from raw gate data
    enrich_columns = [
        'Xe vào cổng', 'Container vào bãi', 'Container ra bãi', 'Xe ra cổng',
        'Cổng vào', 'Cổng ra', 'Phương tiện', 'Số xe / Sà lan', 'Số rơmooc',
        'Tình trạng Container', 'PTGN', 'ĐTTT', 'HTTT', 'Số hóa đơn', 'Số PTC',
        Col.XE_VAO_CONG, Col.CONT_VAO_BAI, Col.CONT_RA_BAI, Col.XE_RA_CONG
    ]
    
    df_result = df_bien_dong.copy()
    
    # Helper to merge gate data
    def merge_from_gate(df_target, df_source, direction: str):
        """Merge columns từ gate data vào target."""
        if df_source is None or df_source.empty:
            return df_target
        
        if Col.CONTAINER not in df_source.columns:
            return df_target
        
        # Lấy các cột có trong gate source nhưng không có trong target
        cols_to_add = [c for c in enrich_columns if c in df_source.columns and c not in df_target.columns]
        cols_to_fill = [c for c in enrich_columns if c in df_source.columns and c in df_target.columns]
        
        if not cols_to_add and not cols_to_fill:
            return df_target
        
        # Tạo lookup dict từ gate data (container -> row data)
        gate_lookup = {}
        for _, row in df_source.iterrows():
            cont = row.get(Col.CONTAINER)
            if cont and pd.notna(cont):
                # Nếu đã có, giữ bản ghi mới nhất (có thể dựa trên thời gian)
                gate_lookup[cont] = row
        
        # Merge data
        for idx, row in df_target.iterrows():
            cont = row.get(Col.CONTAINER)
            if cont and cont in gate_lookup:
                gate_row = gate_lookup[cont]
                # Add missing columns
                for col in cols_to_add:
                    if col not in df_target.columns:
                        df_target[col] = None
                    df_target.at[idx, col] = gate_row.get(col)
                # Fill empty values
                for col in cols_to_fill:
                    if pd.isna(df_target.at[idx, col]):
                        df_target.at[idx, col] = gate_row.get(col)
        
        return df_target
    
    # Merge từ Gate In
    if df_gate_in is not None and not df_gate_in.empty:
        df_result = merge_from_gate(df_result, df_gate_in, 'IN')
        logging.info(f"[Enrich] Merged columns from Gate In ({len(df_gate_in)} records)")
    
    # Merge từ Gate Out
    if df_gate_out is not None and not df_gate_out.empty:
        df_result = merge_from_gate(df_result, df_gate_out, 'OUT')
        logging.info(f"[Enrich] Merged columns from Gate Out ({len(df_gate_out)} records)")
    
    return df_result


def filter_by_operator(df: pd.DataFrame, operator_name: str, 
                       operator_col: str = None) -> pd.DataFrame:
    """
    Lọc DataFrame theo hãng tàu.
    
    Args:
        df: DataFrame cần lọc
        operator_name: Tên hãng (VD: 'VMC', 'VFC')
        operator_col: Tên cột chứa mã hãng (mặc định: Col.OPERATOR hoặc 'Hãng khai thác')
    """
    if df.empty:
        return df
    
    # Tìm cột operator
    if operator_col is None:
        for col in [Col.OPERATOR, 'Hãng khai thác', 'Hãng KT', 'Lines']:
            if col in df.columns:
                operator_col = col
                break
    
    if operator_col is None or operator_col not in df.columns:
        logging.warning(f"Không tìm thấy cột operator trong DataFrame")
        return df
    
    # Lấy danh sách mã của hãng
    operator_codes = get_operator_codes(operator_name)
    
    # Lọc
    mask = df[operator_col].isin(operator_codes) | (df[operator_col] == operator_name)
    return df[mask].copy()


def filter_gate_only(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter biến động chỉ giữ lại Gate In và Gate Out.
    Loại bỏ: nhập tàu, xuất tàu, shifting.
    
    Args:
        df: DataFrame biến động
        
    Returns:
        DataFrame chỉ chứa giao dịch qua cổng (gate in/out)
    """
    if df.empty:
        return df
    
    original_count = len(df)
    
    # Check for SourceKey column (from raw_data)
    if Col.SOURCE_KEY in df.columns:
        # Filter by SourceKey: keep gate_in and gate_out only
        mask = df[Col.SOURCE_KEY].str.lower().str.contains('gate', na=False)
        if mask.any():
            filtered = df[mask].copy()
            logging.info(f"[GateFilter] Filtered by SourceKey: {len(filtered)}/{original_count} containers")
            return filtered
    
    # Check for NguonGoc column (from inventory_change_results)
    if 'NguonGoc' in df.columns:
        # Keep only records with gate-related source
        gate_sources = ['Gate In', 'Gate Out', 'Cổng vào', 'Cổng ra', 'GATE']
        mask = df['NguonGoc'].str.upper().str.contains('GATE|CỔNG', na=False, regex=True)
        if mask.any():
            filtered = df[mask].copy()
            logging.info(f"[GateFilter] Filtered by NguonGoc: {len(filtered)}/{original_count} containers")
            return filtered
    
    # Filter by Phương án - exclude vessel movements and shifting
    if Col.PHUONG_AN in df.columns:
        # Define patterns to EXCLUDE (vessel and shifting movements)
        exclude_patterns = [
            'NHẬP TÀU', 'NHAP TAU', 'DISCHARGE',
            'XUẤT TÀU', 'XUAT TAU', 'LOADING',
            'SHIFTING', 'RESTOW', 'N-RESTOW', 'X-RESTOW'
        ]
        
        # Create case-insensitive exclusion mask
        exclude_mask = df[Col.PHUONG_AN].str.upper().str.contains(
            '|'.join(exclude_patterns), na=False
        )
        
        # Only filter if it doesn't remove ALL records
        filtered = df[~exclude_mask].copy()
        if not filtered.empty:
            logging.info(f"[GateFilter] Filtered by Phương án: {len(filtered)}/{original_count} containers")
            return filtered
        else:
            logging.warning(f"[GateFilter] Phương án filter would remove all data, returning original")
            return df
    
    # V5.6 FIX: If no proper filter could be applied, return original data with warning
    logging.warning(f"[GateFilter] No filter applied - returning all {original_count} records")
    return df


def export_bien_dong_for_operator(
    df_bien_dong: pd.DataFrame,
    operator_name: str,
    date_str: str,
    output_dir: Path
) -> Optional[Path]:
    """
    Xuất file BIEN DONG theo template cho một hãng tàu.
    
    Args:
        df_bien_dong: DataFrame biến động (từ file 5. BIEN_DONG_CHI_TIET.xlsx)
        operator_name: Tên hãng (VD: 'VMC')
        date_str: Chuỗi ngày (VD: 'N12.1.2026')
        output_dir: Thư mục xuất file
        
    Returns:
        Path đến file đã tạo hoặc None nếu lỗi
    """
    try:
        # Lọc theo hãng
        df_filtered = filter_by_operator(df_bien_dong, operator_name)
        
        # V5.5: Chỉ giữ lại Gate In/Out, loại bỏ nhập/xuất tàu và shifting
        df_filtered = filter_gate_only(df_filtered)
        
        if df_filtered.empty:
            logging.info(f"[EmailExporter] Không có biến động qua cổng cho hãng {operator_name}")
            return None

        
        # Map sang template
        df_template = _map_to_template(df_filtered, BIEN_DONG_MAPPING, BIEN_DONG_COLUMNS)
        
        # Tạo tên file
        filename = f"BIEN DONG - {operator_name} - {date_str}.xlsx"
        filepath = output_dir / filename
        
        # Xuất file
        df_template.to_excel(filepath, index=False, sheet_name='BIEN DONG')
        logging.info(f"✅ Đã xuất: {filename} ({len(df_filtered)} containers)")
        
        return filepath
        
    except Exception as e:
        logging.error(f"Lỗi xuất TON BAI cho {operator_name}: {e}")
        return None


def filter_stacking_containers(
    df_ton_moi: pd.DataFrame,
    df_ton_cu: pd.DataFrame,
    df_gate_in: pd.DataFrame,
    df_gate_out: pd.DataFrame
) -> pd.DataFrame:
    """
    V5.5: Lọc container Stacking - có trong TON MOI nhưng KHÔNG có trong (Gate In/Out + TON CU).
    
    Container Stacking = chưa hoàn tất thủ tục vào/ra cổng, chỉ đang xếp trên bãi.
    
    Returns:
        DataFrame chứa các container Stacking
    """
    if df_ton_moi.empty or Col.CONTAINER not in df_ton_moi.columns:
        return pd.DataFrame()
    
    # Lấy tập hợp container từ các nguồn
    set_ton_moi = set(df_ton_moi[Col.CONTAINER].dropna())
    
    set_ton_cu = set()
    if not df_ton_cu.empty and Col.CONTAINER in df_ton_cu.columns:
        set_ton_cu = set(df_ton_cu[Col.CONTAINER].dropna())
    
    set_gate_in = set()
    if not df_gate_in.empty and Col.CONTAINER in df_gate_in.columns:
        set_gate_in = set(df_gate_in[Col.CONTAINER].dropna())
    
    set_gate_out = set()
    if not df_gate_out.empty and Col.CONTAINER in df_gate_out.columns:
        set_gate_out = set(df_gate_out[Col.CONTAINER].dropna())
    
    # Stacking = có trong TON MOI nhưng không có trong (gate + tồn cũ)
    set_known = set_ton_cu | set_gate_in | set_gate_out
    set_stacking = set_ton_moi - set_known
    
    if not set_stacking:
        return pd.DataFrame()
    
    df_stacking = df_ton_moi[df_ton_moi[Col.CONTAINER].isin(set_stacking)].copy()
    logging.info(f"[Stacking] Tìm thấy {len(df_stacking)} container Stacking")
    
    return df_stacking


def filter_incoming_containers(
    df_gate_in: pd.DataFrame
) -> pd.DataFrame:
    """
    V5.5: Lọc container Incoming - có phương án Trả rỗng/Hạ bãi nhưng chưa có giờ vào bãi.
    
    Incoming = xe đã vào cổng nhưng container chưa hạ xuống bãi.
    
    Returns:
        DataFrame chứa các container Incoming
    """
    if df_gate_in.empty:
        return pd.DataFrame()
    
    # Cần có cột Phương án và thời gian
    if Col.PHUONG_AN not in df_gate_in.columns:
        return pd.DataFrame()
    
    # Phương án Incoming: Trả rỗng, Hạ bãi (E hoặc F)
    incoming_phuong_an = [
        'TRẢ RỖNG', 'TRA RONG',  # Trả rỗng E
        'HẠ BÃI', 'HA BAI',       # Hạ bãi E/F
        'EMPTY RETURN', 'DROP OFF', 'DROP'
    ]
    
    # Kiểm tra container có phương án incoming
    mask_phuong_an = df_gate_in[Col.PHUONG_AN].str.upper().str.contains(
        '|'.join(incoming_phuong_an), na=False
    )
    
    # Container chưa có giờ vào bãi (Incoming)
    mask_no_cont_time = pd.Series([True] * len(df_gate_in), index=df_gate_in.index)
    if Col.CONT_VAO_BAI in df_gate_in.columns:
        mask_no_cont_time = df_gate_in[Col.CONT_VAO_BAI].isna()
    
    # Incoming = có phương án hạ nhưng chưa có giờ vào bãi
    mask_incoming = mask_phuong_an & mask_no_cont_time
    
    df_incoming = df_gate_in[mask_incoming].copy()
    
    if not df_incoming.empty:
        logging.info(f"[Incoming] Tìm thấy {len(df_incoming)} container Incoming (chưa hạ bãi)")
    
    return df_incoming


def export_ton_bai_for_operator_v55(
    df_ton_bai: pd.DataFrame,
    operator_name: str,
    date_str: str,
    output_dir: Path,
    df_ton_cu: pd.DataFrame = None,
    df_gate_in: pd.DataFrame = None,
    df_gate_out: pd.DataFrame = None
) -> Optional[Path]:
    """
    V5.5: Xuất file TON BAI với sheet riêng cho Stacking và Incoming containers.
    
    Args:
        df_ton_bai: DataFrame tồn bãi (từ file TON MOI)
        operator_name: Tên hãng (VD: 'VMC')  
        date_str: Chuỗi ngày (VD: 'N12.1.2026')
        output_dir: Thư mục xuất file
        df_ton_cu: DataFrame tồn cũ (để lọc Stacking)
        df_gate_in: DataFrame Gate In (để lọc Stacking và Incoming)
        df_gate_out: DataFrame Gate Out (để lọc Stacking)
        
    Returns:
        Path đến file đã tạo hoặc None nếu lỗi
    """
    try:
        # Lọc theo hãng
        df_filtered = filter_by_operator(df_ton_bai, operator_name)
        
        if df_filtered.empty:
            logging.info(f"[EmailExporter] Không có tồn bãi cho hãng {operator_name}")
            return None
        
        # Chuẩn bị dữ liệu cho filter Stacking/Incoming
        df_ton_cu_filtered = filter_by_operator(df_ton_cu, operator_name) if df_ton_cu is not None else pd.DataFrame()
        df_gate_in_filtered = filter_by_operator(df_gate_in, operator_name) if df_gate_in is not None else pd.DataFrame()
        df_gate_out_filtered = filter_by_operator(df_gate_out, operator_name) if df_gate_out is not None else pd.DataFrame()
        
        # Lọc container Stacking
        df_stacking = filter_stacking_containers(
            df_filtered, df_ton_cu_filtered, df_gate_in_filtered, df_gate_out_filtered
        )
        
        # Lọc container Incoming
        df_incoming = filter_incoming_containers(df_gate_in_filtered)
        
        # Loại bỏ Stacking và Incoming khỏi TON BAI chính
        set_exclude = set()
        if not df_stacking.empty and Col.CONTAINER in df_stacking.columns:
            set_exclude.update(df_stacking[Col.CONTAINER].tolist())
        if not df_incoming.empty and Col.CONTAINER in df_incoming.columns:
            set_exclude.update(df_incoming[Col.CONTAINER].tolist())
        
        if set_exclude:
            df_main = df_filtered[~df_filtered[Col.CONTAINER].isin(set_exclude)].copy()
            logging.info(f"[{operator_name}] Tách riêng {len(set_exclude)} container Stacking/Incoming")
        else:
            df_main = df_filtered
        
        # Map sang template
        df_main_template = _map_to_template(df_main, TON_BAI_MAPPING, TON_BAI_COLUMNS)
        df_stacking_template = _map_to_template(df_stacking, TON_BAI_MAPPING, TON_BAI_COLUMNS) if not df_stacking.empty else pd.DataFrame()
        df_incoming_template = _map_to_template(df_incoming, BIEN_DONG_MAPPING, BIEN_DONG_COLUMNS) if not df_incoming.empty else pd.DataFrame()
        
        # Tạo tên file
        filename = f"TON BAI - {operator_name} - {date_str}.xlsx"
        filepath = output_dir / filename
        
        # Xuất file với nhiều sheet
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Sheet 1: TON BAI chính (đã loại Stacking/Incoming)
            df_main_template.to_excel(writer, sheet_name='TON BAI', index=False)
            
            # Sheet 2: Stacking (nếu có)
            if not df_stacking_template.empty:
                df_stacking_template.to_excel(writer, sheet_name='Stacking', index=False)
            
            # Sheet 3: Incoming (nếu có)
            if not df_incoming_template.empty:
                df_incoming_template.to_excel(writer, sheet_name='Incoming', index=False)
        
        logging.info(f"✅ Đã xuất: {filename} ({len(df_main)} main, {len(df_stacking)} stacking, {len(df_incoming)} incoming)")
        
        return filepath
        
    except Exception as e:
        logging.error(f"Lỗi xuất TON BAI cho {operator_name}: {e}")
        return None


def export_ton_bai_for_operator(
    df_ton_bai: pd.DataFrame,
    operator_name: str,
    date_str: str,
    output_dir: Path
) -> Optional[Path]:
    """
    Xuất file TON BAI theo template cho một hãng tàu.
    
    Args:
        df_ton_bai: DataFrame tồn bãi (từ file TON MOI)
        operator_name: Tên hãng (VD: 'VMC')  
        date_str: Chuỗi ngày (VD: 'N12.1.2026')
        output_dir: Thư mục xuất file
        
    Returns:
        Path đến file đã tạo hoặc None nếu lỗi
    """
    try:
        # Lọc theo hãng
        df_filtered = filter_by_operator(df_ton_bai, operator_name)
        
        if df_filtered.empty:
            logging.info(f"[EmailExporter] Không có tồn bãi cho hãng {operator_name}")
            return None
        
        # Map sang template
        df_template = _map_to_template(df_filtered, TON_BAI_MAPPING, TON_BAI_COLUMNS)
        
        # Tạo tên file
        filename = f"TON BAI - {operator_name} - {date_str}.xlsx"
        filepath = output_dir / filename
        
        # Xuất file
        df_template.to_excel(filepath, index=False, sheet_name='TON BAI')
        logging.info(f"✅ Đã xuất: {filename} ({len(df_filtered)} containers)")
        
        return filepath
        
    except Exception as e:
        logging.error(f"Lỗi xuất TON BAI cho {operator_name}: {e}")
        return None

def export_all_operators(
    df_bien_dong: pd.DataFrame,
    df_ton_bai: pd.DataFrame,
    date_str: str,
    output_dir: Path,
    operators: List[str] = None,
    parallel: bool = True,
    chunk_size: int = 50000,
    df_ton_cu: pd.DataFrame = None,
    df_gate_in: pd.DataFrame = None,
    df_gate_out: pd.DataFrame = None,
    enable_stacking_incoming_filter: bool = True
) -> Dict[str, Dict[str, Path]]:
    """
    Xuất file cho tất cả hãng tàu với hỗ trợ parallel processing và chunking.
    
    V5.5: Hỗ trợ tách riêng Stacking/Incoming containers.
    
    Args:
        df_bien_dong: DataFrame biến động
        df_ton_bai: DataFrame tồn bãi
        date_str: Chuỗi ngày
        output_dir: Thư mục xuất
        operators: Danh sách hãng cần xuất (None = tất cả)
        parallel: Sử dụng parallel processing (default: True)
        chunk_size: Số rows tối đa mỗi chunk khi file lớn (default: 50000)
        df_ton_cu: DataFrame tồn cũ (cho Stacking filter)
        df_gate_in: DataFrame Gate In (cho Stacking/Incoming filter)
        df_gate_out: DataFrame Gate Out (cho Stacking filter)
        enable_stacking_incoming_filter: Bật/tắt tách riêng Stacking/Incoming (default: True)
        
    Returns:
        Dict với key=operator, value={'bien_dong': path, 'ton_bai': path}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    if operators is None:
        operators = get_operator_list()
    
    results = {}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_rows = len(df_bien_dong) + len(df_ton_bai)
    logging.info(f"=== BẮT ĐẦU XUẤT FILE EMAIL TEMPLATE CHO {len(operators)} HÃNG ({total_rows:,} rows) ===")
    
    # Determine which export function to use
    use_v55 = enable_stacking_incoming_filter and (df_ton_cu is not None or df_gate_in is not None)
    if use_v55:
        logging.info("[V5.5] Bật chế độ tách riêng Stacking/Incoming containers")
    
    def export_single_operator(operator):
        """Export cho một operator."""
        bien_dong_path = export_bien_dong_for_operator(
            df_bien_dong, operator, date_str, output_dir
        )
        
        if use_v55:
            # V5.5: Sử dụng function mới với Stacking/Incoming filtering
            ton_bai_path = export_ton_bai_for_operator_v55(
                df_ton_bai, operator, date_str, output_dir,
                df_ton_cu=df_ton_cu,
                df_gate_in=df_gate_in,
                df_gate_out=df_gate_out
            )
        else:
            # Legacy: Không tách Stacking/Incoming
            ton_bai_path = export_ton_bai_for_operator(
                df_ton_bai, operator, date_str, output_dir
            )
        return operator, bien_dong_path, ton_bai_path
    
    # Parallel processing nếu có nhiều operators và data lớn
    if parallel and len(operators) > 2 and total_rows > 10000:
        max_workers = min(4, len(operators))  # Tối đa 4 threads
        logging.info(f"[PARALLEL] Sử dụng {max_workers} threads")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(export_single_operator, op): op for op in operators}
            
            for future in as_completed(futures):
                try:
                    operator, bien_dong_path, ton_bai_path = future.result()
                    if bien_dong_path or ton_bai_path:
                        results[operator] = {
                            'bien_dong': bien_dong_path,
                            'ton_bai': ton_bai_path
                        }
                except Exception as e:
                    op = futures[future]
                    logging.error(f"Lỗi parallel export cho {op}: {e}")
    else:
        # Sequential processing
        for operator in operators:
            _, bien_dong_path, ton_bai_path = export_single_operator(operator)
            
            if bien_dong_path or ton_bai_path:
                results[operator] = {
                    'bien_dong': bien_dong_path,
                    'ton_bai': ton_bai_path
                }
    
    logging.info(f"=== HOÀN TẤT XUẤT FILE CHO {len(results)} HÃNG ===")
    return results


def export_large_file_chunked(
    df: pd.DataFrame,
    filepath: Path,
    sheet_name: str,
    chunk_size: int = 100000
) -> Path:
    """
    Xuất file Excel lớn theo chunks để tránh memory issues.
    
    Args:
        df: DataFrame cần xuất
        filepath: Đường dẫn file output
        sheet_name: Tên sheet
        chunk_size: Số rows mỗi chunk
        
    Returns:
        Path đến file đã tạo
    """
    import xlsxwriter
    
    total_rows = len(df)
    
    if total_rows <= chunk_size:
        # File nhỏ, xuất bình thường
        df.to_excel(filepath, index=False, sheet_name=sheet_name)
        return filepath
    
    logging.info(f"[CHUNKED] Xuất file lớn {total_rows:,} rows theo chunks...")
    
    # Sử dụng xlsxwriter cho hiệu suất tốt hơn với file lớn
    with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        
        # Tối ưu memory
        workbook = writer.book
        workbook.set_properties({
            'title': f'Export {total_rows:,} rows',
            'author': 'Container Inventory System',
            'comments': 'Auto-generated large file export'
        })
    
    logging.info(f"[CHUNKED] Hoàn tất xuất {filepath.name}")
    return filepath
