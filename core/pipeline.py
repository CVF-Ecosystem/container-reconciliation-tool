# File: core/pipeline.py — @2026 v1.0
"""
Reconciliation Pipeline using the Pipeline/Chain-of-Responsibility pattern.

Replaces the monolithic run_full_reconciliation_process() function with
composable, testable pipeline steps.

Usage:
    pipeline = ReconciliationPipeline()
    result = pipeline.run(PipelineContext(input_dir=..., output_dir=...))
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
import pandas as pd

from utils.exceptions import (
    DataLoadError, ValidationError, ReconciliationError, ReportGenerationError
)


# ============ PIPELINE CONTEXT ============

@dataclass
class PipelineContext:
    """
    Shared context passed between pipeline steps.
    
    Each step reads from and writes to this context.
    """
    # Inputs
    input_dir: Path
    output_dir: Path
    
    # Callbacks for GUI integration
    update_status: Optional[Callable[[str], None]] = None
    update_progress: Optional[Callable[[int], None]] = None
    confirm_missing_ton_cu: Optional[Callable[[str], bool]] = None
    
    # Runtime state (populated by steps)
    run_time: datetime = field(default_factory=datetime.now)
    report_folder: Optional[Path] = None
    files_to_process: Dict[str, str] = field(default_factory=dict)
    file_dfs: Dict[str, pd.DataFrame] = field(default_factory=dict)
    ton_cu_from_db: Optional[pd.DataFrame] = None
    quality_warnings: List[str] = field(default_factory=list)
    main_results: Dict[str, Any] = field(default_factory=dict)
    simple_results: Dict[str, Any] = field(default_factory=dict)
    inventory_change_results: Dict[str, Any] = field(default_factory=dict)
    operator_analysis_result: Dict[str, Any] = field(default_factory=dict)
    delta_analysis_result: Any = None
    v51_check_results: Dict[str, Any] = field(default_factory=dict)
    current_summary_df: Optional[pd.DataFrame] = None
    final_results: Dict[str, Any] = field(default_factory=dict)
    
    def notify(self, message: str, progress: Optional[int] = None):
        """Send status update and optional progress."""
        logging.info(message)
        if self.update_status:
            self.update_status(message)
        if progress is not None and self.update_progress:
            self.update_progress(progress)


# ============ PIPELINE STEP BASE ============

class PipelineStep(ABC):
    """Abstract base class for pipeline steps."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Step name for logging."""
        pass
    
    @abstractmethod
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        """
        Execute this step.
        
        Args:
            ctx: Pipeline context with current state
            
        Returns:
            Updated pipeline context
            
        Raises:
            Any exception to abort the pipeline
        """
        pass
    
    def __repr__(self):
        return f"<{self.__class__.__name__}>"


# ============ CONCRETE STEPS ============

class SetupStep(PipelineStep):
    """Step 1: Setup output directory and run timestamp."""
    
    @property
    def name(self) -> str:
        return "Setup"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Bắt đầu quy trình đối soát...", progress=0)
        
        date_part = ctx.run_time.strftime("N%d.%m.%Y")
        time_part = ctx.run_time.strftime("%Hh%M")
        ctx.report_folder = ctx.output_dir / f"Report_{date_part}_{time_part}"
        ctx.report_folder.mkdir(parents=True, exist_ok=True)
        
        return ctx


class FindFilesStep(PipelineStep):
    """Step 2: Scan input directory for data files."""
    
    @property
    def name(self) -> str:
        return "FindFiles"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang tìm kiếm file đầu vào...", progress=5)
        
        from core_logic import find_input_files_from_dir
        ctx.files_to_process = find_input_files_from_dir(ctx.input_dir)
        
        if not ctx.files_to_process:
            raise DataLoadError(
                "Không tìm thấy các file đầu vào cần thiết.",
                {"input_dir": str(ctx.input_dir)}
            )
        
        return ctx


