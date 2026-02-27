# File: utils/observability.py — @2026 v1.0
"""
Observability module: Structured logging, metrics, and distributed tracing.

Integrates with:
- OpenTelemetry (tracing)
- Prometheus (metrics)
- Structured JSON logging

Usage:
    from utils.observability import get_tracer, get_metrics, setup_logging
    
    # Setup at app startup
    setup_logging(service_name="reconciliation-app")
    
    # Tracing
    tracer = get_tracer()
    with tracer.start_as_current_span("reconciliation") as span:
        span.set_attribute("input_dir", str(input_dir))
        result = run_reconciliation(...)
    
    # Metrics
    metrics = get_metrics()
    metrics.reconciliation_counter.inc()
    metrics.reconciliation_duration.observe(elapsed_seconds)
"""

import logging
import os
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager
from functools import wraps


# ============ OPENTELEMETRY SETUP ============

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


def setup_tracing(
    service_name: str = "container-reconciliation",
    service_version: str = "1.0",
    otlp_endpoint: Optional[str] = None
) -> None:
    """
    Setup OpenTelemetry distributed tracing.
    
    Args:
        service_name: Name of the service for tracing
        service_version: Version of the service
        otlp_endpoint: OTLP exporter endpoint (e.g., http://jaeger:4317)
                       If None, uses console exporter for development
    """
    if not OTEL_AVAILABLE:
        logging.debug("OpenTelemetry not installed. Tracing disabled.")
        return
    
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
    })
    
    provider = TracerProvider(resource=resource)
    
    # Configure exporter
    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            logging.info(f"OpenTelemetry: Using OTLP exporter at {otlp_endpoint}")
        except ImportError:
            logging.warning("opentelemetry-exporter-otlp not installed, using console exporter")
            exporter = ConsoleSpanExporter()
    else:
        # Development: log spans to console only if DEBUG
        if os.getenv("OTEL_DEBUG", "false").lower() == "true":
            exporter = ConsoleSpanExporter()
            logging.info("OpenTelemetry: Using console exporter (debug mode)")
        else:
            logging.debug("OpenTelemetry: No exporter configured, tracing disabled")
            return
    
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    logging.info(f"OpenTelemetry tracing initialized for service: {service_name}")


def get_tracer(name: str = "reconciliation") -> Any:
    """Get OpenTelemetry tracer."""
    if OTEL_AVAILABLE:
        return trace.get_tracer(name)
    return _NoOpTracer()


class _NoOpTracer:
    """No-op tracer when OpenTelemetry is not available."""
    
    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        yield _NoOpSpan()
    
    def start_span(self, name: str, **kwargs):
        return _NoOpSpan()


class _NoOpSpan:
    """No-op span."""
    def set_attribute(self, key: str, value: Any): pass
    def set_status(self, status): pass
    def record_exception(self, exc): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


# ============ PROMETHEUS METRICS ============

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class AppMetrics:
    """Application metrics using Prometheus."""
    
    def __init__(self):
        if not PROMETHEUS_AVAILABLE:
            self._available = False
            return
        
        self._available = True
        
        # Reconciliation metrics
        self.reconciliation_total = Counter(
            "reconciliation_total",
            "Total number of reconciliation runs",
            ["status"]  # success, failed
        )
        
        self.reconciliation_duration = Histogram(
            "reconciliation_duration_seconds",
            "Duration of reconciliation runs",
            buckets=[10, 30, 60, 120, 300, 600]
        )
        
        self.containers_processed = Counter(
            "containers_processed_total",
            "Total containers processed",
            ["result"]  # matched, missing, extra
        )
        
        # API metrics
        self.api_requests_total = Counter(
            "api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status_code"]
        )
        
        self.api_request_duration = Histogram(
            "api_request_duration_seconds",
            "API request duration",
            ["method", "endpoint"]
        )
        
        # System metrics
        self.active_tasks = Gauge(
            "active_tasks",
            "Number of currently running reconciliation tasks"
        )
        
        self.cache_hit_rate = Gauge(
            "cache_hit_rate",
            "Cache hit rate percentage"
        )
    
    def record_reconciliation(self, success: bool, duration_seconds: float, counts: Dict[str, int] = None):
        """Record a reconciliation run."""
        if not self._available:
            return
        
        status = "success" if success else "failed"
        self.reconciliation_total.labels(status=status).inc()
        self.reconciliation_duration.observe(duration_seconds)
        
        if counts:
            self.containers_processed.labels(result="matched").inc(counts.get("khop_chuan", 0))
            self.containers_processed.labels(result="missing").inc(counts.get("chenh_lech_am", 0))
            self.containers_processed.labels(result="extra").inc(counts.get("chenh_lech_duong", 0))
    
    def start_metrics_server(self, port: int = 9090):
        """Start Prometheus metrics HTTP server."""
        if not self._available:
            logging.warning("Prometheus not installed. Metrics server not started.")
            return
        
        start_http_server(port)
        logging.info(f"Prometheus metrics server started on port {port}")


