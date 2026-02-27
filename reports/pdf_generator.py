# File: reports/pdf_generator.py
# @2026 v1.0: PDF Report Generation with Charts
"""
PDF Report Generator Module.

Generates professional PDF reports with:
- Executive summary
- Data tables
- Charts and visualizations
- Operator breakdown

Dependencies: reportlab, matplotlib
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, ListFlowable, ListItem
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("reportlab not installed. PDF generation disabled. Run: pip install reportlab")

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-GUI backend
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.warning("matplotlib not installed. Charts disabled. Run: pip install matplotlib")


@dataclass
class ReportData:
    """Container for report data."""
    date: str
    time_slot: str
    total_containers: int
    discrepancies: int
    matched: int
    by_operator: Dict[str, Dict[str, int]]
    by_status: Dict[str, int]
    trends: List[Dict[str, Any]]
    

class PDFReportGenerator:
    """
    Generate professional PDF reports for container reconciliation.
    
    Features:
    - Executive summary with key metrics
    - Detailed tables with styling
    - Bar charts for operator comparison
    - Pie charts for status distribution
    - Trend line charts
    
    Example:
        generator = PDFReportGenerator()
        generator.generate(
            data=report_data,
            output_path=Path("reports/report.pdf")
        )
    """
    
    def __init__(self, title: str = "Container Inventory Reconciliation Report"):
        """
        Initialize PDF generator.
        
        Args:
            title: Report title
        """
        self.title = title
        self.styles = None
        self._temp_images: List[Path] = []
        
        if REPORTLAB_AVAILABLE:
            self._setup_styles()
    
    def _setup_styles(self):
        """Setup custom paragraph styles."""
        self.styles = getSampleStyleSheet()
        
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a5276')
        ))
        
        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#2874a6')
        ))
        
        # Normal text
        self.styles.add(ParagraphStyle(
            name='ReportBody',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        ))
        
        # Highlight text
        self.styles.add(ParagraphStyle(
            name='Highlight',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#c0392b'),
            fontName='Helvetica-Bold'
        ))
    
    def generate(
        self,
        data: ReportData,
        output_path: Path,
        include_charts: bool = True
    ) -> bool:
        """
        Generate PDF report.
        
        Args:
            data: Report data
            output_path: Output file path
            include_charts: Whether to include charts
            
        Returns:
            True if successful
        """
        if not REPORTLAB_AVAILABLE:
            logging.error("reportlab not installed. Cannot generate PDF.")
            return False
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
            
            elements = []
            
            # Title
            elements.append(Paragraph(self.title, self.styles['ReportTitle']))
            elements.append(Paragraph(
                f"Ngày báo cáo: {data.date} | Ca: {data.time_slot}",
                self.styles['ReportBody']
            ))
            elements.append(Paragraph(
                f"Thời gian tạo: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                self.styles['ReportBody']
            ))
            elements.append(Spacer(1, 20))
            
            # Executive Summary
            elements.extend(self._create_summary_section(data))
            
            # Charts
            if include_charts and MATPLOTLIB_AVAILABLE:
                elements.extend(self._create_charts_section(data))
            
            # Operator Details
            elements.extend(self._create_operator_section(data))
            
            # Build PDF
            doc.build(elements)
            
            # Cleanup temp images
            self._cleanup_temp_images()
            
            logging.info(f"PDF report generated: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"PDF generation failed: {e}")
            self._cleanup_temp_images()
            return False
    
    def _create_summary_section(self, data: ReportData) -> List:
        """Create executive summary section."""
        elements = []
        
        elements.append(Paragraph("1. Tổng Quan", self.styles['SectionHeader']))
        
        # Summary table
        summary_data = [
            ['Chỉ số', 'Giá trị'],
            ['Tổng container', f"{data.total_containers:,}"],
            ['Khớp dữ liệu', f"{data.matched:,}"],
            ['Chênh lệch', f"{data.discrepancies:,}"],
            ['Tỷ lệ khớp', f"{(data.matched / data.total_containers * 100):.1f}%" if data.total_containers > 0 else "N/A"],
        ]
        
        table = Table(summary_data, colWidths=[200, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2874a6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#eaf2f8')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#85929e')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        # Highlight discrepancies if any
        if data.discrepancies > 0:
            elements.append(Paragraph(
                f"⚠️ Phát hiện {data.discrepancies} container chênh lệch cần kiểm tra!",
                self.styles['Highlight']
            ))
            elements.append(Spacer(1, 10))
        
        return elements
    
    def _create_charts_section(self, data: ReportData) -> List:
        """Create charts section."""
        elements = []
        
        elements.append(Paragraph("2. Biểu Đồ Phân Tích", self.styles['SectionHeader']))
        
        # Status pie chart
        if data.by_status:
            pie_path = self._create_pie_chart(
                data.by_status,
                "Phân bổ theo trạng thái F/E"
            )
            if pie_path:
                elements.append(Image(str(pie_path), width=300, height=200))
                elements.append(Spacer(1, 10))
        
        # Operator bar chart
        if data.by_operator:
            bar_path = self._create_bar_chart(
                {k: v.get('total', 0) for k, v in data.by_operator.items()},
                "Container theo hãng tàu"
            )
            if bar_path:
                elements.append(Image(str(bar_path), width=400, height=250))
                elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_operator_section(self, data: ReportData) -> List:
        """Create operator details section."""
        elements = []
        
        elements.append(PageBreak())
        elements.append(Paragraph("3. Chi Tiết Theo Hãng Tàu", self.styles['SectionHeader']))
        
        if not data.by_operator:
            elements.append(Paragraph("Không có dữ liệu theo hãng tàu.", self.styles['ReportBody']))
            return elements
        
        # Create table data
        table_data = [['Hãng tàu', 'Tổng', 'Full', 'Empty', 'Chênh lệch']]
        
        for operator, counts in sorted(data.by_operator.items()):
            table_data.append([
                operator,
                str(counts.get('total', 0)),
                str(counts.get('full', 0)),
                str(counts.get('empty', 0)),
                str(counts.get('discrepancy', 0))
            ])
        
        table = Table(table_data, colWidths=[120, 80, 80, 80, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_pie_chart(self, data: Dict[str, int], title: str) -> Optional[Path]:
        """Create a pie chart and save as image."""
        if not MATPLOTLIB_AVAILABLE or not data:
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(6, 4))
            
            labels = list(data.keys())
            values = list(data.values())
            colors_list = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6']
            
            ax.pie(
                values,
                labels=labels,
                autopct='%1.1f%%',
                colors=colors_list[:len(labels)],
                startangle=90
            )
            ax.set_title(title, fontsize=12, fontweight='bold')
            
            # Save to temp file
            temp_path = Path(f"temp_pie_{datetime.now().strftime('%H%M%S%f')}.png")
            plt.savefig(temp_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            self._temp_images.append(temp_path)
            return temp_path
            
        except Exception as e:
            logging.error(f"Failed to create pie chart: {e}")
            return None
    
    def _create_bar_chart(self, data: Dict[str, int], title: str) -> Optional[Path]:
        """Create a bar chart and save as image."""
        if not MATPLOTLIB_AVAILABLE or not data:
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(8, 5))
            
            operators = list(data.keys())[:10]  # Limit to top 10
            values = [data[op] for op in operators]
            
            bars = ax.barh(operators, values, color='#3498db')
            ax.set_xlabel('Số lượng container')
            ax.set_title(title, fontsize=12, fontweight='bold')
            
            # Add value labels
            for bar, value in zip(bars, values):
                ax.text(
                    value + 1, bar.get_y() + bar.get_height()/2,
                    str(value), va='center', fontsize=9
                )
            
            plt.tight_layout()
            
            # Save to temp file
            temp_path = Path(f"temp_bar_{datetime.now().strftime('%H%M%S%f')}.png")
            plt.savefig(temp_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            self._temp_images.append(temp_path)
            return temp_path
            
        except Exception as e:
            logging.error(f"Failed to create bar chart: {e}")
            return None
    
    def _cleanup_temp_images(self):
        """Remove temporary image files."""
        for img_path in self._temp_images:
            try:
                if img_path.exists():
                    img_path.unlink()
            except Exception:
                pass
        self._temp_images.clear()


def generate_pdf_report(
    date: str,
    summary: Dict[str, Any],
    output_path: Path,
    include_charts: bool = True
) -> bool:
    """
    Convenience function to generate PDF report.
    
    Args:
        date: Report date
        summary: Reconciliation summary dictionary
        output_path: Output file path
        include_charts: Include charts
        
    Returns:
        True if successful
    """
    data = ReportData(
        date=date,
        time_slot=summary.get('time_slot', 'N/A'),
        total_containers=summary.get('total', 0),
        discrepancies=summary.get('discrepancies', 0),
        matched=summary.get('matched', 0),
        by_operator=summary.get('by_operator', {}),
        by_status=summary.get('by_status', {}),
        trends=summary.get('trends', [])
    )
    
    generator = PDFReportGenerator()
    return generator.generate(data, output_path, include_charts)
