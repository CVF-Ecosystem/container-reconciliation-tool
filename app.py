# File: app.py
import streamlit as st
import pandas as pd
from pathlib import Path
import config
from core_logic import load_results
from utils.translation import translator_instance

# --- HÀM HỖ TRỢ ---
def prepare_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """
    Chuẩn bị DataFrame để hiển thị an toàn trên Streamlit.
    Chuyển đổi tất cả các cột có kiểu dữ liệu hỗn hợp (object) sang chuỗi.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    df_display = df.copy()
    for col in df_display.columns:
        # Nếu cột là kiểu 'object', chuyển nó sang 'string' để tránh lỗi PyArrow
        if df_display[col].dtype == 'object':
            df_display[col] = df_display[col].astype(str).replace('nan', '').replace('NaT', '')
    return df_display

def add_stt_column(df: pd.DataFrame, t=None) -> pd.DataFrame:
    """Thêm cột STT (Số thứ tự) vào đầu DataFrame."""
    if df is None or df.empty:
        return df
    df_copy = df.copy()
    col_name = t('col_stt') if t else 'STT'
    df_copy.insert(0, col_name, range(1, len(df_copy) + 1))
    return df_copy

def format_operator_table(df: pd.DataFrame, t=None, operator_col: str = None) -> pd.DataFrame:
    """
    Format bảng theo Hãng khai thác: thêm STT, đặt lại tên cột Hãng khai thác.
    Handles dataframes where operator is in index or in a column.
    """
    if df is None or df.empty:
        return df
    
    # Get the index name before reset
    index_name = df.index.name
    
    df_copy = df.reset_index()
    
    # Determine the first column (which was the index) and rename it
    first_col = df_copy.columns[0]
    operator_label = t('col_operator') if t else 'Hãng khai thác'
    
    # Rename the first column to 'Hãng khai thác' if it looks like operator data
    if first_col in ['index', index_name] or first_col is None:
        df_copy = df_copy.rename(columns={first_col: operator_label})
    elif operator_col and operator_col in df_copy.columns:
        df_copy = df_copy.rename(columns={operator_col: operator_label})
    # If first column is already named properly (e.g., 'Hãng khai thác'), keep it
    
    # Add STT column at the beginning
    stt_label = t('col_stt') if t else 'STT'
    if stt_label not in df_copy.columns and 'STT' not in df_copy.columns:
        df_copy.insert(0, stt_label, range(1, len(df_copy) + 1))
    
    return df_copy

def calculate_teus(df: pd.DataFrame, size_col: str = None) -> int:
    """
    Tính tổng TEUs từ DataFrame dựa trên kích thước container.
    20ft = 1 TEU, 40ft/45ft = 2 TEUs
    """
    if df is None or df.empty:
        return 0
    
    # Find size column
    if size_col is None:
        from config import Col
        size_col = Col.ISO if hasattr(Col, 'ISO') else None
    
    if size_col is None or size_col not in df.columns:
        # Default: assume all are 20ft (1 TEU each)
        return len(df)
    
    total_teus = 0
    for size in df[size_col]:
        size_str = str(size).strip().upper() if pd.notna(size) else ''
        # Check first 2 characters for size
        if size_str.startswith('4') or size_str.startswith('45'):
            total_teus += 2  # 40ft or 45ft = 2 TEUs
        else:
            total_teus += 1  # 20ft or unknown = 1 TEU
    
    return total_teus

def add_teus_to_summary(df: pd.DataFrame, count_col: str, size_data: pd.DataFrame = None) -> pd.DataFrame:
    """Thêm cột TEUs vào bảng tổng hợp."""
    if df is None or df.empty:
        return df
    df_copy = df.copy()
    # Simple estimation: assume average 1.5 TEU per container
    if count_col in df_copy.columns:
        df_copy['TEUs'] = (df_copy[count_col] * 1.5).astype(int)
    return df_copy

def add_teus_columns_to_operator_table(operator_df: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Thêm cột TEUs vào bảng operator summary.
    Tính TEUs cho mỗi hãng dựa trên dữ liệu raw.
    """
    if operator_df is None or operator_df.empty:
        return operator_df
    
    from config import Col
    
    df_copy = operator_df.copy()
    
    # Get operator column name from index
    operator_col = Col.OPERATOR if hasattr(Col, 'OPERATOR') else None
    
    if raw_df is not None and not raw_df.empty and operator_col and operator_col in raw_df.columns:
        # Calculate TEUs for each operator
        teus_dict = {}
        for operator in df_copy.index:
            operator_data = raw_df[raw_df[operator_col] == operator]
            teus_dict[operator] = calculate_teus(operator_data)
        
        # Add TEUs columns based on existing columns
        if 'Tồn Mới' in df_copy.columns:
            df_copy['TEUs Mới'] = df_copy.index.map(lambda x: teus_dict.get(x, 0))
        if 'Tồn Cũ' in df_copy.columns:
            # Estimate TEUs for old stock (use same ratio)
            df_copy['TEUs Cũ'] = (df_copy['Tồn Cũ'] * 1.5).astype(int)
    else:
        # Fallback: estimate based on 1.5 TEU per container
        if 'Tồn Mới' in df_copy.columns:
            df_copy['TEUs Mới'] = (df_copy['Tồn Mới'] * 1.5).astype(int)
        if 'Tồn Cũ' in df_copy.columns:
            df_copy['TEUs Cũ'] = (df_copy['Tồn Cũ'] * 1.5).astype(int)
    
    # Reorder columns to put TEUs next to corresponding Conts
    new_cols = []
    for col in df_copy.columns:
        new_cols.append(col)
        if col == 'Tồn Cũ' and 'TEUs Cũ' in df_copy.columns:
            if 'TEUs Cũ' not in new_cols:
                new_cols.append('TEUs Cũ')
        if col == 'Tồn Mới' and 'TEUs Mới' in df_copy.columns:
            if 'TEUs Mới' not in new_cols:
                new_cols.append('TEUs Mới')
    
    # Remove duplicates while preserving order
    seen = set()
    new_cols = [x for x in new_cols if not (x in seen or seen.add(x))]
    
    return df_copy[new_cols]