_metrics: Optional[AppMetrics] = None


def get_metrics() -> AppMetrics:
    """Get global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = AppMetrics()
    return _metrics


# ============ STRUCTURED LOGGING ============

class StructuredFormatter(logging.Formatter):
    """
    JSON structured log formatter.
    
    Outputs logs as JSON for easy parsing by log aggregators (ELK, Splunk, etc.)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ("name", "msg", "args", "levelname", "levelno", "pathname",
                          "filename", "module", "exc_info", "exc_text", "stack_info",
                          "lineno", "funcName", "created", "msecs", "relativeCreated",
                          "thread", "threadName", "processName", "process", "message"):
                log_data[key] = value
        
        # Add trace context if available
        if OTEL_AVAILABLE:
            span = trace.get_current_span()
            if span and span.is_recording():
                ctx = span.get_span_context()
                log_data["trace_id"] = format(ctx.trace_id, "032x")
                log_data["span_id"] = format(ctx.span_id, "016x")
        
        return json.dumps(log_data, default=str, ensure_ascii=False)


def setup_logging(
    service_name: str = "container-reconciliation",
    log_level: str = None,
    json_format: bool = None
) -> None:
    """
    Setup application logging.
    
    Args:
        service_name: Service name for log context
        log_level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to LOG_LEVEL env var or INFO.
        json_format: Use JSON format. Defaults to JSON_LOGS env var or False.
    """
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    json_format = json_format if json_format is not None else os.getenv("JSON_LOGS", "false").lower() == "true"
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create handler
    handler = logging.StreamHandler()
    
    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            f"%(asctime)s [{service_name}] %(levelname)s %(name)s: %(message)s"
        ))
    
    root_logger.addHandler(handler)
    
    # File handler for production
    log_file = os.getenv("LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(StructuredFormatter() if json_format else handler.formatter)
        root_logger.addHandler(file_handler)
    
    logging.info(f"Logging configured: level={log_level}, json={json_format}, service={service_name}")


# ============ TRACING DECORATOR ============

def traced(span_name: str = None, attributes: Dict[str, Any] = None):
    """
    Decorator to add OpenTelemetry tracing to a function.
    
    Usage:
        @traced("reconciliation.load_data")
        def load_data(input_dir: Path) -> dict:
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            name = span_name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    elapsed = time.perf_counter() - start
                    span.set_attribute("duration_ms", round(elapsed * 1000, 2))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


# ============ METRICS MIDDLEWARE FOR FASTAPI ============

def create_metrics_middleware():
    """
    Create FastAPI middleware for automatic request metrics.
    
    Usage in api/server.py:
        from utils.observability import create_metrics_middleware
        app.middleware("http")(create_metrics_middleware())
    """
    async def metrics_middleware(request, call_next):
        start = time.perf_counter()
        
        response = await call_next(request)
        
        elapsed = time.perf_counter() - start
        metrics = get_metrics()
        
        if metrics._available:
            metrics.api_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code
            ).inc()
            
            metrics.api_request_duration.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(elapsed)
        
        return response
    
    return metrics_middleware