class HandleMissingTonCuStep(PipelineStep):
    """Step 3: Handle missing TON CU file (load from DB if available)."""
    
    @property
    def name(self) -> str:
        return "HandleMissingTonCu"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        if 'ton_cu' in ctx.files_to_process:
            return ctx  # TON CU file exists, skip
        
        ctx.notify("⚠️ CẢNH BÁO: Không tìm thấy file TON CU!", progress=8)
        
        from utils.history_db import HistoryDatabase
        history_db = HistoryDatabase(ctx.output_dir)
        available_dates = history_db.get_available_dates(limit=1)
        
        if available_dates:
            msg = f"Không tìm thấy file TON CU.\nCó snapshot ngày {available_dates[0]} trong database.\nBạn muốn sử dụng snapshot này làm TON CU?"
        else:
            msg = "Không tìm thấy file TON CU và không có snapshot trong database.\nBạn có muốn tiếp tục mà không có TON CU?"
        
        if ctx.confirm_missing_ton_cu:
            user_confirmed = ctx.confirm_missing_ton_cu(msg)
            if not user_confirmed:
                raise DataLoadError(
                    "Người dùng hủy vì thiếu file TON CU.",
                    {"action": "user_cancelled"}
                )
            if available_dates:
                ctx.ton_cu_from_db = history_db.get_yesterday_as_ton_cu()
                if ctx.ton_cu_from_db is not None and ctx.ton_cu_from_db.empty:
                    from datetime import datetime as dt
                    latest_date = dt.strptime(available_dates[0], '%Y-%m-%d')
                    ctx.ton_cu_from_db = history_db.get_snapshot_for_date(latest_date)
                if ctx.ton_cu_from_db is not None:
                    ctx.notify(f"Đã tải {len(ctx.ton_cu_from_db)} container từ database làm TON CU")
        else:
            logging.warning("Thiếu file TON CU, tiếp tục mà không có confirm callback")
        
        return ctx


class LoadDataStep(PipelineStep):
    """Step 4: Load and transform all data files (with parallel loading if available)."""
    
    @property
    def name(self) -> str:
        return "LoadData"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang tải và làm sạch dữ liệu...", progress=10)
        
        # Try parallel loading first (faster for multiple files)
        try:
            from data.parallel_loader import load_all_data_parallel
            ctx.file_dfs = load_all_data_parallel(
                ctx.files_to_process, ctx.input_dir, ctx.report_folder
            )
            logging.info("Data loaded using parallel loader")
        except (ImportError, AttributeError, Exception) as e:
            logging.debug(f"Parallel loader unavailable ({e}), using sequential loader")
            from data.data_loader import load_all_data
            ctx.file_dfs = load_all_data(ctx.files_to_process, ctx.input_dir, ctx.report_folder)
        
        if ctx.ton_cu_from_db is not None and not ctx.ton_cu_from_db.empty:
            ctx.file_dfs['ton_cu'] = ctx.ton_cu_from_db
            logging.info(f"Đã sử dụng {len(ctx.ton_cu_from_db)} container từ database làm TON CU")
        
        return ctx


class ValidateDataStep(PipelineStep):
    """Step 5: Validate data structure and quality."""
    
    @property
    def name(self) -> str:
        return "ValidateData"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang kiểm tra chất lượng dữ liệu...", progress=30)
        
        from data.data_validator import validate_dataframes_structure, validate_dataframes_quality
        from config import REQUIRED_COLUMNS_PER_FILE, DATA_VALIDATION_RULES
        
        if not validate_dataframes_structure(ctx.file_dfs, REQUIRED_COLUMNS_PER_FILE):
            raise ValidationError(
                "Dữ liệu không đủ cấu trúc tối thiểu.",
                {"missing_files": [k for k, v in ctx.file_dfs.items() if v.empty]}
            )
        
        ctx.quality_warnings = validate_dataframes_quality(ctx.file_dfs, DATA_VALIDATION_RULES)
        
        # Check for duplicate files
        try:
            from utils.history_db import HistoryDatabase
            history_db = HistoryDatabase(ctx.output_dir)
            dup_results = history_db.check_all_files_duplicate(ctx.file_dfs)
            warnings_found = 0
            for dup_check in dup_results:
                if dup_check['warning_level'] == 'warning':
                    ctx.notify(dup_check['message'])
                    logging.warning(dup_check['message'])
                    warnings_found += 1
                elif dup_check['warning_level'] == 'info':
                    logging.info(dup_check['message'])
            if warnings_found > 0:
                ctx.notify(f"⚠️ Phát hiện {warnings_found} file có thể bị dùng nhầm!")
        except Exception as e:
            logging.debug(f"Could not check file duplicates: {e}")
        
        return ctx


