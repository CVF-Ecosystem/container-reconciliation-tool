# File: pages/1_Overview.py — @2026 v1.0
"""
Page 1: Tổng quan tồn bãi (Overview)
- KPI metrics: Tồn cũ vs Tồn mới, TEUs
- Biến động trong ngày
- Phân tích thời gian tồn bãi (Dwell time)
- Phân tích theo vị trí bãi
- Bảng tóm tắt chi tiết
"""

import streamlit as st
import pandas as pd
from datetime import datetime as dt

from pages._shared import setup_page, get_results, show_data_info
import config
from config import Col, DEFAULT_TEU_FACTOR
from utils.display_helpers import (
    add_stt_column, format_operator_table, calculate_teus
)

# ============ PAGE SETUP ============
t = setup_page("Tổng quan — Báo cáo tồn bãi")
st.title(t("app_title"))

results = get_results()

if results is None:
    st.error(t("no_data_error"))
    st.stop()

show_data_info(results, t)

summary_df = results.get("summary_df")
main_results = results.get("main_results", {})

# ============ SECTION 1: TỒN CŨ VS TỒN MỚI ============
st.header(t("header_overview"))

if isinstance(summary_df, pd.DataFrame):
    try:
        def get_kpi(item_name):
            value = summary_df.loc[summary_df['Hang muc'] == item_name, 'So luong']
            return int(value.iloc[0]) if not value.empty else 0
        
        st.subheader(t("header_inventory"))
        ton_cu = get_kpi('Ton cu (baseline)')
        ton_moi = get_kpi('Ton moi (thoi diem kiem tra)')
        chenh_lech = ton_moi - ton_cu
        
        df_ton_moi_raw = main_results.get("raw_data", {}).get("ton_moi")
        df_ton_cu_raw = main_results.get("raw_data", {}).get("ton_cu")
        teus_moi = calculate_teus(df_ton_moi_raw) if df_ton_moi_raw is not None else int(ton_moi * DEFAULT_TEU_FACTOR)
        teus_cu = calculate_teus(df_ton_cu_raw) if df_ton_cu_raw is not None else int(ton_cu * DEFAULT_TEU_FACTOR)
        teus_chenh = teus_moi - teus_cu
        
        summary_table = pd.DataFrame({
            t('col_category'): [t('inventory_old'), t('inventory_new'), t('inventory_diff')],
            t('col_conts'): [f'{ton_cu:,}', f'{ton_moi:,}', f'{chenh_lech:+,}'],
            t('col_teus'): [f'{teus_cu:,}', f'{teus_moi:,}', f'{teus_chenh:+,}']
        })
        st.dataframe(summary_table, use_container_width=False, hide_index=True)
        
        st.divider()
        
        # ============ SECTION 2: BIẾN ĐỘNG TRONG NGÀY ============
        st.subheader(t("header_daily_activity"))
        nhap = get_kpi('Tong giao dich NHAP')
        xuat = get_kpi('Tong giao dich XUAT')
        moi_vao = get_kpi('Container moi vao bai')
        da_roi = get_kpi('Container da roi bai')
        dao_chuyen = get_kpi('Dao chuyen vi tri')
        
        activity_table = pd.DataFrame({
            t('col_activity'): [t('activity_import'), t('activity_export'), t('activity_new_in'), t('activity_left'), t('activity_relocation')],
            t('col_conts'): [f'{nhap:,}', f'{xuat:,}', f'{moi_vao:,}', f'{da_roi:,}', f'{dao_chuyen:,}'],
            t('col_teus'): [
                f'{int(nhap * DEFAULT_TEU_FACTOR):,}',
                f'{int(xuat * DEFAULT_TEU_FACTOR):,}',
                f'{int(moi_vao * DEFAULT_TEU_FACTOR):,}',
                f'{int(da_roi * DEFAULT_TEU_FACTOR):,}',
                f'{int(dao_chuyen * DEFAULT_TEU_FACTOR):,}'
            ]
        })
        st.dataframe(activity_table, use_container_width=False, hide_index=True)
        
    except Exception as e:
        st.warning(f"{t('cannot_extract_metrics')} {e}")

# ============ SECTION 3: PHÂN TÍCH THỜI GIAN TỒN BÃI ============
st.divider()
st.subheader(t("header_dwell_time"))
try:
    df_ton_moi = main_results.get("raw_data", {}).get("ton_moi")
    if df_ton_moi is not None and not df_ton_moi.empty:
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
            dwell_categories = [t('dwell_under_31'), t('dwell_31_60'), t('dwell_61_90'), t('dwell_over_90')]
            
            dwell_data = []
            for category in dwell_categories:
                cat_df = df_dwell[df_dwell['Nhóm tồn'] == category]
                conts = len(cat_df)
                teus = calculate_teus(cat_df)
                dwell_data.append({t('col_dwell_time'): category, t('col_conts'): f'{conts:,}', t('col_teus'): f'{teus:,}'})
            
            dwell_table = pd.DataFrame(dwell_data)
            st.dataframe(dwell_table, use_container_width=False, hide_index=True)
        else:
            st.info(t("no_date_column"))
    else:
        st.info(t("no_new_inventory"))
except Exception as e:
    st.info(f"{t('cannot_analyze_dwell')} {e}")

# ============ SECTION 4: PHÂN TÍCH THEO VỊ TRÍ BÃI ============
st.divider()
st.subheader(t("header_location"))
try:
    df_ton_moi = main_results.get("raw_data", {}).get("ton_moi")
    if df_ton_moi is not None and not df_ton_moi.empty and Col.LOCATION in df_ton_moi.columns:
        df_loc = df_ton_moi.copy()
        
        def extract_area(loc):
            if pd.isna(loc) or not str(loc).strip():
                return t('dwell_unknown')
            loc_str = str(loc).strip().upper()
            if '-' in loc_str:
                return loc_str.split('-')[0]
            elif len(loc_str) > 0:
                return loc_str[0]
            return 'Khác'
        
        df_loc['Khu vực'] = df_loc[Col.LOCATION].apply(extract_area)
        
        loc_data = []
        for area in df_loc['Khu vực'].unique():
            area_df = df_loc[df_loc['Khu vực'] == area]
            conts = len(area_df)
            teus = calculate_teus(area_df)
            loc_data.append({t('col_area'): area, t('col_conts'): conts, t('col_teus'): teus})
        
        loc_df = pd.DataFrame(loc_data).sort_values(t('col_conts'), ascending=False).head(15)
        loc_df.insert(0, t('col_stt'), range(1, len(loc_df) + 1))
        
        chart_data = loc_df.set_index(t('col_area'))[t('col_conts')]
        st.bar_chart(chart_data)
        
        loc_df[t('col_conts')] = loc_df[t('col_conts')].apply(lambda x: f'{x:,}')
        loc_df[t('col_teus')] = loc_df[t('col_teus')].apply(lambda x: f'{x:,}')
        st.dataframe(loc_df, use_container_width=False, hide_index=True)
    else:
        st.info(t("no_location_data"))
except Exception as e:
    st.info(f"{t('cannot_analyze_location')} {e}")

# ============ SECTION 5: BẢNG TÓM TẮT CHI TIẾT ============
st.divider()
st.subheader(t("header_summary_table"))
if isinstance(summary_df, pd.DataFrame):
    summary_display_df = summary_df.copy()
    summary_display_df['So luong'] = summary_display_df['So luong'].astype(str).replace('.0', '', regex=False)
    st.dataframe(add_stt_column(summary_display_df, t), use_container_width=False, hide_index=True)
