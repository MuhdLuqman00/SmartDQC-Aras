"""
Outlier detection and removal for anthropometric data
"""
import pandas as pd
import numpy as np

# WHO biological ranges for children (0-60 months)
BIOLOGICAL_RANGES = {
    'berat_kg': (0.5, 80),      # Weight: 0.5-80 kg
    'tinggi_cm': (30, 200),     # Height: 30-200 cm
    'panjang_cm': (30, 200),    # Length (same as height)
    'bmi': (5, 60),             # BMI: 5-60
    'age_months_computed': (0, 120),  # Age: 0-120 months (up to 10 years)
}

def detect_outliers(df: pd.DataFrame, method='biological+iqr') -> dict:
    """
    Detect outliers using multiple methods:
    - biological: Outside WHO biological ranges
    - iqr: IQR method (1.5× and 3× for moderate and extreme)
    - zscore: Z-score > 3
    
    Returns dict with outlier analysis per column
    """
    report = {}
    
    for col in df.columns:
        if col not in ['berat_kg', 'tinggi_cm', 'panjang_cm', 'bmi', 'age_months_computed']:
            continue
        
        if df[col].dtype not in [np.float64, np.int64]:
            continue
        
        col_data = df[col].dropna()
        if len(col_data) == 0:
            continue
        
        outliers = {
            'column': col,
            'total_values': len(col_data),
            'biological_outliers': 0,
            'iqr_outliers': 0,
            'extreme_outliers': 0,
            'zscore_outliers': 0,
            'combined_outliers': 0,
        }
        
        # Biological range check
        if col in BIOLOGICAL_RANGES:
            min_val, max_val = BIOLOGICAL_RANGES[col]
            bio_mask = (col_data < min_val) | (col_data > max_val)
            outliers['biological_outliers'] = bio_mask.sum()
            outliers['biological_range'] = BIOLOGICAL_RANGES[col]
        
        # IQR method
        Q1 = col_data.quantile(0.25)
        Q3 = col_data.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        iqr_mask = (col_data < lower_bound) | (col_data > upper_bound)
        outliers['iqr_outliers'] = iqr_mask.sum()
        outliers['iqr_bounds'] = (lower_bound, upper_bound)
        
        # Extreme outliers (3× IQR)
        extreme_lower = Q1 - 3 * IQR
        extreme_upper = Q3 + 3 * IQR
        extreme_mask = (col_data < extreme_lower) | (col_data > extreme_upper)
        outliers['extreme_outliers'] = extreme_mask.sum()
        
        # Z-score method
        mean = col_data.mean()
        std = col_data.std()
        if std > 0:
            z_scores = np.abs((col_data - mean) / std)
            zscore_mask = z_scores > 3
            outliers['zscore_outliers'] = zscore_mask.sum()
        
        # Combined (biological OR extreme IQR)
        if col in BIOLOGICAL_RANGES:
            min_val, max_val = BIOLOGICAL_RANGES[col]
            bio_mask_full = (df[col] < min_val) | (df[col] > max_val)
            combined_mask = bio_mask_full | (df[col] < extreme_lower) | (df[col] > extreme_upper)
            outliers['combined_outliers'] = combined_mask.sum()
        
        outliers['pct_outliers'] = (outliers['combined_outliers'] / len(col_data) * 100) if len(col_data) > 0 else 0
        
        report[col] = outliers
    
    return report


def remove_outliers(df: pd.DataFrame, method='biological', columns=None) -> pd.DataFrame:
    """
    Remove outliers from specified columns.
    
    Args:
        df: DataFrame
        method: 'biological' (WHO ranges), 'iqr' (1.5× IQR), 'extreme' (3× IQR), 'zscore' (Z>3)
        columns: List of columns to filter, defaults to anthropometric columns
    
    Returns:
        DataFrame with outliers removed (rows filtered out)
    """
    if columns is None:
        columns = ['berat_kg', 'tinggi_cm', 'panjang_cm', 'bmi', 'age_months_computed']
    
    df_clean = df.copy()
    mask = pd.Series([True] * len(df), index=df.index)
    
    for col in columns:
        if col not in df.columns:
            continue
        if df[col].dtype not in [np.float64, np.int64]:
            continue
        
        col_data = df[col]
        
        if method == 'biological' and col in BIOLOGICAL_RANGES:
            min_val, max_val = BIOLOGICAL_RANGES[col]
            col_mask = (col_data >= min_val) & (col_data <= max_val) | col_data.isna()
            mask &= col_mask
        
        elif method == 'iqr':
            Q1 = col_data.quantile(0.25)
            Q3 = col_data.quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            col_mask = (col_data >= lower) & (col_data <= upper) | col_data.isna()
            mask &= col_mask
        
        elif method == 'extreme':
            Q1 = col_data.quantile(0.25)
            Q3 = col_data.quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 3 * IQR
            upper = Q3 + 3 * IQR
            col_mask = (col_data >= lower) & (col_data <= upper) | col_data.isna()
            mask &= col_mask
        
        elif method == 'zscore':
            mean = col_data.mean()
            std = col_data.std()
            if std > 0:
                z_scores = np.abs((col_data - mean) / std)
                col_mask = (z_scores <= 3) | col_data.isna()
                mask &= col_mask
    
    df_clean = df_clean[mask]
    return df_clean


def flag_outliers(df: pd.DataFrame, method='biological') -> pd.DataFrame:
    """
    Add outlier flag columns instead of removing rows.
    Adds columns: flag_outlier_<column>, flag_outlier_any
    """
    df = df.copy()
    outlier_flags = []
    
    for col in ['berat_kg', 'tinggi_cm', 'panjang_cm', 'bmi', 'age_months_computed']:
        if col not in df.columns:
            continue
        if df[col].dtype not in [np.float64, np.int64]:
            continue
        
        flag_col = f'flag_outlier_{col}'
        
        if method == 'biological' and col in BIOLOGICAL_RANGES:
            min_val, max_val = BIOLOGICAL_RANGES[col]
            df[flag_col] = ((df[col] < min_val) | (df[col] > max_val)) & df[col].notna()
        
        elif method == 'extreme':
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 3 * IQR
            upper = Q3 + 3 * IQR
            df[flag_col] = ((df[col] < lower) | (df[col] > upper)) & df[col].notna()
        
        outlier_flags.append(flag_col)
    
    # Add combined flag
    if outlier_flags:
        df['flag_outlier_any'] = df[outlier_flags].any(axis=1)
    
    return df
