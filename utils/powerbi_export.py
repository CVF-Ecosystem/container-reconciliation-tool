# File: utils/powerbi_export.py
"""
Power BI Export Module - Export data in format suitable for Power BI.

V5.0 - Phase 5: Analytics
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
import pandas as pd


class PowerBIExporter:
    """Export reconciliation data for Power BI analysis."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.bi_folder = self.output_dir / "BI_Data"
        self.bi_folder.mkdir(exist_ok=True)
    
    def export_all(self, days: int = 30) -> Path:
        """
        Export all data for Power BI in a single Excel file with multiple sheets.
        
        Args:
            days: Number of days to include
        
        Returns:
            Path to exported file
        """
        from utils.history_db import HistoryDatabase
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.bi_folder / f"PowerBI_Data_{timestamp}.xlsx"
        
        try:
            history_db = HistoryDatabase(self.output_dir)
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Sheet 1: Daily Inventory Trend
                df_trend = self._get_inventory_trend(history_db, days)
                df_trend.to_excel(writer, sheet_name='Inventory_Trend', index=False)
                
                # Sheet 2: Latest Snapshot
                df_snapshot = self._get_latest_snapshot(history_db)
                df_snapshot.to_excel(writer, sheet_name='Current_Inventory', index=False)
                
                # Sheet 3: Recent Transactions
                df_transactions = self._get_recent_transactions(history_db, days)
                df_transactions.to_excel(writer, sheet_name='Transactions', index=False)
                
                # Sheet 4: Discrepancy Summary
                df_discrepancy = self._get_discrepancy_trend(history_db, days)
                df_discrepancy.to_excel(writer, sheet_name='Discrepancy_Trend', index=False)
                
                # Sheet 5: Operator Analysis
                df_operators = self._get_operator_summary(history_db)
                df_operators.to_excel(writer, sheet_name='By_Operator', index=False)
                
                # Sheet 6: Thời gian lưu bãi (Dwell Time)
                df_age = self._get_container_age_analysis(history_db)
                df_age.to_excel(writer, sheet_name='Dwell_Time', index=False)
                
                # Sheet 7: Metadata
                df_meta = self._create_metadata(days)
                df_meta.to_excel(writer, sheet_name='_Metadata', index=False)
            
            logging.info(f"[PowerBI] Exported data to {output_file}")
            return output_file
            
        except Exception as e:
            logging.error(f"[PowerBI] Export failed: {e}")
            raise
    
    def _get_inventory_trend(self, db, days: int) -> pd.DataFrame:
        """Get daily inventory counts."""
        try:
            df = db.get_inventory_trend(days)
            if df.empty:
                return pd.DataFrame(columns=['Date', 'Container_Count'])
            df.columns = ['Date', 'Container_Count']
            return df
        except:
            return pd.DataFrame(columns=['Date', 'Container_Count'])
    
    def _get_latest_snapshot(self, db) -> pd.DataFrame:
        """Get latest inventory snapshot."""
        try:
            dates = db.get_available_dates(limit=1)
            if not dates:
                return pd.DataFrame()
            
            from datetime import datetime as dt
            latest_date = dt.strptime(dates[0], '%Y-%m-%d')
            df = db.get_snapshot_for_date(latest_date)
            
            # Rename columns for Power BI
            if not df.empty:
                df = df.rename(columns={
                    'Số Container': 'Container_ID',
                    'Trạng thái': 'Status',
                    'Kích cỡ': 'Size',
                    'Hãng khai thác': 'Operator',
                    'Vị trí bãi': 'Location',
                    'Số lệnh': 'Job_Order',
                    'Ngày nhập bãi': 'Entry_Date'
                })
            return df
        except:
            return pd.DataFrame()
    
    def _get_recent_transactions(self, db, days: int) -> pd.DataFrame:
        """Get recent container transactions."""
        try:
            import sqlite3
            with sqlite3.connect(db.db_path) as conn:
                query = f"""
                    SELECT 
                        transaction_date as Date,
                        container_id as Container_ID,
                        move_type as Move_Type,
                        source_key as Source,
                        phuong_an as Method,
                        fe as Status,
                        operator as Operator
                    FROM container_transactions
                    WHERE transaction_date >= date('now', '-{days} days')
                    ORDER BY transaction_date DESC, id DESC
                """
                return pd.read_sql_query(query, conn)
        except:
            return pd.DataFrame()
    
    def _get_discrepancy_trend(self, db, days: int) -> pd.DataFrame:
        """Get discrepancy counts over time."""
        try:
            df = db.get_discrepancy_trend(days)
            if df.empty:
                return pd.DataFrame(columns=['Date', 'Missing', 'Extra', 'Wrong_Info'])
            df.columns = ['Date', 'Missing', 'Extra', 'Wrong_Info']
            return df
        except:
            return pd.DataFrame(columns=['Date', 'Missing', 'Extra', 'Wrong_Info'])
    
    def _get_operator_summary(self, db) -> pd.DataFrame:
        """Get container count by operator."""
        try:
            import sqlite3
            with sqlite3.connect(db.db_path) as conn:
                # Get from latest snapshot
                dates = db.get_available_dates(limit=1)
                if not dates:
                    return pd.DataFrame(columns=['Operator', 'Container_Count', 'Percentage'])
                
                query = f"""
                    SELECT 
                        COALESCE(operator, 'Unknown') as Operator,
                        COUNT(*) as Container_Count
                    FROM container_snapshots
                    WHERE snapshot_date = '{dates[0]}'
                    GROUP BY operator
                    ORDER BY Container_Count DESC
                """
                df = pd.read_sql_query(query, conn)
                
                if not df.empty:
                    total = df['Container_Count'].sum()
                    df['Percentage'] = (df['Container_Count'] / total * 100).round(1)
                
                return df
        except:
            return pd.DataFrame(columns=['Operator', 'Container_Count', 'Percentage'])
    
    def _get_container_age_analysis(self, db) -> pd.DataFrame:
        """Phân tích thời gian lưu bãi của container."""
        try:
            import sqlite3
            with sqlite3.connect(db.db_path) as conn:
                dates = db.get_available_dates(limit=1)
                if not dates:
                    return pd.DataFrame()
                
                query = f"""
                    SELECT 
                        container_id as Container_ID,
                        fe as Status,
                        operator as Operator,
                        ngay_nhap_bai as Entry_Date,
                        julianday('{dates[0]}') - julianday(ngay_nhap_bai) as Dwell_Days
                    FROM container_snapshots
                    WHERE snapshot_date = '{dates[0]}'
                    AND ngay_nhap_bai IS NOT NULL
                    AND ngay_nhap_bai != ''
                    ORDER BY Days_In_Yard DESC
                """
                df = pd.read_sql_query(query, conn)
                
                # Add age category
                if not df.empty and 'Dwell_Days' in df.columns:
                    df['Dwell_Category'] = pd.cut(
                        df['Dwell_Days'].fillna(0),
                        bins=[-1, 7, 14, 30, 60, 90, float('inf')],
                        labels=['0-7 ngày', '8-14 ngày', '15-30 ngày', '31-60 ngày', '61-90 ngày', '>90 ngày']
                    )
                
                return df
        except Exception as e:
            logging.warning(f"Age analysis failed: {e}")
            return pd.DataFrame()
    
    def _create_metadata(self, days: int) -> pd.DataFrame:
        """Create metadata sheet."""
        return pd.DataFrame([
            {'Key': 'Export_Time', 'Value': datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
            {'Key': 'Days_Included', 'Value': str(days)},
            {'Key': 'Data_Source', 'Value': 'Container Reconciliation Tool V5.0'},
            {'Key': 'Format_Version', 'Value': '1.0'},
        ])


def export_for_powerbi(output_dir: Path, days: int = 30) -> Optional[Path]:
    """
    Convenience function to export Power BI data.
    
    Args:
        output_dir: Output directory
        days: Number of days to include
    
    Returns:
        Path to exported file or None if failed
    """
    try:
        exporter = PowerBIExporter(output_dir)
        return exporter.export_all(days)
    except Exception as e:
        logging.error(f"Power BI export failed: {e}")
        return None
