# File: gui/dialogs.py
"""Các dialog cơ bản: TextHandler, AppearanceDialog, SettingsDialog, ExportDialog"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import logging
from pathlib import Path
from datetime import datetime
import configparser
import os

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
except ImportError:
    pass

import config
from utils.gui_translator import gui_translator, t

SETTINGS_FILE = Path("gui_settings.ini")


class TextHandler(logging.Handler):
    """Handler để hiển thị log lên GUI"""
    def __init__(self, text_queue):
        super().__init__()
        self.text_queue = text_queue
    
    def emit(self, record):
        self.text_queue.put(self.format(record))


class AppearanceDialog(ttkb.Toplevel):
    """V5.0: Dialog for Theme and Language selection with live switching."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("gui_appearance"))
        self.geometry("420x450")
        self.transient(parent)
        self.parent_app = parent
        
        self.theme_var = tk.StringVar(value="litera")
        self.language_var = tk.StringVar(value="vi")
        
        self.load_current_settings()
        self.create_widgets()
    
    def load_current_settings(self):
        """Load current theme and language from settings."""
        try:
            config_parser = configparser.ConfigParser()
            if SETTINGS_FILE.exists():
                config_parser.read(SETTINGS_FILE)
                self.theme_var.set(config_parser.get('Appearance', 'theme', fallback='litera'))
                self.language_var.set(config_parser.get('Appearance', 'language', fallback='vi'))
        except:
            pass
    
    def create_widgets(self):
        main_frame = ttkb.Frame(self, padding=20)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Theme Section
        theme_frame = ttkb.LabelFrame(main_frame, text=f"🎨 {t('gui_theme')}", padding=10)
        theme_frame.pack(pady=10, fill="x")
        
        theme_options = [
            ("☀️ Light", "litera"),
            ("🌙 Dark", "darkly"),
            ("🔵 Blue", "cosmo"),
            ("🟢 Green", "minty"),
            ("🟣 Purple", "pulse")
        ]
        
        for text, value in theme_options:
            ttkb.Radiobutton(
                theme_frame, text=text, variable=self.theme_var, value=value,
                bootstyle="info-toolbutton", command=self.on_theme_change
            ).pack(anchor="w", pady=2)
        
        # Language Section
        lang_frame = ttkb.LabelFrame(main_frame, text=f"🌐 {t('gui_language')}", padding=10)
        lang_frame.pack(pady=10, fill="x")
        
        lang_options = [
            ("🇻🇳 Tiếng Việt", "vi"),
            ("🇬🇧 English", "en")
        ]
        
        for text, value in lang_options:
            ttkb.Radiobutton(
                lang_frame, text=text, variable=self.language_var, value=value,
                bootstyle="success-toolbutton", command=self.on_language_change
            ).pack(anchor="w", pady=2)
        
        # Buttons
        btn_frame = ttkb.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttkb.Button(btn_frame, text=t("gui_save_apply"), command=self.save_and_close, bootstyle=SUCCESS).pack(side="left", padx=5)
        ttkb.Button(btn_frame, text=t("gui_cancel"), command=self.destroy, bootstyle=SECONDARY).pack(side="left", padx=5)
    
    def on_theme_change(self):
        """Apply theme immediately."""
        new_theme = self.theme_var.get()
        try:
            self.parent_app.style.theme_use(new_theme)
            logging.info(f"[Theme] Applied: {new_theme}")
        except Exception as e:
            logging.warning(f"[Theme] Could not apply: {e}")
    
    def on_language_change(self):
        """Apply language immediately."""
        new_lang = self.language_var.get()
        gui_translator.set_language(new_lang)
        logging.info(f"[Language] Applied: {new_lang}")
    
    def save_and_close(self):
        """Save settings to file and close."""
        try:
            config_parser = configparser.ConfigParser()
            if SETTINGS_FILE.exists():
                config_parser.read(SETTINGS_FILE)
            
            if 'Appearance' not in config_parser:
                config_parser['Appearance'] = {}
            
            config_parser['Appearance']['theme'] = self.theme_var.get()
            config_parser['Appearance']['language'] = self.language_var.get()
            
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                config_parser.write(f)
            
            logging.info("[Appearance] Settings saved")
        except Exception as e:
            logging.error(f"[Appearance] Could not save: {e}")
        
        self.destroy()


