# File: tests/test_email_notifier.py
"""
Tests for utils/email_notifier.py module.

V5.4 - Phase 2: Enhanced Features
Tests cover:
- EmailNotifier class
- AnomalyAlert and AlertLevel
- AnomalyDetector with thresholds
- Email template generation
- Anomaly alert emails
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from email.mime.multipart import MIMEMultipart

from utils.email_notifier import (
    EmailNotifier,
    AlertLevel,
    AnomalyAlert,
    AnomalyDetector,
    create_reconciliation_email,
    create_anomaly_alert_email,
    send_reconciliation_notification,
    send_anomaly_alert
)


# =============================================================================
# AlertLevel Tests
# =============================================================================

class TestAlertLevel:
    """Tests for AlertLevel enum."""
    
    def test_alert_levels_exist(self):
        """Test all alert levels are defined."""
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.CRITICAL.value == "critical"
    
    def test_alert_level_comparison(self):
        """Test alert levels can be compared."""
        assert AlertLevel.INFO != AlertLevel.WARNING
        assert AlertLevel.WARNING != AlertLevel.CRITICAL


# =============================================================================
# AnomalyAlert Tests
# =============================================================================

class TestAnomalyAlert:
    """Tests for AnomalyAlert dataclass."""
    
    def test_create_alert_minimal(self):
        """Test creating alert with minimal parameters."""
        alert = AnomalyAlert(
            level=AlertLevel.WARNING,
            title="Test Alert",
            description="Test description"
        )
        
        assert alert.level == AlertLevel.WARNING
        assert alert.title == "Test Alert"
        assert alert.description == "Test description"
        assert alert.details == {}
        assert isinstance(alert.timestamp, datetime)
    
    def test_create_alert_with_details(self):
        """Test creating alert with details."""
        details = {"count": 50, "threshold": 10}
        alert = AnomalyAlert(
            level=AlertLevel.CRITICAL,
            title="Critical Alert",
            description="Something critical",
            details=details
        )
        
        assert alert.details == details
        assert alert.details["count"] == 50
    
    def test_alert_to_html(self):
        """Test converting alert to HTML."""
        alert = AnomalyAlert(
            level=AlertLevel.WARNING,
            title="Warning Alert",
            description="Warning description",
            details={"key1": "value1"}
        )
        
        html = alert.to_html()
        
        assert "Warning Alert" in html
        assert "Warning description" in html
        assert "key1" in html
        assert "value1" in html
        # Check warning color (yellow)
        assert "#ffc107" in html
    
    def test_alert_html_critical_color(self):
        """Test critical alert has correct color."""
        alert = AnomalyAlert(
            level=AlertLevel.CRITICAL,
            title="Critical",
            description="Critical issue"
        )
        
        html = alert.to_html()
        assert "#dc3545" in html  # Red color
    
    def test_alert_html_info_color(self):
        """Test info alert has correct color."""
        alert = AnomalyAlert(
            level=AlertLevel.INFO,
            title="Info",
            description="Info message"
        )
        
        html = alert.to_html()
        assert "#17a2b8" in html  # Blue color


# =============================================================================
# EmailNotifier Tests
# =============================================================================

class TestEmailNotifier:
    """Tests for EmailNotifier class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        notifier = EmailNotifier()
        
        assert notifier.smtp_server == "smtp.gmail.com"
        assert notifier.smtp_port == 587
        assert notifier.sender_email == ""
        assert notifier.sender_password == ""
        assert notifier.use_tls is True
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        notifier = EmailNotifier(
            smtp_server="smtp.outlook.com",
            smtp_port=25,
            sender_email="test@test.com",
            sender_password="secret",
            use_tls=False
        )
        
        assert notifier.smtp_server == "smtp.outlook.com"
        assert notifier.smtp_port == 25
        assert notifier.sender_email == "test@test.com"
        assert notifier.sender_password == "secret"
        assert notifier.use_tls is False
    
    def test_send_notification_no_credentials(self):
        """Test sending fails without credentials."""
        notifier = EmailNotifier()
        
        result = notifier.send_notification(
            recipients=["test@test.com"],
            subject="Test",
            body_html="<p>Test</p>"
        )
        
        assert result is False
    
    def test_send_notification_no_recipients(self):
        """Test sending fails without recipients."""
        notifier = EmailNotifier(
            sender_email="sender@test.com",
            sender_password="password"
        )
        
        result = notifier.send_notification(
            recipients=[],
            subject="Test",
            body_html="<p>Test</p>"
        )
        
        assert result is False
    
    @patch('smtplib.SMTP')
    def test_send_notification_success(self, mock_smtp):
        """Test successful email sending."""
        # Setup mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = Mock(return_value=False)
        
        notifier = EmailNotifier(
            sender_email="sender@test.com",
            sender_password="password"
        )
        
        result = notifier.send_notification(
            recipients=["recipient@test.com"],
            subject="Test Subject",
            body_html="<p>Test Body</p>"
        )
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()
    
    @patch('smtplib.SMTP')
    def test_send_notification_with_attachment(self, mock_smtp, tmp_path):
        """Test sending email with attachment."""
        # Create temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")
        
        # Setup mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = Mock(return_value=False)
        
        notifier = EmailNotifier(
            sender_email="sender@test.com",
            sender_password="password"
        )
        
        result = notifier.send_notification(
            recipients=["recipient@test.com"],
            subject="Test",
            body_html="<p>Test</p>",
            attachments=[test_file]
        )
        
        assert result is True
    
    @patch('smtplib.SMTP')
    def test_send_notification_smtp_error(self, mock_smtp):
        """Test handling SMTP errors."""
        mock_smtp.return_value.__enter__ = Mock(side_effect=Exception("SMTP Error"))
        
        notifier = EmailNotifier(
            sender_email="sender@test.com",
            sender_password="password"
        )
        
        result = notifier.send_notification(
            recipients=["recipient@test.com"],
            subject="Test",
            body_html="<p>Test</p>"
        )
        
        assert result is False


