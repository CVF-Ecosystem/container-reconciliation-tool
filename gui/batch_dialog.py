# File: gui/batch_dialog.py
"""Dialog xử lý batch nhiều ngày"""

import tkinter as tk
from tkinter import messagebox
import logging
from pathlib import Path
from datetime import datetime
import threading
import os
import configparser
import time

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
except ImportError:
    pass

import config
from core.batch_processor import BatchProcessor, extract_date_from_filename, extract_date_slot_from_filename, DateSlot, format_slot_chain_validation_message
from utils.gui_translator import t
from utils.gui_translator import t


class BatchModeDialog(ttkb.Toplevel):
    """Dialog để xử lý batch nhiều ngày"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("gui_batch_title"))
        self.geometry("750x680")
        self.transient(parent)
        self.parent_app = parent
        self.processor = None
        self.selected_slots = []  # V5.1: Lí DateSlot thay vì date
        self.slot_vars = {}  # {DateSlot: BooleanVar}
        self.create_widgets()
        self.scan_files()
    
    def create_widgets(self):
        main_frame = ttkb.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Header
        ttkb.Label(main_frame, text=t("gui_batch_header"), font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))
        ttkb.Label(main_frame, text=t("gui_batch_logic"), font=("Segoe UI", 9)).pack(anchor="w")
        
        # Dates frame with scrollable checkboxes
        dates_frame = ttkb.LabelFrame(main_frame, text=t("gui_batch_dates_found"), padding=10)
        dates_frame.pack(fill="both", expand=True, pady=10)
        
        # Create canvas with scrollbar for checkboxes
        canvas = tk.Canvas(dates_frame, highlightthickness=0)
        scrollbar = ttkb.Scrollbar(dates_frame, orient="vertical", command=canvas.yview)
        self.checkbox_frame = ttkb.Frame(canvas)
        
        self.checkbox_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.checkbox_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Summary
        self.summary_label = ttkb.Label(main_frame, text="", font=("Segoe UI", 9), bootstyle="info")
        self.summary_label.pack(anchor="w", pady=5)
        
        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttkb.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=10)
        
        # Status
        self.status_label = ttkb.Label(main_frame, text=t("gui_batch_ready"), font=("Segoe UI", 10))
        self.status_label.pack(anchor="w")
        
        # Buttons frame
        btn_frame = ttkb.Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
        
        # RUN button (prominent)
        self.run_btn = ttkb.Button(btn_frame, text="▶ Chạy Xử Lý", command=self.run_batch, width=15, bootstyle=SUCCESS)
        self.run_btn.pack(side="left", padx=3)
        
        # Other buttons
        ttkb.Button(btn_frame, text="🔄 Quét lại", command=self.scan_files, width=11, bootstyle=INFO).pack(side="left", padx=3)
        ttkb.Button(btn_frame, text="☑ Chọn tất cả", command=self.select_all, width=13, bootstyle=SECONDARY).pack(side="left", padx=3)
        ttkb.Button(btn_frame, text="✕ Bỏ chọn", command=self.deselect_all, width=11, bootstyle=(SECONDARY, OUTLINE)).pack(side="left", padx=3)
    
    def scan_files(self):
        """Quét files trong data_input và nhóm theo DateSlot (ngày + time slot)"""
        # Clear existing checkboxes
        for widget in self.checkbox_frame.winfo_children():
            widget.destroy()
        self.slot_vars.clear()
        self.status_label.config(text=t("gui_processing"))
        
        try:
            self.processor = BatchProcessor(config.INPUT_DIR, config.OUTPUT_DIR)
            self.processor.scan_files()
            slots = self.processor.get_available_slots()  # V5.1: Dùng slots thay vì dates
            
            # V4.8: Check for files WITHOUT dates (warning)
            try:
                all_files = os.listdir(config.INPUT_DIR)
                files_without_date = []
                for fname in all_files:
                    if fname.endswith(('.xlsx', '.xls', '.csv')):
                        if extract_date_slot_from_filename(fname) is None:
                            files_without_date.append(fname)
                
                if files_without_date:
                    warning_msg = (
                        t("gui_batch_no_date_warning_title") + "\n\n"
                        + "\n".join(f"  • {f}" for f in files_without_date[:5])
                    )
                    if len(files_without_date) > 5:
                        warning_msg += f"\n  ... và {len(files_without_date) - 5} file khác"
                    warning_msg += (
                        "\n\n🔹 Các file này sẽ KHÔNG được xử lý.\n"
                        "🔹 Đặt tên folder theo format: 8H N7.1 - 15H N7.1 hoặc N8.1.2026"
                    )
                    messagebox.showwarning(t("msg_title_warning"), warning_msg)
            except Exception:
                pass
            
            if not slots:
                self.status_label.config(text="Không tìm thấy file nào có ngày trong tên. Vui lòng đổi tên file/folder.")
                messagebox.showinfo(
                    "Hướng dẫn đặt tên folder",
                    "Để hệ thống nhận diện đúng ngày, vui lòng đặt tên folder theo format:\n\n"
                    "• 8H N7.1 - 15H N7.1  (→ slot 15H ngày 7/1)\n"
                    "• 15H N7.1 - 8H N8.1  (→ slot 8H ngày 8/1)\n"
                    "• N8.1.2026           (→ nguyên ngày 8/1/2026)\n\n"
                    "Hoặc đặt file trực tiếp: TON MOI N7.1.2026.xlsx"
                )
                return
            
            # Create checkbox for each slot
            for i, slot in enumerate(slots):
                files = self.processor.grouped_files_slot.get(slot, {})
                # V5.2.1: Bỏ qua key đặc biệt khi hiển thị
                actual_files = {k: v for k, v in files.items() if k != 'duplicate_warnings'}
                file_types = ", ".join(actual_files.keys())
                
                var = tk.BooleanVar(value=True)  # Selected by default
                self.slot_vars[slot] = var
                
                # Create a frame for each row
                row_frame = ttkb.Frame(self.checkbox_frame)
                row_frame.pack(fill="x", pady=2)
                
                # V5.1: Hiển thị slot label
                cb = ttkb.Checkbutton(
                    row_frame, 
                    text=f"📅 {slot.display_label()}", 
                    variable=var,
                    bootstyle="success-round-toggle"
                )
                cb.pack(side="left")
                
                # File info label
                info_label = ttkb.Label(
                    row_frame, 
                    text=f" - {len(actual_files)} files ({file_types})",
                    font=("Segoe UI", 9),
                    bootstyle="secondary"
                )
                info_label.pack(side="left", padx=5)
            
            # V5.1: Kiểm tra mix format (full-day và half-day cùng ngày)
            dates_with_slots = {}  # {date: [slots]}
            for slot in slots:
                if slot.date_value not in dates_with_slots:
                    dates_with_slots[slot.date_value] = []
                dates_with_slots[slot.date_value].append(slot.slot)
            
            mixed_dates = []
            for d, slot_list in dates_with_slots.items():
                has_full_day = None in slot_list
                has_half_day = any(s is not None for s in slot_list)
                if has_full_day and has_half_day:
                    mixed_dates.append(d.strftime('%d/%m/%Y'))
            
            if mixed_dates:
                warning_msg = (
                    t("gui_batch_mixed_format_warning_title") + "\n\n"
                    + "\n".join(f"  • {d}" for d in mixed_dates)
                    + "\n\nĐiều này có thể gây trùng dữ liệu!\n"
                    + "Khuyến nghị: Dùng ĐỒNG NHẤT một format cho tất cả ngày.\n"
                    + "• Full-day: 8H N7.1 - 8H N8.1\n"
                    + "• Half-day: 8H N7.1 - 15H N7.1 VÀ 15H N7.1 - 8H N8.1"
                )
                messagebox.showwarning(t("msg_title_warning"), warning_msg)
            
            # V5.2.1: Kiểm tra duplicate files trong cùng slot
            all_duplicates = []
            for slot in slots:
                files = self.processor.grouped_files_slot.get(slot, {})
                if 'duplicate_warnings' in files:
                    for dup in files['duplicate_warnings']:
                        all_duplicates.append({
                            'slot': slot.display_label(),
                            'type': dup['type'],
                            'using': dup['existing'].split('\\')[-1] if '\\' in dup['existing'] else dup['existing'],
                            'skipped': dup['duplicate'].split('\\')[-1] if '\\' in dup['duplicate'] else dup['duplicate']
                        })
            
            if all_duplicates:
                # V5.2.1: Hàm helper để tính range ngày từ filename
                import re
                from datetime import date, datetime
                
                def get_range_days(fname):
                    """Tính số ngày từ time range trong filename"""
                    range_pattern = r'N?(\d{1,2})\.(\d{1,2})(?:\.\d{4})?\s*-\s*\d*H?\s*N?(\d{1,2})\.(\d{1,2})'
                    match = re.search(range_pattern, fname)
                    if match:
                        start_day, start_month = int(match.group(1)), int(match.group(2))
                        end_day, end_month = int(match.group(3)), int(match.group(4))
                        year = datetime.now().year
                        try:
                            start = date(year, start_month, start_day)
                            end = date(year, end_month, end_day)
                            return (end - start).days
                        except:
                            return 0
                    return 0
                
                # Tạo message chi tiết
                dup_details = []
                for d in all_duplicates[:5]:  # Chỉ hiển thị 5 đầu tiên
                    using_days = get_range_days(d['using'])
                    skipped_days = get_range_days(d['skipped'])
                    dup_details.append(
                        f"• [{d['slot']}] {d['type'].upper()}:\n"
                        f"   ✅ Dùng: {d['using']} (range: {using_days} ngày)\n"
                        f"   ❌ Bỏ qua: {d['skipped']} (range: {skipped_days} ngày)"
                    )
                
                if len(all_duplicates) > 5:
                    dup_details.append(t("gui_batch_duplicate_more", len(all_duplicates) - 5))
                
                warning_msg = (
                    t("gui_batch_duplicate_warning_title") + "\n\n"
                    + t("gui_batch_duplicate_warning_msg") + "\n\n"
                    + "\n\n".join(dup_details)
                    + "\n\n" + t("gui_batch_duplicate_continue_yes") + "\n"
                    + t("gui_batch_duplicate_continue_no")
                )
                
                result = messagebox.askyesno(t("msg_title_warning"), warning_msg)
                if not result:
                    self.status_label.config(text=t("gui_batch_stopped"))
                    return
            
            self.summary_label.config(text=t("gui_batch_found_summary", len(slots)))
            self.status_label.config(text=t("gui_batch_ready"))
            self.selected_slots = slots
        except Exception as e:
            self.status_label.config(text=f"{t('msg_title_error')}: {e}")
    
    def select_all(self):
        for var in self.slot_vars.values():
            var.set(True)
    
    def deselect_all(self):
        for var in self.slot_vars.values():
            var.set(False)
    
    def run_batch(self):
        """Chạy batch processing"""
        if not self.processor or not self.selected_slots:
            messagebox.showwarning(t("msg_title_warning"), t("gui_batch_no_data"))
            return
        
        # V5.1: Get selected slots from checkboxes
        slots_to_process = [s for s, var in self.slot_vars.items() if var.get()]
        slots_to_process.sort()  # Sort by DateSlot
        
        if not slots_to_process:
            messagebox.showwarning(t("msg_title_warning"), t("gui_batch_select_one"))
            return
        
        # V5.5: Kiểm tra toàn diện tính hợp lệ của slots
        validation = self.processor.validate_slots(slots_to_process)
        
        warnings = validation.get('warnings', [])
        chain_results = validation.get('chain_results', [])
        gaps = validation.get('gaps', [])
        duplicates = validation.get('duplicates', [])
        has_critical_issues = validation.get('has_critical_issues', False)
        
        # Nếu có lỗi nghiêm trọng (thiếu TON MOI), không cho tiếp tục
        if has_critical_issues:
            messagebox.showerror(
                t("gui_batch_critical_error_title"),
                t("gui_batch_critical_error_msg") + "\n\n" + 
                "\n".join([w for w in warnings if w.startswith("❌")])
            )
            return
        
        # Tổng hợp tất cả cảnh báo
        all_warnings = []
        
        # 1. Cảnh báo GAP (thiếu slots trong chuỗi)
        if gaps:
            non_weekend_gaps = [g for g in gaps if not g.get('is_weekend_gap', False)]
            if non_weekend_gaps:
                all_warnings.append(t("gui_batch_gap_header"))
                for gap in non_weekend_gaps:
                    all_warnings.append(
                        t("gui_batch_gap_item", 
                          gap['slot_before'].display_label(),
                          gap['slot_after'].display_label(),
                          gap['gap_description'])
                    )
                all_warnings.append("")
        
        # 2. Cảnh báo TRÙNG LẶP với database
        if duplicates:
            all_warnings.append(t("gui_batch_duplicate_db_header"))
            for dup in duplicates:
                all_warnings.append(
                    t("gui_batch_duplicate_db_item",
                      dup['slot'].display_label(),
                      dup['existing_count'])
                )
            all_warnings.append(t("gui_batch_duplicate_db_overwrite"))
            all_warnings.append("")
        
        # 3. Cảnh báo TON CU không khớp TON MOI
        if chain_results:
            missing_ton_cu = sum(1 for r in chain_results if r['status'] == 'missing_ton_cu')
            mismatch = sum(1 for r in chain_results if r['status'] == 'mismatch')
            mostly_match = sum(1 for r in chain_results if r['status'] == 'mostly_match')
            
            if missing_ton_cu > 0 or mismatch > 0 or mostly_match > 0:
                all_warnings.append(t("gui_batch_chain_header"))
                for r in chain_results:
                    slot_n = r['slot_n'].display_label()
                    slot_n1 = r['slot_n1'].display_label()
                    match_pct = f"{r['match_rate']:.1f}"
                    
                    if r['status'] == 'match':
                        all_warnings.append(t("gui_batch_chain_match", slot_n, slot_n1, match_pct))
                    elif r['status'] == 'mostly_match':
                        all_warnings.append(t("gui_batch_chain_mostly_match", slot_n, slot_n1, match_pct))
                    elif r['status'] == 'mismatch':
                        all_warnings.append(t("gui_batch_chain_mismatch", slot_n, slot_n1, match_pct))
                    elif r['status'] == 'missing_ton_cu':
                        all_warnings.append(t("gui_batch_chain_missing_ton_cu", slot_n, slot_n1))
                        all_warnings.append(t("gui_batch_chain_use_ton_moi", slot_n))
                all_warnings.append("")
        
        # 4. Các cảnh báo khác
        other_warnings = [w for w in warnings if not w.startswith("❌")]
        if other_warnings and not all_warnings:  # Chỉ thêm nếu chưa có warning trên
            all_warnings.extend(other_warnings)
        
        # Hiển thị tổng hợp cảnh báo nếu có
        if all_warnings:
            warning_text = "\n".join(all_warnings)
            warning_text += "\n\n" + "═" * 40
            warning_text += f"\n{t('gui_batch_logic_header')}\n"
            warning_text += f"{t('gui_batch_logic_8h')}\n"
            warning_text += f"{t('gui_batch_logic_15h')}\n"
            warning_text += f"{t('gui_batch_logic_weekend')}\n"
            warning_text += f"\n{t('gui_batch_continue_question')}"
            
            result = messagebox.askyesno(
                t("gui_batch_validation_title"),
                warning_text,
                icon='warning'
            )
            
            if not result:
                self.status_label.config(text=t("gui_batch_stopped"))
                return
        
        # Disable button
        self.run_btn.config(state=tk.DISABLED)
        
        # V5.7: Track processing time
        self.batch_start_time = time.time()
        
        def update_status(msg):
            self.after(0, lambda: self.status_label.config(text=msg))
        
        def update_progress(val):
            self.after(0, lambda: self.progress_var.set(val))
        
        self.processor.update_status = update_status
        self.processor.update_progress = update_progress
        
        # V5.1: Run in thread using run_batch_slots
        def run_thread():
            try:
                results = self.processor.run_batch_slots(slots_to_process)
                self.after(0, lambda: self.on_batch_complete(results))
            except Exception as e:
                self.after(0, lambda: self.on_batch_error(str(e)))
        
        threading.Thread(target=run_thread, daemon=True).start()
    
    def on_batch_complete(self, results):
        self.run_btn.config(state=tk.NORMAL)
        success = sum(1 for r in results if r.get('success'))
        total = len(results)
        
        # V5.7: Calculate processing time
        elapsed_time = time.time() - getattr(self, 'batch_start_time', time.time())
        time_str = self._format_elapsed_time(elapsed_time)
        
        # V5.0: Send email notification if enabled
        self._send_email_notification(results, success, total)
        
        complete_msg = t("gui_batch_complete_msg", success, total)
        complete_msg += f"\n\n{t('gui_batch_complete_time', time_str)}"
        messagebox.showinfo(t("gui_batch_complete"), complete_msg)
    
    def _format_elapsed_time(self, seconds):
        """V5.7: Format elapsed time to human readable string"""
        if seconds < 60:
            return f"{seconds:.1f} giây"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins} phút {secs} giây"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours} giờ {mins} phút"
    
    def _send_email_notification(self, results, success_count, total_count):
        """V5.0: Send email notification after batch completion."""
        try:
            config_parser = configparser.ConfigParser()
            config_path = Path("gui_settings.ini")
            
            if not config_path.exists():
                return
            
            config_parser.read(config_path)
            
            if not config_parser.getboolean('Email', 'enabled', fallback=False):
                return
            
            recipients_str = config_parser.get('Email', 'recipients', fallback='')
            if not recipients_str:
                return
            
            recipients = [r.strip() for r in recipients_str.split(',') if r.strip()]
            if not recipients:
                return
            
            smtp_config = {
                'server': config_parser.get('Email', 'smtp_server', fallback='smtp.gmail.com'),
                'port': int(config_parser.get('Email', 'smtp_port', fallback='587')),
                'email': config_parser.get('Email', 'smtp_user', fallback=''),
                'password': config_parser.get('Email', 'smtp_password', fallback='')
            }
            
            if not smtp_config['email'] or not smtp_config['password']:
                logging.warning("Email credentials not configured")
                return
            
            from utils.email_notifier import send_reconciliation_notification
            
            date_str = datetime.now().strftime('%d/%m/%Y')
            
            # Create combined results for email
            combined_results = {'main_results': {'counts': {}}}
            if results:
                # Use the last successful result
                for r in reversed(results):
                    if r.get('success') and r.get('summary_df') is not None:
                        combined_results = r
                        break
            
            logging.info(f"Đang gửi email thông báo đến {', '.join(recipients)}...")
            
            if send_reconciliation_notification(combined_results, date_str, recipients, smtp_config):
                logging.info("✅ Đã gửi email thông báo!")
            else:
                logging.warning("❌ Không thể gửi email")
                
        except Exception as e:
            logging.warning(f"Email notification failed: {e}")
    
    def on_batch_error(self, error_msg):
        self.run_btn.config(state=tk.NORMAL)
        messagebox.showerror(t("gui_batch_error_title"), f"{t('gui_batch_error_msg')}\n{error_msg}")
