# File: utils/performance_check.py
# @2026 v1.0: Performance analysis script for key operations
"""
Performance Analysis Module.

Provides functions to profile and analyze performance of key operations
in the Container Inventory Reconciliation Tool.

Usage:
    from utils.performance_check import run_performance_analysis
    report = run_performance_analysis("path/to/data_input")
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from utils.profiler import (
    PerformanceProfiler,
    Timer,
    benchmark,
    get_profiling_summary,
    export_profiling_report,
    clear_profiling_results
)


def profile_excel_loading(file_path: Path, **read_kwargs) -> Dict[str, Any]:
    """
    Profile Excel file loading performance.
    
    Args:
        file_path: Path to Excel file
        **read_kwargs: Additional arguments for pd.read_excel
        
    Returns:
        Dictionary with profiling results including:
        - elapsed_ms: Time to load file
        - rows: Number of rows loaded
        - columns: Number of columns
        - file_size_mb: File size in MB
    """
    import pandas as pd
    
    file_size_mb = file_path.stat().st_size / (1024 * 1024) if file_path.exists() else 0
    
    with PerformanceProfiler(
        f"load_excel:{file_path.name}",
        track_memory=True,
        metadata={"file_size_mb": file_size_mb}
    ) as p:
        df = pd.read_excel(file_path, **read_kwargs)
    
    return {
        "file": file_path.name,
        "elapsed_ms": p.elapsed_ms,
        "rows": len(df),
        "columns": len(df.columns),
        "file_size_mb": round(file_size_mb, 2),
        "memory_peak_mb": p.result.memory_peak_mb,
        "ms_per_1000_rows": p.elapsed_ms / (len(df) / 1000) if len(df) > 0 else 0
    }


def profile_dataframe_operations(df, operations: List[str] = None) -> Dict[str, Any]:
    """
    Profile common DataFrame operations.
    
    Args:
        df: pandas DataFrame to test
        operations: List of operations to profile. Options:
            - 'sort': Sort by first column
            - 'filter': Filter rows
            - 'groupby': Group and aggregate
            - 'merge': Self-merge
            - 'copy': Deep copy
        
    Returns:
        Dictionary with timing for each operation
    """
    import pandas as pd
    
    if operations is None:
        operations = ['sort', 'filter', 'groupby', 'copy']
    
    results = {"rows": len(df), "columns": len(df.columns)}
    
    if 'sort' in operations and len(df.columns) > 0:
        with PerformanceProfiler("df_sort", track_memory=False) as p:
            _ = df.sort_values(by=df.columns[0])
        results['sort_ms'] = p.elapsed_ms
    
    if 'filter' in operations and len(df) > 0:
        with PerformanceProfiler("df_filter", track_memory=False) as p:
            _ = df[df.index % 2 == 0]  # Filter even indices
        results['filter_ms'] = p.elapsed_ms
    
    if 'groupby' in operations and len(df.columns) > 0:
        with PerformanceProfiler("df_groupby", track_memory=False) as p:
            _ = df.groupby(df.columns[0]).size()
        results['groupby_ms'] = p.elapsed_ms
    
    if 'copy' in operations:
        with PerformanceProfiler("df_copy", track_memory=True) as p:
            _ = df.copy(deep=True)
        results['copy_ms'] = p.elapsed_ms
        results['copy_memory_mb'] = p.result.memory_peak_mb
    
    return results


def profile_reconciliation_logic(
    df_ton_moi: 'pd.DataFrame',
    df_gate: 'pd.DataFrame',
    container_column: str = 'Số Container'
) -> Dict[str, Any]:
    """
    Profile the core reconciliation comparison logic.
    
    Args:
        df_ton_moi: Main inventory DataFrame
        df_gate: Gate movement DataFrame  
        container_column: Name of container ID column
        
    Returns:
        Dictionary with profiling results for reconciliation steps
    """
    import pandas as pd
    
    results = {
        "ton_moi_rows": len(df_ton_moi),
        "gate_rows": len(df_gate)
    }
    
    timer = Timer().start()
    
    # Step 1: Normalize container IDs
    timer.lap("start")
    
    if container_column in df_ton_moi.columns:
        with PerformanceProfiler("normalize_containers_1", track_memory=False) as p:
            ton_containers = set(df_ton_moi[container_column].dropna().str.strip().str.upper())
        results['normalize_ton_ms'] = p.elapsed_ms
        results['unique_ton_containers'] = len(ton_containers)
    
    if container_column in df_gate.columns:
        with PerformanceProfiler("normalize_containers_2", track_memory=False) as p:
            gate_containers = set(df_gate[container_column].dropna().str.strip().str.upper())
        results['normalize_gate_ms'] = p.elapsed_ms
        results['unique_gate_containers'] = len(gate_containers)
    
    # Step 2: Set operations for comparison
    if container_column in df_ton_moi.columns and container_column in df_gate.columns:
        with PerformanceProfiler("set_difference", track_memory=False) as p:
            only_in_ton = ton_containers - gate_containers
            only_in_gate = gate_containers - ton_containers
            in_both = ton_containers & gate_containers
        
        results['set_operations_ms'] = p.elapsed_ms
        results['only_in_ton'] = len(only_in_ton)
        results['only_in_gate'] = len(only_in_gate)
        results['in_both'] = len(in_both)
    
    timer.stop()
    results['total_ms'] = timer.elapsed_ms
    
    return results


def profile_report_generation(
    df: 'pd.DataFrame',
    output_path: Path,
    include_charts: bool = False
) -> Dict[str, Any]:
    """
    Profile Excel report generation performance.
    
    Args:
        df: DataFrame to export
        output_path: Path for output Excel file
        include_charts: Whether to include chart generation
        
    Returns:
        Dictionary with timing results
    """
    import pandas as pd
    
    results = {"rows": len(df), "columns": len(df.columns)}
    
    with PerformanceProfiler("report_to_excel", track_memory=True) as p:
        df.to_excel(output_path, index=False)
    
    results['excel_export_ms'] = p.elapsed_ms
    results['memory_peak_mb'] = p.result.memory_peak_mb
    
    if output_path.exists():
        results['output_size_mb'] = output_path.stat().st_size / (1024 * 1024)
    
    return results


def run_performance_analysis(
    data_input_path: Path = None,
    output_report_path: Path = None
) -> Dict[str, Any]:
    """
    Run comprehensive performance analysis on the application.
    
    Args:
        data_input_path: Path to data_input folder with Excel files
        output_report_path: Path to save JSON performance report
        
    Returns:
        Dictionary with comprehensive performance analysis results
    """
    import pandas as pd
    
    clear_profiling_results()
    
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "excel_loading": [],
        "dataframe_operations": [],
        "reconciliation": None,
        "summary": None
    }
    
    # Find Excel files to analyze
    if data_input_path and data_input_path.exists():
        excel_files = list(data_input_path.rglob("*.xlsx"))[:5]  # Limit to 5 files
        
        for excel_file in excel_files:
            try:
                result = profile_excel_loading(excel_file)
                analysis["excel_loading"].append(result)
                
                # Also profile DataFrame operations on this data
                df = pd.read_excel(excel_file)
                if len(df) > 0:
                    df_result = profile_dataframe_operations(df)
                    df_result['file'] = excel_file.name
                    analysis["dataframe_operations"].append(df_result)
                    
            except Exception as e:
                logging.warning(f"Could not profile {excel_file}: {e}")
    
    # Get overall summary
    analysis["summary"] = get_profiling_summary()
    
    # Export report if path provided
    if output_report_path:
        export_profiling_report(output_report_path)
    
    return analysis


def print_performance_report(analysis: Dict[str, Any]) -> None:
    """
    Print a formatted performance report to console.
    
    Args:
        analysis: Performance analysis dictionary from run_performance_analysis
    """
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE ANALYSIS REPORT")
    print("=" * 60)
    print(f"Timestamp: {analysis.get('timestamp', 'N/A')}")
    
    # Excel Loading
    if analysis.get("excel_loading"):
        print("\n📁 Excel Loading Performance:")
        print("-" * 40)
        for item in analysis["excel_loading"]:
            print(f"  {item['file']}:")
            print(f"    - Time: {item['elapsed_ms']:.0f}ms")
            print(f"    - Rows: {item['rows']:,}")
            print(f"    - Size: {item['file_size_mb']:.2f}MB")
            print(f"    - Speed: {item['ms_per_1000_rows']:.1f}ms/1000 rows")
    
    # DataFrame Operations
    if analysis.get("dataframe_operations"):
        print("\n🔧 DataFrame Operations (avg):")
        print("-" * 40)
        ops = analysis["dataframe_operations"]
        if ops:
            avg_sort = sum(o.get('sort_ms', 0) for o in ops) / len(ops)
            avg_filter = sum(o.get('filter_ms', 0) for o in ops) / len(ops)
            avg_groupby = sum(o.get('groupby_ms', 0) for o in ops) / len(ops)
            print(f"  Sort:    {avg_sort:.1f}ms avg")
            print(f"  Filter:  {avg_filter:.1f}ms avg")
            print(f"  GroupBy: {avg_groupby:.1f}ms avg")
    
    # Summary
    if analysis.get("summary"):
        summary = analysis["summary"]
        print("\n📈 Summary:")
        print("-" * 40)
        print(f"  Total Operations: {summary.get('total_operations', 0)}")
        print(f"  Total Time: {summary.get('total_time_ms', 0):.0f}ms")
        
        if summary.get("slowest_operations"):
            print("\n  ⚠️ Slowest Operations:")
            for op in summary["slowest_operations"][:3]:
                print(f"    - {op['name']}: {op['elapsed_ms']:.0f}ms")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Example usage
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    data_path = Path("data_input") if len(sys.argv) < 2 else Path(sys.argv[1])
    
    if data_path.exists():
        print(f"Analyzing performance for: {data_path}")
        analysis = run_performance_analysis(data_path)
        print_performance_report(analysis)
    else:
        print(f"Data path not found: {data_path}")
        print("Usage: python performance_check.py [data_input_path]")
