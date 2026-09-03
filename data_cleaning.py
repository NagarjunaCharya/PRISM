"""
SIIH2026 Data Cleaning Script
Cleans all datasets in data/ folder per REQ-5 (Data Quality and Pipeline Management).
Outputs cleaned CSVs to data/cleaned/ with a quality report.
"""
import pandas as pd
import numpy as np
import os
import json
import re
import hashlib
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================
DATA_DIR = r"c:\Users\Nagarjuna\OneDrive\Documents\Desktop\SIIH2026\data"
OUTPUT_DIR = os.path.join(DATA_DIR, "cleaned")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Global report
report = {}

def log_metric(dataset_name, metric_name, value):
    """Log a cleaning metric."""
    if dataset_name not in report:
        report[dataset_name] = {}
    report[dataset_name][metric_name] = value

def strip_all_strings(df):
    """Strip whitespace from all string columns. Returns count of fixes."""
    fixes = 0
    for col in df.select_dtypes(include=['object']).columns:
        mask = df[col].notna()
        original = df.loc[mask, col].copy()
        df.loc[mask, col] = df.loc[mask, col].apply(
            lambda x: x.strip() if isinstance(x, str) else x
        )
        fixes += (original != df.loc[mask, col]).sum()
    return fixes

def replace_empty_strings(df):
    """Replace empty strings with NaN. Returns count of replacements."""
    count = 0
    for col in df.select_dtypes(include=['object']).columns:
        mask = df[col].apply(lambda x: isinstance(x, str) and x.strip() == '')
        count += mask.sum()
        df.loc[mask, col] = np.nan
    return count