class SettingsDialog(ttkb.Toplevel):
    """Dialog cài đặt tự động hóa (lịch chạy, email)"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("gui_settings_title"))
        self.geometry("480x580")
        self.transient(parent)
        self.parent_app = parent
        self.config = configparser.ConfigParser()
        self.config_path = SETTINGS_FILE
        
        self.schedule_enabled_var = tk.BooleanVar()
        self.schedule_time_var = tk.StringVar()
        self.email_enabled_var = tk.BooleanVar()
        self.recipient_email_var = tk.StringVar()
        self.smtp_server_var = tk.StringVar()
        self.smtp_port_var = tk.StringVar()
        self.smtp_user_var = tk.StringVar()
        self.smtp_pass_var = tk.StringVar()
        
        self.create_widgets()
        self.load_settings()

    def create_widgets(self):
        main_frame = ttkb.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Schedule section
        schedule_frame = ttkb.LabelFrame(main_frame, text=t("gui_settings_schedule"), padding=10)
        schedule_frame.pack(pady=10, fill="x")
        
        ttkb.Checkbutton(
            schedule_frame, text=t("gui_settings_enable_schedule"), 
            variable=self.schedule_enabled_var, bootstyle="success-round-toggle"
        ).pack(anchor="w", pady=5)
        
        time_entry_frame = ttkb.Frame(schedule_frame)
        time_entry_frame.pack(pady=5, fill="x", padx=5)
        ttkb.Label(time_entry_frame, text=t("gui_settings_run_at")).pack(side="left")
        ttkb.Entry(time_entry_frame, textvariable=self.schedule_time_var, width=10).pack(side="left", padx=5)
        
        # Email section
        email_frame = ttkb.LabelFrame(main_frame, text=t("gui_settings_email"), padding=10)
        email_frame.pack(pady=10, fill="x")
        
        ttkb.Checkbutton(
            email_frame, text=t("gui_settings_enable_email"), 
            variable=self.email_enabled_var, bootstyle="success-round-toggle"
        ).pack(anchor="w", pady=5)
        
        grid_frame = ttkb.Frame(email_frame)
        grid_frame.pack(fill="x", padx=5, pady=5)
        grid_frame.columnconfigure(1, weight=1)
        
        fields = {
            t("gui_settings_recipient"): self.recipient_email_var,
            t("gui_settings_smtp_server"): self.smtp_server_var,
            t("gui_settings_smtp_port"): self.smtp_port_var,
            t("gui_settings_smtp_user"): self.smtp_user_var,
            t("gui_settings_smtp_pass"): self.smtp_pass_var
        }
        
        for i, (label, var) in enumerate(fields.items()):
            ttkb.Label(grid_frame, text=label).grid(row=i, column=0, sticky="w", pady=3, padx=5)
            entry = ttkb.Entry(grid_frame, textvariable=var)
            if t("gui_settings_smtp_pass") in label:
                entry.config(show="*")
            entry.grid(row=i, column=1, sticky="ew", pady=3)
        
        # Save button
        save_button = ttkb.Button(main_frame, text=t("gui_settings_save"), command=self.save_settings, bootstyle=SUCCESS)
        save_button.pack(pady=20)

    def load_settings(self):
        if self.config_path.exists():
            self.config.read(self.config_path)
            self.schedule_enabled_var.set(self.config.getboolean('Schedule', 'enabled', fallback=False))
            self.schedule_time_var.set(self.config.get('Schedule', 'run_time', fallback='08:00'))
            self.email_enabled_var.set(self.config.getboolean('Email', 'enabled', fallback=False))
            self.recipient_email_var.set(self.config.get('Email', 'recipients', fallback=''))
            self.smtp_server_var.set(self.config.get('Email', 'smtp_server', fallback='smtp.gmail.com'))
            self.smtp_port_var.set(self.config.get('Email', 'smtp_port', fallback='587'))
            self.smtp_user_var.set(self.config.get('Email', 'smtp_user', fallback=''))
            self.smtp_pass_var.set(self.config.get('Email', 'smtp_password', fallback=''))

    def save_settings(self):
        # Load existing config to preserve Appearance settings
        if self.config_path.exists():
            self.config.read(self.config_path)
        
        self.config['Schedule'] = {
            'enabled': str(self.schedule_enabled_var.get()),
            'run_time': self.schedule_time_var.get()
        }
        self.config['Email'] = {
            'enabled': str(self.email_enabled_var.get()),
            'recipients': self.recipient_email_var.get(),
            'smtp_server': self.smtp_server_var.get(),
            'smtp_port': self.smtp_port_var.get(),
            'smtp_user': self.smtp_user_var.get(),
            'smtp_password': self.smtp_pass_var.get()
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)
        
        messagebox.showinfo(t("msg_title_saved"), t("msg_settings_saved"), parent=self)
        self.destroy()


class ExportDialog(ttkb.Toplevel):
    """Dialog để trích xuất dữ liệu lịch sử"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("gui_export_dialog_title"))
        self.geometry("520x580")
        self.transient(parent)
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttkb.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Header
        ttkb.Label(main_frame, text=t("gui_export_choose"), font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        
        # Button grid frame
        btn_frame = ttkb.Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
        
        # Export buttons
        ttkb.Button(btn_frame, text=t("gui_export_snapshot"), command=self.export_snapshot, width=35, bootstyle=PRIMARY).pack(pady=5, anchor="w")
        ttkb.Button(btn_frame, text=t("gui_export_compare"), command=self.compare_dates, width=35, bootstyle=INFO).pack(pady=5, anchor="w")
        ttkb.Button(btn_frame, text=t("gui_export_trend"), command=self.show_trend, width=35, bootstyle=SUCCESS).pack(pady=5, anchor="w")
        ttkb.Button(btn_frame, text=t("gui_export_lookup"), command=self.lookup_container, width=35, bootstyle=WARNING).pack(pady=5, anchor="w")
        
        # V5.0: Power BI Export
        ttkb.Label(btn_frame, text="").pack(pady=5)
        ttkb.Label(btn_frame, text=t("gui_export_powerbi_label"), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttkb.Button(btn_frame, text=t("gui_export_powerbi"), command=self.export_powerbi, width=35, bootstyle=(SUCCESS, "outline")).pack(pady=5, anchor="w")
        
        # V5.1.4: Export theo hãng tàu
        ttkb.Label(btn_frame, text="").pack(pady=3)
        ttkb.Label(btn_frame, text=t("gui_export_by_hang_label"), font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttkb.Button(btn_frame, text=t("gui_export_by_hang"), command=self.open_hang_tau_dialog, width=35, bootstyle=(INFO, "outline")).pack(pady=5, anchor="w")
        
        # Available dates
        self.dates_label = ttkb.Label(main_frame, text="", font=("Segoe UI", 9))
        self.dates_label.pack(anchor="w", pady=(20, 0))
        self.load_available_dates()
    
    def open_hang_tau_dialog(self):
        """V5.1.4: Mở dialog xuất theo hãng tàu"""
        from .export_dialog import HangTauExportDialog
        HangTauExportDialog(self)
    
    def load_available_dates(self):
        try:
            from utils.history_db import HistoryDatabase
            db = HistoryDatabase(config.OUTPUT_DIR)
            dates = db.get_available_dates(limit=30)
            if dates:
                dates_count = len(dates)
                first_date = dates[-1]
                last_date = dates[0]
                if first_date == last_date:
                    date_range = first_date
                else:
                    date_range = f"{first_date} → {last_date}"
                self.dates_label.config(text=t("gui_data_available", dates_count, date_range))
            else:
                self.dates_label.config(text=t("gui_no_data"))
        except Exception as e:
            self.dates_label.config(text=f"Error: {e}")
    
    def export_snapshot(self):
        dialog = ttkb.Toplevel(self)
        dialog.title("Xuất Snapshot")
        dialog.geometry("300x200")
        dialog.transient(self)
        
        ttkb.Label(dialog, text="Từ ngày:").pack(pady=5)
        start_entry = ttkb.Entry(dialog, width=15)
        start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        start_entry.pack()
        
        ttkb.Label(dialog, text="Đến ngày:").pack(pady=5)
        end_entry = ttkb.Entry(dialog, width=15)
        end_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        end_entry.pack()
        
        def do_export():
            try:
                from utils.history_db import HistoryDatabase
                db = HistoryDatabase(config.OUTPUT_DIR)
                start = datetime.strptime(start_entry.get(), '%Y-%m-%d')
                end = datetime.strptime(end_entry.get(), '%Y-%m-%d')
                path = db.export_snapshot_range(start, end)
                messagebox.showinfo("Thành công", f"Đã xuất ra:\n{path}", parent=self)
                os.startfile(path)
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Lỗi", str(e), parent=self)
        
        ttkb.Button(dialog, text="Xuất", command=do_export, bootstyle=SUCCESS).pack(pady=20)
    
    def compare_dates(self):
        dialog = ttkb.Toplevel(self)
        dialog.title("So sánh 2 ngày")
        dialog.geometry("300x200")
        dialog.transient(self)
        
        ttkb.Label(dialog, text="Ngày 1 (cũ):").pack(pady=5)
        date1_entry = ttkb.Entry(dialog, width=15)
        date1_entry.pack()
        
        ttkb.Label(dialog, text="Ngày 2 (mới):").pack(pady=5)
        date2_entry = ttkb.Entry(dialog, width=15)
        date2_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date2_entry.pack()
        
        def do_compare():
            try:
                from utils.history_db import HistoryDatabase
                db = HistoryDatabase(config.OUTPUT_DIR)
                date1 = datetime.strptime(date1_entry.get(), '%Y-%m-%d')
                date2 = datetime.strptime(date2_entry.get(), '%Y-%m-%d')
                result = db.compare_two_dates(date1, date2)
                summary = result.get('summary', {})
                msg = f"So sánh {date1_entry.get()} vs {date2_entry.get()}:\n\n"
                msg += f"Tồn ngày 1: {summary.get('ton_1', 0)}\n"
                msg += f"Tồn ngày 2: {summary.get('ton_2', 0)}\n"
                msg += f"Mới vào: {summary.get('moi_vao', 0)}\n"
                msg += f"Đã rời: {summary.get('da_roi', 0)}\n"
                msg += f"Vẫn tồn: {summary.get('van_ton', 0)}"
                messagebox.showinfo("Kết quả", msg, parent=self)
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Lỗi", str(e), parent=self)
        
        ttkb.Button(dialog, text="So sánh", command=do_compare, bootstyle=INFO).pack(pady=20)
    
    def show_trend(self):
        try:
            from utils.history_db import HistoryDatabase
            db = HistoryDatabase(config.OUTPUT_DIR)
            df = db.get_inventory_trend(days=30)
            if df.empty:
                messagebox.showinfo("Thông tin", "Chưa có dữ liệu tồn bãi", parent=self)
                return
            msg = "=== Tồn bãi thời điểm kiểm tra ===\n\n"
            for _, row in df.iterrows():
                msg += f"{row['Ngày']}: {row['Số lượng container']:,} container\n"
            messagebox.showinfo("Tồn bãi", msg, parent=self)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e), parent=self)
    
    def lookup_container(self):
        container_id = simpledialog.askstring("Tra cứu", "Nhập số container:", parent=self)
        if not container_id:
            return
        try:
            from utils.history_db import HistoryDatabase
            db = HistoryDatabase(config.OUTPUT_DIR)
            path = db.export_container_history(container_id)
            messagebox.showinfo("Thành công", f"Đã xuất lịch sử:\n{path}", parent=self)
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e), parent=self)
    
    def export_powerbi(self):
        """V5.0: Export data for Power BI."""
        try:
            from utils.powerbi_export import export_for_powerbi
            
            days = simpledialog.askinteger(
                "Power BI Export",
                "Số ngày dữ liệu cần xuất:",
                initialvalue=30,
                minvalue=7,
                maxvalue=365,
                parent=self
            )
            
            if not days:
                return
            
            logging.info(f"[PowerBI] Exporting {days} days data...")
            output_file = export_for_powerbi(config.OUTPUT_DIR, days=days)
            
            if output_file and output_file.exists():
                messagebox.showinfo(
                    "Export thành công",
                    f"Đã tạo file Power BI data:\n\n"
                    f"📁 {output_file.name}\n\n"
                    f"Bao gồm 7 sheets:\n"
                    f"• Inventory_Trend\n"
                    f"• Current_Inventory\n"
                    f"• Transactions\n"
                    f"• Discrepancy_Trend\n"
                    f"• By_Operator\n"
                    f"• Dwell_Time\n"
                    f"• _Metadata",
                    parent=self
                )
                os.startfile(str(output_file.parent))
                logging.info(f"[PowerBI] Exported to {output_file}")
            else:
                messagebox.showwarning(t("msg_title_error"), t("gui_export_powerbi_failed"), parent=self)
        except Exception as e:
            logging.error(f"[PowerBI] Export failed: {e}")
            messagebox.showerror(t("msg_title_error"), f"{t('gui_export_error')}:\n{e}", parent=self)