# =============================================================================
# AnomalyDetector Tests
# =============================================================================

class TestAnomalyDetector:
    """Tests for AnomalyDetector class."""
    
    def test_init_default_thresholds(self):
        """Test initialization with default thresholds."""
        detector = AnomalyDetector()
        
        assert detector.thieu_threshold == 10
        assert detector.thua_threshold == 10
        assert detector.match_rate_threshold == 95.0
        assert detector.auto_notify is True
    
    def test_init_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        detector = AnomalyDetector(
            thieu_threshold=5,
            thua_threshold=20,
            match_rate_threshold=90.0,
            auto_notify=False
        )
        
        assert detector.thieu_threshold == 5
        assert detector.thua_threshold == 20
        assert detector.match_rate_threshold == 90.0
        assert detector.auto_notify is False
    
    def test_check_results_no_anomalies(self):
        """Test with results that have no anomalies."""
        detector = AnomalyDetector(thieu_threshold=10, thua_threshold=10)
        
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 98,
                    'thieu': 1,
                    'thua': 1
                }
            }
        }
        
        alerts = detector.check_results(results)
        
        assert len(alerts) == 0
        assert not detector.has_critical_alerts()
        assert not detector.has_warnings()
    
    def test_check_results_thieu_warning(self):
        """Test detection of missing containers warning."""
        detector = AnomalyDetector(thieu_threshold=5, match_rate_threshold=80.0)
        
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 90,
                    'thieu': 8,  # Exceeds threshold of 5
                    'thua': 2
                }
            }
        }
        
        alerts = detector.check_results(results)
        
        # Should have at least 1 alert for thieu
        assert len(alerts) >= 1
        thieu_alerts = [a for a in alerts if "thiếu" in a.title.lower()]
        assert len(thieu_alerts) == 1
        assert thieu_alerts[0].level == AlertLevel.WARNING
    
    def test_check_results_thieu_critical(self):
        """Test detection of missing containers critical (2x threshold)."""
        detector = AnomalyDetector(thieu_threshold=5)
        
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 80,
                    'thieu': 15,  # More than 2x threshold
                    'thua': 5
                }
            }
        }
        
        alerts = detector.check_results(results)
        
        # Should have critical alert for thieu
        thieu_alert = [a for a in alerts if "thiếu" in a.title.lower()][0]
        assert thieu_alert.level == AlertLevel.CRITICAL
        assert detector.has_critical_alerts()
    
    def test_check_results_thua_warning(self):
        """Test detection of extra containers warning."""
        detector = AnomalyDetector(thua_threshold=5)
        
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 92,
                    'thieu': 0,
                    'thua': 8  # Exceeds threshold
                }
            }
        }
        
        alerts = detector.check_results(results)
        
        assert any("thừa" in a.title.lower() for a in alerts)
        assert detector.has_warnings()
    
    def test_check_results_low_match_rate(self):
        """Test detection of low match rate."""
        detector = AnomalyDetector(match_rate_threshold=95.0)
        
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 80,  # 80% match rate
                    'thieu': 0,
                    'thua': 0
                }
            }
        }
        
        alerts = detector.check_results(results)
        
        assert any("khớp" in a.title.lower() for a in alerts)
    
    def test_check_results_multiple_anomalies(self):
        """Test detection of multiple anomalies."""
        detector = AnomalyDetector(
            thieu_threshold=5,
            thua_threshold=5,
            match_rate_threshold=95.0
        )
        
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 70,  # 70% match rate
                    'thieu': 15,       # Exceeds threshold
                    'thua': 15         # Exceeds threshold
                }
            }
        }
        
        alerts = detector.check_results(results)
        
        assert len(alerts) >= 2  # At least 2 anomalies
    
    def test_callback_triggered(self):
        """Test that callbacks are triggered on anomaly detection."""
        detector = AnomalyDetector(thieu_threshold=5, match_rate_threshold=80.0)
        
        callback_results = []
        def test_callback(alert):
            callback_results.append(alert)
        
        detector.add_callback(test_callback)
        
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 90,
                    'thieu': 10,
                    'thua': 0
                }
            }
        }
        
        detector.check_results(results)
        
        # Should have callback called at least once for thieu alert
        assert len(callback_results) >= 1
        thieu_callbacks = [a for a in callback_results if "thiếu" in a.title.lower()]
        assert len(thieu_callbacks) == 1
    
    def test_get_alerts(self):
        """Test getting alerts returns a copy."""
        detector = AnomalyDetector(thieu_threshold=5)
        
        results = {
            'main_results': {
                'counts': {'ton_moi': 100, 'khop_chuan': 90, 'thieu': 10, 'thua': 0}
            }
        }
        
        detector.check_results(results)
        alerts1 = detector.get_alerts()
        alerts2 = detector.get_alerts()
        
        assert alerts1 is not alerts2
        assert len(alerts1) == len(alerts2)
    
    def test_clear_alerts(self):
        """Test clearing alerts."""
        detector = AnomalyDetector(thieu_threshold=5)
        
        results = {
            'main_results': {
                'counts': {'ton_moi': 100, 'khop_chuan': 90, 'thieu': 10, 'thua': 0}
            }
        }
        
        detector.check_results(results)
        assert len(detector.get_alerts()) > 0
        
        detector.clear_alerts()
        assert len(detector.get_alerts()) == 0