def parse_date_flexible(date_str):
    """Parse dates in multiple formats to ISO-8601."""
    if pd.isna(date_str) or (isinstance(date_str, str) and date_str.strip() == ''):
        return np.nan
    
    date_str = str(date_str).strip()
    
    # Try multiple formats
    formats = [
        '%m/%d/%Y',           # 1/1/2015 or 01/01/2015
        '%Y%m%d',             # 19840924
        '%d-%b-%Y',           # 29-APR-2004
        '%Y-%m-%d',           # Already ISO
        '%m/%d/%Y %I:%M:%S %p',  # 3/2/2022 2:31:59 PM
        '%b-%Y',              # NOV-1986
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # Try pandas as last resort
    try:
        dt = pd.to_datetime(date_str)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return date_str  # Return original if unparseable


def compute_content_hash(row):
    """Compute SHA-256 hash for duplicate detection."""
    content = '|'.join(str(v) for v in row.values)
    return hashlib.sha256(content.encode('utf-8', errors='replace')).hexdigest()[:16]


# =============================================================================
# 1.1 OSHA INCIDENTS
# =============================================================================
def clean_osha_incidents():
    """Clean January2015toNovember2025.csv (OSHA Incident Reports)."""
    print("\n[1/9] Cleaning OSHA Incidents...")
    filepath = os.path.join(DATA_DIR, "January2015toNovember2025.csv")
    
    df = pd.read_csv(filepath, low_memory=False)
    original_rows = len(df)
    log_metric("osha_incidents", "original_rows", original_rows)
    log_metric("osha_incidents", "original_columns", len(df.columns))
    
    # Strip whitespace
    ws_fixes = strip_all_strings(df)
    log_metric("osha_incidents", "whitespace_fixes", int(ws_fixes))
    print(f"  Fixed {ws_fixes:,} whitespace issues")
    
    # Replace empty strings with NaN
    empty_fixes = replace_empty_strings(df)
    log_metric("osha_incidents", "empty_string_fixes", int(empty_fixes))
    print(f"  Replaced {empty_fixes:,} empty strings with NaN")
    
    # Standardize EventDate to ISO-8601
    df['EventDate'] = df['EventDate'].apply(parse_date_flexible)
    print("  Standardized EventDate to ISO-8601")
    
    # Convert Zip to string (was float due to nulls)
    df['Zip'] = df['Zip'].apply(lambda x: str(int(x)).zfill(5) if pd.notna(x) else np.nan)
    print("  Converted Zip to zero-padded string")
    
    # Normalize State and City to uppercase
    df['State'] = df['State'].str.upper()
    df['City'] = df['City'].str.upper()
    print("  Normalized State and City to uppercase")
    
    # Normalize text encoding for Final Narrative (critical for NLP)
    df['Final Narrative'] = df['Final Narrative'].apply(
        lambda x: x.encode('utf-8', errors='replace').decode('utf-8') if isinstance(x, str) else x
    )
    # Remove excessive whitespace in narratives
    df['Final Narrative'] = df['Final Narrative'].apply(
        lambda x: re.sub(r'\s+', ' ', x).strip() if isinstance(x, str) else x
    )
    print("  Normalized Final Narrative text encoding and whitespace")
    
    # Remove exact duplicate rows
    dups = df.duplicated().sum()
    df = df.drop_duplicates()
    log_metric("osha_incidents", "duplicates_removed", int(dups))
    print(f"  Removed {dups} duplicate rows")
    
    # Flag rows with >30% nulls
    null_pct = df.isnull().sum(axis=1) / len(df.columns)
    high_null = (null_pct > 0.3).sum()
    log_metric("osha_incidents", "rows_over_30pct_null", int(high_null))
    
    # Quality score
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = df.isnull().sum().sum()
    quality_score = round((1 - total_nulls / total_cells) * 100, 1)
    log_metric("osha_incidents", "quality_score", quality_score)
    log_metric("osha_incidents", "cleaned_rows", len(df))
    log_metric("osha_incidents", "null_percentage", round((total_nulls / total_cells) * 100, 2))
    
    # Save
    output_path = os.path.join(OUTPUT_DIR, "osha_incidents.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  Saved to {output_path} ({len(df):,} rows, quality={quality_score}%)")
    return df


# =============================================================================
# 1.2 PIPELINE EVENTS (2100)
# =============================================================================
def clean_pipeline_events():
    """Clean 2100delimit.txt (Pipeline Event History)."""
    print("\n[2/9] Cleaning Pipeline Events (2100)...")
    filepath = os.path.join(DATA_DIR, "2100delimit.txt")
    
    # Read with proper headers (file has no header row — first row is data)
    df = pd.read_csv(filepath, encoding='latin-1', header=None, low_memory=False)
    
    # Assign proper column names from BSEE Pipeline History schema
    column_names = ['SEGMENT_NUMBER', 'EVENT_DATE', 'STATUS_CODE', 'STATUS_DATE', 'REMARKS']
    df.columns = column_names
    original_rows = len(df)
    log_metric("pipeline_events", "original_rows", original_rows)
    
    # Strip whitespace
    ws_fixes = strip_all_strings(df)
    log_metric("pipeline_events", "whitespace_fixes", int(ws_fixes))
    print(f"  Fixed {ws_fixes:,} whitespace issues")
    
    # Replace empty strings
    empty_fixes = replace_empty_strings(df)
    log_metric("pipeline_events", "empty_string_fixes", int(empty_fixes))
    
    # Standardize dates
    df['EVENT_DATE'] = df['EVENT_DATE'].apply(parse_date_flexible)
    df['STATUS_DATE'] = df['STATUS_DATE'].apply(parse_date_flexible)
    print("  Standardized dates to ISO-8601")
    
    # Remove duplicates
    dups = df.duplicated().sum()
    df = df.drop_duplicates()
    log_metric("pipeline_events", "duplicates_removed", int(dups))
    
    # Quality
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = df.isnull().sum().sum()
    quality_score = round((1 - total_nulls / total_cells) * 100, 1)
    log_metric("pipeline_events", "quality_score", quality_score)
    log_metric("pipeline_events", "cleaned_rows", len(df))
    log_metric("pipeline_events", "encoding_fixed", "latin-1 -> UTF-8")
    
    output_path = os.path.join(OUTPUT_DIR, "pipeline_events.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  Saved to {output_path} ({len(df):,} rows, quality={quality_score}%)")
    return df


# =============================================================================
# 1.3 WELL BORE DATA (5010)
# =============================================================================
def clean_well_bore():
    """Clean 5010.txt (Well Bore / Borehole Data)."""
    print("\n[3/9] Cleaning Well Bore Data (5010)...")
    filepath = os.path.join(DATA_DIR, "5010.txt")
    
    df = pd.read_csv(filepath, header=None, low_memory=False)
    
    # Assign BSEE well bore column names
    column_names = [
        'API_WELL_NUMBER', 'SIDETRACK_NUM', 'BOTTOM_FIELD_NAME_CODE', 'COMPANY_NUMBER',
        'WELL_NAME', 'SPUD_DATE', 'SURFACE_LEASE_NUMBER', 'WATER_DEPTH',
        'TOTAL_DEPTH', 'TRUE_VERTICAL_DEPTH', 'SURFACE_COORDINATES',
        'SURFACE_AREA_BLOCK', 'BOTTOM_COORDINATES', 'BOTTOM_AREA_BLOCK',
        'COMPLETION_DATE', 'STATUS_DATE', 'WELL_STATUS_CODE', 'DISTRICT_CODE',
        'WELL_TYPE_CODE', 'PROPOSED_MD', 'SURFACE_LONGITUDE', 'SURFACE_LATITUDE',
        'BOTTOM_LONGITUDE', 'BOTTOM_LATITUDE', 'OPERATOR_LEASE_NUMBER',
        'PLATFORM_COMPLEX_ID', 'STRUCTURE_NUMBER', 'LAST_UPDATE_DATE',
        'DIRECTIONAL_SURVEY_TYPE'
    ]
    df.columns = column_names
    original_rows = len(df)
    log_metric("well_bore", "original_rows", original_rows)
    
    # Strip whitespace (major issue: 630K+)
    ws_fixes = strip_all_strings(df)
    log_metric("well_bore", "whitespace_fixes", int(ws_fixes))
    print(f"  Fixed {ws_fixes:,} whitespace issues")
    
    # Replace empty strings (54K+)
    empty_fixes = replace_empty_strings(df)
    log_metric("well_bore", "empty_string_fixes", int(empty_fixes))
    print(f"  Replaced {empty_fixes:,} empty strings with NaN")
    
    # Standardize dates (YYYYMMDD format)
    date_cols = ['SPUD_DATE', 'COMPLETION_DATE', 'STATUS_DATE', 'LAST_UPDATE_DATE']
    for col in date_cols:
        df[col] = df[col].apply(parse_date_flexible)
    print("  Standardized date columns to ISO-8601")
    
    # Quality
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = df.isnull().sum().sum()
    quality_score = round((1 - total_nulls / total_cells) * 100, 1)
    log_metric("well_bore", "quality_score", quality_score)
    log_metric("well_bore", "cleaned_rows", len(df))
    
    output_path = os.path.join(OUTPUT_DIR, "well_bore.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  Saved to {output_path} ({len(df):,} rows, quality={quality_score}%)")
    return df


# =============================================================================
# 1.4 PLATFORM APPROVALS
# =============================================================================
def clean_platform_approvals():
    """Clean platformapprovalsdelimit.txt."""
    print("\n[4/9] Cleaning Platform Approvals...")
    filepath = os.path.join(DATA_DIR, "platformapprovalsdelimit.txt")
    
    df = pd.read_csv(filepath, encoding='latin-1', header=None, low_memory=False)
    
    column_names = [
        'APPLICATION_DATE', 'COMPANY_NUMBER', 'COMPANY_NAME', 'BUS_ASC_NUMBER',
        'PROJECT_NAME', 'PROJECT_DESCRIPTION', 'LEASE_NUMBER', 'AREA_CODE',
        'BLOCK_NUMBER', 'STRUCTURE_NAME', 'NORTH_SOUTH_DISTANCE', 'NORTH_SOUTH_CODE',
        'EAST_WEST_DISTANCE', 'EAST_WEST_CODE', 'WATER_DEPTH',
        'APPROVAL_DATE', 'MAJOR_COMPLEX_FLAG'
    ]
    df.columns = column_names
    original_rows = len(df)
    log_metric("platform_approvals", "original_rows", original_rows)
    
    # Strip whitespace
    ws_fixes = strip_all_strings(df)
    log_metric("platform_approvals", "whitespace_fixes", int(ws_fixes))
    print(f"  Fixed {ws_fixes:,} whitespace issues")
    
    # Replace empty strings
    empty_fixes = replace_empty_strings(df)
    log_metric("platform_approvals", "empty_string_fixes", int(empty_fixes))
    
    # Standardize dates
    for col in ['APPLICATION_DATE', 'APPROVAL_DATE']:
        df[col] = df[col].apply(parse_date_flexible)
    print("  Standardized dates to ISO-8601")
    
    # Quality
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = df.isnull().sum().sum()
    quality_score = round((1 - total_nulls / total_cells) * 100, 1)
    log_metric("platform_approvals", "quality_score", quality_score)
    log_metric("platform_approvals", "cleaned_rows", len(df))
    log_metric("platform_approvals", "encoding_fixed", "latin-1 -> UTF-8")
    
    output_path = os.path.join(OUTPUT_DIR, "platform_approvals.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  Saved to {output_path} ({len(df):,} rows, quality={quality_score}%)")
    return df


# =============================================================================
# 1.5 PLATFORM STRUCTURE REMOVAL
# =============================================================================
def clean_platform_removal():
    """Clean platstruremdelimit.txt."""
    print("\n[5/9] Cleaning Platform Structure Removal...")
    filepath = os.path.join(DATA_DIR, "platstruremdelimit.txt")
    
    df = pd.read_csv(filepath, header=None, low_memory=False)
    
    column_names = [
        'COMPANY_NAME', 'COMPANY_NUMBER', 'REMOVAL_CASE_NUMBER',
        'APPLICATION_DATE', 'PERMIT_APPROVAL_DATE', 'REMOVAL_START_DATE',
        'REMOVAL_COMPLETE_DATE', 'REMOVAL_TYPE', 'LEASE_NUMBER',
        'AREA_CODE', 'BLOCK_NUMBER', 'STRUCTURE_NAME', 'REMOVAL_MONTH_YEAR',
        'REMOVAL_METHOD', 'REMOVAL_METHOD_CODE', 'COMPLEX_ID',
        'STRUCTURE_NUMBER', 'WATER_DEPTH'
    ]
    df.columns = column_names
    original_rows = len(df)
    log_metric("platform_removal", "original_rows", original_rows)
    
    # Strip whitespace
    ws_fixes = strip_all_strings(df)
    log_metric("platform_removal", "whitespace_fixes", int(ws_fixes))
    print(f"  Fixed {ws_fixes:,} whitespace issues")
    
    # Replace empty strings
    empty_fixes = replace_empty_strings(df)
    log_metric("platform_removal", "empty_string_fixes", int(empty_fixes))
    
    # Standardize dates
    date_cols = ['APPLICATION_DATE', 'PERMIT_APPROVAL_DATE', 'REMOVAL_START_DATE', 'REMOVAL_COMPLETE_DATE']
    for col in date_cols:
        df[col] = df[col].apply(parse_date_flexible)
    print("  Standardized dates to ISO-8601")
    
    # Quality
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = df.isnull().sum().sum()
    quality_score = round((1 - total_nulls / total_cells) * 100, 1)
    log_metric("platform_removal", "quality_score", quality_score)
    log_metric("platform_removal", "cleaned_rows", len(df))
    
    output_path = os.path.join(OUTPUT_DIR, "platform_structure_removal.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  Saved to {output_path} ({len(df):,} rows, quality={quality_score}%)")
    return df


# =============================================================================
# 1.6 PIPELINE MASTER
# =============================================================================
def clean_pipeline_master():
    """Clean pplmastdelimit.txt."""
    print("\n[6/9] Cleaning Pipeline Master...")
    filepath = os.path.join(DATA_DIR, "pplmastdelimit.txt")
    
    df = pd.read_csv(filepath, header=None, low_memory=False)
    
    column_names = [
        'SEGMENT_NUMBER', 'SEGMENT_LENGTH', 'ORIG_ID_NAME', 'ORIG_AREA_CODE',
        'ORIG_BLOCK_NUMBER', 'ORIG_LEASE_NUMBER', 'DEST_ID_NAME', 'DEST_AREA_CODE',
        'DEST_BLOCK_NUMBER', 'DEST_LEASE_NUMBER', 'ABAN_APPROVAL_DATE', 'ABAN_DATE',
        'APPROVED_DATE', 'STATUS_CODE', 'ROW_PERMIT_FLAG', 'FEDERAL_WATERS_FLAG',
        'PPL_SIZE_CODE', 'PPL_SIZE_INCHES', 'SEGMENT_LENGTH_MILES', 'DIRECTION_CODE',
        'LAST_UPDATE_DATE', 'INSTALL_DATE', 'MAX_ALLOWABLE_PRESSURE',
        'PPL_STATUS_CODE', 'DISTRICT_CODE', 'SDE_COMPLEX_ID',
        'BURIAL_DEPTH', 'RISER_LENGTH', 'RISER_DIAMETER',
        'PRODUCT_CODE', 'SHORE_CROSSING_FLAG', 'MMS_REGION_CODE',
        'OPERATOR_NUMBER', 'SEGMENTS_WITHIN', 'SEGMENTS_TOTAL',
        'CATHODIC_PROTECTION', 'WALL_THICKNESS', 'EXTERNAL_COATING',
        'INTERNAL_LINING', 'LEAK_DETECTION', 'PIPE_MATERIAL',
        'ABANDONMENT_METHOD'
    ]
    df.columns = column_names
    original_rows = len(df)
    log_metric("pipeline_master", "original_rows", original_rows)
    
    # Strip whitespace
    ws_fixes = strip_all_strings(df)
    log_metric("pipeline_master", "whitespace_fixes", int(ws_fixes))
    print(f"  Fixed {ws_fixes:,} whitespace issues")
    
    # Replace empty strings
    empty_fixes = replace_empty_strings(df)
    log_metric("pipeline_master", "empty_string_fixes", int(empty_fixes))
    print(f"  Replaced {empty_fixes:,} empty strings with NaN")
    
    # Identify and drop 100% null columns
    null_pct = df.isnull().sum() / len(df)
    fully_null_cols = null_pct[null_pct >= 0.999].index.tolist()
    if fully_null_cols:
        df = df.drop(columns=fully_null_cols)
        log_metric("pipeline_master", "dropped_100pct_null_columns", fully_null_cols)
        print(f"  Dropped {len(fully_null_cols)} columns with 100% nulls: {fully_null_cols}")
    
    # Standardize dates (YYYYMMDD format)
    date_cols = ['ABAN_APPROVAL_DATE', 'ABAN_DATE', 'APPROVED_DATE', 'LAST_UPDATE_DATE', 'INSTALL_DATE']
    for col in date_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: parse_date_flexible(str(int(x))) if pd.notna(x) and isinstance(x, (int, float)) else parse_date_flexible(x)
            )
    print("  Standardized dates to ISO-8601")
    
    # Flag high-null rows
    null_per_row = df.isnull().sum(axis=1) / len(df.columns)
    high_null_rows = (null_per_row > 0.3).sum()
    log_metric("pipeline_master", "rows_over_30pct_null", int(high_null_rows))
    print(f"  Flagged {high_null_rows:,} rows with >30% nulls (kept for review)")
    
    # Quality
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = df.isnull().sum().sum()
    quality_score = round((1 - total_nulls / total_cells) * 100, 1)
    log_metric("pipeline_master", "quality_score", quality_score)
    log_metric("pipeline_master", "cleaned_rows", len(df))
    log_metric("pipeline_master", "cleaned_columns", len(df.columns))
    
    output_path = os.path.join(OUTPUT_DIR, "pipeline_master.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  Saved to {output_path} ({len(df):,} rows, {len(df.columns)} cols, quality={quality_score}%)")
    return df


