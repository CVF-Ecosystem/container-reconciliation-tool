# File: api/server.py
# V5.4 Phase 2: REST API Server for Container Inventory Reconciliation
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
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
        Run container inventory reconciliation.
        
        This endpoint triggers a reconciliation process for the specified date.
        The process runs in the background and generates reports.
        """
        global _last_reconciliation
        
        try:
            import time
            start_time = time.perf_counter()
            
            # Import core logic
            from core_logic import run_reconciliation as core_reconcile
            from config import INPUT_DIR, OUTPUT_DIR
            
            # Run reconciliation
            result = core_reconcile(
                date_str=request.date,
                time_slot=request.time_slot,
                include_cfs=request.include_cfs
            )
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            _last_reconciliation = datetime.now()
            
            return ReconciliationResponse(
                success=True,
                message="Reconciliation completed successfully",
                date=request.date,
                summary=result.get('summary') if result else None,
                report_path=result.get('report_path') if result else None,
                elapsed_ms=elapsed_ms
            )
            
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Data files not found: {e}")
        except Exception as e:
            logging.error(f"Reconciliation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
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
        """Download a report file."""
        path = Path(file_path)
        
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
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
            from reports.report_generator import ReportGenerator
            from config import OUTPUT_DIR
            
            generator = ReportGenerator()
            
            output_path = Path(OUTPUT_DIR) / f"Report_{request.date.replace('.', '')}"
            output_path.mkdir(parents=True, exist_ok=True)
            
            if request.format == "excel":
                report_path = generator.generate_excel(
                    date=request.date,
                    output_dir=output_path,
                    operators=request.operators
                )
            elif request.format == "json":
                report_path = generator.generate_json(
                    date=request.date,
                    output_dir=output_path
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")
            
            return {
                "success": True,
                "message": "Report generated",
                "path": str(report_path) if report_path else None
            }
            
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