# =============================================================================
# Email Template Tests
# =============================================================================

class TestEmailTemplates:
    """Tests for email template generation functions."""
    
    def test_create_reconciliation_email_success(self):
        """Test creating reconciliation email for successful run."""
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 500,
                    'khop_chuan': 480,
                    'thieu': 10,
                    'thua': 10
                }
            }
        }
        
        html = create_reconciliation_email(results, "N13.01.2026", success=True)
        
        assert "N13.01.2026" in html
        assert "500" in html
        assert "480" in html
        assert "✅" in html
        assert "Thành công" in html
    
    def test_create_reconciliation_email_failure(self):
        """Test creating reconciliation email for failed run."""
        results = {'main_results': {'counts': {}}}
        
        html = create_reconciliation_email(results, "N13.01.2026", success=False)
        
        assert "❌" in html
        assert "Có lỗi" in html
    
    def test_create_anomaly_alert_email_empty(self):
        """Test creating anomaly alert email with no alerts."""
        html = create_anomaly_alert_email([], "N13.01.2026")
        assert html == ""
    
    def test_create_anomaly_alert_email_warning(self):
        """Test creating anomaly alert email with warnings."""
        alerts = [
            AnomalyAlert(
                level=AlertLevel.WARNING,
                title="Warning Alert",
                description="Test warning"
            )
        ]
        
        html = create_anomaly_alert_email(alerts, "N13.01.2026")
        
        assert "Warning Alert" in html
        assert "CẢNH BÁO" in html
        assert "#ffc107" in html  # Warning color
    
    def test_create_anomaly_alert_email_critical(self):
        """Test creating anomaly alert email with critical alerts."""
        alerts = [
            AnomalyAlert(
                level=AlertLevel.CRITICAL,
                title="Critical Alert",
                description="Test critical"
            )
        ]
        
        html = create_anomaly_alert_email(alerts, "N13.01.2026")
        
        assert "KHẨN CẤP" in html
        assert "#dc3545" in html  # Critical/red color
    
    def test_create_anomaly_alert_email_with_additional_info(self):
        """Test creating anomaly alert email with additional info."""
        alerts = [
            AnomalyAlert(level=AlertLevel.WARNING, title="Test", description="Test")
        ]
        
        html = create_anomaly_alert_email(
            alerts,
            "N13.01.2026",
            additional_info={"Operator": "Test Operator", "Location": "Yard A"}
        )
        
        assert "Operator" in html
        assert "Test Operator" in html
        assert "Location" in html


