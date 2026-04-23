# File: app.py — @2026 v1.0
"""Streamlit entry point.

The real user pages are registered explicitly so the entry script itself does
not appear as an extra "app" page in the sidebar.
"""

import streamlit as st


st.set_page_config(
    page_title="Báo cáo tồn bãi",
    layout="wide",
    initial_sidebar_state="expanded",
)

dashboard = st.navigation(
    [
        st.Page("pages/1_Overview.py", title="Overview", icon="📊"),
        st.Page("pages/2_Operator.py", title="Operator", icon="🏢"),
    ]
)

dashboard.run()