# --- CẤU HÌNH TRANG & NGÔN NGỮ ---
st.set_page_config(page_title="Báo cáo tồn bãi", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for table styling
st.markdown("""
<style>
    /* Header: center-aligned */
    .stDataFrame thead th {
        text-align: center !important;
        font-weight: bold !important;
    }
    /* Content: left-aligned */
    .stDataFrame tbody td {
        text-align: left !important;
    }
    /* Numeric columns: right-aligned */
    .stDataFrame tbody td:nth-child(n+3) {
        text-align: right !important;
    }
    /* Reduce column padding for compact look */
    .stDataFrame td, .stDataFrame th {
        padding: 4px 8px !important;
        white-space: nowrap !important;
    }
    /* Auto-fit column width */
    .stDataFrame table {
        width: auto !important;
        table-layout: auto !important;
    }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("Language / Ngôn ngữ")
selected_language_code = st.sidebar.selectbox(
    "Choose a language / Chọn ngôn ngữ",
    options=["vi", "en"],
    format_func=lambda x: "Tiếng Việt" if x == "vi" else "English"
)
translator_instance.set_language(selected_language_code or "vi")
t = translator_instance.get_translator()

# --- TIÊU ĐỀ VÀ NÚT TẢI LẠI ---
st.title(t("app_title"))
# Info message removed - redundant with timestamp shown below
if st.button(t("reload_button")):
    st.rerun()

# --- TẢI VÀ HIỂN THỊ DỮ LIỆU ---
results = load_results(config.OUTPUT_DIR)

if results is None:
    st.error(t("no_data_error"))
else:
    run_timestamp = results.get("run_timestamp")
    summary_df = results.get("summary_df")
    main_results = results.get("main_results", {})
    operator_summary = results.get("operator_analysis_result", {}).get("summary")
    
    # Note: Variables for removed tabs (thieu, thua, sai_thong_tin) are no longer needed

    # Show timestamp and data availability info
    from datetime import datetime
    current_time = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    st.success(f"{t('showing_results')} {current_time}")
    
    # Show available dates in database - concise format
    try:
        from utils.history_db import HistoryDatabase
        history_db = HistoryDatabase(config.OUTPUT_DIR)
        available_dates = history_db.get_available_dates(limit=100)  # Get all
        if available_dates:
            dates_count = len(available_dates)
            # Format: "X ngày (ngày đầu → ngày cuối)"
            first_date = available_dates[-1]  # Oldest (dates are DESC order)
            last_date = available_dates[0]    # Newest
            if dates_count == 1:
                date_range = first_date
            else:
                date_range = f"{first_date} → {last_date}"
            st.info(f"📊 **{t('data_available')}** {dates_count} {t('days')} ({date_range})")
    except Exception:
        pass  # Silently fail if no history db

    tab_overview, tab_operator, tab_analytics, tab_fe, tab_export = st.tabs([
        t("tab_overview"), 
        t("tab_operator"),
        "📈 Analytics",
        t("tab_fe"),
        t("tab_export")
    ])

    with tab_overview:
        st.header(t("header_overview"))
        
        if isinstance(summary_df, pd.DataFrame):
            try:
                def get_kpi(item_name):
                    value = summary_df.loc[summary_df['Hang muc'] == item_name, 'So luong']
                    return int(value.iloc[0]) if not value.empty else 0
                
                # ===== SECTION 1: TỒN CŨ VS TỒN MỚI =====
                st.subheader(t("header_inventory"))
                ton_cu = get_kpi('Ton cu (baseline)')
                ton_moi = get_kpi('Ton moi (thoi diem kiem tra)')
                chenh_lech = ton_moi - ton_cu
                
                # Calculate TEUs from raw data
                df_ton_moi_raw = main_results.get("raw_data", {}).get("ton_moi")
                df_ton_cu_raw = main_results.get("raw_data", {}).get("ton_cu")
                teus_moi = calculate_teus(df_ton_moi_raw) if df_ton_moi_raw is not None else int(ton_moi * 1.5)
                teus_cu = calculate_teus(df_ton_cu_raw) if df_ton_cu_raw is not None else int(ton_cu * 1.5)
                teus_chenh = teus_moi - teus_cu
                
                # Create summary table
                summary_table = pd.DataFrame({
                    t('col_category'): [t('inventory_old'), t('inventory_new'), t('inventory_diff')],
                    t('col_conts'): [f'{ton_cu:,}', f'{ton_moi:,}', f'{chenh_lech:+,}'],
                    t('col_teus'): [f'{teus_cu:,}', f'{teus_moi:,}', f'{teus_chenh:+,}']
                })
                st.dataframe(summary_table, use_container_width=False, hide_index=True)
                
                st.divider()
                
                # ===== SECTION 2: BIẾN ĐỘNG TRONG NGÀY =====
                st.subheader(t("header_daily_activity"))
                nhap = get_kpi('Tong giao dich NHAP')
                xuat = get_kpi('Tong giao dich XUAT')
                moi_vao = get_kpi('Container moi vao bai')
                da_roi = get_kpi('Container da roi bai')
                dao_chuyen = get_kpi('Dao chuyen vi tri')
                
                # Estimate TEUs (average 1.5 TEU per container)
                nhap_teus = int(nhap * 1.5)
                xuat_teus = int(xuat * 1.5)
                moi_vao_teus = int(moi_vao * 1.5)
                da_roi_teus = int(da_roi * 1.5)
                dao_chuyen_teus = int(dao_chuyen * 1.5)
                
                # Create activity table with TEUs
                activity_table = pd.DataFrame({
                    t('col_activity'): [t('activity_import'), t('activity_export'), t('activity_new_in'), t('activity_left'), t('activity_relocation')],
                    t('col_conts'): [f'{nhap:,}', f'{xuat:,}', f'{moi_vao:,}', f'{da_roi:,}', f'{dao_chuyen:,}'],
                    t('col_teus'): [f'{nhap_teus:,}', f'{xuat_teus:,}', f'{moi_vao_teus:,}', f'{da_roi_teus:,}', f'{dao_chuyen_teus:,}']
                })
                st.dataframe(activity_table, use_container_width=False, hide_index=True)
                
            except Exception as e:
                st.warning(f"{t('cannot_extract_metrics')} {e}")
        
        # Sections 3 and 4 moved to separate tabs
        
        # ===== SECTION 5: PHÂN TÍCH THỜI GIAN TỒN BÃI =====
        st.subheader(t("header_dwell_time"))
        try:
            from config import Col
            from datetime import datetime as dt
            
            df_ton_moi = main_results.get("raw_data", {}).get("ton_moi")
            if df_ton_moi is not None and not df_ton_moi.empty:
                # Tìm cột ngày nhập bãi
                ngay_nhap_col = None
                for col in df_ton_moi.columns:
                    if 'ngay' in col.lower() and ('nhap' in col.lower() or 'vao' in col.lower()):
                        ngay_nhap_col = col
                        break
                
                if ngay_nhap_col is None and Col.NGAY_NHAP_BAI in df_ton_moi.columns:
                    ngay_nhap_col = Col.NGAY_NHAP_BAI
                
                if ngay_nhap_col:
                    df_dwell = df_ton_moi.copy()
                    df_dwell[ngay_nhap_col] = pd.to_datetime(df_dwell[ngay_nhap_col], errors='coerce')
                    today = dt.now()
                    df_dwell['Ngày tồn'] = (today - df_dwell[ngay_nhap_col]).dt.days
                    
                    # Phân loại theo khoảng thời gian
                    def categorize_dwell(days):
                        if pd.isna(days) or days < 0:
                            return t('dwell_unknown')
                        elif days <= 30:
                            return t('dwell_under_31')
                        elif days <= 60:
                            return t('dwell_31_60')
                        elif days <= 90:
                            return t('dwell_61_90')
                        else:
                            return t('dwell_over_90')
                    
                    df_dwell['Nhóm tồn'] = df_dwell['Ngày tồn'].apply(categorize_dwell)
                    dwell_summary = df_dwell['Nhóm tồn'].value_counts()
                    
                    # Calculate TEUs for each dwell category
                    dwell_data = []
                    for category in [t('dwell_under_31'), t('dwell_31_60'), t('dwell_61_90'), t('dwell_over_90')]:
                        cat_df = df_dwell[df_dwell['Nhóm tồn'] == category]
                        conts = len(cat_df)
                        teus = calculate_teus(cat_df)
                        dwell_data.append({t('col_dwell_time'): category, t('col_conts'): f'{conts:,}', t('col_teus'): f'{teus:,}'})
                    
                    dwell_table = pd.DataFrame(dwell_data)
                    st.dataframe(dwell_table, use_container_width=False, hide_index=True)
                    
                    # Chi tiết theo hãng và thời gian tồn
                    if Col.OPERATOR in df_dwell.columns:
                        st.write(f"**{t('col_operator')}:**")
                        dwell_by_operator = df_dwell.groupby([Col.OPERATOR, 'Nhóm tồn'], observed=False).size().unstack(fill_value=0)
                        dwell_categories = [t('dwell_under_31'), t('dwell_31_60'), t('dwell_61_90'), t('dwell_over_90')]
                        dwell_by_operator = dwell_by_operator.reindex(columns=dwell_categories, fill_value=0)
                        
                        # Calculate TEUs for each operator and dwell category
                        for category in dwell_categories:
                            teus_col = f'{category} TEUs'
                            teus_dict = {}
                            for operator in dwell_by_operator.index:
                                cat_df = df_dwell[(df_dwell[Col.OPERATOR] == operator) & (df_dwell['Nhóm tồn'] == category)]
                                teus_dict[operator] = calculate_teus(cat_df)
                            dwell_by_operator[teus_col] = dwell_by_operator.index.map(lambda x: teus_dict.get(x, 0))
                        
                        # Reorder columns: Conts then TEUs for each category
                        ordered_cols = []
                        for cat in dwell_categories:
                            ordered_cols.append(cat)
                            ordered_cols.append(f'{cat} TEUs')
                        dwell_by_operator = dwell_by_operator[ordered_cols]
                        
                        st.dataframe(format_operator_table(dwell_by_operator, t), use_container_width=False, hide_index=True)
                else:
                    st.info(t("no_date_column"))
            else:
                st.info(t("no_new_inventory"))
        except Exception as e:
            st.info(f"{t('cannot_analyze_dwell')} {e}")
        
        st.divider()
        
        # ===== SECTION 6: PHÂN TÍCH THEO VỊ TRÍ BÃI =====
        st.subheader(t("header_location"))
        try:
            from config import Col
            
            df_ton_moi = main_results.get("raw_data", {}).get("ton_moi")
            if df_ton_moi is not None and not df_ton_moi.empty and Col.LOCATION in df_ton_moi.columns:
                df_loc = df_ton_moi.copy()
                
                # Tách vị trí thành khu vực (lấy chữ cái đầu hoặc phần đầu)
                def extract_area(loc):
                    if pd.isna(loc) or not str(loc).strip():
                        return t('dwell_unknown')
                    loc_str = str(loc).strip().upper()
                    # Lấy ký tự đầu tiên hoặc phần trước dấu -
                    if '-' in loc_str:
                        return loc_str.split('-')[0]
                    elif len(loc_str) > 0:
                        return loc_str[0]
                    return 'Khác'
                
                df_loc['Khu vực'] = df_loc[Col.LOCATION].apply(extract_area)
                
                # Calculate Conts and TEUs for each area
                loc_data = []
                for area in df_loc['Khu vực'].unique():
                    area_df = df_loc[df_loc['Khu vực'] == area]
                    conts = len(area_df)
                    teus = calculate_teus(area_df)
                    loc_data.append({t('col_area'): area, t('col_conts'): conts, t('col_teus'): teus})
                
                loc_df = pd.DataFrame(loc_data).sort_values(t('col_conts'), ascending=False).head(15)
                loc_df.insert(0, t('col_stt'), range(1, len(loc_df) + 1))
                
                # Hiển thị biểu đồ
                chart_data = loc_df.set_index(t('col_area'))[t('col_conts')]
                st.bar_chart(chart_data)
                
                # Format numbers for display
                loc_df[t('col_conts')] = loc_df[t('col_conts')].apply(lambda x: f'{x:,}')
                loc_df[t('col_teus')] = loc_df[t('col_teus')].apply(lambda x: f'{x:,}')
                
                # Bảng chi tiết
                st.dataframe(loc_df, use_container_width=False, hide_index=True)
            else:
                st.info(t("no_location_data"))
        except Exception as e:
            st.info(f"{t('cannot_analyze_location')} {e}")
        
        # ===== SECTION 7: BẢNG TÓM TẮT CHI TIẾT =====
        st.divider()
        st.subheader(t("header_summary_table"))
        if isinstance(summary_df, pd.DataFrame):
            summary_display_df = summary_df.copy()
            summary_display_df['So luong'] = summary_display_df['So luong'].astype(str).replace('.0', '', regex=False)
            st.dataframe(add_stt_column(summary_display_df, t), use_container_width=False, hide_index=True)

    # ===== TAB 2: TỔNG QUAN THEO HÃNG TÀU =====
    with tab_operator:
        st.header(t("header_operator_overview"))
        
        if isinstance(operator_summary, pd.DataFrame) and not operator_summary.empty:
            # Metrics tổng quan
            total_operators = len(operator_summary)
            total_ton_moi = operator_summary['Tồn Mới'].sum() if 'Tồn Mới' in operator_summary.columns else 0
            total_ton_cu = operator_summary['Tồn Cũ'].sum() if 'Tồn Cũ' in operator_summary.columns else 0
            
            # Calculate TEUs
            df_ton_moi_raw = main_results.get("raw_data", {}).get("ton_moi")
            df_ton_cu_raw = main_results.get("raw_data", {}).get("ton_cu")
            teus_moi = calculate_teus(df_ton_moi_raw) if df_ton_moi_raw is not None else int(total_ton_moi * 1.5)
            teus_cu = calculate_teus(df_ton_cu_raw) if df_ton_cu_raw is not None else int(total_ton_cu * 1.5)
            
            # Create operator summary table
            operator_overview = pd.DataFrame({
                t('col_metric'): [t('operator_count'), t('old_inventory'), t('new_inventory'), t('inventory_diff')],
                t('col_conts'): [f'{total_operators}', f'{int(total_ton_cu):,}', f'{int(total_ton_moi):,}', f'{int(total_ton_moi - total_ton_cu):+,}'],
                t('col_teus'): ['-', f'{teus_cu:,}', f'{teus_moi:,}', f'{teus_moi - teus_cu:+,}']
            })
            st.dataframe(operator_overview, use_container_width=False, hide_index=True)
            
            st.divider()
            
            # Bar chart tồn cũ vs tồn mới
            st.subheader(t("chart_old_vs_new"))
            st.bar_chart(operator_summary[['Tồn Cũ', 'Tồn Mới']])
            
            st.divider()
            
            # Top 10 hãng có tồn nhiều nhất
            st.subheader(t("top_10_operators"))
            top_operators = operator_summary.nlargest(10, 'Tồn Mới')
            # Add TEUs columns
            top_operators_with_teus = add_teus_columns_to_operator_table(top_operators, df_ton_moi_raw)
            top_operators_display = format_operator_table(top_operators_with_teus, t)
            st.dataframe(top_operators_display, use_container_width=False, hide_index=True)
            
            st.divider()
            
            # Bảng đầy đủ
            st.subheader(t("full_operator_list"))
            full_with_teus = add_teus_columns_to_operator_table(operator_summary, df_ton_moi_raw)
            full_operator_display = format_operator_table(full_with_teus, t)
            st.dataframe(full_operator_display, use_container_width=False, hide_index=True)
        else:
            st.info(t("no_operator_data"))
    
    # ===== TAB 3: ANALYTICS (BIỂU ĐỒ NÂNG CAO) =====
    with tab_analytics:
        st.header("📈 Phân tích")
        
        try:
            import plotly.express as px
            import plotly.graph_objects as go
            from utils.history_db import HistoryDatabase
            
            db = HistoryDatabase(config.OUTPUT_DIR)
            
            # --- SECTION 1: XU HƯỚNG TỒN BÃI ---
            st.subheader("📊Tồn bãi (30 ngày)")
            
            df_trend = db.get_inventory_trend(30)
            if not df_trend.empty:
                df_trend.columns = ['Ngày', 'Số lượng Container']
                # Convert to date only (remove time component)
                df_trend['Ngày'] = pd.to_datetime(df_trend['Ngày']).dt.date
                fig_trend = px.line(
                    df_trend, x='Ngày', y='Số lượng Container',
                    markers=True,
                    title='Biến động tồn bãi theo thời gian'
                )
                fig_trend.update_layout(
                    hovermode='x unified',
                    xaxis=dict(
                        tickformat='%d/%m/%Y',
                        dtick='D1',  # Show every day
                        tickangle=45
                    )
                )
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("Chưa có đủ dữ liệu lịch sử. Hãy chạy đối soát thêm vài ngày.")
            
            st.divider()
            
            # --- SECTION 2: PIE CHART THEO HÃNG KHAI THÁC ---
            st.subheader("🏢Hãng khai thác")
            
            if isinstance(operator_summary, pd.DataFrame) and not operator_summary.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Pie chart
                    pie_data = operator_summary.nlargest(10, 'Tồn Mới').copy()
                    pie_data = pie_data.reset_index()
                    fig_pie = px.pie(
                        pie_data, 
                        values='Tồn Mới', 
                        names='Hãng khai thác' if 'Hãng khai thác' in pie_data.columns else pie_data.columns[0],
                        title='Top 10',
                        hole=0.4
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                with col2:
                    # Horizontal bar chart
                    bar_data = operator_summary.nlargest(10, 'Tồn Mới').copy()
                    bar_data = bar_data.reset_index()
                    fig_bar = px.bar(
                        bar_data,
                        y='Hãng khai thác' if 'Hãng khai thác' in bar_data.columns else bar_data.columns[0],
                        x='Tồn Mới',
                        orientation='h',
                        title='Top 10 Hãng - Số Container'
                    )
                    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Không có dữ liệu hãng khai thác.")
            
            st.divider()
            
            # --- SECTION 3: THỜI GIAN LƯU BÃI ---
            st.subheader("⏱️Lưu bãi")
            
            df_ton_moi = main_results.get("raw_data", {}).get("ton_moi")
            if df_ton_moi is not None and not df_ton_moi.empty:
                from config import Col
                from datetime import datetime
                
                if Col.NGAY_NHAP_BAI in df_ton_moi.columns:
                    df_dwell = df_ton_moi.copy()
                    
                    # Calculate dwell days
                    today = datetime.now()
                    df_dwell['Dwell_Days'] = df_dwell[Col.NGAY_NHAP_BAI].apply(
                        lambda x: (today - pd.to_datetime(x)).days if pd.notna(x) else None
                    )
                    df_dwell = df_dwell.dropna(subset=['Dwell_Days'])
                    
                    if not df_dwell.empty:
                        # Dwell time distribution
                        df_dwell['Nhóm'] = pd.cut(
                            df_dwell['Dwell_Days'],
                            bins=[-1, 7, 14, 30, 60, 90, float('inf')],
                            labels=['0-7 ngày', '8-14 ngày', '15-30 ngày', '31-60 ngày', '61-90 ngày', '>90 ngày']
                        )
                        
                        dwell_counts = df_dwell['Nhóm'].value_counts().sort_index()
                        
                        fig_dwell = px.bar(
                            x=dwell_counts.index.astype(str),
                            y=dwell_counts.values,
                            title='Thời gian',
                            labels={'x': 'Khoảng thời gian', 'y': 'Số container'},
                            color=dwell_counts.values,
                            color_continuous_scale='RdYlGn_r'
                        )
                        st.plotly_chart(fig_dwell, use_container_width=True)
                        
                        # Stats
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Trung bình", f"{df_dwell['Dwell_Days'].mean():.1f} ngày")
                        with col2:
                            st.metric("Lâu nhất", f"{df_dwell['Dwell_Days'].max():.0f} ngày")
                        with col3:
                            long_term = len(df_dwell[df_dwell['Dwell_Days'] > 30])
                            st.metric("Lưu >30 ngày", f"{long_term:,} cont")
                    else:
                        st.info("Không có dữ liệu ngày nhập bãi hợp lệ.")
                else:
                    st.info("Cột ngày nhập bãi không có trong dữ liệu.")
            else:
                st.info("Không có dữ liệu tồn mới.")
            
        except ImportError:
            st.warning("Cần cài đặt Plotly để hiển thị biểu đồ nâng cao: `pip install plotly`")
        except Exception as e:
            st.error(f"Lỗi khi tải Analytics: {e}")
    
    # ===== TAB 4: TỔNG QUAN THEO TRẠNG THÁI (FULL/EMPTY) =====
    with tab_fe:
        st.header(t("header_fe_status"))
        
        try:
            from config import Col
            import plotly.express as px
            
            df_ton_moi = main_results.get("raw_data", {}).get("ton_moi")
            if df_ton_moi is not None and not df_ton_moi.empty and Col.FE in df_ton_moi.columns:
                fe_counts = df_ton_moi[Col.FE].value_counts()
                full_count = fe_counts.get('F', 0)
                empty_count = fe_counts.get('E', 0)
                total_fe = full_count + empty_count
                
                # Calculate TEUs for Full and Empty
                df_full = df_ton_moi[df_ton_moi[Col.FE] == 'F']
                df_empty = df_ton_moi[df_ton_moi[Col.FE] == 'E']
                teus_full = calculate_teus(df_full)
                teus_empty = calculate_teus(df_empty)
                total_teus = teus_full + teus_empty
                
                # Create F/E summary table
                fe_table = pd.DataFrame({
                    t('col_status'): [t('status_full'), t('status_empty'), t('status_total')],
                    t('col_conts'): [f'{full_count:,}', f'{empty_count:,}', f'{total_fe:,}'],
                    t('col_teus'): [f'{teus_full:,}', f'{teus_empty:,}', f'{total_teus:,}'],
                    t('col_ratio'): [f'{full_count/total_fe*100:.1f}%' if total_fe > 0 else '0%',
                             f'{empty_count/total_fe*100:.1f}%' if total_fe > 0 else '0%',
                             '100%']
                })
                st.dataframe(fe_table, use_container_width=False, hide_index=True)
                
                st.divider()
                
                # Pie chart
                if total_fe > 0:
                    st.subheader(t("fe_ratio_chart"))
                    fig = px.pie(
                        values=[full_count, empty_count],
                        names=['Full (F)', 'Empty (E)'],
                        title=t("fe_ratio_chart"),
                        color_discrete_sequence=['#2ecc71', '#95a5a6']
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                st.divider()
                
                # Phân tích theo Hãng + F/E
                st.subheader(t("fe_by_operator"))
                if Col.OPERATOR in df_ton_moi.columns:
                    fe_by_operator = df_ton_moi.groupby([Col.OPERATOR, Col.FE], observed=False).size().unstack(fill_value=0)
                    fe_by_operator = fe_by_operator.reindex(columns=['F', 'E'], fill_value=0)
                    fe_by_operator.columns = ['Full', 'Empty']
                    fe_by_operator['Tổng'] = fe_by_operator['Full'] + fe_by_operator['Empty']
                    
                    # Calculate TEUs for each operator by F/E
                    teus_full_dict = {}
                    teus_empty_dict = {}
                    for operator in fe_by_operator.index:
                        op_data = df_ton_moi[df_ton_moi[Col.OPERATOR] == operator]
                        teus_full_dict[operator] = calculate_teus(op_data[op_data[Col.FE] == 'F'])
                        teus_empty_dict[operator] = calculate_teus(op_data[op_data[Col.FE] == 'E'])
                    
                    fe_by_operator['Full TEUs'] = fe_by_operator.index.map(lambda x: teus_full_dict.get(x, 0))
                    fe_by_operator['Empty TEUs'] = fe_by_operator.index.map(lambda x: teus_empty_dict.get(x, 0))
                    fe_by_operator['Tổng TEUs'] = fe_by_operator['Full TEUs'] + fe_by_operator['Empty TEUs']
                    
                    # Reorder columns
                    fe_by_operator = fe_by_operator[['Full', 'Full TEUs', 'Empty', 'Empty TEUs', 'Tổng', 'Tổng TEUs']]
                    fe_by_operator = fe_by_operator.sort_values('Tổng', ascending=False)
                    st.dataframe(format_operator_table(fe_by_operator, t), use_container_width=False, hide_index=True)
                else:
                    st.info(t("no_operator_info"))
            else:
                st.info(t("no_fe_data"))
        except Exception as e:
            st.info(f"{t('cannot_analyze_fe')} {e}")
    
    # V4.7.2: Tab trích xuất dữ liệu lịch sử
    with tab_export:
        st.header(t("header_export"))
        
        try:
            from utils.history_db import HistoryDatabase
            from datetime import datetime, timedelta
            from config import Col
            
            db = HistoryDatabase(config.OUTPUT_DIR)
            available_dates = db.get_available_dates(limit=30)
            
            if not available_dates:
                st.warning(t("no_history_data"))
            else:
                # Data availability already shown in header - no need to repeat here
                
                # Convert available dates to datetime objects for date_input
                from datetime import datetime as dt
                available_date_objs = [dt.strptime(d, '%Y-%m-%d').date() for d in available_dates]
                min_date = min(available_date_objs)
                max_date = max(available_date_objs)
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.subheader(t("date_lookup"))
                    selected_date = st.date_input(
                        t("select_date"),
                        value=max_date,
                        min_value=min_date,
                        max_value=max_date,
                        key="date_lookup"
                    )
                    
                    if st.button(t("lookup_button"), type="primary"):
                        target_date = dt.combine(selected_date, dt.min.time())
                        df_snapshot = db.get_snapshot_for_date(target_date)
                        if not df_snapshot.empty:
                            df_snapshot.insert(0, t('col_stt'), range(1, len(df_snapshot) + 1))
                            st.dataframe(df_snapshot, use_container_width=False, hide_index=True)
                            st.info(t("total_containers").replace("{count}", str(len(df_snapshot))))
                        else:
                            st.warning(t("no_data_for_date"))
                
                with col2:
                    st.subheader(t("container_lookup"))
                    container_id = st.text_input(t("enter_container"))
                    
                    if st.button(t("lookup_history"), type="secondary"):
                        if container_id:
                            df_history = db.get_container_history(container_id.strip().upper(), days=365)
                            df_timeline = db.get_container_timeline(container_id.strip().upper())
                            
                            if not df_history.empty or not df_timeline.empty:
                                st.write(f"**{t('inventory_history')}**")
                                if not df_history.empty:
                                    st.dataframe(df_history, hide_index=True)
                                else:
                                    st.info(t("no_inventory_history"))
                                
                                st.write(f"**{t('transaction_history')}**")
                                if not df_timeline.empty:
                                    st.dataframe(df_timeline, hide_index=True)
                                else:
                                    st.info(t("no_transaction_history"))
                            else:
                                st.warning(t("container_not_found").replace("{id}", container_id))
                        else:
                            st.warning(t("enter_container_warning"))
                
                with col3:
                    st.subheader(t("operator_lookup"))
                    
                    # Get list of operators from current data
                    df_ton_moi = main_results.get("raw_data", {}).get("ton_moi")
                    if df_ton_moi is not None and not df_ton_moi.empty and Col.OPERATOR in df_ton_moi.columns:
                        operators = sorted(df_ton_moi[Col.OPERATOR].dropna().unique().tolist())
                        selected_operator = st.selectbox(
                            t("select_operator"),
                            options=operators,
                            key="operator_lookup"
                        )
                        
                        if st.button(t("lookup_by_operator"), type="secondary"):
                            if selected_operator:
                                df_operator = df_ton_moi[df_ton_moi[Col.OPERATOR] == selected_operator].copy()
                                if not df_operator.empty:
                                    # Select relevant columns
                                    display_cols = [Col.CONTAINER]
                                    for c in [Col.ISO, Col.FE, Col.LOCATION, Col.NGAY_NHAP_BAI]:
                                        if c in df_operator.columns:
                                            display_cols.append(c)
                                    df_display = df_operator[display_cols].copy()
                                    df_display.insert(0, t('col_stt'), range(1, len(df_display) + 1))
                                    st.dataframe(df_display, use_container_width=False, hide_index=True)
                                    st.info(t("operator_container_total").replace("{count}", str(len(df_display))).replace("{operator}", selected_operator))
                                else:
                                    st.warning(t("no_operator_containers").replace("{operator}", selected_operator))
                    else:
                        st.info(t("no_operator_data_export"))
                
                st.divider()
                
                st.subheader(t("compare_dates"))
                if len(available_dates) >= 2:
                    col3, col4 = st.columns(2)
                    with col3:
                        date1 = st.date_input(
                            t("date1_old"),
                            value=available_date_objs[1] if len(available_date_objs) > 1 else available_date_objs[0],
                            min_value=min_date,
                            max_value=max_date,
                            key="compare_date1"
                        )
                    with col4:
                        date2 = st.date_input(
                            t("date2_new"),
                            value=max_date,
                            min_value=min_date,
                            max_value=max_date,
                            key="compare_date2"
                        )
                    
                    if st.button(t("compare_button"), type="primary"):
                        d1 = dt.combine(date1, dt.min.time())
                        d2 = dt.combine(date2, dt.min.time())
                        result = db.compare_two_dates(d1, d2)
                        summary = result.get('summary', {})
                        
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric(t("inventory_day1"), summary.get('ton_1', 0))
                        c2.metric(t("inventory_day2"), summary.get('ton_2', 0))
                        c3.metric(t("new_entries"), summary.get('moi_vao', 0))
                        c4.metric(t("left_entries"), summary.get('da_roi', 0))
                else:
                    st.info(t("need_2_days"))
                    
        except Exception as e:
            st.error(f"{t('history_load_error')} {e}")