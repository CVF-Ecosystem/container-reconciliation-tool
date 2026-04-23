# File: pages/2_Operator.py — @2026 v1.0
"""
Page 2: Tổng quan theo Hãng tàu (Operator)
- Metrics tổng quan
- Bar chart Tồn cũ vs Tồn mới
- Top 10 hãng có tồn nhiều nhất
- Bảng đầy đủ tất cả hãng
"""

import streamlit as st
import pandas as pd

from utils.streamlit_shared import setup_page, get_results, show_data_info
import config
from config import DEFAULT_TEU_FACTOR
from utils.display_helpers import (
    format_operator_table, calculate_teus, add_teus_columns_to_operator_table
)

# ============ PAGE SETUP ============
t = setup_page("Hãng tàu — Báo cáo tồn bãi")
st.title(t("app_title"))

results = get_results()

if results is None:
    st.error(t("no_data_error"))
    st.stop()

show_data_info(results, t)

main_results = results.get("main_results", {})
operator_summary = results.get("operator_analysis_result", {}).get("summary")

# ============ OPERATOR OVERVIEW ============
st.header(t("header_operator_overview"))

if isinstance(operator_summary, pd.DataFrame) and not operator_summary.empty:
    total_operators = len(operator_summary)
    total_ton_moi = operator_summary['Tồn Mới'].sum() if 'Tồn Mới' in operator_summary.columns else 0
    total_ton_cu = operator_summary['Tồn Cũ'].sum() if 'Tồn Cũ' in operator_summary.columns else 0
    
    df_ton_moi_raw = main_results.get("raw_data", {}).get("ton_moi")
    df_ton_cu_raw = main_results.get("raw_data", {}).get("ton_cu")
    teus_moi = calculate_teus(df_ton_moi_raw) if df_ton_moi_raw is not None else int(total_ton_moi * DEFAULT_TEU_FACTOR)
    teus_cu = calculate_teus(df_ton_cu_raw) if df_ton_cu_raw is not None else int(total_ton_cu * DEFAULT_TEU_FACTOR)
    
    operator_overview = pd.DataFrame({
        t('col_metric'): [t('operator_count'), t('old_inventory'), t('new_inventory'), t('inventory_diff')],
        t('col_conts'): [f'{total_operators}', f'{int(total_ton_cu):,}', f'{int(total_ton_moi):,}', f'{int(total_ton_moi - total_ton_cu):+,}'],
        t('col_teus'): ['-', f'{teus_cu:,}', f'{teus_moi:,}', f'{teus_moi - teus_cu:+,}']
    })
    st.dataframe(operator_overview, use_container_width=False, hide_index=True)
    
    st.divider()
    
    # Bar chart
    st.subheader(t("chart_old_vs_new"))
    st.bar_chart(operator_summary[['Tồn Cũ', 'Tồn Mới']])
    
    st.divider()
    
    # Top 10
    st.subheader(t("top_10_operators"))
    top_operators = operator_summary.nlargest(10, 'Tồn Mới')
    top_operators_with_teus = add_teus_columns_to_operator_table(top_operators, df_ton_moi_raw)
    top_operators_display = format_operator_table(top_operators_with_teus, t)
    st.dataframe(top_operators_display, use_container_width=False, hide_index=True)
    
    st.divider()
    
    # Full list
    st.subheader(t("full_operator_list"))
    full_with_teus = add_teus_columns_to_operator_table(operator_summary, df_ton_moi_raw)
    full_operator_display = format_operator_table(full_with_teus, t)
    st.dataframe(full_operator_display, use_container_width=False, hide_index=True)
else:
    st.info(t("no_operator_data"))
