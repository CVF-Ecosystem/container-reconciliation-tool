# File: app_gui.py
"""
Main GUI Application - V5.7
Auto-creates data_input, data_output, logs folders
Refactored: Các dialog được tách ra module gui/
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog
import logging
from pathlib import Path
import os
from datetime import datetime
import queue
import threading
import configparser
import subprocess
import sys
import webbrowser

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
except ImportError:
    messagebox.showerror("Lỗi Thiếu Thư Viện", "Thư viện 'ttkbootstrap' chưa được cài đặt.\nVui lòng chạy: pip install ttkbootstrap")
    sys.exit()

try:
    import config
    from core_logic import run_full_reconciliation_process
    from core.batch_processor import BatchProcessor, get_available_dates, group_files_by_date
    from utils.gui_translator import gui_translator, t, register_language_callback
    
    # Import từ module gui
    from gui import (
        TextHandler, 
        AppearanceDialog, 
        SettingsDialog, 
        ExportDialog,
        HangTauExportDialog,
        BatchModeDialog,
        CompareFilesDialog
    )
except ImportError as e:
    messagebox.showerror("Lỗi Khởi Tạo", f"Không thể import các module cần thiết:\n{e}")
    sys.exit()

# Settings file in same directory as EXE/script
SETTINGS_FILE = config.BASE_DIR / "gui_settings.ini"


class App(ttkb.Window):
    """Main Application Window"""
    
    def __init__(self):
        # V5.0: Load saved theme
        saved_theme = self._load_saved_theme()
        super().__init__(themename=saved_theme)
        self.title(f"Inventory Reconciliation Tool V{config.APP_VERSION}")
        self.geometry("950x650")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.latest_report_folder = None
        self.log_queue = queue.Queue()
        self.processor_thread = None
        self.streamlit_process = None
        self.settings_window = None
        self.scheduler = None
        
        self.create_widgets()
        self.setup_logging()
        self.setup_keyboard_shortcuts()
        self.run_health_check()
        self.start_scheduler()
        
        # V5.0: Register language callback for live UI updates
        register_language_callback(self.update_language)
        self.after(100, self.process_log_queue)
    
    def _load_saved_theme(self):
        """V5.0: Load theme from settings file."""
        try:
            config_parser = configparser.ConfigParser()
            if SETTINGS_FILE.exists():
                config_parser.read(SETTINGS_FILE)
                return config_parser.get('Appearance', 'theme', fallback='litera')
        except:
            pass
        return 'litera'
    
    def start_scheduler(self):
        """V5.0: Start the background scheduler."""
        try:
            from utils.scheduler import TaskScheduler
            
            self.scheduler = TaskScheduler()
            self.scheduler.set_callback(self.run_scheduled_reconciliation)
            self.scheduler.start()
        except Exception as e:
            logging.warning(f"Could not start scheduler: {e}")
    
    def run_scheduled_reconciliation(self):
        """V5.0: Run reconciliation from scheduler (all available dates)."""
        logging.info("[Scheduler] Running scheduled reconciliation...")
        try:
            processor = BatchProcessor(config.INPUT_DIR, config.OUTPUT_DIR)
            processor.scan_files()
            dates = processor.get_available_dates()
            
            if dates:
                results = processor.run_batch(dates)
                success = sum(1 for r in results if r.get('success'))
                logging.info(f"[Scheduler] Completed: {success}/{len(dates)} days processed")
            else:
                logging.warning("[Scheduler] No dates found to process")
        except Exception as e:
            logging.error(f"[Scheduler] Failed: {e}")
    
    def setup_keyboard_shortcuts(self):
        """V5.0: Setup keyboard shortcuts for quick actions."""
        self.bind('<F5>', lambda e: self.open_batch_dialog())
        self.bind('<Control-r>', lambda e: self.open_batch_dialog())
        self.bind('<Control-R>', lambda e: self.open_batch_dialog())
        self.bind('<Control-o>', lambda e: self.open_output_folder())
        self.bind('<Control-O>', lambda e: self.open_output_folder())
        self.bind('<Control-d>', lambda e: self.open_web_dashboard())
        self.bind('<Control-D>', lambda e: self.open_web_dashboard())
        self.bind('<Control-e>', lambda e: self.open_export_dialog())
        self.bind('<Control-E>', lambda e: self.open_export_dialog())
        self.bind('<F1>', lambda e: self.show_shortcuts_help())
        
        logging.info("[Shortcuts] Keyboard shortcuts enabled. Press F1 for help.")
    
    def show_shortcuts_help(self):
        """Show keyboard shortcuts help dialog."""
        help_text = """⌨️ KEYBOARD SHORTCUTS

