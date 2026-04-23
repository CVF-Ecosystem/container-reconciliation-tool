# File: utils/streamlit_shared.py — @2026 v1.0
"""
Shared utilities for the Streamlit multi-page dashboard.

This module intentionally lives outside `pages/` so Streamlit does not expose it
as a blank user-facing page in the sidebar.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

import config
from core_logic import load_results
from utils.translation import translator_instance


SHARED_CSS = """
<style>
    .stDataFrame thead th {
        text-align: center !important;
        font-weight: bold !important;
    }
    .stDataFrame tbody td {
        text-align: left !important;
    }
    .stDataFrame tbody td:nth-child(n+3) {
        text-align: right !important;
    }
    .stDataFrame td, .stDataFrame th {
        padding: 4px 8px !important;
        white-space: nowrap !important;
    }
    .stDataFrame table {
        width: auto !important;
        table-layout: auto !important;
    }
</style>
"""


def setup_page(page_title: str = "Báo cáo tồn bãi"):
    """Common page setup: CSS and language selector."""
    st.markdown(SHARED_CSS, unsafe_allow_html=True)

    st.sidebar.title("Language / Ngôn ngữ")
    selected_language_code = st.sidebar.selectbox(
        "Choose a language / Chọn ngôn ngữ",
        options=["vi", "en"],
        format_func=lambda x: "Tiếng Việt" if x == "vi" else "English",
        key="language_selector",
    )
    translator_instance.set_language(selected_language_code or "vi")
    return translator_instance.get_translator()


@st.cache_data(ttl=300, show_spinner=False)
def load_dashboard_data(output_dir_str: str) -> Optional[Dict[str, Any]]:
    """Load and cache reconciliation results for dashboard pages."""
    return load_results(Path(output_dir_str))


def get_results(auto_refresh_seconds: int = 0) -> Optional[Dict[str, Any]]:
    """Get cached results with manual and optional auto-refresh."""
    col1, col2 = st.sidebar.columns([2, 1])

    with col1:
        if st.button("🔄 Tải lại dữ liệu", key="reload_btn", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with col2:
        auto_refresh = st.checkbox("Auto", key="auto_refresh_toggle", value=False)

    if auto_refresh:
        refresh_interval = st.sidebar.slider(
            "Refresh mỗi (giây)",
            min_value=30,
            max_value=600,
            value=auto_refresh_seconds or 300,
            step=30,
            key="refresh_interval",
        )

        placeholder = st.sidebar.empty()
        last_refresh_key = "last_refresh_time"
        if last_refresh_key not in st.session_state:
            st.session_state[last_refresh_key] = time.time()

        elapsed = time.time() - st.session_state[last_refresh_key]
        remaining = max(0, refresh_interval - elapsed)
        placeholder.caption(f"⏱️ Tự động tải lại sau {remaining:.0f}s")

        if elapsed >= refresh_interval:
            st.session_state[last_refresh_key] = time.time()
            st.cache_data.clear()
            st.rerun()

    return load_dashboard_data(str(config.OUTPUT_DIR))


def show_data_info(results: Dict[str, Any], t):
    """Show data timestamp and availability info."""
    current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
    st.success(f"{t('showing_results')} {current_time}")

    try:
        from utils.history_db import HistoryDatabase

        history_db = HistoryDatabase(config.OUTPUT_DIR)
        available_dates = history_db.get_available_dates(limit=100)
        if available_dates:
            dates_count = len(available_dates)
            first_date = available_dates[-1]
            last_date = available_dates[0]
            date_range = first_date if dates_count == 1 else f"{first_date} → {last_date}"
            st.info(f"📊 **{t('data_available')}** {dates_count} {t('days')} ({date_range})")
    except Exception as e:
        logging.debug(f"Could not load history database dates: {e}")
