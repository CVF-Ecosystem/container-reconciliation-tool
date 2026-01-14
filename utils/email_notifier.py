# File: utils/email_notifier.py
"""
Email Notifier Module - Send email notifications after reconciliation.

V5.4 - Phase 2: Enhanced Features
- Email notifications for reconciliation results
- Anomaly detection alerts (auto-send when issues detected)
- HTML templates with professional styling
- Attachment support (Excel, PDF)
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AnomalyAlert:
    """Represents an anomaly detection alert."""
    level: AlertLevel
    title: str
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_html(self) -> str:
        """Convert alert to HTML representation."""
        colors = {
            AlertLevel.INFO: "#17a2b8",
            AlertLevel.WARNING: "#ffc107", 
            AlertLevel.CRITICAL: "#dc3545"
        }
        icons = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨"
        }
        
        color = colors.get(self.level, "#6c757d")
        icon = icons.get(self.level, "📌")
        
        details_html = ""
        if self.details:
            details_html = "<ul>"
            for key, value in self.details.items():
                details_html += f"<li><strong>{key}:</strong> {value}</li>"
            details_html += "</ul>"
        
        return f"""
        <div style="border-left: 4px solid {color}; padding: 10px 15px; margin: 10px 0; background: #f8f9fa;">
            <div style="font-weight: bold; color: {color};">{icon} {self.title}</div>
            <div style="margin-top: 5px;">{self.description}</div>
            {details_html}
            <div style="font-size: 12px; color: #666; margin-top: 5px;">
                {self.timestamp.strftime('%H:%M:%S %d/%m/%Y')}
            </div>
        </div>
        """


class EmailNotifier:
    """Send email notifications with reconciliation results."""
    
    def __init__(
        self,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str = "",
        sender_password: str = "",
        use_tls: bool = True
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.use_tls = use_tls
    
    def send_notification(
        self,
        recipients: List[str],
        subject: str,
        body_html: str,
        attachments: Optional[List[Path]] = None
    ) -> bool:
        """
        Send email notification.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            body_html: HTML content of the email
            attachments: Optional list of file paths to attach
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.sender_email or not self.sender_password:
            logging.warning("Email credentials not configured")
            return False
        
        if not recipients:
            logging.warning("No recipients specified")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(recipients)
            
            # Attach HTML body
            msg.attach(MIMEText(body_html, 'html'))
            
            # Attach files if any
            if attachments:
                for file_path in attachments:
                    if file_path.exists():
                        self._attach_file(msg, file_path)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipients, msg.as_string())
            
            logging.info(f"Email sent to {', '.join(recipients)}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False
    
    def _attach_file(self, msg: MIMEMultipart, file_path: Path):
        """Attach a file to the email message."""
        try:
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {file_path.name}'
            )
            msg.attach(part)
        except Exception as e:
            logging.warning(f"Could not attach file {file_path}: {e}")


