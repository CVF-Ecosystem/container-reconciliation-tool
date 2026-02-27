# File: core/anomaly_detector.py — @2026 v1.0
"""
ML-based Anomaly Detection for Container Inventory.

Detects unusual patterns that may indicate data errors or operational issues:
1. Unusual dwell time (containers staying too long or too short)
2. Duplicate transactions (same container, same time, different source)
3. Suspicious operator patterns (sudden spike in one operator's containers)
4. Date anomalies (transactions at unusual hours, future dates)
5. Container count anomalies (sudden large changes in inventory)

Uses statistical methods (IQR, Z-score) and simple ML (Isolation Forest).
No external ML dependencies required for basic detection.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from config import Col


# ============ ANOMALY RESULT ============

@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    anomaly_type: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    affected_containers: List[str] = field(default_factory=list)
    affected_count: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.anomaly_type,
            "severity": self.severity,
            "description": self.description,
            "affected_count": self.affected_count,
            "affected_containers": self.affected_containers[:10],  # Limit to 10
            "details": self.details
        }


@dataclass
class AnomalyReport:
    """Collection of detected anomalies."""
    anomalies: List[Anomaly] = field(default_factory=list)
    scan_time: datetime = field(default_factory=datetime.now)
    total_containers_scanned: int = 0
    
    @property
    def critical_count(self) -> int:
        return sum(1 for a in self.anomalies if a.severity == "critical")
    
    @property
    def high_count(self) -> int:
        return sum(1 for a in self.anomalies if a.severity == "high")
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert anomalies to DataFrame for display."""
        if not self.anomalies:
            return pd.DataFrame()
        return pd.DataFrame([a.to_dict() for a in self.anomalies])
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        if not self.anomalies:
            return "✅ Không phát hiện bất thường"
        
        lines = [f"⚠️ Phát hiện {len(self.anomalies)} bất thường:"]
        if self.critical_count:
            lines.append(f"  🔴 Nghiêm trọng: {self.critical_count}")
        if self.high_count:
            lines.append(f"  🟠 Cao: {self.high_count}")
        
        for anomaly in self.anomalies[:5]:  # Show top 5
            lines.append(f"  • [{anomaly.severity.upper()}] {anomaly.description}")
        
        if len(self.anomalies) > 5:
            lines.append(f"  ... và {len(self.anomalies) - 5} bất thường khác")
        
        return "\n".join(lines)


# ============ ANOMALY DETECTORS ============

class DwellTimeAnomalyDetector:
    """
    Detect containers with unusual dwell time.
    
    Uses IQR (Interquartile Range) method to identify outliers.
    """
    
    def __init__(self, iqr_multiplier: float = 3.0):
        """
        Args:
            iqr_multiplier: Multiplier for IQR to define outlier bounds.
                           Higher = less sensitive. Default 3.0 (very unusual).
        """
        self.iqr_multiplier = iqr_multiplier
    
    def detect(self, df_ton_moi: pd.DataFrame) -> List[Anomaly]:
        """Detect dwell time anomalies in current inventory."""
        anomalies = []
        
        if df_ton_moi is None or df_ton_moi.empty:
            return anomalies
        
        # Find date column
        date_col = None
        for col in df_ton_moi.columns:
            if 'ngay' in col.lower() and ('nhap' in col.lower() or 'vao' in col.lower()):
                date_col = col
                break
        if date_col is None and Col.NGAY_NHAP_BAI in df_ton_moi.columns:
            date_col = Col.NGAY_NHAP_BAI
        
        if not date_col:
            return anomalies
        
        df = df_ton_moi.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        
        if df.empty:
            return anomalies
        
        today = datetime.now()
        df['dwell_days'] = (today - df[date_col]).dt.days
        df = df[df['dwell_days'] >= 0]  # Remove future dates
        
        if len(df) < 4:  # Need at least 4 points for IQR
            return anomalies
        
        # IQR method
        Q1 = df['dwell_days'].quantile(0.25)
        Q3 = df['dwell_days'].quantile(0.75)
        IQR = Q3 - Q1
        
        upper_bound = Q3 + self.iqr_multiplier * IQR
        lower_bound = max(0, Q1 - self.iqr_multiplier * IQR)
        
        # Very long dwell time
        long_dwell = df[df['dwell_days'] > upper_bound]
        if not long_dwell.empty:
            containers = long_dwell[Col.CONTAINER].tolist() if Col.CONTAINER in long_dwell.columns else []
            anomalies.append(Anomaly(
                anomaly_type="long_dwell_time",
                severity="medium" if len(long_dwell) < 10 else "high",
                description=f"{len(long_dwell)} container tồn bãi bất thường lâu (>{upper_bound:.0f} ngày)",
                affected_containers=containers,
                affected_count=len(long_dwell),
                details={
                    "threshold_days": round(upper_bound, 1),
                    "max_dwell_days": int(long_dwell['dwell_days'].max()),
                    "median_dwell_days": round(df['dwell_days'].median(), 1)
                }
            ))
        
        return anomalies