F5 / Ctrl+R    Run Reconciliation
Ctrl+O         Open Latest Report
Ctrl+D         Open Web Dashboard
Ctrl+E         Export Data
F1             Show this help
"""
        messagebox.showinfo("Keyboard Shortcuts", help_text)
    
    def update_language(self):
        """V5.0: Update all button texts when language changes (live switching)."""
        try:
            self.batch_button.config(text=t("gui_run_reconciliation"))
            self.open_report_button.config(text=t("gui_open_latest_report"))
            self.open_bi_button.config(text=t("gui_open_bi_dashboard"))
            self.open_web_button.config(text=t("gui_open_web_dashboard"))
            self.export_button.config(text=t("gui_export_data"))
            self.compare_button.config(text=t("gui_compare_files"))
            self.clear_data_button.config(text=t("gui_clear_data"))
            self.settings_button.config(text=t("gui_settings"))
            self.appearance_button.config(text=t("gui_appearance"))
            
            if self.log_frame.winfo_viewable():
                self.log_button.config(text=t("gui_hide_log"))
            else:
                self.log_button.config(text=t("gui_show_log"))
            
            self.footer_label.config(text=t("gui_developed_by", "Tien-Tan Thuan Port", config.APP_VERSION, config.APP_YEAR))
            
            logging.info(f"[Language] UI updated to: {gui_translator.get_language()}")
        except Exception as e:
            logging.warning(f"[Language] Could not update UI: {e}")
    
    def run_health_check(self):
        """V5.0: Run health checks on startup with visual feedback."""
        try:
            from utils.health_check import run_all_health_checks, log_health_results
            
            all_passed, results = run_all_health_checks(config.INPUT_DIR, config.OUTPUT_DIR)
            log_health_results(results)
            
            passed_count = sum(1 for r in results if r.passed)
            total_count = len(results)
            
            if not all_passed:
                critical_failures = [r for r in results if not r.passed and r.critical]
                if critical_failures:
                    msg = "Phát hiện vấn đề khi khởi động:\n\n"
                    for r in critical_failures:
                        msg += f"❌ {r.name}: {r.message}\n"
                    msg += "\nỨng dụng vẫn có thể chạy nhưng có thể gặp lỗi."
                    messagebox.showwarning("Health Check Warning", msg)
                    self.status_label.config(text=f"⚠️ Health Check: {passed_count}/{total_count} passed")
                    self.status_icon.config(text="⚠️")
            else:
                self.status_label.config(text=f"✅ Ready - Health Check: {passed_count}/{total_count} OK")
                self.status_icon.config(text="✅")
                logging.info(f"[Health] All {total_count} startup checks passed ✅")
        except Exception as e:
            logging.warning(f"[Health] Could not run health checks: {e}")
            self.status_label.config(text="Ready...")

    def setup_logging(self):
        # Use config.LOG_DIR which is relative to EXE location
        log_folder = config.LOG_DIR
        log_folder.mkdir(parents=True, exist_ok=True)
        log_file = log_folder / f"gui_log_{datetime.now().strftime('%Y%m%d')}.txt"
        
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s: %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        text_handler = TextHandler(self.log_queue)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s', datefmt='%H:%M:%S'))
        logging.getLogger().addHandler(text_handler)
        logging.info("Ứng dụng đã khởi động.")

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text_widget.config(state=tk.NORMAL)
                self.log_text_widget.insert(tk.END, msg + "\n")
                self.log_text_widget.see(tk.END)
                self.log_text_widget.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_log_queue)

    def create_widgets(self):
        main_frame = ttkb.Frame(self, padding="15")
        main_frame.pack(expand=True, fill=tk.BOTH)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Status frame
        status_frame = ttkb.Frame(main_frame)
        status_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        status_frame.columnconfigure(1, weight=1)
        
        self.status_icon = ttkb.Label(status_frame, text="✅", font=("Segoe UI Symbol", 14))
        self.status_icon.grid(row=0, column=0, padx=(0, 10))
        
        self.status_label = ttkb.Label(status_frame, text="Ready...", font=("Segoe UI", 12, "bold"))
        self.status_label.grid(row=0, column=1, sticky="w")
        
        self.progress_bar = ttkb.Progressbar(status_frame, orient="horizontal", mode="indeterminate")
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        self.progress_bar.grid_remove()
        
        # Button frame - Row 1
        button_frame = ttkb.Frame(main_frame)
        button_frame.grid(row=1, column=0, pady=(10, 20), sticky="w")
        
        self.batch_button = ttkb.Button(button_frame, text=t("gui_run_reconciliation"), command=self.open_batch_dialog, width=22, bootstyle=PRIMARY)
        self.batch_button.pack(side=tk.LEFT, padx=5)
        
        self.open_report_button = ttkb.Button(button_frame, text=t("gui_open_latest_report"), command=self.open_output_folder, width=22, bootstyle=SECONDARY)
        self.open_report_button.pack(side=tk.LEFT, padx=5)
        
        self.open_bi_button = ttkb.Button(button_frame, text=t("gui_open_bi_dashboard"), command=self.open_bi_dashboard, width=22, bootstyle=SUCCESS)
        self.open_bi_button.pack(side=tk.LEFT, padx=5)
        
        self.open_web_button = ttkb.Button(button_frame, text=t("gui_open_web_dashboard"), command=self.open_web_dashboard, width=25, bootstyle=INFO)
        self.open_web_button.pack(side=tk.LEFT, padx=5)
        
        # Row 2: Secondary buttons
        button_frame2 = ttkb.Frame(main_frame)
        button_frame2.grid(row=2, column=0, pady=(0, 10), sticky="w")
        main_frame.rowconfigure(3, weight=1)
        
        self.export_button = ttkb.Button(button_frame2, text=t("gui_export_data"), command=self.open_export_dialog, width=20, bootstyle=(WARNING, OUTLINE))
        self.export_button.pack(side=tk.LEFT, padx=5)
        
        self.compare_button = ttkb.Button(button_frame2, text=t("gui_compare_files"), command=self.open_compare_dialog, width=20, bootstyle=(INFO, OUTLINE))
        self.compare_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_data_button = ttkb.Button(button_frame2, text=t("gui_clear_data"), command=self.clear_data, width=20, bootstyle=(DANGER, OUTLINE))
        self.clear_data_button.pack(side=tk.LEFT, padx=5)
        
        # Log frame
        self.log_frame = ttkb.LabelFrame(main_frame, text="Activity Log", padding=10)
        self.log_frame.grid(row=3, column=0, sticky="nsew")
        self.log_frame.grid_remove()
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        
        self.log_text_widget = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text_widget.grid(row=0, column=0, sticky="nsew")
        self.log_text_widget.config(state=tk.DISABLED)
        
        # Footer frame
        footer_frame = ttkb.Frame(main_frame, padding=(0, 10))
        footer_frame.grid(row=4, column=0, sticky="ew")
        footer_frame.columnconfigure(2, weight=1)
        
        self.settings_button = ttkb.Button(footer_frame, text=t("gui_settings"), command=self.open_settings_window, width=15, bootstyle=(DARK, OUTLINE))
        self.settings_button.grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.appearance_button = ttkb.Button(footer_frame, text=t("gui_appearance"), command=self.open_appearance_dialog, width=15, bootstyle=(INFO, OUTLINE))
        self.appearance_button.grid(row=0, column=1, sticky="w")
        
        self.log_button = ttkb.Button(footer_frame, text=t("gui_show_log"), command=self.toggle_log, width=15, bootstyle=(INFO, OUTLINE))
        self.log_button.grid(row=0, column=3, sticky="e")
        
        footer_text = t("gui_developed_by", "Tien-Tan Thuan Port", config.APP_VERSION, config.APP_YEAR)
        self.footer_label = ttkb.Label(footer_frame, text=footer_text, font=("Segoe UI", 8))
        self.footer_label.grid(row=0, column=2, sticky="e", padx=20)

    def toggle_log(self):
        if self.log_frame.winfo_viewable():
            self.log_frame.grid_remove()
            self.log_button.config(text="📝 Show Log")
        else:
            self.log_frame.grid()
            self.log_button.config(text="📝 Hide Log")

    def open_settings_window(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        self.settings_window = SettingsDialog(self)
    
    def open_appearance_dialog(self):
        """V5.0: Open Appearance dialog for Theme and Language."""
        AppearanceDialog(self)
    
    def open_export_dialog(self):
        """Mở dialog Export Data"""
        ExportDialog(self)
    
    def open_batch_dialog(self):
        """Mở dialog Batch Mode"""
        BatchModeDialog(self)
    
    def open_compare_dialog(self):
        """V5.4: Mở dialog So sánh File (App vs TOS)"""
        CompareFilesDialog(self)
    
    def open_bi_dashboard(self):
        """BI Dashboard - Coming Soon (waiting for .pbix file)."""
        result = messagebox.askyesno(
            t("gui_bi_title"),
            t("gui_bi_message"),
            icon='info'
        )
        if result:
            try:
                output_dir = config.OUTPUT_DIR
                if output_dir.exists():
                    os.startfile(str(output_dir))
                    logging.info("Opened data folder for BI")
            except Exception as e:
                logging.error(f"Error opening folder: {e}")
    
    def open_output_folder(self):
        """Mở folder chứa báo cáo mới nhất"""
        try:
            output_dir = config.OUTPUT_DIR
            
            # Find the latest report folder by modification time (not name)
            report_folders = [f for f in output_dir.iterdir() if f.is_dir() and f.name.startswith("Report_")]
            
            if report_folders:
                # V5.6: Sort by modification time to get truly latest folder
                latest_folder = sorted(report_folders, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                os.startfile(str(latest_folder))
                logging.info(f"Đã mở folder: {latest_folder}")
            else:
                if output_dir.exists():
                    os.startfile(str(output_dir))
                    logging.info("Đã mở folder Output (chưa có báo cáo)")
                else:
                    messagebox.showwarning(
                        "Không tìm thấy báo cáo",
                        "Chưa có báo cáo nào được tạo.\nVui lòng chạy đối soát trước."
                    )
        except Exception as e:
            logging.error(f"Lỗi mở folder: {e}")
            messagebox.showerror("Lỗi", f"Không thể mở folder:\n{e}")

    def clear_data(self):
        """Xóa dữ liệu output để chạy lại từ đầu"""
        result = messagebox.askyesno(
            "⚠️ Xác nhận xóa dữ liệu",
            "Bạn có chắc muốn xóa toàn bộ dữ liệu đã chạy?\n\n"
            "Điều này sẽ xóa:\n"
            "• Tất cả file báo cáo trong thư mục Output\n"
            "• Lịch sử tồn bãi (history database)\n"
            "• File kết quả JSON\n\n"
            "Thao tác này không thể hoàn tác!",
            icon='warning'
        )
        
        if result:
            try:
                import shutil
                output_dir = config.OUTPUT_DIR
                
                files_deleted = 0
                
                if output_dir.exists():
                    for item in output_dir.iterdir():
                        if item.is_file():
                            item.unlink()
                            files_deleted += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            files_deleted += 1
                
                history_db_path = output_dir / "container_history.db"
                if history_db_path.exists():
                    history_db_path.unlink()
                    logging.info("Đã xóa database lịch sử")
                
                results_json = output_dir / "latest_results.json"
                if results_json.exists():
                    results_json.unlink()
                
                logging.info(f"Đã xóa {files_deleted} file/thư mục trong Output")
                messagebox.showinfo(
                    "✅ Hoàn thành",
                    f"Đã xóa thành công {files_deleted} file/thư mục.\n\n"
                    "Bạn có thể chạy lại đối soát từ đầu."
                )
            
            except Exception as e:
                logging.error(f"Lỗi khi xóa dữ liệu: {e}")
                messagebox.showerror("Lỗi", f"Không thể xóa dữ liệu:\n{e}")

    def start_reconciliation(self):
        if self.processor_thread and self.processor_thread.is_alive():
            messagebox.showwarning("Processing", "Another process is already running.")
            return
        self.set_gui_state(processing=True)
        self.processor_thread = threading.Thread(target=self.processing_worker, daemon=True)
        self.processor_thread.start()

    def processing_worker(self):
        try:
            self.latest_report_folder = run_full_reconciliation_process(config.INPUT_DIR, config.OUTPUT_DIR)
            self.after(0, self.on_finished)
        except Exception as e:
            logging.error(f"Lỗi nghiêm trọng trong quá trình xử lý: {e}", exc_info=True)
            self.after(0, self.on_error, str(e))

    def on_finished(self):
        self.set_gui_state(processing=False)
        messagebox.showinfo("Complete", f"Processing finished successfully!\nReports are saved in:\n{self.latest_report_folder}")

    def on_error(self, error_message):
        self.set_gui_state(processing=False)
        messagebox.showerror("Error", f"An error occurred during processing:\n\n{error_message}")

    def set_gui_state(self, processing: bool):
        state = tk.DISABLED if processing else tk.NORMAL
        self.batch_button.config(state=state)
        self.settings_button.config(state=state)
        
        if processing:
            self.status_icon.config(text="🔄")
            self.status_label.config(text="Processing... Please wait.")
            self.progress_bar.grid()
            self.progress_bar.start(10)
        else:
            self.progress_bar.stop()
            self.progress_bar.grid_remove()
            self.status_icon.config(text="✅")
            self.status_label.config(text="Ready...")

    def open_web_dashboard(self):
        if self.streamlit_process and self.streamlit_process.poll() is None:
            logging.info("Web Dashboard đã đang chạy. Mở lại trình duyệt.")
            webbrowser.open("http://localhost:8501", new=2)
            return
        
        logging.info("Đang khởi chạy Web Dashboard...")
        try:
            app_path = Path(__file__).parent / 'app.py'
            command = [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.headless", "true"]
            self.streamlit_process = subprocess.Popen(command)
            self.after(3000, lambda: webbrowser.open("http://localhost:8501", new=2))
        except Exception as e:
            logging.error(f"Lỗi khi khởi chạy dashboard: {e}")
            messagebox.showerror("Lỗi", f"Không thể khởi chạy Web Dashboard.\nLỗi: {e}")

    def on_closing(self):
        if self.streamlit_process:
            self.streamlit_process.terminate()
            self.streamlit_process.wait()
        if self.processor_thread and self.processor_thread.is_alive():
            if not messagebox.askyesno("Exit", "A process is running. Are you sure you want to exit?"):
                return
        self.destroy()


if __name__ == "__main__":
    if not hasattr(config, 'APP_VERSION'):
        config.APP_VERSION = "1.0"
    app = App()
    app.mainloop()
