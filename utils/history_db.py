"""
SQLite History Database for storing reconciliation results.
Enables historical analysis and comparison between runs.
"""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd


class HistoryDatabase:
    """
    SQLite database for storing reconciliation run history.
    
    Features:
    - Store summary statistics for each run
    - Track discrepancy counts over time
    - Query historical trends
    """
    
    DB_FILENAME = "reconciliation_history.db"
    
    def __init__(self, output_dir: Path):
        """
        Initialize the history database.
        
        Args:
            output_dir: Directory where the database file will be stored.
        """
        self.db_path = output_dir / self.DB_FILENAME
        self._init_database()
    
    def _init_database(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Main runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_timestamp DATETIME NOT NULL,
                    report_folder TEXT,
                    ton_ly_thuyet INTEGER,
                    ton_thuc_te INTEGER,
                    khop_chuan INTEGER,
                    khop_sai INTEGER,
                    thieu INTEGER,
                    thua INTEGER,
                    van_ton INTEGER,
                    future_moves INTEGER,
                    suspicious_dates INTEGER,
                    time_slot TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Detailed discrepancy table for trend analysis
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discrepancies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    container_id TEXT,
                    discrepancy_type TEXT,
                    details TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs (id)
                )
            """)
            
            # V5.1: Daily container snapshots with time_slot support
            # time_slot = '8H', '15H', hoặc NULL (full-day)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS container_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date DATE NOT NULL,
                    time_slot TEXT,
                    container_id TEXT NOT NULL,
                    fe TEXT,
                    iso TEXT,
                    operator TEXT,
                    location TEXT,
                    job_order TEXT,
                    ngay_nhap_bai DATE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(snapshot_date, time_slot, container_id)
                )
            """)
            
            # V4.7.2: Container transactions - Lịch sử giao dịch IN/OUT
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS container_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_date DATE NOT NULL,
                    container_id TEXT NOT NULL,
                    move_type TEXT,
                    source_key TEXT,
                    phuong_an TEXT,
                    fe TEXT,
                    iso TEXT,
                    operator TEXT,
                    location TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # V5.1: Migration - thêm cột time_slot nếu chưa có
            try:
                cursor.execute("ALTER TABLE container_snapshots ADD COLUMN time_slot TEXT")
                logging.info("Added time_slot column to container_snapshots")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE runs ADD COLUMN time_slot TEXT")
                logging.info("Added time_slot column to runs")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_date 
                ON container_snapshots(snapshot_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_container_id 
                ON container_snapshots(container_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_slot 
                ON container_snapshots(snapshot_date, time_slot)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trans_date 
                ON container_transactions(transaction_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trans_container 
                ON container_transactions(container_id)
            """)
            
            conn.commit()
            logging.info(f"History database initialized at {self.db_path}")
    
    def save_run(self, results: Dict[str, Any]) -> int:
        """
        Save a reconciliation run to the database.
        
        Args:
            results: The final_results dictionary from run_full_reconciliation_process.
        
        Returns:
            The ID of the inserted run record.
        """
        main_results = results.get("main_results", {})
        counts = main_results.get("counts", {})
        run_timestamp = results.get("run_timestamp", datetime.now())
        report_folder = str(results.get("report_folder", ""))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO runs (
                    run_timestamp, report_folder,
                    ton_ly_thuyet, ton_thuc_te,
                    khop_chuan, khop_sai, thieu, thua, van_ton,
                    future_moves, suspicious_dates
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_timestamp.isoformat(),
                report_folder,
                counts.get("ton_ly_thuyet", 0),
                counts.get("ton_moi", 0),
                counts.get("khop_chuan", 0),
                counts.get("khop_sai", 0),
                counts.get("thieu", 0),
                counts.get("thua", 0),
                counts.get("van_ton", 0),
                counts.get("future_moves", 0),
                counts.get("suspicious_dates", 0)
            ))
            
            run_id = cursor.lastrowid
            conn.commit()
            
            logging.info(f"Saved run #{run_id} to history database.")
            return run_id
    
    def get_recent_runs(self, limit: int = 10) -> pd.DataFrame:
        """
        Get the most recent reconciliation runs.
        
        Args:
            limit: Maximum number of runs to return.
        
        Returns:
            DataFrame with run history.
        """
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
                    id, run_timestamp, 
                    khop_chuan, khop_sai, thieu, thua, van_ton
                FROM runs
                ORDER BY run_timestamp DESC
                LIMIT ?
            """
            return pd.read_sql_query(query, conn, params=(limit,))
    
    def get_discrepancy_trend(self, days: int = 30) -> pd.DataFrame:
        """
        Get discrepancy counts over time for trend analysis.
        
        Args:
            days: Number of days to look back.
        
        Returns:
            DataFrame with date and discrepancy counts.
        """
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
                    DATE(run_timestamp) as date,
                    SUM(thieu) as total_thieu,
                    SUM(thua) as total_thua,
                    SUM(khop_sai) as total_sai_info
                FROM runs
                WHERE run_timestamp >= date('now', ?)
                GROUP BY DATE(run_timestamp)
                ORDER BY date
            """
            return pd.read_sql_query(query, conn, params=(f"-{days} days",))
    
    # ========== V4.7.2: DAILY CONTAINER SNAPSHOT METHODS ==========
    
    def save_daily_snapshot(self, df_ton_moi: pd.DataFrame, snapshot_date: Optional[datetime] = None) -> int:
        """
        Lưu snapshot tồn bãi theo ngày.
        TON MOI hôm nay sẽ là TON CU ngày mai.
        
        Args:
            df_ton_moi: DataFrame chứa danh sách container tồn bãi
            snapshot_date: Ngày lưu snapshot (mặc định = hôm nay)
        
        Returns:
            Số container đã lưu
        """
        from config import Col
        
        if df_ton_moi.empty:
            logging.warning("DataFrame tồn bãi rỗng, không lưu snapshot.")
            return 0
        
        if snapshot_date is None:
            snapshot_date = datetime.now()
        
        date_str = snapshot_date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Xóa snapshot cũ của ngày này (nếu có) để cập nhật mới
            cursor.execute("DELETE FROM container_snapshots WHERE snapshot_date = ?", (date_str,))
            
            # Chuẩn bị dữ liệu
            count = 0
            for _, row in df_ton_moi.iterrows():
                container_id = str(row.get(Col.CONTAINER, ''))
                if not container_id:
                    continue
                    
                cursor.execute("""
                    INSERT OR REPLACE INTO container_snapshots 
                    (snapshot_date, container_id, fe, iso, operator, location, job_order, ngay_nhap_bai)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str,
                    container_id,
                    str(row.get(Col.FE, '')),
                    str(row.get(Col.ISO, '')),
                    str(row.get(Col.OPERATOR, '')),
                    str(row.get(Col.LOCATION, '')),
                    str(row.get(Col.JOB_ORDER, '')),
                    str(row.get(Col.NGAY_NHAP_BAI, ''))
                ))
                count += 1
            
            conn.commit()
            logging.info(f"Đã lưu snapshot {count} container cho ngày {date_str}")
            return count
    
    def get_snapshot_for_date(self, target_date: datetime) -> pd.DataFrame:
        """
        Lấy snapshot tồn bãi của một ngày cụ thể.
        
        Args:
            target_date: Ngày cần lấy snapshot
            
        Returns:
            DataFrame chứa danh sách container
        """
        date_str = target_date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
                    container_id as 'Số Container',
                    fe as 'Trạng thái',
                    iso as 'Kích cỡ',
                    operator as 'Hãng khai thác',
                    location as 'Vị trí bãi',
                    job_order as 'Số lệnh',
                    ngay_nhap_bai as 'Ngày nhập bãi'
                FROM container_snapshots
                WHERE snapshot_date = ?
            """
            return pd.read_sql_query(query, conn, params=(date_str,))
    
    # ========== V5.1: TIME SLOT METHODS ==========
    
    def save_daily_snapshot_with_slot(
        self, 
        df_ton_moi: pd.DataFrame, 
        snapshot_date: Optional[datetime] = None,
        time_slot: Optional[str] = None
    ) -> int:
        """
        Lưu snapshot tồn bãi theo ngày VÀ time slot.
        
        Args:
            df_ton_moi: DataFrame chứa danh sách container tồn bãi
            snapshot_date: Ngày lưu snapshot (mặc định = hôm nay)
            time_slot: Time slot ('8H', '15H', hoặc None cho full-day)
        
        Returns:
            Số container đã lưu
        """
        from config import Col
        
        if df_ton_moi.empty:
            logging.warning("DataFrame tồn bãi rỗng, không lưu snapshot.")
            return 0
        
        if snapshot_date is None:
            snapshot_date = datetime.now()
        
        date_str = snapshot_date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Xóa snapshot cũ của ngày + slot này (nếu có)
            if time_slot:
                cursor.execute(
                    "DELETE FROM container_snapshots WHERE snapshot_date = ? AND time_slot = ?", 
                    (date_str, time_slot)
                )
            else:
                cursor.execute(
                    "DELETE FROM container_snapshots WHERE snapshot_date = ? AND time_slot IS NULL", 
                    (date_str,)
                )
            
            count = 0
            for _, row in df_ton_moi.iterrows():
                container_id = str(row.get(Col.CONTAINER, ''))
                if not container_id:
                    continue
                    
                cursor.execute("""
                    INSERT OR REPLACE INTO container_snapshots 
                    (snapshot_date, time_slot, container_id, fe, iso, operator, location, job_order, ngay_nhap_bai)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str,
                    time_slot,
                    container_id,
                    str(row.get(Col.FE, '')),
                    str(row.get(Col.ISO, '')),
                    str(row.get(Col.OPERATOR, '')),
                    str(row.get(Col.LOCATION, '')),
                    str(row.get(Col.JOB_ORDER, '')),
                    str(row.get(Col.NGAY_NHAP_BAI, ''))
                ))
                count += 1
            
            conn.commit()
            slot_label = f" ({time_slot})" if time_slot else ""
            logging.info(f"Đã lưu snapshot {count} container cho ngày {date_str}{slot_label}")
            return count
    
    def get_snapshot_for_date_slot(
        self, 
        target_date: datetime, 
        time_slot: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Lấy snapshot tồn bãi của một ngày + slot cụ thể.
        
        Args:
            target_date: Ngày cần lấy snapshot
            time_slot: Time slot ('8H', '15H', hoặc None)
            
        Returns:
            DataFrame chứa danh sách container
        """
        date_str = target_date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            if time_slot:
                query = """
                    SELECT 
                        container_id as 'Số Container',
                        fe as 'Trạng thái',
                        iso as 'Kích cỡ',
                        operator as 'Hãng khai thác',
                        location as 'Vị trí bãi',
                        job_order as 'Số lệnh',
                        ngay_nhap_bai as 'Ngày nhập bãi'
                    FROM container_snapshots
                    WHERE snapshot_date = ? AND time_slot = ?
                """
                return pd.read_sql_query(query, conn, params=(date_str, time_slot))
            else:
                query = """
                    SELECT 
                        container_id as 'Số Container',
                        fe as 'Trạng thái',
                        iso as 'Kích cỡ',
                        operator as 'Hãng khai thác',
                        location as 'Vị trí bãi',
                        job_order as 'Số lệnh',
                        ngay_nhap_bai as 'Ngày nhập bãi'
                    FROM container_snapshots
                    WHERE snapshot_date = ? AND time_slot IS NULL
                """
                return pd.read_sql_query(query, conn, params=(date_str,))
    
    def get_previous_slot_as_ton_cu(
        self, 
        current_date: datetime, 
        current_slot: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Lấy snapshot của slot trước đó làm TON CU.
        
        Logic:
        - Nếu current_slot = '15H' → lấy slot '8H' cùng ngày
        - Nếu current_slot = '8H' → lấy slot '15H' ngày hôm trước
        - Nếu current_slot = None (full-day) → lấy full-day ngày hôm trước
        
        Args:
            current_date: Ngày hiện tại
            current_slot: Slot hiện tại
        
        Returns:
            DataFrame tồn bãi của slot trước
        """
        from datetime import timedelta
        
        if current_slot == '15H':
            # Lấy slot 8H cùng ngày
            df = self.get_snapshot_for_date_slot(current_date, '8H')
            if not df.empty:
                logging.info(f"Đã tải {len(df)} container từ slot 8H cùng ngày làm TON CU.")
                return df
        elif current_slot == '8H':
            # Lấy slot 15H ngày hôm trước
            yesterday = current_date - timedelta(days=1)
            df = self.get_snapshot_for_date_slot(yesterday, '15H')
            if not df.empty:
                logging.info(f"Đã tải {len(df)} container từ slot 15H hôm qua làm TON CU.")
                return df
        
        # Fallback: lấy slot gần nhất
        yesterday = current_date - timedelta(days=1)
        df = self.get_snapshot_for_date_slot(yesterday, current_slot)
        if not df.empty:
            logging.info(f"Đã tải {len(df)} container từ snapshot hôm qua làm TON CU.")
            return df
        
        # Ultimate fallback: lấy bất kỳ snapshot nào của ngày hôm qua
        df = self.get_snapshot_for_date(yesterday)
        if not df.empty:
            logging.info(f"Đã tải {len(df)} container từ snapshot hôm qua (any slot) làm TON CU.")
        else:
            logging.warning(f"Không tìm thấy snapshot nào cho ngày/slot trước đó.")
        
        return df
    
    def get_yesterday_as_ton_cu(self) -> pd.DataFrame:
        """
        Lấy snapshot ngày hôm qua làm TON CU cho hôm nay.
        Đây là function chính để sử dụng trong workflow hàng ngày.
        
        Returns:
            DataFrame tồn bãi ngày hôm qua (sẵn sàng làm TON CU)
        """
        from datetime import timedelta
        yesterday = datetime.now() - timedelta(days=1)
        df = self.get_snapshot_for_date(yesterday)
        
        if df.empty:
            logging.warning(f"Không tìm thấy snapshot ngày {yesterday.strftime('%Y-%m-%d')}. "
                          "Có thể chưa chạy đối soát ngày hôm qua.")
        else:
            logging.info(f"Đã tải {len(df)} container từ snapshot ngày hôm qua làm TON CU.")
        
        return df
    
    def get_available_dates(self, limit: int = 30) -> List[str]:
        """
        Lấy danh sách các ngày có snapshot.
        
        Returns:
            List các ngày (format: YYYY-MM-DD)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT snapshot_date 
                FROM container_snapshots 
                ORDER BY snapshot_date DESC
                LIMIT ?
            """, (limit,))
            return [row[0] for row in cursor.fetchall()]
    
    def get_container_history(self, container_id: str, days: int = 30) -> pd.DataFrame:
        """
        Xem lịch sử của một container trong N ngày gần đây.
        
        Args:
            container_id: Số container cần tra cứu
            days: Số ngày nhìn lại
            
        Returns:
            DataFrame lịch sử container
        """
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
                    snapshot_date as 'Ngày',
                    container_id as 'Số Container',
                    fe as 'Trạng thái',
                    location as 'Vị trí bãi'
                FROM container_snapshots
                WHERE container_id = ? 
                AND snapshot_date >= date('now', ?)
                ORDER BY snapshot_date DESC
            """
            return pd.read_sql_query(query, conn, params=(container_id, f"-{days} days"))
    
    # ========== V4.7.2: TRANSACTION LOGGING ==========
    
    def save_transactions(self, df_all_moves: pd.DataFrame, transaction_date: Optional[datetime] = None) -> int:
        """
        Lưu tất cả giao dịch IN/OUT vào database.
        
        Args:
            df_all_moves: DataFrame chứa tất cả giao dịch
            transaction_date: Ngày giao dịch (mặc định = hôm nay)
        
        Returns:
            Số giao dịch đã lưu
        """
        from config import Col
        
        if df_all_moves.empty:
            return 0
        
        if transaction_date is None:
            transaction_date = datetime.now()
        
        date_str = transaction_date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            count = 0
            for _, row in df_all_moves.iterrows():
                container_id = str(row.get(Col.CONTAINER, ''))
                if not container_id:
                    continue
                
                cursor.execute("""
                    INSERT INTO container_transactions 
                    (transaction_date, container_id, move_type, source_key, phuong_an, fe, iso, operator, location)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str,
                    container_id,
                    str(row.get(Col.MOVE_TYPE, '')),
                    str(row.get(Col.SOURCE_KEY, '')),
                    str(row.get(Col.PHUONG_AN, '')),
                    str(row.get(Col.FE, '')),
                    str(row.get(Col.ISO, '')),
                    str(row.get(Col.OPERATOR, '')),
                    str(row.get(Col.LOCATION, ''))
                ))
                count += 1
            
            conn.commit()
            logging.info(f"Đã lưu {count} giao dịch cho ngày {date_str}")
            return count
    
    # ========== V4.7.2: EXPORT FUNCTIONS ==========
    
    def export_snapshot_range(self, start_date: datetime, end_date: datetime, output_path: Optional[Path] = None) -> Path:
        """
        Xuất snapshot tồn bãi theo khoảng thời gian ra file Excel.
        
        Args:
            start_date: Ngày bắt đầu
            end_date: Ngày kết thúc
            output_path: Đường dẫn file output (mặc định = data_output/export_xxx.xlsx)
        
        Returns:
            Path đến file đã xuất
        """
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
                    snapshot_date as 'Ngày kiểm tra',
                    container_id as 'Số Container',
                    fe as 'Trạng thái',
                    iso as 'Kích cỡ',
                    operator as 'Hãng khai thác',
                    location as 'Vị trí bãi'
                FROM container_snapshots
                WHERE snapshot_date BETWEEN ? AND ?
                ORDER BY snapshot_date, container_id
            """
            df = pd.read_sql_query(query, conn, params=(start_str, end_str))
        
        # Thêm cột STT (số thứ tự)
        if not df.empty:
            df.insert(0, 'STT', range(1, len(df) + 1))
        
        if output_path is None:
            output_path = self.db_path.parent / f"Danh_sach_ton_bai_{start_str}_to_{end_str}.xlsx"
        
        df.to_excel(output_path, index=False, engine='openpyxl')
        logging.info(f"Đã xuất {len(df)} records ra {output_path}")
        return output_path
    
    def compare_two_dates(self, date1: datetime, date2: datetime) -> Dict[str, pd.DataFrame]:
        """
        So sánh tồn bãi giữa 2 ngày bất kỳ.
        
        Args:
            date1: Ngày thứ nhất (cũ hơn)
            date2: Ngày thứ hai (mới hơn)
        
        Returns:
            Dict với keys: 'moi_vao' (chỉ có ở date2), 'da_roi' (chỉ có ở date1), 'van_ton' (có ở cả 2)
        """
        df1 = self.get_snapshot_for_date(date1)
        df2 = self.get_snapshot_for_date(date2)
        
        if df1.empty or df2.empty:
            logging.warning("Một trong hai ngày không có snapshot")
            return {'moi_vao': pd.DataFrame(), 'da_roi': pd.DataFrame(), 'van_ton': pd.DataFrame()}
        
        set1 = set(df1['Số Container'])
        set2 = set(df2['Số Container'])
        
        moi_vao = list(set2 - set1)
        da_roi = list(set1 - set2)
        van_ton = list(set1 & set2)
        
        return {
            'moi_vao': df2[df2['Số Container'].isin(moi_vao)],
            'da_roi': df1[df1['Số Container'].isin(da_roi)],
            'van_ton': df2[df2['Số Container'].isin(van_ton)],
            'summary': {
                'date1': date1.strftime('%Y-%m-%d'),
                'date2': date2.strftime('%Y-%m-%d'),
                'ton_1': len(df1),
                'ton_2': len(df2),
                'moi_vao': len(moi_vao),
                'da_roi': len(da_roi),
                'van_ton': len(van_ton)
            }
        }
    
    def get_inventory_trend(self, days: int = 30) -> pd.DataFrame:
        """
        Lấy xu hướng tồn bãi theo ngày (số lượng container mỗi ngày).
        
        Args:
            days: Số ngày nhìn lại
        
        Returns:
            DataFrame với cột Ngày và Số lượng
        """
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
                    snapshot_date as 'Ngày',
                    COUNT(*) as 'Số lượng container'
                FROM container_snapshots
                WHERE snapshot_date >= date('now', ?)
                GROUP BY snapshot_date
                ORDER BY snapshot_date
            """
            return pd.read_sql_query(query, conn, params=(f"-{days} days",))
    
    def get_container_timeline(self, container_id: str) -> pd.DataFrame:
        """
        Lấy toàn bộ lịch sử vào/ra của một container từ bảng transactions.
        
        Args:
            container_id: Số container
        
        Returns:
            DataFrame lịch sử giao dịch
        """
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
                    transaction_date as 'Ngày giao dịch',
                    move_type as 'Loại di chuyển',
                    source_key as 'Nguồn chứng từ',
                    phuong_an as 'Phương án',
                    fe as 'Trạng thái',
                    location as 'Vị trí bãi'
                FROM container_transactions
                WHERE container_id = ?
                ORDER BY transaction_date DESC, id DESC
            """
            return pd.read_sql_query(query, conn, params=(container_id,))
    
    def export_container_history(self, container_id: str, output_path: Optional[Path] = None) -> Path:
        """
        Xuất lịch sử một container ra file Excel.
        """
        df_snapshots = self.get_container_history(container_id, days=365)
        df_transactions = self.get_container_timeline(container_id)
        
        # Thêm STT cho cả 2 DataFrame
        if not df_snapshots.empty:
            df_snapshots.insert(0, 'STT', range(1, len(df_snapshots) + 1))
        if not df_transactions.empty:
            df_transactions.insert(0, 'STT', range(1, len(df_transactions) + 1))
        
        if output_path is None:
            output_path = self.db_path.parent / f"Lich_su_container_{container_id}.xlsx"
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df_snapshots.to_excel(writer, sheet_name='Tồn bãi theo ngày', index=False)
            df_transactions.to_excel(writer, sheet_name='Lịch sử giao dịch', index=False)
        
        logging.info(f"Đã xuất lịch sử container {container_id} ra {output_path}")
        return output_path
    
    # ========== V4.7.2: DUPLICATE TON CU DETECTION ==========
    
    def check_ton_cu_duplicate(self, df_ton_cu: pd.DataFrame) -> Dict[str, Any]:
        """
        Kiểm tra xem file TON CU có bị dùng lại từ ngày trước không.
        So sánh với các snapshot trong database.
        
        Args:
            df_ton_cu: DataFrame tồn cũ từ file
        
        Returns:
            Dict với keys:
                - 'is_duplicate': True nếu phát hiện trùng
                - 'matched_date': Ngày snapshot trùng khớp (nếu có)
                - 'match_percentage': % container trùng khớp
                - 'warning_level': 'none', 'warning', 'error'
                - 'message': Thông báo cho user
        """
        from config import Col
        
        result = {
            'is_duplicate': False,
            'matched_date': None,
            'match_percentage': 0,
            'warning_level': 'none',
            'message': ''
        }
        
        if df_ton_cu.empty:
            return result
        
        # Lấy danh sách container từ TON CU
        ton_cu_containers = set(df_ton_cu[Col.CONTAINER].astype(str).tolist())
        if not ton_cu_containers:
            return result
        
        # Lấy các snapshot gần đây để so sánh
        available_dates = self.get_available_dates(limit=7)
        
        for date_str in available_dates:
            from datetime import datetime as dt
            snapshot_date = dt.strptime(date_str, '%Y-%m-%d')
            df_snapshot = self.get_snapshot_for_date(snapshot_date)
            
            if df_snapshot.empty:
                continue
            
            snapshot_containers = set(df_snapshot['Số Container'].astype(str).tolist())
            
            # Tính % trùng khớp
            common = ton_cu_containers & snapshot_containers
            if len(ton_cu_containers) == 0:
                match_pct = 0
            else:
                match_pct = len(common) / len(ton_cu_containers) * 100
            
            # Nếu trùng >= 98% → Có thể dùng nhầm file
            if match_pct >= 98:
                result['is_duplicate'] = True
                result['matched_date'] = date_str
                result['match_percentage'] = round(match_pct, 1)
                
                # Kiểm tra ngày - nếu trùng với hôm qua thì OK, xa hơn thì cảnh báo
                from datetime import datetime, timedelta
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                
                if date_str == yesterday:
                    result['warning_level'] = 'info'
                    result['message'] = f"✓ TON CU khớp {match_pct:.0f}% với snapshot ngày {date_str} (hôm qua) - Bình thường"
                else:
                    result['warning_level'] = 'warning'
                    result['message'] = f"⚠️ CẢNH BÁO: TON CU trùng {match_pct:.0f}% với snapshot ngày {date_str}. Có thể bạn đang dùng nhầm file cũ!"
                
                return result
        
        result['message'] = "✓ TON CU không trùng với snapshot cũ nào"
        return result
    
    def check_transactions_duplicate(self, df_transactions: pd.DataFrame, source_key: str) -> Dict[str, Any]:
        """
        Kiểm tra xem file giao dịch (GATE, NHAPXUAT, SHIFTING) có bị dùng lại không.
        So sánh với các transactions trong database.
        
        Args:
            df_transactions: DataFrame giao dịch từ file
            source_key: Loại file ('gate_in', 'gate_out', 'nhap_tau', 'xuat_tau', etc.)
        
        Returns:
            Dict with duplicate detection results
        """
        from config import Col
        
        result = {
            'is_duplicate': False,
            'matched_date': None,
            'match_percentage': 0,
            'warning_level': 'none',
            'message': '',
            'source_key': source_key
        }
        
        if df_transactions.empty:
            return result
        
        # Lấy danh sách container từ file input
        if Col.CONTAINER not in df_transactions.columns:
            return result
            
        input_containers = set(df_transactions[Col.CONTAINER].astype(str).tolist())
        if not input_containers or len(input_containers) < 10:  # Quá ít để so sánh
            return result
        
        # So sánh với transactions đã lưu trong 7 ngày gần đây
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT DISTINCT transaction_date, container_id
                FROM container_transactions
                WHERE source_key LIKE ?
                AND transaction_date >= date('now', '-7 days')
                ORDER BY transaction_date DESC
            """
            df_saved = pd.read_sql_query(query, conn, params=(f"%{source_key.split('_')[0]}%",))
        
        if df_saved.empty:
            result['message'] = f"✓ {source_key}: Không có dữ liệu cũ để so sánh"
            return result
        
        # Group by date và so sánh
        for date_str in df_saved['transaction_date'].unique():
            saved_containers = set(df_saved[df_saved['transaction_date'] == date_str]['container_id'].tolist())
            
            if len(saved_containers) < 10:
                continue
            
            common = input_containers & saved_containers
            match_pct = len(common) / len(input_containers) * 100
            
            # Nếu trùng >= 90% → Cảnh báo dùng nhầm file
            if match_pct >= 90:
                result['is_duplicate'] = True
                result['matched_date'] = date_str
                result['match_percentage'] = round(match_pct, 1)
                
                from datetime import datetime, timedelta
                today = datetime.now().strftime('%Y-%m-%d')
                
                if date_str == today:
                    result['warning_level'] = 'info'
                    result['message'] = f"✓ {source_key}: Khớp {match_pct:.0f}% với giao dịch hôm nay - Bình thường"
                else:
                    result['warning_level'] = 'warning'
                    result['message'] = f"⚠️ {source_key}: Trùng {match_pct:.0f}% với giao dịch ngày {date_str}. Có thể dùng nhầm file cũ!"
                
                return result
        
        result['message'] = f"✓ {source_key}: Không phát hiện trùng lặp"
        return result
    
    def check_all_files_duplicate(self, file_dfs: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Kiểm tra tất cả các file đầu vào xem có bị dùng lại không.
        
        Args:
            file_dfs: Dictionary chứa tất cả DataFrames
        
        Returns:
            List các kết quả kiểm tra
        """
        results = []
        
        # Kiểm tra TON CU
        if 'ton_cu' in file_dfs and not file_dfs['ton_cu'].empty:
            results.append(self.check_ton_cu_duplicate(file_dfs['ton_cu']))
        
        # Kiểm tra các file giao dịch
        transaction_keys = ['gate_in', 'gate_out', 'nhap_tau', 'xuat_tau', 'nhap_shifting', 'xuat_shifting']
        for key in transaction_keys:
            if key in file_dfs and not file_dfs[key].empty:
                results.append(self.check_transactions_duplicate(file_dfs[key], key))
        
        return results








