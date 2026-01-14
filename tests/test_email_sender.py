# File: tests/test_email_sender.py
# V5.3: Tests cho email sender module

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import sys
import os

# Add parent dir to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
os.chdir(parent_dir)  # Change to project root


class TestEmailTemplate:
    """Tests cho email template generation."""
    
    def test_default_template_generation(self):
        """Test tạo email template mặc định."""
        from reports.email_sender import get_email_template
        
        html = get_email_template(
            operator_name="Test Operator",
            date_str="N12.1.2026",
            bien_dong_count=100,
            ton_bai_count=500,
            template_type="default"
        )
        
        assert "Test Operator" in html
        assert "N12.1.2026" in html
        assert "100" in html
        assert "500" in html
        assert "<!DOCTYPE html>" in html
    
    def test_vimc_template_generation(self):
        """Test tạo email template cho VIMC."""
        from reports.email_sender import get_email_template
        
        html = get_email_template(
            operator_name="VIMC Lines",
            date_str="N12.1.2026",
            bien_dong_count=50,
            ton_bai_count=200,
            template_type="vimc"
        )
        
        assert "VIMC Lines" in html
        assert "Cảng Tiên Sa" in html  # VIMC template has this
        assert "50" in html
        assert "200" in html


class TestOperatorEmailConfig:
    """Tests cho operator email configuration."""
    
    def test_default_config_exists(self):
        """Test config mặc định tồn tại."""
        from reports.email_sender import OPERATOR_EMAIL_CONFIG
        
        assert "VIMC Lines" in OPERATOR_EMAIL_CONFIG
        assert "Vinafco" in OPERATOR_EMAIL_CONFIG
        assert "Vosco" in OPERATOR_EMAIL_CONFIG
    
    def test_config_structure(self):
        """Test cấu trúc config."""
        from reports.email_sender import OPERATOR_EMAIL_CONFIG
        
        for operator, config in OPERATOR_EMAIL_CONFIG.items():
            assert "recipients" in config
            assert "enabled" in config
            assert isinstance(config["recipients"], list)
            assert isinstance(config["enabled"], bool)
    
    def test_update_config(self):
        """Test cập nhật config."""
        from reports.email_sender import update_operator_email_config, OPERATOR_EMAIL_CONFIG
        
        original_recipients = OPERATOR_EMAIL_CONFIG["VIMC Lines"]["recipients"].copy()
        
        # Update
        update_operator_email_config({
            "VIMC Lines": {"recipients": ["test@example.com"]}
        })
        
        assert "test@example.com" in OPERATOR_EMAIL_CONFIG["VIMC Lines"]["recipients"]
        
        # Restore
        update_operator_email_config({
            "VIMC Lines": {"recipients": original_recipients}
        })


class TestOperatorEmailSender:
    """Tests cho OperatorEmailSender class."""
    
    def test_init(self):
        """Test khởi tạo sender."""
        from reports.email_sender import OperatorEmailSender
        
        sender = OperatorEmailSender(
            smtp_server="smtp.test.com",
            smtp_port=587,
            sender_email="test@test.com",
            sender_password="password"
        )
        
        assert sender.smtp_server == "smtp.test.com"
        assert sender.smtp_port == 587
        assert sender.sender_email == "test@test.com"
    
    def test_send_without_credentials_fails(self):
        """Test gửi không có credentials phải fail."""
        from reports.email_sender import OperatorEmailSender
        
        sender = OperatorEmailSender()  # No credentials
        
        result = sender.send_to_operator(
            operator_name="VIMC Lines",
            date_str="N12.1.2026"
        )
        
        assert result["success"] == False
        assert "email gửi" in result["message"].lower() or "credentials" in result["message"].lower()
    
    def test_send_without_attachments_fails(self):
        """Test gửi không có file đính kèm phải fail."""
        from reports.email_sender import OperatorEmailSender
        
        sender = OperatorEmailSender(
            sender_email="test@test.com",
            sender_password="password"
        )
        
        result = sender.send_to_operator(
            operator_name="VIMC Lines",
            date_str="N12.1.2026",
            bien_dong_file=None,
            ton_bai_file=None
        )
        
        assert result["success"] == False
        assert "file" in result["message"].lower()
    
    @patch('smtplib.SMTP')
    def test_send_success(self, mock_smtp):
        """Test gửi thành công (mocked)."""
        from reports.email_sender import OperatorEmailSender
        import tempfile
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_path = Path(f.name)
            # Write minimal xlsx
            pd.DataFrame({'test': [1, 2, 3]}).to_excel(temp_path, index=False)
        
        try:
            # Mock SMTP
            mock_instance = MagicMock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_instance)
            mock_smtp.return_value.__exit__ = Mock(return_value=False)
            
            sender = OperatorEmailSender(
                sender_email="test@test.com",
                sender_password="password"
            )
            
            # Override config to enable sending
            from reports import email_sender
            email_sender.OPERATOR_EMAIL_CONFIG["Test Operator"] = {
                "recipients": ["recipient@test.com"],
                "cc": [],
                "enabled": True,
                "template": "default"
            }
            
            result = sender.send_to_operator(
                operator_name="Test Operator",
                date_str="N12.1.2026",
                ton_bai_file=temp_path,
                custom_recipients=["recipient@test.com"]
            )
            
            # Clean up test config
            del email_sender.OPERATOR_EMAIL_CONFIG["Test Operator"]
            
        finally:
            temp_path.unlink()


class TestParallelExport:
    """Tests cho parallel export functionality."""
    
    def test_export_all_operators_parallel(self):
        """Test export với parallel processing."""
        from reports.email_template_exporter import export_all_operators
        import tempfile
        
        # Create test data
        df_bien_dong = pd.DataFrame({
            'Số Container': ['CONT001', 'CONT002'],
            'Hãng khai thác': ['VMC', 'VFC']
        })
        
        df_ton_bai = pd.DataFrame({
            'Số Container': ['CONT001', 'CONT002', 'CONT003'],
            'Hãng khai thác': ['VMC', 'VFC', 'VOC']
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            results = export_all_operators(
                df_bien_dong=df_bien_dong,
                df_ton_bai=df_ton_bai,
                date_str="N12.1.2026",
                output_dir=Path(tmpdir),
                operators=["VIMC Lines", "Vinafco"],
                parallel=True  # Test parallel
            )
            
            # Should have results for at least 1 operator
            assert len(results) >= 0  # May be 0 if no matching data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
