# File: reports/email_sender.py
# V5.4: Auto-send Email với external config và improved error handling

import smtplib
import logging
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


def load_email_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load email configuration from external JSON file.
    
    Args:
        config_path: Path to email_config.json (default: ./email_config.json)
        
    Returns:
        Dict with smtp_settings and operator_recipients
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "email_config.json"
    
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logging.info(f"Loaded email config from {config_path}")
                return config
        else:
            logging.warning(f"Email config file not found: {config_path}, using defaults")
            return _get_default_config()
    except Exception as e:
        logging.error(f"Error loading email config: {e}, using defaults")
        return _get_default_config()


def _get_default_config() -> Dict[str, Any]:
    """Return default email configuration."""
    return {
        "smtp_settings": {
            "server": "smtp.gmail.com",
            "port": 587,
            "use_tls": True,
            "enabled": False
        },
        "operator_recipients": {
            "VIMC Lines": {
                "recipients": ["vimc.ops@example.com"],
                "cc": [],
                "enabled": True,
                "template": "vimc",
                "max_attachment_size_mb": 20
            }
        }
    }


# Load config at module level
_EMAIL_CONFIG = load_email_config()
OPERATOR_EMAIL_CONFIG = _EMAIL_CONFIG.get("operator_recipients", {})


def get_email_template(operator_name: str, date_str: str, 
                       bien_dong_count: int, ton_bai_count: int,
                       template_type: str = "default") -> str:
    """
    Tạo HTML email template cho từng hãng tàu.
    
    Args:
        operator_name: Tên hãng tàu
        date_str: Chuỗi ngày (VD: N12.1.2026)
        bien_dong_count: Số lượng container biến động
        ton_bai_count: Số lượng container tồn bãi
        template_type: Loại template (default, vimc, ...)
    """
    current_time = datetime.now().strftime("%H:%M %d/%m/%Y")
    
    if template_type == "vimc":
        # Template riêng cho VIMC Lines
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 650px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #1a5276 0%, #2980b9 100%); color: white; padding: 25px; border-radius: 10px 10px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 22px; }}
                .header .date {{ font-size: 14px; margin-top: 5px; opacity: 0.9; }}
                .content {{ background: #f8f9fa; padding: 25px; border: 1px solid #ddd; }}
                .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .stat-box {{ text-align: center; padding: 15px 25px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stat-number {{ font-size: 32px; font-weight: bold; color: #1a5276; }}
                .stat-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
                .attachments {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin-top: 20px; }}
                .attachments h3 {{ margin: 0 0 10px 0; color: #856404; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; border-top: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 BÁO CÁO TỒN BÃI - {operator_name}</h1>
                    <div class="date">{date_str} | Tạo lúc: {current_time}</div>
                </div>
                
                <div class="content">
                    <p>Kính gửi Quý đối tác <strong>{operator_name}</strong>,</p>
                    <p>Cảng Tiên Sa - Tân Thuận trân trọng gửi báo cáo tồn bãi container định kỳ:</p>
                    
                    <div class="stats">
                        <div class="stat-box">
                            <div class="stat-number">{ton_bai_count:,}</div>
                            <div class="stat-label">Container Tồn Bãi</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-number">{bien_dong_count:,}</div>
                            <div class="stat-label">Biến Động Trong Kỳ</div>
                        </div>
                    </div>
                    
                    <div class="attachments">
                        <h3>📎 File đính kèm:</h3>
                        <ul>
                            <li><strong>TON BAI - {operator_name}.xlsx</strong>: Danh sách chi tiết container đang tồn</li>
                            <li><strong>BIEN DONG - {operator_name}.xlsx</strong>: Chi tiết các giao dịch nhập/xuất</li>
                        </ul>
                    </div>
                    
                    <p style="margin-top: 20px;">Mọi thắc mắc xin liên hệ: <strong>ops@tientanthuanport.vn</strong></p>
                </div>
                
                <div class="footer">
                    <p>© 2026 Cảng Tiên Sa - Tân Thuận | Container Inventory System V5.3</p>
                    <p><em>Email được gửi tự động - Vui lòng không reply</em></p>
                </div>
            </div>
        </body>
        </html>
        """
    else:
        # Default template
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f5f5f5; padding: 20px; }}
                .highlight {{ font-size: 24px; font-weight: bold; color: #2980b9; }}
                .footer {{ text-align: center; padding: 15px; color: #666; font-size: 11px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #2c3e50; color: white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>📦 Báo Cáo Tồn Bãi Container - {operator_name}</h2>
                    <div>Ngày: {date_str} | Thời gian: {current_time}</div>
                </div>
                
                <div class="content">
                    <p>Kính gửi <strong>{operator_name}</strong>,</p>
                    <p>Đính kèm là báo cáo tồn bãi container định kỳ:</p>
                    
                    <table>
                        <tr>
                            <th>Chỉ số</th>
                            <th>Số lượng</th>
                        </tr>
                        <tr>
                            <td>Container tồn bãi</td>
                            <td class="highlight">{ton_bai_count:,}</td>
                        </tr>
                        <tr>
                            <td>Biến động trong kỳ</td>
                            <td class="highlight">{bien_dong_count:,}</td>
                        </tr>
                    </table>
                    
                    <p><strong>File đính kèm:</strong></p>
                    <ul>
                        <li>TON BAI - {operator_name}.xlsx</li>
                        <li>BIEN DONG - {operator_name}.xlsx</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>Container Inventory System V5.3 | © 2026</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    return html


class OperatorEmailSender:
    """Gửi email tự động cho từng hãng tàu với file template."""
    
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
        self._connection = None
    
    def _connect(self) -> bool:
        """Thiết lập kết nối SMTP."""
        try:
            self._connection = smtplib.SMTP(self.smtp_server, self.smtp_port)
            if self.use_tls:
                self._connection.starttls()
            self._connection.login(self.sender_email, self.sender_password)
            return True
        except Exception as e:
            logging.error(f"Không thể kết nối SMTP: {e}")
            return False
    
    def _disconnect(self):
        """Đóng kết nối SMTP."""
        if self._connection:
            try:
                self._connection.quit()
            except:
                pass
            self._connection = None
    
    def _attach_file(self, msg: MIMEMultipart, file_path: Path) -> bool:
        """Đính kèm file vào email."""
        try:
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            # Encode filename for non-ASCII characters
            filename = file_path.name
            part.add_header(
                'Content-Disposition',
                'attachment',
                filename=('utf-8', '', filename)
            )
            msg.attach(part)
            return True
        except Exception as e:
            logging.warning(f"Không thể đính kèm file {file_path}: {e}")
            return False
    
    def send_to_operator(
        self,
        operator_name: str,
        date_str: str,
        bien_dong_file: Optional[Path] = None,
        ton_bai_file: Optional[Path] = None,
        custom_recipients: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Gửi email cho một hãng tàu.
        
        Args:
            operator_name: Tên hãng tàu
            date_str: Chuỗi ngày
            bien_dong_file: Path đến file BIEN DONG
            ton_bai_file: Path đến file TON BAI
            custom_recipients: Override recipients (for testing)
            
        Returns:
            Dict với status và message
        """
        result = {
            "operator": operator_name,
            "success": False,
            "message": "",
            "recipients": []
        }
        
        # Check config
        op_config = OPERATOR_EMAIL_CONFIG.get(operator_name, {})
        if not op_config.get("enabled", False):
            result["message"] = "Email bị tắt cho hãng này"
            return result
        
        recipients = custom_recipients or op_config.get("recipients", [])
        if not recipients:
            result["message"] = "Không có email người nhận"
            return result
        
        # Check credentials
        if not self.sender_email or not self.sender_password:
            result["message"] = "Chưa cấu hình email gửi"
            return result
        
        # Check attachments with improved error handling
        attachments = []
        bien_dong_count = 0
        ton_bai_count = 0
        max_size_mb = op_config.get("max_attachment_size_mb", 20)
        
        def safe_get_row_count(filepath: Path) -> int:
            """Safely get Excel file row count."""
            try:
                import pandas as pd
                # Use nrows to avoid loading entire file
                test_df = pd.read_excel(filepath, nrows=0)
                # Now get actual count
                df = pd.read_excel(filepath)
                return len(df)
            except FileNotFoundError:
                logging.error(f"File not found: {filepath}")
                return 0
            except PermissionError:
                logging.error(f"Permission denied: {filepath}")
                return 0
            except Exception as e:
                logging.warning(f"Cannot read Excel file {filepath.name}: {type(e).__name__} - {e}")
                return 0
        
        if bien_dong_file and bien_dong_file.exists():
            try:
                file_size_mb = bien_dong_file.stat().st_size / (1024 * 1024)
                if file_size_mb > max_size_mb:
                    logging.warning(f"File {bien_dong_file.name} quá lớn ({file_size_mb:.1f}MB > {max_size_mb}MB), bỏ qua")
                else:
                    attachments.append(bien_dong_file)
                    bien_dong_count = safe_get_row_count(bien_dong_file)
            except OSError as e:
                logging.error(f"OS error accessing {bien_dong_file}: {e}")
        
        if ton_bai_file and ton_bai_file.exists():
            try:
                file_size_mb = ton_bai_file.stat().st_size / (1024 * 1024)
                if file_size_mb > max_size_mb:
                    logging.warning(f"File {ton_bai_file.name} quá lớn ({file_size_mb:.1f}MB > {max_size_mb}MB), bỏ qua")
                else:
                    attachments.append(ton_bai_file)
                    ton_bai_count = safe_get_row_count(ton_bai_file)
            except OSError as e:
                logging.error(f"OS error accessing {ton_bai_file}: {e}")
            if file_size_mb > 20:
                logging.warning(f"File {ton_bai_file.name} quá lớn ({file_size_mb:.1f}MB), bỏ qua")
            else:
                attachments.append(ton_bai_file)
                try:
                    import pandas as pd
                    df = pd.read_excel(ton_bai_file, nrows=1000)  # Limit rows for count
                    ton_bai_count = len(pd.read_excel(ton_bai_file))
                except Exception as e:
                    logging.warning(f"Không thể đọc file {ton_bai_file.name}: {e}")
                    ton_bai_count = 0
        
        if not attachments:
            result["message"] = "Không có file đính kèm"
            return result
        
        # Create email
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"📊 Báo Cáo Tồn Bãi - {operator_name} - {date_str}"
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(recipients)
            
            cc_list = op_config.get("cc", [])
            if cc_list:
                msg['Cc'] = ', '.join(cc_list)
                recipients = recipients + cc_list
            
            # HTML body
            template_type = op_config.get("template", "default")
            html_body = get_email_template(
                operator_name, date_str, 
                bien_dong_count, ton_bai_count,
                template_type
            )
            msg.attach(MIMEText(html_body, 'html'))
            
            # Attach files
            for file_path in attachments:
                self._attach_file(msg, file_path)
            
            # Send
            if not self._connection:
                if not self._connect():
                    result["message"] = "Không thể kết nối SMTP server"
                    return result
            
            self._connection.sendmail(self.sender_email, recipients, msg.as_string())
            
            result["success"] = True
            result["recipients"] = recipients
            result["message"] = f"Đã gửi thành công đến {len(recipients)} địa chỉ"
            logging.info(f"✅ Email sent to {operator_name}: {', '.join(recipients)}")
            
        except Exception as e:
            result["message"] = str(e)
            logging.error(f"❌ Email failed for {operator_name}: {e}")
        
        return result
    
    def send_to_all_operators(
        self,
        export_results: Dict[str, Dict[str, Path]],
        date_str: str,
        parallel: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        Gửi email cho tất cả hãng tàu có file.
        
        Args:
            export_results: Dict từ email_template_exporter.export_all_operators
            date_str: Chuỗi ngày
            parallel: Gửi song song (cần connection pool)
            
        Returns:
            Dict với kết quả gửi cho từng hãng
        """
        results = {}
        
        if not export_results:
            logging.warning("[EmailSender] Không có file để gửi")
            return results
        
        logging.info(f"=== BẮT ĐẦU GỬI EMAIL CHO {len(export_results)} HÃNG ===")
        
        # Connect once, send multiple
        if not self._connect():
            logging.error("Không thể kết nối SMTP server")
            return results
        
        try:
            for operator, files in export_results.items():
                bien_dong_file = files.get('bien_dong')
                ton_bai_file = files.get('ton_bai')
                
                result = self.send_to_operator(
                    operator_name=operator,
                    date_str=date_str,
                    bien_dong_file=bien_dong_file,
                    ton_bai_file=ton_bai_file
                )
                results[operator] = result
        
        finally:
            self._disconnect()
        
        # Summary
        success_count = sum(1 for r in results.values() if r.get("success"))
        logging.info(f"=== HOÀN TẤT: {success_count}/{len(results)} email gửi thành công ===")
        
        return results


def send_operator_emails(
    export_results: Dict[str, Dict[str, Path]],
    date_str: str,
    smtp_config: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function để gửi email cho tất cả hãng.
    
    Args:
        export_results: Kết quả từ export_all_operators
        date_str: Chuỗi ngày
        smtp_config: Dict với keys: server, port, email, password
        
    Returns:
        Dict kết quả gửi
    """
    sender = OperatorEmailSender(
        smtp_server=smtp_config.get('server', 'smtp.gmail.com'),
        smtp_port=smtp_config.get('port', 587),
        sender_email=smtp_config.get('email', ''),
        sender_password=smtp_config.get('password', '')
    )
    
    return sender.send_to_all_operators(export_results, date_str)


def update_operator_email_config(config_updates: Dict[str, Dict]) -> None:
    """
    Cập nhật email config cho operators.
    
    Args:
        config_updates: Dict với format {operator_name: {recipients: [...], enabled: bool}}
    """
    global OPERATOR_EMAIL_CONFIG
    
    for operator, updates in config_updates.items():
        if operator in OPERATOR_EMAIL_CONFIG:
            OPERATOR_EMAIL_CONFIG[operator].update(updates)
        else:
            OPERATOR_EMAIL_CONFIG[operator] = {
                "recipients": updates.get("recipients", []),
                "cc": updates.get("cc", []),
                "enabled": updates.get("enabled", True),
                "template": updates.get("template", "default")
            }
    
    logging.info(f"Đã cập nhật email config cho {len(config_updates)} hãng")
