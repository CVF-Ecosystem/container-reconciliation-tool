# File: BI_Dashboard/bi_app.py
"""
BI Dashboard - Streamlit app for business intelligence visualization.

V5.0 - Phase 5: Analytics
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OUTPUT_DIR
from utils.history_db import HistoryDatabase


st.set_page_config(
    page_title="📊 BI Dashboard - Tồn Bãi Container",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def get_database():
    """Get database connection."""
    return HistoryDatabase(OUTPUT_DIR)


def main():
    st.title("📊 BI Dashboard - Phân Tích Tồn Bãi Container")
    st.markdown("---")
    
    db = get_database()
    
    # Sidebar: Controls
    with st.sidebar:
        st.header("⚙️ Cài đặt")
        days = st.slider("Số ngày phân tích", 7, 90, 30)
        
        st.markdown("---")
        
        if st.button("🔄 Làm mới dữ liệu"):
            st.cache_resource.clear()
            st.rerun()
        
        if st.button("📥 Export Power BI Data"):
            export_powerbi_data(days)
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Xu hướng tồn bãi",
        "📊 Phân tích theo Hãng",
        "⏱️ Thời gian lưu bãi",
        "📋 Chi tiết tồn bãi"
    ])
    
    with tab1:
        show_inventory_trend(db, days)
    
    with tab2:
        show_operator_analysis(db)
    
    with tab3:
        show_dwell_time_analysis(db)
    
    with tab4:
        show_inventory_detail(db)


def show_inventory_trend(db, days: int):
    """Hiển thị xu hướng tồn bãi."""
    st.subheader("📈 Xu Hướng Tồn Bãi Theo Ngày")
    
    df = db.get_inventory_trend(days)
    
    if df.empty:
        st.warning("Chưa có dữ liệu. Hãy chạy đối soát trước.")
        return
    
    df.columns = ['Ngày', 'Số lượng']
    
    # Line chart
    fig = px.line(
        df, x='Ngày', y='Số lượng',
        title=f'Tồn Bãi {days} Ngày Gần Đây',
        markers=True
    )
    fig.update_layout(
        xaxis_title="Ngày",
        yaxis_title="Số Container",
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Hiện tại", f"{df['Số lượng'].iloc[-1]:,}" if len(df) > 0 else "N/A")
    with col2:
        if len(df) > 1:
            change = df['Số lượng'].iloc[-1] - df['Số lượng'].iloc[-2]
            st.metric("So với hôm qua", f"{change:+,}")
        else:
            st.metric("So với hôm qua", "N/A")
    with col3:
        st.metric("Trung bình", f"{df['Số lượng'].mean():,.0f}")
    with col4:
        st.metric("Cao nhất", f"{df['Số lượng'].max():,}")


def show_operator_analysis(db):
    """Phân tích theo hãng khai thác."""
    st.subheader("📊 Phân Tích Theo Hãng Khai Thác")
    
    dates = db.get_available_dates(limit=1)
    if not dates:
        st.warning("Chưa có dữ liệu snapshot.")
        return
    
    # Query operator summary
    import sqlite3
    with sqlite3.connect(db.db_path) as conn:
        query = f"""
            SELECT 
                COALESCE(operator, 'Chưa xác định') as Operator,
                COUNT(*) as Count
            FROM container_snapshots
            WHERE snapshot_date = '{dates[0]}'
            GROUP BY operator
            ORDER BY Count DESC
        """
        df = pd.read_sql_query(query, conn)
    
    if df.empty:
        st.warning("Không có dữ liệu.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart
        fig = px.pie(
            df, values='Count', names='Operator',
            title='Tỷ lệ theo Hãng Khai Thác',
            hole=0.4
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Bar chart
        fig = px.bar(
            df.head(10), x='Count', y='Operator',
            orientation='h',
            title='Top 10 Hãng Khai Thác'
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    
    # Table
    st.dataframe(df, use_container_width=True)


def show_dwell_time_analysis(db):
    """Phân tích thời gian lưu bãi."""
    st.subheader("⏱️ Phân Tích Thời Gian Lưu Bãi")
    
    dates = db.get_available_dates(limit=1)
    if not dates:
        st.warning("Chưa có dữ liệu.")
        return
    
    import sqlite3
    with sqlite3.connect(db.db_path) as conn:
        query = f"""
            SELECT 
                container_id,
                fe as Status,
                operator as Operator,
                ngay_nhap_bai as Entry_Date,
                julianday('{dates[0]}') - julianday(ngay_nhap_bai) as Dwell_Days
            FROM container_snapshots
            WHERE snapshot_date = '{dates[0]}'
            AND ngay_nhap_bai IS NOT NULL
            AND ngay_nhap_bai != ''
        """
        df = pd.read_sql_query(query, conn)
    
    if df.empty:
        st.warning("Không có dữ liệu thời gian lưu bãi.")
        return
    
    # Add category
    df['Dwell_Category'] = pd.cut(
        df['Dwell_Days'].fillna(0),
        bins=[-1, 7, 14, 30, 60, 90, float('inf')],
        labels=['0-7 ngày', '8-14 ngày', '15-30 ngày', '31-60 ngày', '61-90 ngày', '>90 ngày']
    )
    
    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Trung bình (ngày)", f"{df['Dwell_Days'].mean():.1f}")
    with col2:
        st.metric("Lâu nhất (ngày)", f"{df['Dwell_Days'].max():.0f}")
    with col3:
        long_term = len(df[df['Dwell_Days'] > 30])
        st.metric("Lưu >30 ngày", f"{long_term:,}")
    
    # Distribution chart
    category_counts = df['Dwell_Category'].value_counts().sort_index()
    fig = px.bar(
        x=category_counts.index.astype(str),
        y=category_counts.values,
        title='Phân Bố Thời Gian Lưu Bãi',
        labels={'x': 'Khoảng thời gian', 'y': 'Số container'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Top long-term containers
    st.subheader("🔴 Container lưu lâu nhất")
    top_long = df.nlargest(20, 'Dwell_Days')[['container_id', 'Operator', 'Entry_Date', 'Dwell_Days']]
    top_long.columns = ['Container', 'Hãng KT', 'Ngày nhập', 'Số ngày']
    st.dataframe(top_long, use_container_width=True)


def show_inventory_detail(db):
    """Chi tiết tồn bãi."""
    st.subheader("📋 Chi Tiết Tồn Bãi Hiện Tại")
    
    dates = db.get_available_dates(limit=1)
    if not dates:
        st.warning("Chưa có dữ liệu.")
        return
    
    from datetime import datetime as dt
    df = db.get_snapshot_for_date(dt.strptime(dates[0], '%Y-%m-%d'))
    
    if df.empty:
        st.warning("Không có dữ liệu.")
        return
    
    st.info(f"📅 Dữ liệu ngày: **{dates[0]}** | Tổng: **{len(df):,}** container")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        operators = ['Tất cả'] + df['Hãng khai thác'].dropna().unique().tolist()
        selected_op = st.selectbox("Lọc theo Hãng KT", operators)
    with col2:
        search = st.text_input("🔍 Tìm Container", "")
    
    # Apply filters
    filtered = df.copy()
    if selected_op != 'Tất cả':
        filtered = filtered[filtered['Hãng khai thác'] == selected_op]
    if search:
        filtered = filtered[filtered['Số Container'].str.contains(search.upper(), na=False)]
    
    st.dataframe(filtered, use_container_width=True, height=500)
    
    # Download
    csv = filtered.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Tải xuống CSV",
        csv,
        f"ton_bai_{dates[0]}.csv",
        "text/csv"
    )


def export_powerbi_data(days: int):
    """Export Power BI data."""
    try:
        from utils.powerbi_export import export_for_powerbi
        
        with st.spinner("Đang tạo file Power BI..."):
            output_file = export_for_powerbi(OUTPUT_DIR, days)
        
        if output_file and output_file.exists():
            st.success(f"✅ Đã tạo: {output_file.name}")
            
            with open(output_file, 'rb') as f:
                st.download_button(
                    "📥 Tải file Power BI",
                    f,
                    output_file.name,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.error("Không thể tạo file")
    except Exception as e:
        st.error(f"Lỗi: {e}")


if __name__ == "__main__":
    main()
