# File: utils/file_comparator.py
# V5.4: Công cụ so sánh 2 file Excel để đối chiếu dữ liệu
"""
So sánh file BIEN DONG/TON BAI từ ứng dụng với file từ TOS Cảng.
Mục đích: Xác nhận 2 file khớp 100% hay có sai lệch.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import re


class FileComparator:
    """So sánh 2 file Excel theo số container."""
    
    # Các tên cột container có thể có
    CONTAINER_COLUMN_NAMES = [
        'Số Container', 'Container', 'CONTAINER', 'container',
        'Số Cont', 'CONT', 'ContainerNo', 'Container No',
        'Số container', 'SO_CONTAINER'
    ]
    
    def __init__(self):
        self.file1_df: Optional[pd.DataFrame] = None
        self.file2_df: Optional[pd.DataFrame] = None
        self.file1_path: Optional[Path] = None
        self.file2_path: Optional[Path] = None
        self.comparison_result: Optional[Dict] = None
    
    def _find_container_column(self, df: pd.DataFrame) -> Optional[str]:
        """Tìm cột chứa số container trong DataFrame."""
        for col_name in self.CONTAINER_COLUMN_NAMES:
            if col_name in df.columns:
                return col_name
        
        # Fallback: tìm cột có chứa "container" trong tên
        for col in df.columns:
            if 'container' in col.lower() or 'cont' in col.lower():
                return col
        
        return None
    
    def _normalize_container(self, container: str) -> str:
        """Chuẩn hóa số container (uppercase, bỏ khoảng trắng)."""
        if pd.isna(container):
            return ""
        return str(container).upper().strip().replace(" ", "")
    
    def _load_file(self, file_path: Path, sheet_name: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
        """
        Load file Excel và trả về DataFrame + tên cột container.
        
        Args:
            file_path: Đường dẫn file Excel
            sheet_name: Tên sheet (None = sheet đầu tiên)
        
        Returns:
            Tuple (DataFrame, container_column_name)
        """
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            # Thử đọc sheet đầu tiên
            df = pd.read_excel(file_path)
        
        container_col = self._find_container_column(df)
        if not container_col:
            raise ValueError(f"Không tìm thấy cột Container trong file {file_path.name}")
        
        return df, container_col
    
    def load_files(self, 
                   file1_path: str, 
                   file2_path: str,
                   sheet1: Optional[str] = None,
                   sheet2: Optional[str] = None) -> Dict:
        """
        Load 2 file để so sánh.
        
        Args:
            file1_path: File từ ứng dụng (BIEN DONG export)
            file2_path: File từ TOS Cảng
            sheet1, sheet2: Tên sheet cụ thể (optional)
        
        Returns:
            Dict với thông tin 2 file đã load
        """
        self.file1_path = Path(file1_path)
        self.file2_path = Path(file2_path)
        
        # Load file 1
        self.file1_df, self.file1_container_col = self._load_file(self.file1_path, sheet1)
        
        # Load file 2
        self.file2_df, self.file2_container_col = self._load_file(self.file2_path, sheet2)
        
        return {
            'file1': {
                'name': self.file1_path.name,
                'rows': len(self.file1_df),
                'columns': len(self.file1_df.columns),
                'container_column': self.file1_container_col
            },
            'file2': {
                'name': self.file2_path.name,
                'rows': len(self.file2_df),
                'columns': len(self.file2_df.columns),
                'container_column': self.file2_container_col
            }
        }
    
    def compare(self) -> Dict:
        """
        So sánh 2 file đã load.
        
        Returns:
            Dict chứa kết quả so sánh chi tiết
        """
        if self.file1_df is None or self.file2_df is None:
            raise ValueError("Chưa load file. Gọi load_files() trước.")
        
        # Lấy danh sách container từ mỗi file
        containers1 = set(
            self._normalize_container(c) 
            for c in self.file1_df[self.file1_container_col] 
            if self._normalize_container(c)
        )
        
        containers2 = set(
            self._normalize_container(c) 
            for c in self.file2_df[self.file2_container_col] 
            if self._normalize_container(c)
        )
        
        # So sánh
        matching = containers1 & containers2  # Giao
        only_in_file1 = containers1 - containers2  # Chỉ có trong file 1
        only_in_file2 = containers2 - containers1  # Chỉ có trong file 2
        
        # Tính phần trăm khớp
        total_unique = len(containers1 | containers2)
        match_percent = (len(matching) / total_unique * 100) if total_unique > 0 else 0
        
        # Kiểm tra khớp 100%
        is_perfect_match = len(only_in_file1) == 0 and len(only_in_file2) == 0
        
        self.comparison_result = {
            'summary': {
                'is_perfect_match': is_perfect_match,
                'match_percent': round(match_percent, 2),
                'file1_total': len(containers1),
                'file2_total': len(containers2),
                'matching_count': len(matching),
                'only_in_file1_count': len(only_in_file1),
                'only_in_file2_count': len(only_in_file2),
            },
            'details': {
                'matching': sorted(matching),
                'only_in_file1': sorted(only_in_file1),
                'only_in_file2': sorted(only_in_file2),
            },
            'files': {
                'file1': self.file1_path.name,
                'file2': self.file2_path.name,
            }
        }
        
        return self.comparison_result
    
    def get_summary_text(self) -> str:
        """Tạo text tóm tắt kết quả so sánh."""
        if not self.comparison_result:
            return "Chưa có kết quả so sánh."
        
        r = self.comparison_result
        s = r['summary']
        
        lines = [
            "=" * 50,
            "📊 KẾT QUẢ SO SÁNH 2 FILE",
            "=" * 50,
            "",
            f"📁 File 1 (Ứng dụng): {r['files']['file1']}",
            f"📁 File 2 (TOS Cảng): {r['files']['file2']}",
            "",
            "-" * 50,
            "",
        ]
        
        if s['is_perfect_match']:
            lines.extend([
                "✅ KẾT QUẢ: KHỚP 100%",
                "",
                f"   Tổng container: {s['matching_count']}",
            ])
        else:
            lines.extend([
                f"⚠️ KẾT QUẢ: KHỚP {s['match_percent']}%",
                "",
                f"   📊 File 1: {s['file1_total']} container",
                f"   📊 File 2: {s['file2_total']} container",
                "",
                f"   ✅ Khớp nhau: {s['matching_count']} container",
                f"   ❌ Chỉ có trong File 1: {s['only_in_file1_count']} container",
                f"   ❌ Chỉ có trong File 2: {s['only_in_file2_count']} container",
            ])
            
            # Hiển thị chi tiết nếu có sai lệch
            if s['only_in_file1_count'] > 0:
                lines.append("")
                lines.append("📋 Container CHỈ CÓ trong File 1 (thiếu trong TOS):")
                for cont in r['details']['only_in_file1'][:10]:
                    lines.append(f"   • {cont}")
                if s['only_in_file1_count'] > 10:
                    lines.append(f"   ... và {s['only_in_file1_count'] - 10} container khác")
            
            if s['only_in_file2_count'] > 0:
                lines.append("")
                lines.append("📋 Container CHỈ CÓ trong File 2 (thiếu trong App):")
                for cont in r['details']['only_in_file2'][:10]:
                    lines.append(f"   • {cont}")
                if s['only_in_file2_count'] > 10:
                    lines.append(f"   ... và {s['only_in_file2_count'] - 10} container khác")
        
        lines.extend([
            "",
            "-" * 50,
            f"⏰ Thời gian so sánh: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            "=" * 50,
        ])
        
        return "\n".join(lines)
    
    def export_comparison_report(self, output_path: Optional[str] = None) -> Path:
        """
        Xuất báo cáo so sánh ra file Excel.
        
        Args:
            output_path: Đường dẫn output (optional, tự tạo nếu không có)
        
        Returns:
            Path của file báo cáo
        """
        if not self.comparison_result:
            raise ValueError("Chưa có kết quả so sánh. Gọi compare() trước.")
        
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = Path(f"Comparison_Report_{timestamp}.xlsx")
        else:
            output_path = Path(output_path)
        
        r = self.comparison_result
        s = r['summary']
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Sheet 1: Summary
            summary_data = {
                'Chỉ số': [
                    'Kết quả',
                    'Tỷ lệ khớp (%)',
                    'File 1 - Tổng container',
                    'File 2 - Tổng container',
                    'Container khớp nhau',
                    'Chỉ có trong File 1',
                    'Chỉ có trong File 2',
                    '',
                    'File 1',
                    'File 2',
                ],
                'Giá trị': [
                    'KHỚP 100%' if s['is_perfect_match'] else f"KHỚP {s['match_percent']}%",
                    s['match_percent'],
                    s['file1_total'],
                    s['file2_total'],
                    s['matching_count'],
                    s['only_in_file1_count'],
                    s['only_in_file2_count'],
                    '',
                    r['files']['file1'],
                    r['files']['file2'],
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Tóm tắt', index=False)
            
            # Sheet 2: Matching containers
            if r['details']['matching']:
                pd.DataFrame({'Container khớp': r['details']['matching']}).to_excel(
                    writer, sheet_name='Khớp', index=False
                )
            
            # Sheet 3: Only in File 1
            if r['details']['only_in_file1']:
                pd.DataFrame({'Chỉ có trong File 1': r['details']['only_in_file1']}).to_excel(
                    writer, sheet_name='Chỉ File 1', index=False
                )
            
            # Sheet 4: Only in File 2
            if r['details']['only_in_file2']:
                pd.DataFrame({'Chỉ có trong File 2': r['details']['only_in_file2']}).to_excel(
                    writer, sheet_name='Chỉ File 2', index=False
                )
        
        logging.info(f"[Comparator] Exported report to {output_path}")
        return output_path


def compare_two_files(file1: str, file2: str, 
                      sheet1: Optional[str] = None, 
                      sheet2: Optional[str] = None) -> Dict:
    """
    Hàm tiện ích để so sánh nhanh 2 file.
    
    Args:
        file1: Đường dẫn file 1 (từ ứng dụng)
        file2: Đường dẫn file 2 (từ TOS)
        sheet1, sheet2: Tên sheet (optional)
    
    Returns:
        Dict kết quả so sánh
    
    Example:
        >>> result = compare_two_files(
        ...     "BIEN DONG - VIMC Lines - N12.1.2026.xlsx",
        ...     "TOS_Export_VIMC_12012026.xlsx"
        ... )
        >>> print(f"Khớp: {result['summary']['match_percent']}%")
    """
    comparator = FileComparator()
    comparator.load_files(file1, file2, sheet1, sheet2)
    return comparator.compare()


# === CLI Interface ===
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python file_comparator.py <file1> <file2> [output_report.xlsx]")
        print("\nExample:")
        print('  python file_comparator.py "BIEN DONG - VIMC.xlsx" "TOS_Export.xlsx"')
        sys.exit(1)
    
    file1 = sys.argv[1]
    file2 = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) > 3 else None
    
    comparator = FileComparator()
    
    print(f"Loading {file1}...")
    print(f"Loading {file2}...")
    
    try:
        comparator.load_files(file1, file2)
        comparator.compare()
        
        print(comparator.get_summary_text())
        
        if output:
            report_path = comparator.export_comparison_report(output)
            print(f"\n📁 Báo cáo chi tiết: {report_path}")
    
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        sys.exit(1)
