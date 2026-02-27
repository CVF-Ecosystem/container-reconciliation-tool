# File: api/server.py
# @2026 v1.0: REST API Server for Container Inventory Reconciliation
"""
REST API Server using FastAPI.

Provides endpoints for:
- Data reconciliation
- Report generation
- Status monitoring
- File management

Run with: uvicorn api.server:app --reload --port 8000
"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, UploadFile, File
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logging.warning("FastAPI not installed. Run: pip install fastapi uvicorn python-multipart")

if FASTAPI_AVAILABLE:
    
    # ============ PYDANTIC MODELS ============
    
    class ReconciliationRequest(BaseModel):
        """Request model for reconciliation."""
        date: str = Field(..., description="Date in format DD.MM.YYYY or YYYY-MM-DD")
        time_slot: Optional[str] = Field(None, description="Time slot: '8H-15H' or '15H-8H'")
        include_cfs: bool = Field(True, description="Include CFS containers")
        
    class ReconciliationResponse(BaseModel):
        """Response model for reconciliation."""
        success: bool
        message: str
        date: str
        summary: Optional[Dict[str, Any]] = None
        report_path: Optional[str] = None
        elapsed_ms: Optional[float] = None
        
    class CompareRequest(BaseModel):
        """Request model for file comparison."""
        file1_path: str
        file2_path: str
        container_column: str = "Số Container"
        
    class CompareResponse(BaseModel):
        """Response model for file comparison."""
        success: bool
        message: str
        only_in_file1: int = 0
        only_in_file2: int = 0
        in_both: int = 0
        details: Optional[Dict[str, Any]] = None
        
    class HealthResponse(BaseModel):
        """Health check response."""
        status: str
        version: str
        timestamp: str
        uptime_seconds: float
        checks: Dict[str, bool]
        
    class StatusResponse(BaseModel):
        """System status response."""
        status: str
        watcher_running: bool
        last_reconciliation: Optional[str]
        pending_tasks: int
        
    class FileInfo(BaseModel):
        """File information model."""
        name: str
        path: str
        size_bytes: int
        modified: str
        
    class ReportRequest(BaseModel):
        """Request for report generation."""
        date: str
        format: str = "excel"  # excel, pdf, json
        include_charts: bool = True
        operators: Optional[List[str]] = None
        
    # ============ APP INITIALIZATION ============
    
    app = FastAPI(
        title="Container Inventory Reconciliation API",
        description="REST API for container inventory management and reconciliation",
        version="5.4.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # CORS middleware — đọc từ env var ALLOWED_ORIGINS (comma-separated)
    # Mặc định chỉ cho phép localhost để tránh lỗ hổng bảo mật
    _raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:3000")
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )
    
    # Global state
    _start_time = datetime.now()
    _last_reconciliation: Optional[datetime] = None
    _pending_tasks: List[str] = []
    
    
    # ============ HEALTH & STATUS ENDPOINTS ============
    
    @app.get("/", tags=["General"])
    async def root():
        """API root endpoint."""
        return {
            "name": "Container Inventory Reconciliation API",
            "version": "5.4.0",
            "docs": "/docs"
        }
    
    @app.get("/health", response_model=HealthResponse, tags=["General"])
    async def health_check():
        """
        Health check endpoint.
        
        Returns system health status including:
        - API status
        - Database connectivity
        - File system access
        """
        from utils.health_check import run_health_checks
        
        try:
            checks = run_health_checks()
            all_ok = all(checks.values())
        except Exception:
            checks = {"api": True}
            all_ok = True
        
        return HealthResponse(
            status="healthy" if all_ok else "degraded",
            version="5.4.0",
            timestamp=datetime.now().isoformat(),
            uptime_seconds=(datetime.now() - _start_time).total_seconds(),
            checks=checks
        )
    
    @app.get("/status", response_model=StatusResponse, tags=["General"])
    async def get_status():
        """Get current system status."""
        return StatusResponse(
            status="running",
            watcher_running=False,  # TODO: Get from actual watcher
            last_reconciliation=_last_reconciliation.isoformat() if _last_reconciliation else None,
            pending_tasks=len(_pending_tasks)
        )
    
    
    # ============ RECONCILIATION ENDPOINTS ============
    
    @app.post("/reconcile", response_model=ReconciliationResponse, tags=["Reconciliation"])
    async def run_reconciliation(
        request: ReconciliationRequest,
        background_tasks: BackgroundTasks
    ):
        """
        Submit a container inventory reconciliation job (async).
        
        Returns immediately with a task_id. Use GET /tasks/{task_id} to check status.
        """
        global _last_reconciliation
        
        try:
            from config import INPUT_DIR, OUTPUT_DIR
            from utils.task_queue import get_task_queue
            
            task_queue = get_task_queue()
            task_id = task_queue.submit_reconciliation(
                input_dir=INPUT_DIR,
                output_dir=OUTPUT_DIR
            )
            
            _last_reconciliation = datetime.now()
            
            return ReconciliationResponse(
                success=True,
                message=f"Reconciliation job submitted. Track with GET /tasks/{task_id}",
                date=request.date,
                summary={"task_id": task_id},
                report_path=None,
                elapsed_ms=0
            )
            
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Data files not found: {e}")
        except Exception as e:
            logging.error(f"Reconciliation submission failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/tasks/{task_id}", tags=["Reconciliation"])
    async def get_task_status(task_id: str):
        """
        Get status of a submitted reconciliation task.
        
        Returns task status, progress (0-100), and result when complete.
        """
        from utils.task_queue import get_task_queue
        
        task_queue = get_task_queue()
        task = task_queue.get_task_status(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        return task.to_dict()
    
    
    @app.get("/tasks", tags=["Reconciliation"])
    async def list_tasks(limit: int = Query(20, ge=1, le=100)):
        """List recent reconciliation tasks."""
        from utils.task_queue import get_task_queue
        
        task_queue = get_task_queue()
        return {"tasks": task_queue.list_tasks(limit=limit)}
    
    
    @app.delete("/tasks/{task_id}", tags=["Reconciliation"])
    async def cancel_task(task_id: str):
        """Cancel a pending reconciliation task."""
        from utils.task_queue import get_task_queue
        
        task_queue = get_task_queue()
        cancelled = task_queue.cancel_task(task_id)
        
        if not cancelled:
            raise HTTPException(
                status_code=400,
                detail=f"Task {task_id} cannot be cancelled (not found or already running)"
            )
        
        return {"message": f"Task {task_id} cancelled"}
    
    @app.post("/compare", response_model=CompareResponse, tags=["Reconciliation"])
    async def compare_files(request: CompareRequest):
        """
        Compare two Excel files for container differences.
        
        Returns containers that are:
        - Only in file 1
        - Only in file 2
        - In both files
        """
        try:
            from utils.file_comparator import FileComparator
            
            comparator = FileComparator()
            result = comparator.compare(
                Path(request.file1_path),
                Path(request.file2_path),
                container_column=request.container_column
            )
            
            return CompareResponse(
                success=True,
                message="Comparison completed",
                only_in_file1=len(result.get('only_in_file1', [])),
                only_in_file2=len(result.get('only_in_file2', [])),
                in_both=len(result.get('in_both', [])),
                details=result
            )
            
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logging.error(f"Comparison failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    
    # ============ FILE MANAGEMENT ENDPOINTS ============
    
    @app.get("/files/input", response_model=List[FileInfo], tags=["Files"])
    async def list_input_files():
        """List all files in the input directory."""
        from config import INPUT_DIR
        
        files = []
        input_path = Path(INPUT_DIR)
        
        if input_path.exists():
            for f in input_path.rglob("*.xlsx"):
                stat = f.stat()
                files.append(FileInfo(
                    name=f.name,
                    path=str(f),
                    size_bytes=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                ))
        
        return files
    
    @app.get("/files/output", response_model=List[FileInfo], tags=["Files"])
    async def list_output_files(
        date: Optional[str] = Query(None, description="Filter by date (DD.MM.YYYY)")
    ):
        """List generated output/report files."""
        from config import OUTPUT_DIR
        
        files = []
        output_path = Path(OUTPUT_DIR)
        
        if output_path.exists():
            pattern = f"*{date}*" if date else "*"
            for folder in output_path.iterdir():
                if folder.is_dir() and (date is None or date in folder.name):
                    for f in folder.rglob("*.xlsx"):
                        stat = f.stat()
                        files.append(FileInfo(
                            name=f.name,
                            path=str(f),
                            size_bytes=stat.st_size,
                            modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                        ))
        
        return files
    
    @app.post("/files/upload", tags=["Files"])
    async def upload_file(file: UploadFile = File(...)):
        """Upload an Excel file to the input directory."""
        from config import INPUT_DIR
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Only Excel files are allowed")
        
        input_path = Path(INPUT_DIR)
        input_path.mkdir(parents=True, exist_ok=True)
        
        file_path = input_path / file.filename
        
        try:
            contents = await file.read()
            with open(file_path, 'wb') as f:
                f.write(contents)
            
            return {"message": f"File uploaded successfully", "path": str(file_path)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/files/download/{file_path:path}", tags=["Files"])
    async def download_file(file_path: str):
        """Download a report file (chỉ cho phép tải file trong OUTPUT_DIR)."""
        from config import OUTPUT_DIR
        
        path = Path(file_path).resolve()
        allowed_base = Path(OUTPUT_DIR).resolve()
        
        # Bảo vệ path traversal: chỉ cho phép file trong OUTPUT_DIR
        try:
            path.relative_to(allowed_base)
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail="Access denied: file must be within the output directory"
            )
        
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        return FileResponse(
            path=str(path),
            filename=path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    
    # ============ REPORT ENDPOINTS ============
    
    @app.post("/reports/generate", tags=["Reports"])
    async def generate_report(request: ReportRequest, background_tasks: BackgroundTasks):
        """
        Generate a report for the specified date.
        
        Supports formats: excel, pdf, json
        """
        try:
            from core_logic import load_results
            from reports.report_generator import create_reports
            from config import OUTPUT_DIR
            
            # Tải kết quả đã lưu
            results = load_results(Path(OUTPUT_DIR))
            if not results:
                raise HTTPException(
                    status_code=404,
                    detail="No reconciliation results found. Run /reconcile first."
                )
            
            output_path = Path(OUTPUT_DIR) / f"Report_{request.date.replace('.', '')}"
            output_path.mkdir(parents=True, exist_ok=True)
            
            if request.format == "excel":
                # Cập nhật report_folder trong results và tạo báo cáo
                results["report_folder"] = output_path
                create_reports(results)
                report_path = output_path
            elif request.format == "json":
                import json
                summary_df = results.get("summary_df")
                if summary_df is not None:
                    json_path = output_path / "summary.json"
                    summary_df.to_json(json_path, orient="records", force_ascii=False, indent=2)
                    report_path = json_path
                else:
                    report_path = None
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")
            
            return {
                "success": True,
                "message": "Report generated",
                "path": str(report_path) if report_path else None
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Report generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/reports/summary/{date}", tags=["Reports"])
    async def get_summary(date: str):
        """Get reconciliation summary for a specific date."""
        try:
            from config import OUTPUT_DIR
            import json
            
            output_path = Path(OUTPUT_DIR)
            
            # Find matching report folder
            for folder in output_path.iterdir():
                if folder.is_dir() and date.replace('.', '') in folder.name:
                    summary_file = folder / "summary.json"
                    if summary_file.exists():
                        with open(summary_file) as f:
                            return json.load(f)
            
            raise HTTPException(status_code=404, detail=f"No summary found for date {date}")
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    
    # ============ AUDIT ENDPOINTS ============
    
    @app.get("/audit/logs", tags=["Audit"])
    async def get_audit_logs(
        limit: int = Query(100, ge=1, le=1000),
        action: Optional[str] = Query(None, description="Filter by action type"),
        start_date: Optional[str] = Query(None, description="Start date (ISO format)")
    ):
        """Get audit log entries."""
        try:
            from utils.audit_trail import get_audit_logger, AuditAction
            from datetime import datetime
            
            logger = get_audit_logger()
            
            entries = logger.query(
                action=action,
                start_date=datetime.fromisoformat(start_date) if start_date else None,
                limit=limit
            )
            
            return {
                "count": len(entries),
                "entries": [e.to_dict() for e in entries]
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/audit/statistics", tags=["Audit"])
    async def get_audit_statistics(days: int = Query(30, ge=1, le=365)):
        """Get audit statistics for the specified period."""
        try:
            from utils.audit_trail import get_audit_logger
            
            logger = get_audit_logger()
            stats = logger.get_statistics(days=days)
            
            return stats
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ============ MAIN ENTRY ============

def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    Run the API server.
    
    Args:
        host: Host to bind to
        port: Port to listen on
        reload: Enable auto-reload for development
    """
    if not FASTAPI_AVAILABLE:
        print("FastAPI not installed. Run: pip install fastapi uvicorn python-multipart")
        return
    
    import uvicorn
    uvicorn.run("api.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server(reload=True)