class ReconcileStep(PipelineStep):
    """Step 6: Run main reconciliation (Rule Engine)."""
    
    @property
    def name(self) -> str:
        return "Reconcile"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang chạy đối soát chính (Rule Engine)...", progress=40)
        
        from core.reconciliation_engine import perform_reconciliation
        ctx.main_results = perform_reconciliation(ctx.file_dfs, ctx.report_folder, ctx.run_time)
        
        if not ctx.main_results:
            raise ReconciliationError(
                "Quá trình đối soát chính không thành công.",
                {"step": "perform_reconciliation", "run_time": str(ctx.run_time)}
            )
        
        return ctx


class CrossCheckStep(PipelineStep):
    """Step 7: Cross-check with SourceKey method."""
    
    @property
    def name(self) -> str:
        return "CrossCheck"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang chạy kiểm tra chéo (SourceKey)...", progress=60)
        
        from core.advanced_checker import perform_simple_reconciliation
        ctx.simple_results = perform_simple_reconciliation(ctx.file_dfs)
        
        return ctx


class AnalyzeStep(PipelineStep):
    """Step 8: Analyze inventory changes and operators."""
    
    @property
    def name(self) -> str:
        return "Analyze"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang phân tích biến động tồn bãi...", progress=70)
        
        from core.inventory_checker import compare_inventories
        from reports.operator_analyzer import analyze_by_operator
        from core.duplicate_checker import run_all_duplicate_checks
        
        ctx.inventory_change_results = compare_inventories(ctx.file_dfs)
        ctx.operator_analysis_result = analyze_by_operator(ctx.file_dfs)
        
        ctx.notify("Đang chạy kiểm tra lỗi nâng cao...", progress=75)
        ctx.v51_check_results = run_all_duplicate_checks(ctx.file_dfs)
        
        return ctx


class SummarizeStep(PipelineStep):
    """Step 9: Create summary DataFrame and delta analysis."""
    
    @property
    def name(self) -> str:
        return "Summarize"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang tạo tóm tắt và phân tích Delta...", progress=80)
        
        from core_logic import create_summary_dataframe
        from core.delta_checker import perform_delta_analysis
        import config
        
        ctx.current_summary_df = create_summary_dataframe(
            ctx.main_results, ctx.simple_results, ctx.inventory_change_results
        )
        
        ctx.delta_analysis_result = perform_delta_analysis(
            ctx.current_summary_df.set_index('Hang muc'),
            config.OUTPUT_DIR,
            ctx.report_folder.name
        )
        
        return ctx


class BuildResultsStep(PipelineStep):
    """Step 10: Assemble final results dictionary."""
    
    @property
    def name(self) -> str:
        return "BuildResults"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.main_results['v51_checks'] = ctx.v51_check_results
        
        ctx.final_results = {
            "main_results": ctx.main_results,
            "simple_results": ctx.simple_results,
            "inventory_change_results": ctx.inventory_change_results,
            "operator_analysis_result": ctx.operator_analysis_result,
            "delta_analysis_result": ctx.delta_analysis_result,
            "summary_df": ctx.current_summary_df,
            "quality_warnings": ctx.quality_warnings,
            "report_folder": ctx.report_folder,
            "run_timestamp": ctx.run_time
        }
        
        return ctx


class GenerateReportsStep(PipelineStep):
    """Step 11: Generate Excel reports."""
    
    @property
    def name(self) -> str:
        return "GenerateReports"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang tạo các file báo cáo...", progress=85)
        
        from reports.report_generator import create_reports
        create_reports(ctx.final_results)
        
        return ctx


