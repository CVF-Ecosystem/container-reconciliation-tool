# File: email_notifier.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import logging
from datetime import datetime
import pandas as pd
from typing import List
from config import EMAIL_SETTINGS

def send_report_email(report_folder: Path, summary_df: pd.DataFrame) -> None:
    """
    Soạn và gửi email báo cáo với các file quan trọng được đính kèm.
    """
    if not EMAIL_SETTINGS.get("enabled", False):
        logging.info("Tính năng gửi email đã bị tắt trong file config.")
        return

    try:
        logging.info("--- BẮT ĐẦU GỬI EMAIL BÁO CÁO ---")
        
        sender_email: str = EMAIL_SETTINGS["sender_email"]
        recipients: List[str] = EMAIL_SETTINGS["recipients"]
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ", ".join(recipients)
        
        today_str = datetime.now().strftime("%d/%m/%Y")
        msg['Subject'] = f"{EMAIL_SETTINGS['subject_prefix']} - Ngày {today_str}"

        # --- Tạo nội dung email ---
        try:
            thieu = summary_df.loc[summary_df['Hạng mục'] == 'Thiếu trên bãi', 'Số lượng'].iloc[0]
            thua = summary_df.loc[summary_df['Hạng mục'] == 'Thừa trên bãi', 'Số lượng'].iloc[0]
            khong_chung_tu = summary_df.loc[summary_df['Hạng mục'] == 'CẢNH BÁO: Rời bãi không có chứng từ', 'Số lượng'].iloc[0]
        except (IndexError, KeyError):
            logging.error("Không thể trích xuất KPI từ DataFrame summary để tạo nội dung email.")
            thieu, thua, khong_chung_tu = "N/A", "N/A", "N/A"

        html_body = f"""
        <html>
        <body>
            <p>Xin chào,</p>
            <p>Hệ thống đã hoàn tất chạy đối soát tự động cho ngày <strong>{today_str}</strong>.</p>
            <p>Kết quả tóm tắt:</p>
            <ul>
                <li>Số container <strong>Thiếu</strong> trên bãi: <strong>{thieu}</strong></li>
                <li>Số container <strong>Thừa</strong> trên bãi: <strong>{thua}</strong></li>
                <li style="color:red;">Cảnh báo rời bãi không chứng từ: <strong>{khong_chung_tu}</strong></li>
            </ul>
            <p>Vui lòng xem các file báo cáo chi tiết được đính kèm hoặc truy cập thư mục báo cáo.</p>
            <p><em>Đây là email được gửi tự động.</em></p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html'))

        # --- Đính kèm các file báo cáo quan trọng ---
        files_to_attach = [
            "0_Summary.xlsx",
            "3_Thieu_Tren_Bai_(Logic_Chinh).xlsx",
            "4_Thua_Tren_Bai_(Logic_Chinh).xlsx",
            "10_CANH_BAO_Roi_Bai_KHONG_Chung_Tu.xlsx"
        ]

        for filename in files_to_attach:
            file_path = report_folder / filename
            if file_path.exists():
                try:
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename= {filename}")
                    msg.attach(part)
                    logging.info(f"  -> Đã đính kèm file: {filename}")
                except Exception as attach_error:
                    logging.error(f"Không thể đính kèm file {filename}: {attach_error}")

        # --- Gửi email ---
        server = smtplib.SMTP(EMAIL_SETTINGS["smtp_server"], EMAIL_SETTINGS["smtp_port"])
        server.starttls()
        server.login(sender_email, EMAIL_SETTINGS["sender_password"])
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        
        logging.info(f"--- ĐÃ GỬI EMAIL THÀNH CÔNG TỚI: {', '.join(recipients)} ---")

    except Exception as e:
        logging.error(f"Lỗi nghiêm trọng khi gửi email: {e}", exc_info=True)