def create_reconciliation_email(
    results: Dict[str, Any],
    date_str: str,
    success: bool = True
) -> str:
    """
    Create HTML email content for reconciliation notification.
    
    Args:
        results: Reconciliation results dictionary
        date_str: Date string for the reconciliation
        success: Whether the reconciliation was successful
    
    Returns:
        HTML content string
    """
    status_icon = "✅" if success else "❌"
    status_text = "Thành công" if success else "Có lỗi"
    status_color = "#28a745" if success else "#dc3545"
    
    # Extract counts from results
    main_results = results.get('main_results', {})
    counts = main_results.get('counts', {})
    
    ton_moi = counts.get('ton_moi', 0)
    khop_chuan = counts.get('khop_chuan', 0)
    thieu = counts.get('thieu', 0)
    thua = counts.get('thua', 0)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
            .status {{ font-size: 24px; font-weight: bold; }}
            .content {{ background: #f8f9fa; padding: 20px; }}
            .summary-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .summary-table th, .summary-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .summary-table th {{ background: #667eea; color: white; }}
            .metric {{ font-size: 24px; font-weight: bold; color: #667eea; }}
            .warning {{ color: #dc3545; font-weight: bold; }}
            .success {{ color: #28a745; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="status">{status_icon} Đối Soát Tồn Bãi - {status_text}</div>
                <div>Ngày: {date_str} | Thời gian: {datetime.now().strftime('%H:%M:%S')}</div>
            </div>
            
            <div class="content">
                <h2>📊 Tóm Tắt Kết Quả</h2>
                
                <table class="summary-table">
                    <tr>
                        <th>Chỉ Số</th>
                        <th>Số Lượng</th>
                    </tr>
                    <tr>
                        <td>Tổng tồn bãi (TON MOI)</td>
                        <td class="metric">{ton_moi:,}</td>
                    </tr>
                    <tr>
                        <td>Khớp hoàn toàn</td>
                        <td class="success">{khop_chuan:,}</td>
                    </tr>
                    <tr>
                        <td>Thiếu trên bãi</td>
                        <td class="{'warning' if thieu > 0 else ''}">{thieu:,}</td>
                    </tr>
                    <tr>
                        <td>Thừa trên bãi</td>
                        <td class="{'warning' if thua > 0 else ''}">{thua:,}</td>
                    </tr>
                </table>
                
                <p>Xem chi tiết báo cáo trong thư mục data_output.</p>
            </div>
            
            <div class="footer">
                <p>Container Inventory Reconciliation Tool V5.4</p>
                <p>Developed by Tien-Tan Thuan Port | © 2026</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def send_reconciliation_notification(
    results: Dict[str, Any],
    date_str: str,
    recipients: List[str],
    smtp_config: Dict[str, Any],
    attach_summary: bool = True,
    summary_file: Optional[Path] = None
) -> bool:
    """
    Convenience function to send reconciliation notification.
    
    Args:
        results: Reconciliation results
        date_str: Date string
        recipients: List of email recipients
        smtp_config: SMTP configuration dict with keys: server, port, email, password
        attach_summary: Whether to attach summary file
        summary_file: Path to summary Excel file
    
    Returns:
        True if sent successfully
    """
    notifier = EmailNotifier(
        smtp_server=smtp_config.get('server', 'smtp.gmail.com'),
        smtp_port=smtp_config.get('port', 587),
        sender_email=smtp_config.get('email', ''),
        sender_password=smtp_config.get('password', '')
    )
    
    html_content = create_reconciliation_email(results, date_str)
    
    attachments = []
    if attach_summary and summary_file and summary_file.exists():
        attachments.append(summary_file)
    
    return notifier.send_notification(
        recipients=recipients,
        subject=f"📊 Báo Cáo Đối Soát Tồn Bãi - {date_str}",
        body_html=html_content,
        attachments=attachments if attachments else None
    )


class AnomalyDetector:
    """
    Detect anomalies in reconciliation results and trigger alerts.
    
    Thresholds can be configured for:
    - Missing containers (thiếu)
    - Extra containers (thừa)
    - Match rate percentage
    - Specific operator issues
    """
    
    def __init__(
        self,
        thieu_threshold: int = 10,
        thua_threshold: int = 10,
        match_rate_threshold: float = 95.0,
        auto_notify: bool = True
    ):
        """
        Initialize anomaly detector.
        
        Args:
            thieu_threshold: Alert if missing count exceeds this
            thua_threshold: Alert if extra count exceeds this  
            match_rate_threshold: Alert if match rate below this %
            auto_notify: Automatically send email on detection
        """
        self.thieu_threshold = thieu_threshold
        self.thua_threshold = thua_threshold
        self.match_rate_threshold = match_rate_threshold
        self.auto_notify = auto_notify
        self._alerts: List[AnomalyAlert] = []
        self._callbacks: List[Callable[[AnomalyAlert], None]] = []
    
    def add_callback(self, callback: Callable[[AnomalyAlert], None]):
        """Add callback to be called when anomaly detected."""
        self._callbacks.append(callback)
    
    def check_results(self, results: Dict[str, Any]) -> List[AnomalyAlert]:
        """
        Check reconciliation results for anomalies.
        
        Args:
            results: Reconciliation results dictionary
            
        Returns:
            List of detected anomaly alerts
        """
        self._alerts = []
        
        main_results = results.get('main_results', {})
        counts = main_results.get('counts', {})
        
        thieu = counts.get('thieu', 0)
        thua = counts.get('thua', 0)
        ton_moi = counts.get('ton_moi', 0)
        khop_chuan = counts.get('khop_chuan', 0)
        
        # Check missing containers
        if thieu > self.thieu_threshold:
            alert = AnomalyAlert(
                level=AlertLevel.CRITICAL if thieu > self.thieu_threshold * 2 else AlertLevel.WARNING,
                title="Phát hiện container thiếu bất thường",
                description=f"Số container thiếu ({thieu}) vượt ngưỡng cho phép ({self.thieu_threshold})",
                details={
                    "Số thiếu": thieu,
                    "Ngưỡng": self.thieu_threshold,
                    "Mức vượt": f"{((thieu / self.thieu_threshold) - 1) * 100:.1f}%"
                }
            )
            self._alerts.append(alert)
            self._trigger_callbacks(alert)
        
        # Check extra containers  
        if thua > self.thua_threshold:
            alert = AnomalyAlert(
                level=AlertLevel.WARNING,
                title="Phát hiện container thừa bất thường",
                description=f"Số container thừa ({thua}) vượt ngưỡng cho phép ({self.thua_threshold})",
                details={
                    "Số thừa": thua,
                    "Ngưỡng": self.thua_threshold
                }
            )
            self._alerts.append(alert)
            self._trigger_callbacks(alert)
        
        # Check match rate
        if ton_moi > 0:
            match_rate = (khop_chuan / ton_moi) * 100
            if match_rate < self.match_rate_threshold:
                alert = AnomalyAlert(
                    level=AlertLevel.CRITICAL if match_rate < self.match_rate_threshold - 10 else AlertLevel.WARNING,
                    title="Tỷ lệ khớp thấp bất thường",
                    description=f"Tỷ lệ khớp ({match_rate:.1f}%) thấp hơn ngưỡng ({self.match_rate_threshold}%)",
                    details={
                        "Tỷ lệ khớp": f"{match_rate:.1f}%",
                        "Ngưỡng": f"{self.match_rate_threshold}%",
                        "Tổng tồn": ton_moi,
                        "Số khớp": khop_chuan
                    }
                )
                self._alerts.append(alert)
                self._trigger_callbacks(alert)
        
        return self._alerts
    
    def _trigger_callbacks(self, alert: AnomalyAlert):
        """Trigger all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception as e:
                logging.error(f"Callback error: {e}")
    
    def get_alerts(self) -> List[AnomalyAlert]:
        """Get all detected alerts."""
        return self._alerts.copy()
    
    def has_critical_alerts(self) -> bool:
        """Check if any critical alerts exist."""
        return any(a.level == AlertLevel.CRITICAL for a in self._alerts)
    
    def has_warnings(self) -> bool:
        """Check if any warning alerts exist."""
        return any(a.level == AlertLevel.WARNING for a in self._alerts)
    
    def clear_alerts(self):
        """Clear all alerts."""
        self._alerts = []


def create_anomaly_alert_email(
    alerts: List[AnomalyAlert],
    date_str: str,
    additional_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create HTML email for anomaly alerts.
    
    Args:
        alerts: List of anomaly alerts
        date_str: Date string
        additional_info: Optional additional context
        
    Returns:
        HTML email content
    """
    if not alerts:
        return ""
    
    # Determine overall severity
    has_critical = any(a.level == AlertLevel.CRITICAL for a in alerts)
    header_color = "#dc3545" if has_critical else "#ffc107"
    header_icon = "🚨" if has_critical else "⚠️"
    header_text = "CẢNH BÁO KHẨN CẤP" if has_critical else "CẢNH BÁO"
    
    # Build alerts HTML
    alerts_html = "\n".join(alert.to_html() for alert in alerts)
    
    # Additional info section
    info_html = ""
    if additional_info:
        info_html = "<h3>📋 Thông tin bổ sung</h3><ul>"
        for key, value in additional_info.items():
            info_html += f"<li><strong>{key}:</strong> {value}</li>"
        info_html += "</ul>"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: {header_color}; color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 22px; }}
            .content {{ background: #fff; padding: 20px; border: 1px solid #ddd; }}
            .footer {{ text-align: center; padding: 15px; color: #666; font-size: 12px; background: #f8f9fa; border-radius: 0 0 10px 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{header_icon} {header_text}</h1>
                <div>Đối Soát Tồn Bãi - {date_str}</div>
            </div>
            
            <div class="content">
                <p>Hệ thống đã phát hiện <strong>{len(alerts)} bất thường</strong> trong quá trình đối soát:</p>
                
                {alerts_html}
                
                {info_html}
                
                <p style="margin-top: 20px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                    <strong>Hành động cần thiết:</strong> Vui lòng kiểm tra và xác minh các container được đánh dấu.
                </p>
            </div>
            
            <div class="footer">
                <p>Container Inventory Reconciliation Tool V5.4</p>
                <p>Email tự động - Vui lòng không trả lời</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def send_anomaly_alert(
    alerts: List[AnomalyAlert],
    date_str: str,
    recipients: List[str],
    smtp_config: Dict[str, Any],
    additional_info: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Send anomaly alert email.
    
    Args:
        alerts: List of anomaly alerts
        date_str: Date string
        recipients: List of email recipients
        smtp_config: SMTP configuration
        additional_info: Optional additional context
        
    Returns:
        True if sent successfully
    """
    if not alerts:
        logging.info("No alerts to send")
        return True
    
    notifier = EmailNotifier(
        smtp_server=smtp_config.get('server', 'smtp.gmail.com'),
        smtp_port=smtp_config.get('port', 587),
        sender_email=smtp_config.get('email', ''),
        sender_password=smtp_config.get('password', '')
    )
    
    has_critical = any(a.level == AlertLevel.CRITICAL for a in alerts)
    priority = "KHẨN CẤP" if has_critical else "CẢNH BÁO"
    
    html_content = create_anomaly_alert_email(alerts, date_str, additional_info)
    
    return notifier.send_notification(
        recipients=recipients,
        subject=f"🚨 [{priority}] Bất thường đối soát tồn bãi - {date_str}",
        body_html=html_content
    )
