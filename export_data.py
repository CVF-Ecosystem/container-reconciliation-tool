"""
Export Data Utility - Trích xuất dữ liệu từ database lịch sử
V4.7.2 - 2026-01-08

Sử dụng:
    python export_data.py --help
    python export_data.py snapshot --start 2026-01-01 --end 2026-01-08
    python export_data.py compare --date1 2026-01-05 --date2 2026-01-08
    python export_data.py container --id ABCD1234567
    python export_data.py trend --days 30
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.history_db import HistoryDatabase


def parse_date(date_str: str) -> datetime:
    """Parse date string in format YYYY-MM-DD"""
    return datetime.strptime(date_str, '%Y-%m-%d')


def export_snapshot_range(db: HistoryDatabase, args):
    """Xuất snapshot theo khoảng thời gian"""
    start = parse_date(args.start)
    end = parse_date(args.end)
    output_path = db.export_snapshot_range(start, end)
    logging.info(f"✓ Đã xuất snapshot từ {args.start} đến {args.end}")
    logging.info(f"  File: {output_path}")


def compare_dates(db: HistoryDatabase, args):
    """So sánh tồn bãi 2 ngày"""
    date1 = parse_date(args.date1)
    date2 = parse_date(args.date2)
    result = db.compare_two_dates(date1, date2)
    
    summary = result.get('summary', {})
    logging.info(f"\n=== So sánh {args.date1} vs {args.date2} ===")
    logging.info(f"  Tồn ngày {args.date1}: {summary.get('ton_1', 0)} container")
    logging.info(f"  Tồn ngày {args.date2}: {summary.get('ton_2', 0)} container")
    logging.info(f"  Mới vào:  {summary.get('moi_vao', 0)}")
    logging.info(f"  Đã rời:   {summary.get('da_roi', 0)}")
    logging.info(f"  Vẫn tồn:  {summary.get('van_ton', 0)}")
    
    # Export to Excel if requested
    if args.export:
        from pathlib import Path
        import pandas as pd
        output_path = Path('data_output') / f"compare_{args.date1}_vs_{args.date2}.xlsx"
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            result['moi_vao'].to_excel(writer, sheet_name='Mới vào', index=False)
            result['da_roi'].to_excel(writer, sheet_name='Đã rời', index=False)
            result['van_ton'].to_excel(writer, sheet_name='Vẫn tồn', index=False)
        print(f"  Đã xuất chi tiết: {output_path}")


def export_container_history(db: HistoryDatabase, args):
    """Xuất lịch sử container"""
    output_path = db.export_container_history(args.id)
    print(f"✓ Đã xuất lịch sử container {args.id}")
    print(f"  File: {output_path}")


def show_trend(db: HistoryDatabase, args):
    """Hiển thị xu hướng tồn bãi"""
    df = db.get_inventory_trend(days=args.days)
    
    print(f"\n=== Xu hướng tồn bãi {args.days} ngày gần đây ===")
    if df.empty:
        print("  Không có dữ liệu")
    else:
        for _, row in df.iterrows():
            print(f"  {row['Ngày']}: {row['Số lượng container']:,} container")
    
    if args.export:
        output_path = Path('data_output') / f"trend_{args.days}_days.xlsx"
        df.to_excel(output_path, index=False, engine='openpyxl')
        print(f"\n  Đã xuất: {output_path}")


def list_available_dates(db: HistoryDatabase, args):
    """Liệt kê các ngày có snapshot"""
    dates = db.get_available_dates(limit=30)
    print(f"\n=== Các ngày có snapshot ({len(dates)} ngày) ===")
    for d in dates:
        print(f"  - {d}")


def main():
    parser = argparse.ArgumentParser(
        description='Export Data Utility - Trích xuất dữ liệu từ database lịch sử',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python export_data.py list
  python export_data.py snapshot --start 2026-01-01 --end 2026-01-08
  python export_data.py compare --date1 2026-01-05 --date2 2026-01-08 --export
  python export_data.py container --id ABCD1234567
  python export_data.py trend --days 30 --export
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Các lệnh có sẵn')
    
    # Command: list
    list_parser = subparsers.add_parser('list', help='Liệt kê các ngày có snapshot')
    
    # Command: snapshot
    snap_parser = subparsers.add_parser('snapshot', help='Xuất snapshot theo khoảng thời gian')
    snap_parser.add_argument('--start', required=True, help='Ngày bắt đầu (YYYY-MM-DD)')
    snap_parser.add_argument('--end', required=True, help='Ngày kết thúc (YYYY-MM-DD)')
    
    # Command: compare
    comp_parser = subparsers.add_parser('compare', help='So sánh tồn bãi 2 ngày')
    comp_parser.add_argument('--date1', required=True, help='Ngày thứ nhất (YYYY-MM-DD)')
    comp_parser.add_argument('--date2', required=True, help='Ngày thứ hai (YYYY-MM-DD)')
    comp_parser.add_argument('--export', action='store_true', help='Xuất chi tiết ra Excel')
    
    # Command: container
    cont_parser = subparsers.add_parser('container', help='Xuất lịch sử container')
    cont_parser.add_argument('--id', required=True, help='Số container')
    
    # Command: trend
    trend_parser = subparsers.add_parser('trend', help='Xu hướng tồn bãi')
    trend_parser.add_argument('--days', type=int, default=30, help='Số ngày (mặc định: 30)')
    trend_parser.add_argument('--export', action='store_true', help='Xuất ra Excel')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize database
    db = HistoryDatabase(Path('data_output'))
    
    # Execute command
    if args.command == 'list':
        list_available_dates(db, args)
    elif args.command == 'snapshot':
        export_snapshot_range(db, args)
    elif args.command == 'compare':
        compare_dates(db, args)
    elif args.command == 'container':
        export_container_history(db, args)
    elif args.command == 'trend':
        show_trend(db, args)


if __name__ == '__main__':
    main()
