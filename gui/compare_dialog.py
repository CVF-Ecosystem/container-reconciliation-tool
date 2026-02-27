# File: gui/compare_dialog.py
# @2026 v1.0: Dialog so sánh 2 file Excel (App vs TOS)
"""Dialog để so sánh file BIEN DONG/TON BAI từ App với file từ TOS Cảng."""

import tkinter as tk
from tkinter import messagebox, filedialog
import logging
from pathlib import Path
from datetime import datetime
import os

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
except ImportError:
    pass

import config
from utils.gui_translator import t
from utils.file_comparator import FileComparator


class CompareFilesDialog(ttkb.Toplevel):
    """Dialog so sánh 2 file Excel."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("gui_compare_title"))
        self.geometry("700x600")
        self.transient(parent)
        
        self.file1_path = tk.StringVar()
        self.file2_path = tk.StringVar()
        self.comparator = FileComparator()
        
        self.create_widgets()
        self.center_window()
    
    def center_window(self):
        """Center dialog on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
    
    def create_widgets(self):
        main_frame = ttkb.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Header
        header_frame = ttkb.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 15))
        
        ttkb.Label(
            header_frame, 
            text=t("gui_compare_header"), 
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")
        
        ttkb.Label(
            header_frame,
            text=t("gui_compare_subtitle"),
            font=("Segoe UI", 10),
            bootstyle="secondary"
        ).pack(anchor="w")
        
        # File 1 Selection
        file1_frame = ttkb.LabelFrame(main_frame, text="📁 " + t("gui_compare_file1"), padding=10)
        file1_frame.pack(fill="x", pady=5)
        
        file1_entry_frame = ttkb.Frame(file1_frame)
        file1_entry_frame.pack(fill="x")
        
        self.file1_entry = ttkb.Entry(file1_entry_frame, textvariable=self.file1_path, width=60)
        self.file1_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttkb.Button(
            file1_entry_frame, 
            text=t("gui_compare_browse"), 
            command=self.browse_file1,
            bootstyle="outline"
        ).pack(side="right")
        
        ttkb.Button(
            file1_frame,
            text=t("gui_compare_open_templates"),
            command=self.browse_email_templates,
            bootstyle="info-outline"
        ).pack(anchor="w", pady=(5, 0))
        
        # File 2 Selection  
        file2_frame = ttkb.LabelFrame(main_frame, text="📁 " + t("gui_compare_file2"), padding=10)
        file2_frame.pack(fill="x", pady=5)
        
        file2_entry_frame = ttkb.Frame(file2_frame)
        file2_entry_frame.pack(fill="x")
        
        self.file2_entry = ttkb.Entry(file2_entry_frame, textvariable=self.file2_path, width=60)
        self.file2_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttkb.Button(
            file2_entry_frame, 
            text=t("gui_compare_browse"), 
            command=self.browse_file2,
            bootstyle="outline"
        ).pack(side="right")
        
        # Compare Button
        btn_frame = ttkb.Frame(main_frame)
        btn_frame.pack(fill="x", pady=15)
        
        self.compare_btn = ttkb.Button(
            btn_frame,
            text=t("gui_compare_run"),
            command=self.do_compare,
            bootstyle="success",
            width=20
        )
        self.compare_btn.pack(side="left", padx=5)
        
        self.export_btn = ttkb.Button(
            btn_frame,
            text=t("gui_compare_export"),
            command=self.export_report,
            bootstyle="info",
            width=20,
            state="disabled"
        )
        self.export_btn.pack(side="left", padx=5)
        
        ttkb.Button(
            btn_frame,
            text=t("gui_close"),
            command=self.destroy,
            bootstyle="secondary-outline",
            width=15
        ).pack(side="right", padx=5)
        
        # Results Frame
        results_frame = ttkb.LabelFrame(main_frame, text="📊 " + t("gui_compare_result"), padding=10)
        results_frame.pack(fill="both", expand=True, pady=5)
        
        # Result text with scrollbar
        text_frame = ttkb.Frame(results_frame)
        text_frame.pack(fill="both", expand=True)
        
        self.result_text = tk.Text(
            text_frame, 
            wrap=tk.WORD, 
            font=("Consolas", 10),
            height=15
        )
        self.result_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttkb.Scrollbar(text_frame, command=self.result_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.result_text.config(yscrollcommand=scrollbar.set)
        
        # Initial message
        self.result_text.insert("1.0", t("gui_compare_instructions"))
        self.result_text.config(state="disabled")
    
    def browse_file1(self):
        """Browse for file 1."""
        initial_dir = self._get_latest_email_templates_dir()
        
        file_path = filedialog.askopenfilename(
            title="Chọn file từ Ứng Dụng",
            initialdir=initial_dir,
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.file1_path.set(file_path)
    
    def browse_file2(self):
        """Browse for file 2."""
        file_path = filedialog.askopenfilename(
            title="Chọn file từ TOS Cảng",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.file2_path.set(file_path)
    
    def browse_email_templates(self):
        """Open email templates folder directly."""
        templates_dir = self._get_latest_email_templates_dir()
        if templates_dir and templates_dir.exists():
            os.startfile(str(templates_dir))
        else:
            messagebox.showwarning(
                "Thư mục không tồn tại",
                "Chưa có thư mục Email Templates.\nVui lòng chạy đối soát trước."
            )
    
    def _get_latest_email_templates_dir(self) -> Path:
        """Get latest report's email templates directory."""
        try:
            output_dir = config.OUTPUT_DIR
            report_folders = sorted(
                [f for f in output_dir.iterdir() if f.is_dir() and f.name.startswith("Report_")],
                key=lambda x: x.name,
                reverse=True
            )
            if report_folders:
                email_dir = report_folders[0] / "7_Email_Templates"
                if email_dir.exists():
                    return email_dir
                return report_folders[0]
        except:
            pass
        return config.OUTPUT_DIR
    
    def do_compare(self):
        """Execute comparison."""
        file1 = self.file1_path.get().strip()
        file2 = self.file2_path.get().strip()
        
        if not file1 or not file2:
            messagebox.showwarning("Thiếu file", "Vui lòng chọn cả 2 file để so sánh.")
            return
        
        if not Path(file1).exists():
            messagebox.showerror("Lỗi", f"File 1 không tồn tại:\n{file1}")
            return
        
        if not Path(file2).exists():
            messagebox.showerror("Lỗi", f"File 2 không tồn tại:\n{file2}")
            return
        
        # Update UI
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", "⏳ Đang so sánh...\n")
        self.result_text.config(state="disabled")
        self.update()
        
        try:
            # Load and compare
            self.comparator.load_files(file1, file2)
            result = self.comparator.compare()
            
            # Display results
            summary_text = self.comparator.get_summary_text()
            
            self.result_text.config(state="normal")
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert("1.0", summary_text)
            self.result_text.config(state="disabled")
            
            # Enable export button
            self.export_btn.config(state="normal")
            
            # Show popup for quick result
            s = result['summary']
            if s['is_perfect_match']:
                messagebox.showinfo(
                    "✅ Khớp 100%",
                    f"Hai file khớp hoàn toàn!\n\n"
                    f"Tổng container: {s['matching_count']}"
                )
            else:
                messagebox.showwarning(
                    f"⚠️ Khớp {s['match_percent']}%",
                    f"Phát hiện sai lệch!\n\n"
                    f"✅ Khớp: {s['matching_count']} container\n"
                    f"❌ Chỉ File 1: {s['only_in_file1_count']} container\n"
                    f"❌ Chỉ File 2: {s['only_in_file2_count']} container\n\n"
                    f"Xem chi tiết trong kết quả bên dưới."
                )
            
            logging.info(f"[Compare] {file1} vs {file2}: {s['match_percent']}% match")
            
        except Exception as e:
            self.result_text.config(state="normal")
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert("1.0", f"❌ Lỗi khi so sánh:\n\n{str(e)}")
            self.result_text.config(state="disabled")
            
            messagebox.showerror("Lỗi", f"Không thể so sánh file:\n{e}")
            logging.error(f"[Compare] Error: {e}")
    
    def export_report(self):
        """Export comparison report to Excel."""
        if not self.comparator.comparison_result:
            messagebox.showwarning("Chưa có dữ liệu", "Vui lòng so sánh trước khi xuất báo cáo.")
            return
        
        # Ask for save location
        default_name = f"Comparison_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        file_path = filedialog.asksaveasfilename(
            title="Lưu báo cáo so sánh",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")]
        )
        
        if not file_path:
            return
        
        try:
            report_path = self.comparator.export_comparison_report(file_path)
            
            result = messagebox.askyesno(
                "Xuất thành công",
                f"Đã xuất báo cáo:\n{report_path}\n\nMở file ngay?"
            )
            
            if result:
                os.startfile(str(report_path))
                
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xuất báo cáo:\n{e}")


# Quick launcher function
def open_compare_dialog(parent=None):
    """Open the compare dialog."""
    if parent:
        CompareFilesDialog(parent)
    else:
        # Standalone mode
        root = ttkb.Window(themename="cosmo")
        root.withdraw()
        dialog = CompareFilesDialog(root)
        dialog.mainloop()


if __name__ == "__main__":
    open_compare_dialog()
