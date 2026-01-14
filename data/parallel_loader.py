"""
Parallel file loading utility.
Uses concurrent.futures to load multiple Excel files simultaneously.
"""
import logging
from pathlib import Path
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd


def load_files_parallel(
    files_config: Dict[str, str], 
    input_dir: Path, 
    loader_func, 
    report_folder: Path,
    max_workers: int = 4
) -> Dict[str, pd.DataFrame]:
    """
    Load multiple Excel files in parallel using ThreadPoolExecutor.
    
    Args:
        files_config: Dictionary mapping file key to filename (e.g., {'ton_cu': 'TON CU.xlsx'}).
        input_dir: Directory containing the Excel files.
        loader_func: Function to load and transform a single file.
                     Signature: loader_func(file_path, filename, file_key, cleaned_dir) -> DataFrame
        report_folder: Directory for saving cleaned files.
        max_workers: Maximum number of parallel threads (default: 4).
    
    Returns:
        Dictionary mapping file key to loaded DataFrame.
    
    Note:
        Parallel loading can significantly speed up processing when dealing with
        multiple large Excel files, especially on systems with SSDs.
    """
    file_dfs = {}
    cleaned_files_dir = report_folder / "0a_Cleaned_Files"
    cleaned_files_dir.mkdir(exist_ok=True)
    
    def load_single(key_filename_tuple):
        key, filename = key_filename_tuple
        file_path = input_dir / filename
        try:
            return key, loader_func(file_path, filename, key, cleaned_files_dir)
        except Exception as e:
            logging.error(f"Error loading {filename}: {e}")
            return key, pd.DataFrame()
    
    logging.info(f"Starting parallel file loading with {max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(load_single, (key, filename)): key 
            for key, filename in files_config.items()
        }
        
        for future in as_completed(futures):
            key, df = future.result()
            file_dfs[key] = df
            logging.info(f"  -> Loaded: {key} ({len(df)} rows)")
    
    logging.info(f"Parallel loading complete. Loaded {len(file_dfs)} files.")
    return file_dfs