class NotifyAndSaveStep(PipelineStep):
    """Step 12: Send email, save results, update history DB."""
    
    @property
    def name(self) -> str:
        return "NotifyAndSave"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        ctx.notify("Đang gửi email và lưu kết quả dashboard...", progress=90)
        
        from reports.email_notifier import send_report_email
        from core_logic import save_results
        from utils.cache_utils import save_cache_metadata, get_input_files_hashes
        
        send_report_email(ctx.report_folder, ctx.current_summary_df)
        save_results(ctx.final_results, ctx.output_dir)
        
        try:
            from utils.history_db import HistoryDatabase
            history_db = HistoryDatabase(ctx.output_dir)
            history_db.save_run(ctx.final_results)
            
            df_ton_moi = ctx.file_dfs.get('ton_moi', pd.DataFrame())
            if not df_ton_moi.empty:
                snapshot_count = history_db.save_daily_snapshot(df_ton_moi, ctx.run_time)
                ctx.notify(f"Đã lưu snapshot {snapshot_count} container...")
            
            df_master_log = ctx.main_results.get('master_log', pd.DataFrame())
            if not df_master_log.empty:
                trans_count = history_db.save_transactions(df_master_log, ctx.run_time)
                ctx.notify(f"Đã lưu {trans_count} giao dịch vào lịch sử...")
            
            save_cache_metadata(ctx.output_dir, get_input_files_hashes(ctx.input_dir))
        except Exception as e:
            logging.warning(f"Could not save to history database: {e}")
        
        ctx.notify("Hoàn tất!", progress=100)
        return ctx


# ============ PIPELINE ============

class ReconciliationPipeline:
    """
    Orchestrates the full reconciliation workflow as a series of steps.
    
    Each step is independent and testable. Steps can be added, removed,
    or replaced without modifying other steps.
    
    Usage:
        pipeline = ReconciliationPipeline()
        ctx = pipeline.run(PipelineContext(
            input_dir=Path('./data_input'),
            output_dir=Path('./data_output')
        ))
        print(f"Report saved to: {ctx.report_folder}")
    """
    
    DEFAULT_STEPS = [
        SetupStep,
        FindFilesStep,
        HandleMissingTonCuStep,
        LoadDataStep,
        ValidateDataStep,
        ReconcileStep,
        CrossCheckStep,
        AnalyzeStep,
        SummarizeStep,
        BuildResultsStep,
        GenerateReportsStep,
        NotifyAndSaveStep,
    ]
    
    def __init__(self, steps: Optional[List] = None):
        """
        Initialize pipeline with steps.
        
        Args:
            steps: List of PipelineStep classes. Defaults to DEFAULT_STEPS.
        """
        step_classes = steps or self.DEFAULT_STEPS
        self.steps: List[PipelineStep] = [cls() for cls in step_classes]
    
    def run(self, ctx: PipelineContext) -> PipelineContext:
        """
        Execute all pipeline steps in order.
        
        Args:
            ctx: Initial pipeline context
            
        Returns:
            Final pipeline context with all results
            
        Raises:
            Any exception from a step will abort the pipeline
        """
        logging.info(f"Starting ReconciliationPipeline with {len(self.steps)} steps")
        
        for i, step in enumerate(self.steps):
            try:
                logging.info(f"[{i+1}/{len(self.steps)}] Executing step: {step.name}")
                ctx = step.execute(ctx)
            except (DataLoadError, ValidationError, ReconciliationError, ReportGenerationError):
                raise  # Re-raise known exceptions
            except Exception as e:
                logging.error(f"Step '{step.name}' failed: {e}", exc_info=True)
                raise ReconciliationError(
                    f"Pipeline step '{step.name}' failed: {e}",
                    {"step": step.name, "error": str(e)}
                )
        
        logging.info("ReconciliationPipeline completed successfully")
        return ctx
    
    def add_step(self, step: PipelineStep, position: Optional[int] = None):
        """Add a step to the pipeline."""
        if position is None:
            self.steps.append(step)
        else:
            self.steps.insert(position, step)
    
    def remove_step(self, step_name: str) -> bool:
        """Remove a step by name."""
        for i, step in enumerate(self.steps):
            if step.name == step_name:
                self.steps.pop(i)
                return True
        return False