# =============================================================================
# Integration Tests
# =============================================================================

class TestEmailNotifierIntegration:
    """Integration tests for email notification workflow."""
    
    @patch('utils.email_notifier.EmailNotifier.send_notification')
    def test_send_reconciliation_notification(self, mock_send):
        """Test full reconciliation notification workflow."""
        mock_send.return_value = True
        
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 95,
                    'thieu': 3,
                    'thua': 2
                }
            }
        }
        
        smtp_config = {
            'server': 'smtp.test.com',
            'port': 587,
            'email': 'sender@test.com',
            'password': 'secret'
        }
        
        result = send_reconciliation_notification(
            results=results,
            date_str="N13.01.2026",
            recipients=["recipient@test.com"],
            smtp_config=smtp_config
        )
        
        assert result is True
        mock_send.assert_called_once()
    
    @patch('utils.email_notifier.EmailNotifier.send_notification')
    def test_send_anomaly_alert_no_alerts(self, mock_send):
        """Test sending anomaly alert with no alerts."""
        result = send_anomaly_alert(
            alerts=[],
            date_str="N13.01.2026",
            recipients=["test@test.com"],
            smtp_config={}
        )
        
        assert result is True
        mock_send.assert_not_called()
    
    @patch('utils.email_notifier.EmailNotifier.send_notification')
    def test_send_anomaly_alert_with_alerts(self, mock_send):
        """Test sending anomaly alert with alerts."""
        mock_send.return_value = True
        
        alerts = [
            AnomalyAlert(
                level=AlertLevel.WARNING,
                title="Test Warning",
                description="Test description"
            )
        ]
        
        smtp_config = {
            'server': 'smtp.test.com',
            'port': 587,
            'email': 'sender@test.com',
            'password': 'secret'
        }
        
        result = send_anomaly_alert(
            alerts=alerts,
            date_str="N13.01.2026",
            recipients=["test@test.com"],
            smtp_config=smtp_config
        )
        
        assert result is True
        mock_send.assert_called_once()
        
        # Check subject contains warning
        call_args = mock_send.call_args
        assert "CẢNH BÁO" in call_args[1]['subject']
    
    @patch('utils.email_notifier.EmailNotifier.send_notification')
    def test_full_anomaly_detection_and_alert_workflow(self, mock_send):
        """Test complete workflow: detect anomalies and send alert."""
        mock_send.return_value = True
        
        # Setup detector
        detector = AnomalyDetector(
            thieu_threshold=5,
            thua_threshold=5,
            match_rate_threshold=95.0
        )
        
        # Bad results that should trigger alerts
        results = {
            'main_results': {
                'counts': {
                    'ton_moi': 100,
                    'khop_chuan': 80,
                    'thieu': 10,
                    'thua': 10
                }
            }
        }
        
        # Detect anomalies
        alerts = detector.check_results(results)
        
        assert len(alerts) >= 1
        assert detector.has_warnings() or detector.has_critical_alerts()
        
        # Send alert
        smtp_config = {
            'server': 'smtp.test.com',
            'port': 587,
            'email': 'sender@test.com',
            'password': 'secret'
        }
        
        result = send_anomaly_alert(
            alerts=alerts,
            date_str="N13.01.2026",
            recipients=["ops@company.com"],
            smtp_config=smtp_config,
            additional_info={"System": "Production", "Run ID": "12345"}
        )
        
        assert result is True