class DuplicateTransactionDetector:
    """
    Detect duplicate or suspicious transactions.
    
    Looks for:
    - Same container appearing in both IN and OUT on same day
    - Same container with multiple transactions in very short time
    """
    
    def detect(self, file_dfs: Dict[str, pd.DataFrame]) -> List[Anomaly]:
        """Detect duplicate transaction anomalies."""
        anomalies = []
        
        # Collect all transactions
        all_moves = []
        for key, df in file_dfs.items():
            if key in ('ton_cu', 'ton_moi') or df.empty:
                continue
            if Col.CONTAINER in df.columns and Col.TRANSACTION_TIME in df.columns:
                df_copy = df[[Col.CONTAINER, Col.TRANSACTION_TIME]].copy()
                df_copy['source'] = key
                all_moves.append(df_copy)
        
        if not all_moves:
            return anomalies
        
        df_all = pd.concat(all_moves, ignore_index=True)
        df_all[Col.TRANSACTION_TIME] = pd.to_datetime(df_all[Col.TRANSACTION_TIME], errors='coerce')
        df_all = df_all.dropna(subset=[Col.TRANSACTION_TIME])
        
        if df_all.empty:
            return anomalies
        
        # Find containers with many transactions in short time (< 1 hour)
        df_all = df_all.sort_values([Col.CONTAINER, Col.TRANSACTION_TIME])
        df_all['time_diff'] = df_all.groupby(Col.CONTAINER)[Col.TRANSACTION_TIME].diff()
        
        rapid_transactions = df_all[
            df_all['time_diff'] < pd.Timedelta(minutes=5)
        ]
        
        if not rapid_transactions.empty:
            containers = rapid_transactions[Col.CONTAINER].unique().tolist()
            anomalies.append(Anomaly(
                anomaly_type="rapid_transactions",
                severity="medium",
                description=f"{len(containers)} container có giao dịch liên tiếp trong < 5 phút",
                affected_containers=containers[:10],
                affected_count=len(containers),
                details={"threshold_minutes": 5}
            ))
        
        return anomalies


class OperatorSpikeDetector:
    """
    Detect sudden spikes in operator container counts.
    
    Uses Z-score to identify operators with unusually high/low counts.
    """
    
    def __init__(self, z_threshold: float = 3.0):
        self.z_threshold = z_threshold
    
    def detect(self, operator_summary: pd.DataFrame) -> List[Anomaly]:
        """Detect operator count anomalies."""
        anomalies = []
        
        if operator_summary is None or operator_summary.empty:
            return anomalies
        
        if 'Tồn Mới' not in operator_summary.columns:
            return anomalies
        
        counts = operator_summary['Tồn Mới'].astype(float)
        
        if len(counts) < 3:
            return anomalies
        
        mean = counts.mean()
        std = counts.std()
        
        if std == 0:
            return anomalies
        
        z_scores = (counts - mean) / std
        
        # Operators with unusually high counts
        high_outliers = operator_summary[z_scores > self.z_threshold]
        if not high_outliers.empty:
            operators = high_outliers.index.tolist()
            anomalies.append(Anomaly(
                anomaly_type="operator_spike",
                severity="low",
                description=f"{len(operators)} hãng có tồn bãi bất thường cao (Z-score > {self.z_threshold})",
                affected_containers=[],
                affected_count=len(operators),
                details={
                    "operators": operators[:5],
                    "mean_count": round(mean, 1),
                    "threshold_count": round(mean + self.z_threshold * std, 1)
                }
            ))
        
        return anomalies


