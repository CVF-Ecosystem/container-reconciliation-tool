# File: gui/export_dialog.py
"""Dialog xuất báo cáo theo hãng tàu với time slot"""

import tkinter as tk
from tkinter import messagebox
import logging
from datetime import datetime
import calendar
import os
import pandas as pd

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
except ImportError:
    pass

import config
from config import Col, OPERATOR_MAPPING
from utils.gui_translator import t


class HangTauExportDialog(ttkb.Toplevel):
    """V5.1.5: Dialog xuất báo cáo riêng theo hãng tàu với lựa chọn time slot"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("gui_hang_tau_title"))
        self.geometry("600x720")
        self.transient(parent)
        self.parent_app = parent
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttkb.Frame(self, padding=20)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Header
        ttkb.Label(main_frame, text=t("gui_hang_tau_header"), 
                   font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 15))
        
        # Hãng tàu selection
        hang_frame = ttkb.LabelFrame(main_frame, text=t("gui_hang_tau_select"), padding=10)
        hang_frame.pack(fill="x", pady=(0, 10))
        
        self.hang_var = tk.StringVar(value="VMC")
        hang_options = [
            (t("gui_hang_tau_vimc"), "VMC"),
            (t("gui_hang_tau_vosco"), "VOC"),
            (t("gui_hang_tau_vinafco"), "VFC"),
            (t("gui_hang_tau_vanson"), "VSS"),
            (t("gui_hang_tau_vinaline"), "VNL"),
            (t("gui_hang_tau_other"), "DEFAULT")
        ]
        
        for text, value in hang_options:
            ttkb.Radiobutton(
                hang_frame, text=text, variable=self.hang_var, value=value,
                bootstyle="info-toolbutton"
            ).pack(anchor="w", pady=3)
        
        # Time slot selection
        self.ca_frame = ttkb.LabelFrame(main_frame, text=t("gui_hang_tau_shift"), padding=10)
        self.ca_frame.pack(fill="x", pady=(0, 10))
        
        self.ca_var = tk.StringVar(value="full")
        ca_options = [
            (t("gui_hang_tau_morning"), "morning"),
            (t("gui_hang_tau_afternoon"), "afternoon"),
            (t("gui_hang_tau_fullday"), "full")
        ]
        
        for text, value in ca_options:
            ttkb.Radiobutton(
                self.ca_frame, text=text, variable=self.ca_var, value=value,
                bootstyle="success-toolbutton"
            ).pack(anchor="w", pady=3)
        
        # Date selection with calendar button
        date_frame = ttkb.LabelFrame(main_frame, text=t("gui_hang_tau_date"), padding=10)
        date_frame.pack(fill="x", pady=(0, 10))
        
        ttkb.Label(date_frame, text="Ngày (DD-MM-YYYY):").pack(side="left")
        
        self.date_var = tk.StringVar(value=datetime.now().strftime('%d-%m-%Y'))
        self.date_entry = ttkb.Entry(date_frame, textvariable=self.date_var, width=12)
        self.date_entry.pack(side="left", padx=5)
        
        # Calendar button
        ttkb.Button(date_frame, text="📅", command=self.show_calendar, 
                    width=3, bootstyle=(INFO, OUTLINE)).pack(side="left")
        
        # Buttons
        btn_frame = ttkb.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        ttkb.Button(btn_frame, text=t("gui_hang_tau_export"), command=self.export_report,
                    width=20, bootstyle=SUCCESS).pack(side="left", padx=5)
        ttkb.Button(btn_frame, text=t("gui_hang_tau_close"), command=self.destroy,
                    width=15, bootstyle=SECONDARY).pack(side="left", padx=5)
        
        # Bind event to show/hide ca selection
        self.hang_var.trace_add('write', self.on_hang_change)
    
    def show_calendar(self):
        """Show calendar popup to select date - Custom implementation"""
        # Create popup window
        cal_window = ttkb.Toplevel(self)
        cal_window.title("Chọn ngày")
        cal_window.geometry("320x320")
        cal_window.transient(self)
        cal_window.grab_set()
        
        # Parse current date
        try:
            current = datetime.strptime(self.date_var.get(), '%d-%m-%Y')
        except:
            current = datetime.now()
        
        selected_year = tk.IntVar(value=current.year)
        selected_month = tk.IntVar(value=current.month)
        selected_day = tk.IntVar(value=current.day)
        
        # Header with month/year navigation
        header_frame = ttkb.Frame(cal_window)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        # Calendar frame
        cal_frame = ttkb.Frame(cal_window)
        cal_frame.pack(padx=10, pady=5)
        
        def update_calendar():
            # Clear calendar frame
            for widget in cal_frame.winfo_children():
                widget.destroy()
            
            year = selected_year.get()
            month = selected_month.get()
            
            # Day headers
            days = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
            for i, day in enumerate(days):
                lbl = ttkb.Label(cal_frame, text=day, width=4, font=("Segoe UI", 9, "bold"))
                lbl.grid(row=0, column=i, padx=1, pady=2)
            
            # Get calendar for month
            cal = calendar.Calendar(firstweekday=0)
            month_days = cal.monthdayscalendar(year, month)
            
            for row_idx, week in enumerate(month_days):
                for col_idx, day in enumerate(week):
                    if day == 0:
                        lbl = ttkb.Label(cal_frame, text="", width=4)
                        lbl.grid(row=row_idx+1, column=col_idx, padx=1, pady=1)
                    else:
                        btn = ttkb.Button(
                            cal_frame, text=str(day), width=4,
                            command=lambda d=day: select_day(d),
                            bootstyle="outline" if day != selected_day.get() else "primary"
                        )
                        btn.grid(row=row_idx+1, column=col_idx, padx=1, pady=1)
        
        def prev_month():
            m = selected_month.get() - 1
            if m < 1:
                m = 12
                selected_year.set(selected_year.get() - 1)
            selected_month.set(m)
            month_label.config(text=f"{selected_month.get():02d}/{selected_year.get()}")
            update_calendar()
        
        def next_month():
            m = selected_month.get() + 1
            if m > 12:
                m = 1
                selected_year.set(selected_year.get() + 1)
            selected_month.set(m)
            month_label.config(text=f"{selected_month.get():02d}/{selected_year.get()}")
            update_calendar()
        
        def select_day(day):
            selected_day.set(day)
            date_str = f"{day:02d}-{selected_month.get():02d}-{selected_year.get()}"
            self.date_var.set(date_str)
            cal_window.destroy()
        
        def select_today():
            today = datetime.now()
            self.date_var.set(today.strftime('%d-%m-%Y'))
            cal_window.destroy()
        
        # Navigation buttons
        ttkb.Button(header_frame, text="◀", command=prev_month, width=3).pack(side="left")
        month_label = ttkb.Label(header_frame, text=f"{selected_month.get():02d}/{selected_year.get()}", 
                                  font=("Segoe UI", 11, "bold"))
        month_label.pack(side="left", expand=True)
        ttkb.Button(header_frame, text="▶", command=next_month, width=3).pack(side="right")
        
        update_calendar()
        
        # Today button
        ttkb.Button(cal_window, text="📅 Hôm nay", command=select_today, 
                    bootstyle=INFO).pack(pady=10)
    
    def on_hang_change(self, *args):
        """Show/hide ca selection based on selected hang"""
        if self.hang_var.get() in ["VMC", "SVM"]:
            self.ca_frame.pack(fill="x", pady=(0, 10))
        else:
            self.ca_var.set("full")  # Reset to full day
    
    def export_report(self):
        """Export report for selected hang and time slot - V5.1.5 Fixed"""
        hang = self.hang_var.get()
        ca = self.ca_var.get()
        date_str = self.date_var.get()
        
        try:
            target_date = datetime.strptime(date_str, '%d-%m-%Y')
        except ValueError:
            messagebox.showerror(t("msg_title_error"), t("gui_export_invalid_date"), parent=self)
            return
        
        # Get time slot info
        try:
            from utils.time_slot_filter import get_time_range_for_date
            start_dt, end_dt = get_time_range_for_date(hang, target_date, ca)
            time_range_str = f"{start_dt.strftime('%d/%m %H:%M')} - {end_dt.strftime('%d/%m %H:%M')}"
        except ImportError:
            time_range_str = "N/A"
            start_dt, end_dt = None, None
        
        # Show confirmation
        msg = t("gui_hang_tau_confirm").format(hang, ca, date_str, time_range_str)
        
        if not messagebox.askyesno(t("msg_title_confirm"), msg, parent=self):
            return
        
        # Find latest report folder
        try:
            output_dir = config.OUTPUT_DIR
            report_folders = [f for f in output_dir.iterdir() if f.is_dir() and f.name.startswith("Report_")]
            
            if not report_folders:
                messagebox.showwarning(t("msg_title_warning"), t("gui_export_no_report"), parent=self)
                return
            
            latest_folder = sorted(report_folders, key=lambda x: x.name, reverse=True)[0]
            
            # Map hang code to Lines name và operator codes
            hang_to_lines = {
                "VMC": "VIMC_Lines", "SVM": "VIMC_Lines", "VLC": "VIMC_Lines",
                "VOC": "Vosco", "SVC": "Vosco",
                "VFC": "Vinafco", "SVF": "Vinafco",
                "VSS": "Van_Son", "SVS": "Van_Son",
                "VNL": "Vinaline",
                "DEFAULT": "Hang_Khac"
            }
            
            # Lấy list operator codes thuộc hãng này
            lines_name = hang_to_lines.get(hang, "Hang_Khac")
            operator_codes = OPERATOR_MAPPING.get(lines_name, [hang])
            
            # Create export folder
            export_folder = output_dir / "Export_Theo_Hang"
            export_folder.mkdir(exist_ok=True)
            
            # Generate export filename
            ca_suffix = {"morning": "Ca_Sang", "afternoon": "Ca_Chieu", "full": "Ca_Ngay"}
            file_date_str = target_date.strftime('%Y-%m-%d')
            export_filename = f"{lines_name}_{file_date_str}_{ca_suffix.get(ca, 'full')}.xlsx"
            export_path = export_folder / export_filename
            
            # ===== V5.1.5: ĐỌC TỪ FILE BIEN_DONG_CHI_TIET ĐỂ CÓ THỜI GIAN =====
            bien_dong_file = latest_folder / "5. BIEN_DONG_CHI_TIET.xlsx"
            hang_file = latest_folder / "6_Ton_Theo_Hang" / f"TON_{lines_name}.xlsx"
            
            # Đọc biến động chi tiết (có thời gian)
            df_vao_full = pd.DataFrame()
            df_ra_full = pd.DataFrame()
            
            if bien_dong_file.exists():
                try:
                    df_vao_full = pd.read_excel(bien_dong_file, sheet_name="Chi_Tiet_Moi_Vao")
                    df_ra_full = pd.read_excel(bien_dong_file, sheet_name="Chi_Tiet_Da_Roi")
                except Exception as e:
                    logging.warning(f"Không đọc được BIEN_DONG_CHI_TIET: {e}")
            
            # Đọc tồn cũ/mới từ file theo hãng
            df_ton_cu = pd.DataFrame()
            df_ton_moi = pd.DataFrame()
            
            if hang_file.exists():
                try:
                    df_ton_cu = pd.read_excel(hang_file, sheet_name="Ton_Cu")
                    df_ton_moi = pd.read_excel(hang_file, sheet_name="Ton_Moi")
                except Exception as e:
                    logging.warning(f"Không đọc được file hãng: {e}")
            
            # Filter biến động theo hãng tàu
            if not df_vao_full.empty and Col.OPERATOR in df_vao_full.columns:
                df_vao_hang = df_vao_full[df_vao_full[Col.OPERATOR].isin(operator_codes)].copy()
            else:
                df_vao_hang = pd.DataFrame()
            
            if not df_ra_full.empty and Col.OPERATOR in df_ra_full.columns:
                df_ra_hang = df_ra_full[df_ra_full[Col.OPERATOR].isin(operator_codes)].copy()
            else:
                df_ra_hang = pd.DataFrame()
            
            # ===== FILTER THEO TIME SLOT =====
            if ca != "full" and start_dt and end_dt:
                time_cols = ['ThoiDiemGiaoDich', 'Xe vào cổng', 'Container vào bãi', 'Ngày nhập bãi']
                
                # Filter VÀO
                if not df_vao_hang.empty:
                    filtered = False
                    for col in time_cols:
                        if col in df_vao_hang.columns:
                            df_vao_hang['_time'] = pd.to_datetime(df_vao_hang[col], errors='coerce')
                            df_vao_hang = df_vao_hang[
                                (df_vao_hang['_time'] >= start_dt) & (df_vao_hang['_time'] < end_dt)
                            ]
                            df_vao_hang = df_vao_hang.drop(columns=['_time'])
                            filtered = True
                            logging.info(f"[Export] Filter VÀO theo '{col}': {len(df_vao_hang)} records")
                            break
                    if not filtered:
                        logging.warning("[Export] Không tìm thấy cột thời gian để filter VÀO")
                
                # Filter RA
                time_cols_ra = ['ThoiDiemGiaoDich', 'Xe ra cổng', 'Container ra bãi', 'Ngày ra bãi']
                if not df_ra_hang.empty:
                    filtered = False
                    for col in time_cols_ra:
                        if col in df_ra_hang.columns:
                            df_ra_hang['_time'] = pd.to_datetime(df_ra_hang[col], errors='coerce')
                            df_ra_hang = df_ra_hang[
                                (df_ra_hang['_time'] >= start_dt) & (df_ra_hang['_time'] < end_dt)
                            ]
                            df_ra_hang = df_ra_hang.drop(columns=['_time'])
                            filtered = True
                            logging.info(f"[Export] Filter RA theo '{col}': {len(df_ra_hang)} records")
                            break
                    if not filtered:
                        logging.warning("[Export] Không tìm thấy cột thời gian để filter RA")
            
            # Gom biến động
            df_bien_dong = pd.DataFrame()
            if not df_vao_hang.empty or not df_ra_hang.empty:
                bd_list = []
                if not df_vao_hang.empty:
                    df_v = df_vao_hang.copy()
                    df_v['Loai_BD'] = 'VÀO'
                    bd_list.append(df_v)
                if not df_ra_hang.empty:
                    df_r = df_ra_hang.copy()
                    df_r['Loai_BD'] = 'RA'
                    bd_list.append(df_r)
                df_bien_dong = pd.concat(bd_list, ignore_index=True)
            
            # Tạo summary
            count_ton_cu = len(df_ton_cu)
            count_ton_moi = len(df_ton_moi)
            count_vao = len(df_vao_hang)
            count_ra = len(df_ra_hang)
            
            summary_data = {
                'Hạng mục': [
                    f'📊 Tồn Cũ ({lines_name})',
                    f'📊 Tồn Mới ({lines_name})',
                    f'📥 VÀO trong ca ({ca_suffix.get(ca, "full")})',
                    f'📤 RA trong ca ({ca_suffix.get(ca, "full")})',
                    '━━━━━━━━━━━━━━━━━━━━',
                    f'⏰ Time range: {time_range_str}',
                    f'📅 Ngày: {date_str}',
                    f'🏢 Hãng: {lines_name} ({", ".join(operator_codes)})'
                ],
                'Số lượng': [
                    count_ton_cu,
                    count_ton_moi,
                    count_vao,
                    count_ra,
                    '',
                    '',
                    '',
                    ''
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            
            # Write to export file
            with pd.ExcelWriter(export_path, engine='xlsxwriter') as writer:
                df_summary.to_excel(writer, sheet_name="Tong_Hop", index=False)
                
                if not df_ton_cu.empty:
                    df_ton_cu.to_excel(writer, sheet_name="Ton_Cu", index=False)
                
                if not df_ton_moi.empty:
                    df_ton_moi.to_excel(writer, sheet_name="Ton_Moi", index=False)
                
                if not df_bien_dong.empty:
                    df_bien_dong.to_excel(writer, sheet_name="Bien_Dong", index=False)
                
                if not df_vao_hang.empty:
                    df_vao_hang.to_excel(writer, sheet_name="Chi_Tiet_VAO", index=False)
                
                if not df_ra_hang.empty:
                    df_ra_hang.to_excel(writer, sheet_name="Chi_Tiet_RA", index=False)
            
            logging.info(f"[Export] Đã xuất file: {export_path}")
            
            # Show success and open folder
            result = messagebox.askyesno(
                "✅ Thành công",
                f"Đã xuất báo cáo:\n\n"
                f"📁 {export_filename}\n"
                f"🏢 Hãng: {lines_name}\n"
                f"⏰ Ca: {ca_suffix.get(ca, 'full')}\n"
                f"🕐 {time_range_str}\n\n"
                f"Bạn có muốn mở thư mục không?",
                parent=self
            )
            
            if result:
                os.startfile(str(export_folder))
            
        except Exception as e:
            logging.error(f"[Export] Lỗi: {e}")
            messagebox.showerror("Lỗi", f"Không thể xuất báo cáo:\n{e}", parent=self)