# =============================================================================
# 1.7 PLATFORM MASTER (FIXED-WIDTH)
# =============================================================================
def clean_platform_master():
    """Parse and clean platmast.DAT (fixed-width)."""
    print("\n[7/9] Cleaning Platform Master (fixed-width)...")
    filepath = os.path.join(DATA_DIR, "platmast.DAT")
    
    # Field definitions from BSEE Platform Master spec
    # Line length is 97 chars. Parse based on observed data patterns:
    colspecs = [
        (0, 5),    # COMPLEX_ID
        (5, 6),    # CRANE_FLAG (Y/N)
        (6, 7),    # HELIDECK_FLAG (Y/N)
        (7, 8),    # LIVING_QUARTERS_FLAG (Y/N)
        (8, 9),    # PRODUCTION_FLAG (Y/N)
        (9, 13),   # DECK_COUNT
        (13, 14),  # NAVIGATIONAL_AID_FLAG
        (14, 15),  # MANNED_FLAG
        (15, 16),  # MANNED_24HR_FLAG
        (16, 17),  # PIPELINE_RISER_FLAG
        (17, 22),  # COMPANY_NUMBER
        (22, 23),  # BUS_ASC_FLAG (N/Y)
        (23, 24),  # FLARE_FLAG
        (24, 30),  # WATER_DEPTH
        (30, 41),  # INSTALL_DATE (DD-MON-YYYY)
        (41, 42),  # NORTH_SOUTH_CODE
        (42, 43),  # DISPLACEMENT_FLAG
        (43, 44),  # MAJOR_STRUCTURE_FLAG
        (44, 45),  # STRUCTURE_FLAG_1
        (45, 46),  # STRUCTURE_FLAG_2
        (46, 50),  # PERSONNEL_COUNT
        (50, 51),  # EAST_WEST_CODE_1
        (51, 52),  # EAST_WEST_CODE_2
        (52, 54),  # ADDITIONAL_FIELDS
        (54, 55),  # STATUS_FLAG
        (55, 57),  # STRUCTURE_COUNT
        (57, 58),  # ADDITIONAL_FLAG_1
        (58, 59),  # ADDITIONAL_FLAG_2
        (59, 60),  # ADDITIONAL_FLAG_3
        (60, 61),  # SPACE
        (61, 62),  # ADDITIONAL_FLAG_4
        (62, 63),  # ADDITIONAL_FLAG_5
        (63, 64),  # ADDITIONAL_FLAG_6
        (64, 68),  # REGION_CODE
        (68, 71),  # STRUCTURE_NUMBER
        (71, 73),  # DISTRICT_CODE
        (73, 74),  # PLAN_FLAG
        (74, 75),  # ADDITIONAL_FLAG_7
        (75, 76),  # ADDITIONAL_FLAG_8
        (76, 81),  # AREA_CODE
        (81, 87),  # BLOCK_NUMBER
        (87, 88),  # ADDITIONAL_FLAG_9
    ]
    
    # Read with simplified approach — treat as single text lines first
    with open(filepath, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    records = []
    for line in lines:
        line = line.rstrip('\r\n')
        if len(line) < 90:
            continue
        records.append({
            'COMPLEX_ID': line[0:8].strip(),
            'CRANE_FLAG': line[5:6].strip(),
            'HELIDECK_FLAG': line[6:7].strip(),
            'LIVING_QUARTERS_FLAG': line[7:8].strip(),
            'PRODUCTION_FLAG': line[8:9].strip(),
            'DECK_COUNT': line[9:13].strip(),
            'COMPANY_NUMBER': line[17:22].strip(),
            'WATER_DEPTH': line[24:30].strip(),
            'INSTALL_DATE': line[30:41].strip(),
            'PERSONNEL_COUNT': line[46:50].strip(),
            'AREA_CODE': line[76:81].strip() if len(line) > 81 else '',
            'BLOCK_NUMBER': line[81:87].strip() if len(line) > 87 else '',
            'RAW_LINE': line,
        })
    
    df = pd.DataFrame(records)
    original_rows = len(df)
    log_metric("platform_master", "original_rows", original_rows)
    
    # Standardize dates
    df['INSTALL_DATE'] = df['INSTALL_DATE'].apply(parse_date_flexible)
    
    # Convert numeric fields
    for col in ['DECK_COUNT', 'COMPANY_NUMBER', 'WATER_DEPTH', 'PERSONNEL_COUNT']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Replace empty strings
    empty_fixes = replace_empty_strings(df)
    
    # Quality
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = df.isnull().sum().sum()
    quality_score = round((1 - total_nulls / total_cells) * 100, 1)
    log_metric("platform_master", "quality_score", quality_score)
    log_metric("platform_master", "cleaned_rows", len(df))
    log_metric("platform_master", "format_converted", "fixed-width -> CSV")
    
    output_path = os.path.join(OUTPUT_DIR, "platform_master.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  Saved to {output_path} ({len(df):,} rows, quality={quality_score}%)")
    return df


# =============================================================================
# 1.8 PLATFORM STRUCTURE (FIXED-WIDTH)
# =============================================================================
def clean_platform_structure():
    """Parse and clean platstru.DAT (fixed-width)."""
    print("\n[8/9] Cleaning Platform Structure (fixed-width)...")
    filepath = os.path.join(DATA_DIR, "platstru.DAT")
    
    # From BSEE spec - 149 chars per line
    with open(filepath, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    records = []
    for line in lines:
        line = line.rstrip('\r\n')
        if len(line) < 140:
            continue
        records.append({
            'AREA_CODE': line[0:2].strip(),
            'BLOCK_NUMBER': line[2:8].strip(),
            'COMPLEX_ID': line[8:16].strip(),
            'DECK_COUNT': line[16:17].strip(),
            'EW_CODE': line[17:18].strip(),
            'INSTALL_DATE': line[18:29].strip(),
            'REMOVAL_DATE': line[29:40].strip(),
            'MAJOR_STRUCTURE_FLAG': line[40:41].strip(),
            'NS_CODE': line[41:42].strip(),
            'LAST_UPDATE_DATE': line[42:53].strip(),
            'SLOT_COUNT': line[53:58].strip(),
            'DRILL_SLOT_COUNT': line[58:63].strip(),
            'SATELLITE_COMPL_COUNT': line[63:66].strip(),
            'STRUCTURE_NAME': line[66:82].strip(),
            'STRUCTURE_NUMBER': line[82:83].strip(),
            'STRUCTURE_TYPE': line[83:89].strip(),
            'NS_DISTANCE': line[89:95].strip(),
            'EW_DISTANCE': line[95:101].strip(),
            'WATER_DEPTH': line[101:104].strip(),
            'LEASE_TYPE': line[104:120].strip(),
            'LEASE_NUMBER': line[120:128].strip(),
            'PLATFORM_NAME': line[128:149].strip(),
        })
    
    df = pd.DataFrame(records)
    original_rows = len(df)
    log_metric("platform_structure", "original_rows", original_rows)
    
    # Standardize dates (DD-MON-YYYY format)
    for col in ['INSTALL_DATE', 'REMOVAL_DATE', 'LAST_UPDATE_DATE']:
        df[col] = df[col].apply(parse_date_flexible)
    
    # Convert numeric fields
    for col in ['DECK_COUNT', 'SLOT_COUNT', 'DRILL_SLOT_COUNT', 'SATELLITE_COMPL_COUNT', 
                'NS_DISTANCE', 'EW_DISTANCE', 'WATER_DEPTH']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Replace empty strings
    empty_fixes = replace_empty_strings(df)
    
    # Quality
    total_cells = df.shape[0] * df.shape[1]
    total_nulls = df.isnull().sum().sum()
    quality_score = round((1 - total_nulls / total_cells) * 100, 1)
    log_metric("platform_structure", "quality_score", quality_score)
    log_metric("platform_structure", "cleaned_rows", len(df))
    log_metric("platform_structure", "format_converted", "fixed-width -> CSV")
    
    output_path = os.path.join(OUTPUT_DIR, "platform_structure.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"  Saved to {output_path} ({len(df):,} rows, quality={quality_score}%)")
    return df


# =============================================================================
# 1.9 eWELL APD RAW DATA (8 FILES)
# =============================================================================
def clean_ewell_apd():
    """Clean all eWell APD files."""
    print("\n[9/9] Cleaning eWell APD Raw Data (8 files)...")
    apd_dir = os.path.join(DATA_DIR, "eWellAPDRawData")
    apd_output = os.path.join(OUTPUT_DIR, "eWellAPDRawData")
    os.makedirs(apd_output, exist_ok=True)
    
    files = sorted(os.listdir(apd_dir))
    
    for filename in files:
        filepath = os.path.join(apd_dir, filename)
        if not os.path.isfile(filepath):
            continue
        
        dataset_name = f"ewell_{filename.replace('.txt', '')}"
        print(f"\n  Processing: {filename}")
        
        # Try UTF-8 first, fall back to latin-1
        try:
            df = pd.read_csv(filepath, low_memory=False)
            encoding_used = 'utf-8'
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='latin-1', low_memory=False)
            encoding_used = 'latin-1'
            log_metric(dataset_name, "encoding_fixed", "latin-1 -> UTF-8")
        
        original_rows = len(df)
        log_metric(dataset_name, "original_rows", original_rows)
        
        # Strip whitespace
        ws_fixes = strip_all_strings(df)
        log_metric(dataset_name, "whitespace_fixes", int(ws_fixes))
        if ws_fixes > 0:
            print(f"    Fixed {ws_fixes:,} whitespace issues")
        
        # Replace empty strings
        empty_fixes = replace_empty_strings(df)
        log_metric(dataset_name, "empty_string_fixes", int(empty_fixes))
        if empty_fixes > 0:
            print(f"    Replaced {empty_fixes:,} empty strings with NaN")
        
        # Remove duplicates
        dups = df.duplicated().sum()
        if dups > 0:
            df = df.drop_duplicates()
            log_metric(dataset_name, "duplicates_removed", int(dups))
            print(f"    Removed {dups:,} duplicate rows")
        
        # Standardize date columns if present
        date_cols = [col for col in df.columns if any(kw in col.upper() for kw in ['DATE', '_DT'])]
        for col in date_cols:
            df[col] = df[col].apply(parse_date_flexible)
        if date_cols:
            print(f"    Standardized {len(date_cols)} date columns")
        
        # Quality
        total_cells = df.shape[0] * df.shape[1]
        total_nulls = df.isnull().sum().sum()
        quality_score = round((1 - total_nulls / total_cells) * 100, 1) if total_cells > 0 else 100
        log_metric(dataset_name, "quality_score", quality_score)
        log_metric(dataset_name, "cleaned_rows", len(df))
        
        output_path = os.path.join(apd_output, filename.replace('.txt', '.csv'))
        df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"    Saved ({len(df):,} rows, quality={quality_score}%)")


# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main():
    print("=" * 80)
    print("SIIH2026 DATA CLEANING")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 80)
    
    # Run all cleaners
    clean_osha_incidents()
    clean_pipeline_events()
    clean_well_bore()
    clean_platform_approvals()
    clean_platform_removal()
    clean_pipeline_master()
    clean_platform_master()
    clean_platform_structure()
    clean_ewell_apd()
    
    # Save cleaning report
    report['_metadata'] = {
        'generated_at': datetime.now().isoformat(),
        'script': 'data_cleaning.py',
        'output_directory': OUTPUT_DIR,
        'total_datasets_cleaned': len([k for k in report.keys() if not k.startswith('_')]),
    }
    
    report_path = os.path.join(OUTPUT_DIR, "cleaning_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n{'=' * 80}")
    print("CLEANING COMPLETE")
    print(f"{'=' * 80}")
    print(f"\nCleaning report saved to: {report_path}")
    print(f"\nDataset Summary:")
    for name, metrics in report.items():
        if name.startswith('_'):
            continue
        orig = metrics.get('original_rows', '?')
        cleaned = metrics.get('cleaned_rows', '?')
        quality = metrics.get('quality_score', '?')
        print(f"  {name:<35} {orig:>8} -> {cleaned:>8} rows  quality={quality}%")


if __name__ == '__main__':
    main()