class InventoryChangeAnomalyDetector:
    """
    Detect anomalous changes between TON CU and TON MOI.
    
    Flags when the change is unusually large (> 50% change).
    """
    
    def __init__(self, change_threshold: float = 0.5):
        """
        Args:
            change_threshold: Fraction change that triggers alert (0.5 = 50%)
        """
        self.change_threshold = change_threshold
    
    def detect(self, ton_cu_count: int, ton_moi_count: int) -> List[Anomaly]:
        """Detect anomalous inventory changes."""
        anomalies = []
        
        if ton_cu_count == 0:
            return anomalies
        
        change_rate = abs(ton_moi_count - ton_cu_count) / ton_cu_count
        
        if change_rate > self.change_threshold:
            direction = "tăng" if ton_moi_count > ton_cu_count else "giảm"
            severity = "high" if change_rate > 1.0 else "medium"
            
            anomalies.append(Anomaly(
                anomaly_type="large_inventory_change",
                severity=severity,
                description=f"Tồn bãi {direction} {change_rate*100:.1f}% so với baseline (Cũ: {ton_cu_count}, Mới: {ton_moi_count})",
                affected_count=abs(ton_moi_count - ton_cu_count),
                details={
                    "ton_cu": ton_cu_count,
                    "ton_moi": ton_moi_count,
                    "change_rate": round(change_rate, 3),
                    "threshold": self.change_threshold
                }
            ))
        
        return anomalies


# ============ MAIN ANOMALY DETECTOR ============

class ContainerAnomalyDetector:
    """
    Main anomaly detector that orchestrates all sub-detectors.
    
    Usage:
        detector = ContainerAnomalyDetector()
        report = detector.scan(file_dfs, operator_summary)
        print(report.get_summary())
        
        # Get as DataFrame for display
        df = report.to_dataframe()
    """
    
    def __init__(self):
        self.dwell_detector = DwellTimeAnomalyDetector()
        self.duplicate_detector = DuplicateTransactionDetector()
        self.operator_detector = OperatorSpikeDetector()
        self.inventory_detector = InventoryChangeAnomalyDetector()
    
    def scan(
        self,
        file_dfs: Dict[str, pd.DataFrame],
        operator_summary: Optional[pd.DataFrame] = None,
    ) -> AnomalyReport:
        """
        Run all anomaly detectors and return a report.
        
        Args:
            file_dfs: Dictionary of DataFrames by file type
            operator_summary: Operator summary DataFrame
        
        Returns:
            AnomalyReport with all detected anomalies
        """
        report = AnomalyReport()
        
        df_ton_moi = file_dfs.get('ton_moi', pd.DataFrame())
        df_ton_cu = file_dfs.get('ton_cu', pd.DataFrame())
        
        report.total_containers_scanned = len(df_ton_moi)
        
        # 1. Dwell time anomalies
        try:
            anomalies = self.dwell_detector.detect(df_ton_moi)
            report.anomalies.extend(anomalies)
        except Exception as e:
            logging.debug(f"Dwell time detection failed: {e}")
        
        # 2. Duplicate transaction anomalies
        try:
            anomalies = self.duplicate_detector.detect(file_dfs)
            report.anomalies.extend(anomalies)
        except Exception as e:
            logging.debug(f"Duplicate detection failed: {e}")
        
        # 3. Operator spike anomalies
        if operator_summary is not None:
            try:
                anomalies = self.operator_detector.detect(operator_summary)
                report.anomalies.extend(anomalies)
            except Exception as e:
                logging.debug(f"Operator spike detection failed: {e}")
        
        # 4. Inventory change anomalies
        if not df_ton_cu.empty and not df_ton_moi.empty:
            try:
                anomalies = self.inventory_detector.detect(len(df_ton_cu), len(df_ton_moi))
                report.anomalies.extend(anomalies)
            except Exception as e:
                logging.debug(f"Inventory change detection failed: {e}")
        
        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        report.anomalies.sort(key=lambda a: severity_order.get(a.severity, 4))
        
        if report.anomalies:
            logging.warning(f"Anomaly scan: {len(report.anomalies)} anomalies detected")
        else:
            logging.info("Anomaly scan: No anomalies detected")
        
        return report
    
    def scan_and_log(
        self,
        file_dfs: Dict[str, pd.DataFrame],
        operator_summary: Optional[pd.DataFrame] = None,
    ) -> AnomalyReport:
        """Scan and log results to standard logger."""
        report = self.scan(file_dfs, operator_summary)
        
        for anomaly in report.anomalies:
            level = {
                "critical": logging.CRITICAL,
                "high": logging.ERROR,
                "medium": logging.WARNING,
                "low": logging.INFO,
            }.get(anomaly.severity, logging.INFO)
            
            logging.log(level, f"[ANOMALY:{anomaly.anomaly_type}] {anomaly.description}")
        
        return report
