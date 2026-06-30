"""
Data Quality Business Rules
Validates weight & height measurement datasets against defined business rules.
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime
from typing import Dict, List, Tuple

from backend.clinical_ranges import get_range as _cr_get_range

# br02/br03 bounds — DOM, doc §6. Sourced from clinical_ranges registry (Phase 2).
# Intentionally looser than cohort cleaner bounds; flags only physiologically impossible.
_BR02_LO, _BR02_HI = _cr_get_range("br02_weight_impossible")  # 10, 125 kg
_BR03_LO, _BR03_HI = _cr_get_range("br03_height_impossible")  # 50, 200 cm


class QualityChecker:
    """Business rule validation for school-health measurement data"""
    
    def __init__(self, df: pd.DataFrame, range_overrides: dict | None = None):
        self.df = df
        self.issues = []
        self.affected_rows = {}  # Store rows affected by each rule
        # Override-aware DOM bounds (default to module constants / registry defaults).
        self._br02 = _cr_get_range("br02_weight_impossible", range_overrides)
        self._br03 = _cr_get_range("br03_height_impossible", range_overrides)
        
    def check_all_rules(self) -> Dict:
        """Run all business rules and return consolidated report"""
        print("\n" + "="*60)
        print("DATA QUALITY VALIDATION")
        print("="*60)
        
        self.check_br01_null_measurement_dates()
        self.check_br02_berat_outliers()
        self.check_br03_tinggi_outliers()
        self.check_br04_duplicate_ids()
        self.check_br05_unknown_gender()
        self.check_br06_year_level_range()
        self.check_br07_dob_encoding()
        self.check_br08_measurement_pairs_null()
        self.check_br09_suspicious_dates()
        
        print(f"\n✓ Quality check complete: {len(self.issues)} issues detected")
        print("="*60 + "\n")
        
        return {
            "issues": self.issues,
            "affected_rows": self.affected_rows,
            "total_issues": len(self.issues),
            "total_rows": len(self.df),
        }
    
    def check_br01_null_measurement_dates(self):
        """BR-01: Check for entirely NULL measurement date columns"""
        date_cols = [c for c in self.df.columns if 'tarikh' in c.lower() and 'pengukuran' in c.lower()]
        
        for col in date_cols:
            if col not in self.df.columns:
                continue
                
            null_count = self.df[col].isna().sum()
            total = len(self.df)
            
            if null_count == total:
                # Entire column is NULL
                self.issues.append({
                    "rule_id": "BR-01",
                    "column": col,
                    "issue_type": "Entire Column NULL",
                    "description": f"All {total:,} records have NULL measurement date. Cannot determine when weight/height was taken. Limits time-based trend analysis. 2025 dataset has this field populated.",
                    "row_count": total,
                    "pct_total": 100.0,
                    "severity": "CRITICAL",
                    "recommended_fix": "Request actual measurement dates from the data provider. For 2024, use school year (2024) as proxy date only.",
                })
                # Store sample of affected rows (first 100)
                self.affected_rows["BR-01"] = self.df.head(100).to_dict('records')
                
            elif null_count > 0:
                # Partial NULLs
                self.issues.append({
                    "rule_id": "BR-01",
                    "column": col,
                    "issue_type": "Partial NULL",
                    "description": f"{null_count:,} records have NULL measurement date",
                    "row_count": null_count,
                    "pct_total": round(null_count / total * 100, 2),
                    "severity": "WARNING",
                    "recommended_fix": "Fill missing dates with proxy values or flag for data collection team",
                })
                self.affected_rows["BR-01_partial"] = self.df[self.df[col].isna()].head(100).to_dict('records')
    
    def check_br02_berat_outliers(self):
        """BR-02: Check for biologically impossible weight values"""
        berat_cols = [c for c in self.df.columns if 'berat' in c.lower() and 'kg' in c.lower()]
        
        for col in berat_cols:
            if col not in self.df.columns:
                continue
            
            # Convert to numeric
            values = pd.to_numeric(self.df[col], errors='coerce')
            
            outlier_low = values < self._br02[0]
            outlier_high = values > self._br02[1]
            outliers = outlier_low | outlier_high
            
            if outliers.sum() > 0:
                min_val = values[outliers].min()
                max_val = values[outliers].max()
                
                self.issues.append({
                    "rule_id": "BR-02",
                    "column": col,
                    "issue_type": "Outlier: Impossible Values",
                    "description": f"Min: {min_val:.1f} kg (physiologically impossible for a 7-year-old). Max: {max_val:.1f} kg (extremely high- likely entry error). Normal range for 7-year-olds: ~15-30 kg",
                    "row_count": outliers.sum(),
                    "pct_total": round(outliers.sum() / len(self.df) * 100, 2) if len(self.df) > 0 else 0,
                    "severity": "ERROR",
                    "recommended_fix": "Exclude BERAT < 12 kg or > 50 kg before z-score computation. Apply WHO BIV cutoffs.",
                })
                self.affected_rows["BR-02"] = self.df[outliers].head(100).to_dict('records')
    
    def check_br03_tinggi_outliers(self):
        """BR-03: Check for biologically impossible height values"""
        tinggi_cols = [c for c in self.df.columns if 'tinggi' in c.lower() and 'cm' in c.lower()]
        
        for col in tinggi_cols:
            if col not in self.df.columns:
                continue
            
            # Convert to numeric
            values = pd.to_numeric(self.df[col], errors='coerce')
            
            outlier_low = values < self._br03[0]
            outlier_high = values > self._br03[1]
            outliers = outlier_low | outlier_high
            
            if outliers.sum() > 0:
                min_val = values[outliers].min()
                max_val = values[outliers].max()
                
                self.issues.append({
                    "rule_id": "BR-03",
                    "column": col,
                    "issue_type": "Outlier: Suspect Values",
                    "description": f"Min: {min_val:.1f} cm (very low- could be infant data entered in wrong cohort or keyboard error). Max: {max_val:.1f} cm (impossible for a 7-year-old). Normal range for 7-year-olds: ~110-135 cm",
                    "row_count": outliers.sum(),
                    "pct_total": round(outliers.sum() / len(self.df) * 100, 2) if len(self.df) > 0 else 0,
                    "severity": "ERROR",
                    "recommended_fix": "Exclude TINGGI < 100 cm or > 160 cm. Flag as BIV (Biologically Implausible Values).",
                })
                self.affected_rows["BR-03"] = self.df[outliers].head(100).to_dict('records')
    
    def check_br04_duplicate_ids(self):
        """BR-04: Check for duplicate ID_MURID values"""
        id_cols = [c for c in self.df.columns if 'id' in c.lower() and 'murid' in c.lower()]
        
        for col in id_cols:
            if col not in self.df.columns:
                continue
            
            # Find ALL duplicate rows (not just the count)
            # duplicated(keep=False) marks all duplicates including first occurrence
            duplicate_mask = self.df[col].duplicated(keep=False) & self.df[col].notna()
            dupes = self.df[duplicate_mask].copy()
            
            if len(dupes) > 0:
                unique_dupe_ids = dupes[col].nunique()
                
                # Sort by ID so duplicates are grouped together
                dupes_sorted = dupes.sort_values(by=col)
                
                # Check if duplicates are from same student measured twice or different students
                dupe_analysis = "Same student may have been measured twice, or data entry error producing same ID for different students"
                
                self.issues.append({
                    "rule_id": "BR-04",
                    "column": col,
                    "issue_type": "Duplicate Student IDs",
                    "description": f"{unique_dupe_ids:,} duplicate {col} values found affecting {len(dupes)} total rows. {dupe_analysis}",
                    "row_count": len(dupes),
                    "pct_total": round(len(dupes) / len(self.df) * 100, 2) if len(self.df) > 0 else 0,
                    "severity": "WARNING",
                    "recommended_fix": "Investigate duplicates. If same student, keep most recent. If different students, escalate for review.",
                })
                # Store ALL duplicate rows (up to 1000), sorted by ID for easy comparison
                self.affected_rows["BR-04"] = dupes_sorted.head(1000).to_dict('records')
                
                # Also create a summary of duplicate groups
                duplicate_groups = []
                for id_val in dupes[col].unique()[:100]:  # First 100 unique duplicate IDs
                    group = self.df[self.df[col] == id_val]
                    duplicate_groups.append({
                        'id': id_val,
                        'count': len(group),
                        'rows': group.to_dict('records')
                    })
                self.affected_rows["BR-04_groups"] = duplicate_groups
    
    def check_br05_unknown_gender(self):
        """BR-05: Check for unknown/invalid gender values"""
        gender_cols = [c for c in self.df.columns if 'jantina' in c.lower()]
        
        for col in gender_cols:
            if col not in self.df.columns:
                continue
            
            # Valid values: Male/Female/Lelaki/Perempuan/M/F/L/P
            valid_values = ['male', 'female', 'lelaki', 'perempuan', 'm', 'f', 'l', 'p']
            invalid = self.df[
                ~self.df[col].astype(str).str.lower().str.strip().isin(valid_values) & 
                self.df[col].notna()
            ]
            
            if len(invalid) > 0:
                unknown_values = invalid[col].value_counts().to_dict()
                
                self.issues.append({
                    "rule_id": "BR-05",
                    "column": col,
                    "issue_type": "Unknown Gender Value",
                    "description": f"{len(invalid)} records with JANTINA = {list(unknown_values.keys())} (uncertain/unknown). Cannot be included in gender-stratified WHO z-score computation (requires M/F). May be data entry error",
                    "row_count": len(invalid),
                    "pct_total": round(len(invalid) / len(self.df) * 100, 2) if len(self.df) > 0 else 0,
                    "severity": "WARNING",
                    "recommended_fix": "Exclude from gender-stratified analysis. Flag for review.",
                })
                self.affected_rows["BR-05"] = invalid.head(100).to_dict('records')
    
    def check_br06_year_level_range(self):
        """BR-06: Check for students outside expected year level"""
        year_cols = [c for c in self.df.columns if 'thn' in c.lower() and 'ting' in c.lower()]
        
        for col in year_cols:
            if col not in self.df.columns:
                continue
            
            # Expected: Tahun 1-7 (primary school)
            # But dataset is for 7-year-olds specifically, so expect Tahun 1-2 mostly
            values = pd.to_numeric(self.df[col], errors='coerce')
            
            # Flag unusual year levels
            outside_range = (values < 1) | (values > 7) | values.isna()
            unusual = outside_range & self.df[col].notna()
            
            if unusual.sum() > 0:
                value_dist = self.df[unusual][col].value_counts().to_dict()
                
                self.issues.append({
                    "rule_id": "BR-06",
                    "column": col,
                    "issue_type": "Students Outside Expected Year Level",
                    "description": f"Distribution: {value_dist}. Dataset intended for 7-year-old cohort (Tahun Satu + Kelas Khas Rendah)",
                    "row_count": unusual.sum(),
                    "pct_total": round(unusual.sum() / len(self.df) * 100, 2) if len(self.df) > 0 else 0,
                    "severity": "INFO",
                    "recommended_fix": "Clarify with the data provider: include or exclude non-Tahun Satu records? Age-validate against Tarikh Lahir.",
                })
                self.affected_rows["BR-06"] = self.df[unusual].head(100).to_dict('records')
    
    def check_br07_dob_encoding(self):
        """BR-07: Check if DOB is encoded in ID_MURID and validate"""
        id_cols = [c for c in self.df.columns if 'id' in c.lower() and 'murid' in c.lower()]
        dob_cols = [c for c in self.df.columns if 'tarikh' in c.lower() and 'lahir' in c.lower()]
        
        if not id_cols or not dob_cols:
            return
        
        id_col = id_cols[0]
        dob_col = dob_cols[0]
        
        # Check if ID format suggests DOB encoding (e.g., YYMMDDXXXX or DDMMYYYYXXXX)
        # For Malaysian format: positions 2-9 could be DDMMYYYY
        mismatches = []
        
        for idx, row in self.df.head(1000).iterrows():  # Sample first 1000 rows
            id_val = str(row[id_col]) if pd.notna(row[id_col]) else ""
            dob_val = row[dob_col]
            
            if len(id_val) >= 8 and pd.notna(dob_val):
                # Try to extract date from ID (assuming format: M03042018 = 03/04/2018)
                try:
                    # Skip first character, take next 8 digits
                    if id_val[0].isalpha():
                        date_str = id_val[1:9]
                    else:
                        date_str = id_val[0:8]
                    
                    # Parse as DDMMYYYY
                    if len(date_str) == 8 and date_str.isdigit():
                        id_date = datetime.strptime(date_str, '%d%m%Y').date()
                        
                        # Convert dob_val to date
                        if isinstance(dob_val, str):
                            dob_date = pd.to_datetime(dob_val, errors='coerce').date()
                        else:
                            dob_date = pd.to_datetime(dob_val).date()
                        
                        if id_date != dob_date:
                            mismatches.append({
                                'id': id_val,
                                'id_dob': id_date,
                                'actual_dob': dob_date
                            })
                except:
                    pass
        
        if len(mismatches) > 0:
            self.issues.append({
                "rule_id": "BR-07",
                "column": f"{id_col} / {dob_col}",
                "issue_type": "DOB Encoding in ID Not Validated",
                "description": f"{id_col} encodes DOB in positions 2-9 (format DDMMYYYY). Example: M03042018 = born 03/04/2018. Cross-validation against {dob_col} not yet performed",
                "row_count": len(mismatches),
                "pct_total": 0,  # TBC - need full validation
                "severity": "INFO",
                "recommended_fix": "Extract DOB from ID prefix. Compare to TARIKH LAHIR field. Flag mismatches.",
                })
            self.affected_rows["BR-07"] = mismatches[:100]
    
    def check_br08_measurement_pairs_null(self):
        """BR-08: Check for records missing both BERAT and TINGGI"""
        berat_cols = [c for c in self.df.columns if 'berat' in c.lower()]
        tinggi_cols = [c for c in self.df.columns if 'tinggi' in c.lower()]
        
        if not berat_cols or not tinggi_cols:
            return
        
        berat_col = berat_cols[0]
        tinggi_col = tinggi_cols[0]
        
        # Find rows where both are NULL
        both_null = self.df[self.df[berat_col].isna() & self.df[tinggi_col].isna()]
        
        if len(both_null) > 0:
            self.issues.append({
                "rule_id": "BR-08",
                "column": f"{berat_col} / {tinggi_col}",
                "issue_type": "Measurement Pairs NULL",
                "description": f"{len(both_null):,} records missing both BERAT and TINGGI. Cannot compute BMI or z-scores for these records. Expected: students absent on measurement day",
                "row_count": len(both_null),
                "pct_total": round(len(both_null) / len(self.df) * 100, 2) if len(self.df) > 0 else 0,
                "severity": "WARNING",
                "recommended_fix": "Do not drop rows. Keep for school/demographic counts. Filter when running anthropometric analysis.",
                })
            self.affected_rows["BR-08"] = both_null.head(100).to_dict('records')
    
    def check_br09_suspicious_dates(self):
        """BR-09: Check for suspicious historical or future dates"""
        date_cols = [c for c in self.df.columns if 'tarikh' in c.lower()]

        # Reference is the run-time clock, not a hardcoded literal, so the
        # future-date check stays correct every year without a code edit.
        current_year = pd.Timestamp.now().year

        for col in date_cols:
            if col not in self.df.columns:
                continue

            dates = pd.to_datetime(self.df[col], errors='coerce')

            # Check for dates before ~20 years before the run year (clearly too
            # old for this cohort) or after the current year (a future date).
            too_old = dates < pd.Timestamp(f'{current_year - 20}-01-01')
            too_new = dates > pd.Timestamp(f'{current_year}-12-31')
            suspicious = too_old | too_new
            
            if suspicious.sum() > 0:
                old_count = too_old.sum()
                new_count = too_new.sum()
                
                description = []
                if old_count > 0:
                    min_date = dates[too_old].min()
                    description.append(f"{old_count} record(s) dated before {current_year - 20} — over 20 years before the data collection year")
                if new_count > 0:
                    max_date = dates[too_new].max()
                    description.append(f"{new_count} record(s) in future dates")
                
                self.issues.append({
                    "rule_id": "BR-09",
                    "column": col,
                    "issue_type": "Suspicious Historical/Future Date",
                    "description": ". ".join(description) + ". Clearly a system or entry error",
                    "row_count": suspicious.sum(),
                    "pct_total": round(suspicious.sum() / len(self.df) * 100, 2) if len(self.df) > 0 else 0,
                    "severity": "ERROR",
                    "recommended_fix": f"Set to NULL. Cannot be a valid measurement date for a {current_year} cohort.",
                })
                self.affected_rows["BR-09"] = self.df[suspicious].head(100).to_dict('records')


def analyze_quality(df: pd.DataFrame, range_overrides: dict | None = None) -> Dict:
    """
    Main entry point for data quality analysis

    Args:
        df: DataFrame with weight & height data
        range_overrides: optional {registry_key: {min,max}} applied to BR-02/BR-03
            (br02_weight_impossible / br03_height_impossible) for this run.

    Returns:
        Dictionary with quality report and affected rows
    """
    checker = QualityChecker(df, range_overrides)
    return checker.check_all_rules()
