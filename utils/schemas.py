# File: schemas.py
from typing import TypedDict, Set, Dict, Any
import pandas as pd

class SimpleReconResult(TypedDict):
    khop: Set[str]
    thieu: Set[str]
    thua: Set[str]

class MainReconResult(TypedDict):
    ton_chuan: pd.DataFrame
    khop_sai_info: pd.DataFrame
    thieu: pd.DataFrame
    thua: pd.DataFrame
    van_ton: pd.DataFrame
    master_log: pd.DataFrame
    future_moves_report: pd.DataFrame
    suspicious_dates: pd.DataFrame
    timeline: pd.DataFrame
    raw_data: Dict[str, pd.DataFrame]
    counts: Dict[str, Any]