#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Literature Screening Web App - Flask Backend v1.2
文献筛选网页应用 - Flask 后端 v1.2

Version 1.2: Added MiniMax-M2 model support with multi-model selection
"""

from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import io
import zipfile
import threading
import uuid
import time
from datetime import datetime
import rispy
import xlwt
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from striprtf.striprtf import rtf_to_text
import re

from ai_models import (
    DEFAULT_AI_MODEL,
    create_deepseek_completion,
    normalize_ai_model,
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Version
VERSION = "1.2.3"

# Default blacklists
DEFAULT_TITLE_ABSTRACT_BLACKLIST = [
    "surgical", "surgery", "patient", "patients", "clinical trial",
    "hospital", "physician", "nurse", "disease", "therapy",
    "diagnosis", "treatment", "medication", "drug", "pharmaceutical",
    "cancer", "tumor", "tumour", "athlete", "athletes", "sports",
    "game theory", "game-theoretic", "molecular", "molecule",
    "chemical", "chemistry", "physics", "quantum", "genome", "protein",
]

DEFAULT_JOURNAL_BLACKLIST = [
    "medicine", "medical", "clinical", "surgery", "surgical",
    "hospital", "health", "nursing", "pharmacy", "pharmacology",
    "chemistry", "chemical", "physics", "physical", "biology",
    "biological", "biochemistry", "sports", "sport", "athletic",
]

# Column mappings for different data sources (标准字段名: TI, AB, KW, PY, TY, LA, T2/J2, AU)
COLUMN_MAPPINGS = {
    # 标题 (Title)
    "title": ["Title", "title", "TI", "Article Title", "Document Title"],
    # 摘要 (Abstract)
    "abstract": ["Abstract", "abstract", "AB", "Description"],
    # 来源/期刊 (Source/Journal) - T2, J2
    "source": ["Source Title", "source title", "SO", "Source", "Journal",
               "Publication Name", "Publication", "Journal Title", "T2", "J2", "Journal Name"],
    # 关键词 (Keywords) - KW
    "keywords": ["Keywords", "keywords", "KW", "Keyword", "Key Words"],
    # 年份 (Year) - PY
    "year": ["Year", "year", "PY", "Publication Year", "Published", "DP"],
    # 类型 (Type) - TY, M3
    "type": ["Type", "type", "TY", "M3", "Document Type", "Content Type"],
    # 语言 (Language) - LA
    "language": ["Language", "language", "LA", "Languages"],
    # 作者 (Author) - AU
    "author": ["Authors", "authors", "AU", "Author", "Creator"],
    # DOI
    "doi": ["DOI", "doi", "Digital Object Identifier"],
    # URL
    "url": ["URL", "url", "Link"],
}

# Global storage for tasks
tasks = {}

def find_column(df, column_type):
    """Find the actual column name in the dataframe based on mappings."""
    possible_names = COLUMN_MAPPINGS.get(column_type, [])
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def contains_blacklisted_keyword(text, blacklist):
    """Check if text contains any blacklisted keyword."""
    if pd.isna(text) or not isinstance(text, str):
        return False, ""
    text_lower = text.lower()
    for keyword in blacklist:
        if keyword.lower().strip() in text_lower:
            return True, keyword
    return False, ""


def update_time_estimate(task_id, total_items, stage='Keyword'):
    """更新处理速度和剩余时间估算"""
    import time as time_module
    start_time = tasks[task_id].get('start_time')
    if not start_time:
        return

    current_time = time_module.time()
    elapsed = current_time - start_time
    processed = tasks[task_id].get('screening_log_count', 0)

    if processed > 0:
        # 计算处理速度（条/秒）
        speed = processed / elapsed
        tasks[task_id]['speed'] = speed

        # 估算剩余时间
        remaining = total_items - processed
        if remaining > 0 and speed > 0:
            remaining_seconds = remaining / speed
            # 格式化剩余时间
            if remaining_seconds < 60:
                remaining_str = f"{int(remaining_seconds)}秒"
            elif remaining_seconds < 3600:
                remaining_str = f"{int(remaining_seconds/60)}分钟"
            else:
                hours = int(remaining_seconds / 3600)
                mins = int((remaining_seconds % 3600) / 60)
                remaining_str = f"{hours}小时{mins}分钟"

            tasks[task_id]['message'] = f"{stage}筛选: 已处理 {processed}/{total_items}, 剩余约 {remaining_str}"


def remove_duplicates(df, title_col='Title', method='doi_title'):
    """
    Remove duplicate records from DataFrame.
    
    Args:
        df: DataFrame to deduplicate
        title_col: Name of the title column
        method: Deduplication method
            - 'doi': Remove duplicates based on DOI (if available)
            - 'title': Remove duplicates based on title similarity
            - 'doi_title': Try DOI first, then title (default)
    
    Returns:
        Tuple of (deduplicated_df, duplicate_info_dict)
    """
    original_count = len(df)
    df_clean = df.copy()
    
    # Track duplicates
    duplicates_removed = 0
    duplicate_details = []
    
    # Step 1: Remove DOI-based duplicates
    if 'DOI' in df_clean.columns and method in ['doi', 'doi_title']:
        # Only consider rows with non-empty DOI
        doi_mask = df_clean['DOI'].notna() & (df_clean['DOI'].astype(str).str.strip() != '')
        
        if doi_mask.any():
            # Mark duplicates based on DOI (keep first occurrence)
            df_clean['_temp_doi_dup'] = df_clean['DOI'].where(doi_mask)
            duplicated_doi = df_clean.duplicated(subset=['_temp_doi_dup'], keep='first')
            
            if duplicated_doi.any():
                dup_count = duplicated_doi.sum()
                duplicates_removed += dup_count
                duplicate_details.append(f"DOI-based: {dup_count} duplicates")
                df_clean = df_clean[~duplicated_doi]
            
            df_clean = df_clean.drop(columns=['_temp_doi_dup'])
    
    # Step 2: Remove title-based duplicates
    if title_col in df_clean.columns and method in ['title', 'doi_title']:
        # Normalize titles for comparison
        df_clean['_temp_title_norm'] = df_clean[title_col].astype(str).str.lower().str.strip()
        df_clean['_temp_title_norm'] = df_clean['_temp_title_norm'].str.replace(r'[^\w\s]', '', regex=True)
        df_clean['_temp_title_norm'] = df_clean['_temp_title_norm'].str.replace(r'\s+', ' ', regex=True)
        
        # Remove exact title duplicates (keep first)
        duplicated_title = df_clean.duplicated(subset=['_temp_title_norm'], keep='first')
        
        if duplicated_title.any():
            dup_count = duplicated_title.sum()
            duplicates_removed += dup_count
            duplicate_details.append(f"Title-based: {dup_count} duplicates")
            df_clean = df_clean[~duplicated_title]
        
        df_clean = df_clean.drop(columns=['_temp_title_norm'])
    
    # Reset index
    df_clean = df_clean.reset_index(drop=True)
    
    dedup_info = {
        'original_count': int(original_count),
        'duplicates_removed': int(duplicates_removed),
        'final_count': int(len(df_clean)),
        'details': duplicate_details,
        'method': method
    }
    
    return df_clean, dedup_info


def parse_ris_file(file_content):
    """Parse RIS file content and convert to DataFrame."""
    try:
        # RIS files are text-based
        # Try multiple encodings
        text_content = None
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                text_content = file_content.decode(encoding)
                break
            except:
                continue
        
        if text_content is None:
            raise ValueError("Could not decode file with any supported encoding")
        
        entries = rispy.loads(text_content)
        
        if not entries:
            raise ValueError("No RIS entries found in file")
        
        # Convert to DataFrame (标准字段名: TI, AB, KW, PY, TY, LA, T2/J2, AU)
        records = []
        for entry in entries:
            # 解析类型字段 (RIS: type_of_reference -> TY)
            ref_type = entry.get('type_of_reference', '')
            type_mapping = {
                'JOUR': 'Article',
                'BOOK': 'Book',
                'CHAP': 'Book Chapter',
                'CONF': 'Conference',
                'PAPR': 'Conference Paper',
                'THES': 'Thesis',
                'REPT': 'Report',
                'REV': 'Review',
                'ABST': 'Abstract',
                'GEN': 'Generic',
            }
            doc_type = type_mapping.get(ref_type, ref_type)

            record = {
                'TI': entry.get('title') or entry.get('primary_title', ''),
                'AB': entry.get('abstract', ''),
                'T2': entry.get('journal_name') or entry.get('secondary_title', ''),
                'AU': '; '.join(entry.get('authors', [])) if entry.get('authors') else '',
                'PY': str(entry.get('year', '')) if entry.get('year') else '',
                'DO': entry.get('doi', ''),
                'KW': '; '.join(entry.get('keywords', [])) if entry.get('keywords') else '',
                'TY': doc_type,
                'UR': entry.get('url', ''),
                'LA': entry.get('language', ''),
            }

            # 兼容旧字段名（用于前端显示）
            record['Title'] = record['TI']
            record['Abstract'] = record['AB']
            record['Source title'] = record['T2']
            record['Authors'] = record['AU']
            record['Year'] = record['PY']
            record['DOI'] = record['DO']
            record['Keywords'] = record['KW']
            record['Type'] = record['TY']
            record['URL'] = record['UR']

            records.append(record)
        
        df = pd.DataFrame(records)
        print(f"   RIS parser: Found {len(records)} entries, created DataFrame with {len(df)} rows", flush=True)
        return df
    except Exception as e:
        print(f"   RIS parser error: {str(e)}", flush=True)
        raise ValueError(f"Error parsing RIS file: {str(e)}")


def df_to_ris(df, title_col='Title', abstract_col='Abstract', source_col='Source title'):
    """Convert DataFrame to RIS format string."""
    ris_entries = []
    
    for idx, row in df.iterrows():
        entry = {
            'type_of_reference': 'JOUR',  # Journal Article
            'title': str(row.get(title_col, '')) if pd.notna(row.get(title_col)) else '',
            'abstract': str(row.get(abstract_col, '')) if pd.notna(row.get(abstract_col)) else '',
            'journal_name': str(row.get(source_col, '')) if pd.notna(row.get(source_col)) else '',
        }
        
        # Add optional fields if they exist
        if 'Authors' in row and pd.notna(row['Authors']):
            authors_str = str(row['Authors'])
            entry['authors'] = [a.strip() for a in authors_str.split(';') if a.strip()]
        
        if 'Year' in row and pd.notna(row['Year']):
            entry['year'] = str(row['Year'])
        
        if 'DOI' in row and pd.notna(row['DOI']):
            entry['doi'] = str(row['DOI'])
        
        if 'Keywords' in row and pd.notna(row['Keywords']):
            keywords_str = str(row['Keywords'])
            entry['keywords'] = [k.strip() for k in keywords_str.split(';') if k.strip()]
        
        if 'URL' in row and pd.notna(row['URL']):
            entry['url'] = str(row['URL'])
        
        ris_entries.append(entry)
    
    # Use rispy to dump to string
    ris_string = rispy.dumps(ris_entries)
    return ris_string


def parse_bibtex_file(file_content):
    """Parse BibTeX file content and convert to DataFrame."""
    try:
        text_content = file_content.decode('utf-8')
        bib_database = bibtexparser.loads(text_content)
        
        records = []
        for entry in bib_database.entries:
            # 解析类型字段 (BibTeX: entry type -> TY)
            entry_type = entry.get('ENTRYTYPE', '')
            type_mapping = {
                'article': 'Article',
                'book': 'Book',
                'inproceedings': 'Conference',
                'conference': 'Conference',
                'incollection': 'Book Chapter',
                'inbook': 'Book Chapter',
                'phdthesis': 'Thesis',
                'mastersthesis': 'Thesis',
                'techreport': 'Report',
                'misc': 'Generic',
            }
            doc_type = type_mapping.get(entry_type, entry_type)

            # 提取作者列表
            authors_str = entry.get('author', '').replace(' and ', '; ')
            # 提取年份
            year_val = entry.get('year', '')

            record = {
                'TI': entry.get('title', '').replace('{', '').replace('}', ''),
                'AB': entry.get('abstract', ''),
                'T2': entry.get('journal', '') or entry.get('booktitle', ''),
                'AU': authors_str,
                'PY': year_val,
                'DO': entry.get('doi', ''),
                'KW': entry.get('keywords', ''),
                'TY': doc_type,
                'UR': entry.get('url', ''),
                'LA': entry.get('language', ''),
            }

            # 兼容旧字段名（用于前端显示）
            record['Title'] = record['TI']
            record['Abstract'] = record['AB']
            record['Source title'] = record['T2']
            record['Authors'] = record['AU']
            record['Year'] = record['PY']
            record['DOI'] = record['DO']
            record['Keywords'] = record['KW']
            record['Type'] = record['TY']
            record['URL'] = record['UR']
            record['Publisher'] = entry.get('publisher', '')
            record['Volume'] = entry.get('volume', '')
            record['Pages'] = entry.get('pages', '')

            records.append(record)
        
        return pd.DataFrame(records)
    except Exception as e:
        raise ValueError(f"Error parsing BibTeX file: {str(e)}")


def df_to_bibtex(df, title_col='Title', abstract_col='Abstract', source_col='Source title'):
    """Convert DataFrame to BibTeX format string."""
    bib_db = BibDatabase()
    entries = []
    
    for idx, row in df.iterrows():
        # Generate citation key from author and year or use index
        year = str(row.get('Year', '')) if pd.notna(row.get('Year')) else ''
        authors = str(row.get('Authors', '')) if pd.notna(row.get('Authors')) else ''
        
        if authors and year:
            first_author = authors.split(';')[0].split(',')[0].strip().replace(' ', '')
            cite_key = f"{first_author}{year}"
        else:
            cite_key = f"ref{idx+1}"
        
        entry = {
            'ID': cite_key,
            'ENTRYTYPE': 'article',
            'title': str(row.get(title_col, '')) if pd.notna(row.get(title_col)) else '',
            'abstract': str(row.get(abstract_col, '')) if pd.notna(row.get(abstract_col)) else '',
            'journal': str(row.get(source_col, '')) if pd.notna(row.get(source_col)) else '',
        }
        
        # Add optional fields
        if 'Authors' in row and pd.notna(row['Authors']):
            entry['author'] = str(row['Authors']).replace(';', ' and')
        
        if 'Year' in row and pd.notna(row['Year']):
            entry['year'] = str(row['Year'])
        
        if 'DOI' in row and pd.notna(row['DOI']):
            entry['doi'] = str(row['DOI'])
        
        if 'Keywords' in row and pd.notna(row['Keywords']):
            entry['keywords'] = str(row['Keywords'])
        
        if 'URL' in row and pd.notna(row['URL']):
            entry['url'] = str(row['URL'])
        
        if 'Publisher' in row and pd.notna(row['Publisher']):
            entry['publisher'] = str(row['Publisher'])
        
        if 'Volume' in row and pd.notna(row['Volume']):
            entry['volume'] = str(row['Volume'])
        
        if 'Pages' in row and pd.notna(row['Pages']):
            entry['pages'] = str(row['Pages'])
        
        entries.append(entry)
    
    bib_db.entries = entries
    writer = BibTexWriter()
    writer.indent = '  '
    return writer.write(bib_db)


def parse_rtf_file(file_content):
    """
    Parse RTF file content and convert to DataFrame.
    
    RTF files from reference managers (like EndNote, Zotero) typically contain
    structured bibliographic data. This parser attempts to extract common fields
    like Title, Abstract, Authors, Journal, Year, etc.
    """
    try:
        # Decode RTF content
        text_content = None
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'windows-1252']:
            try:
                rtf_content = file_content.decode(encoding)
                # Convert RTF to plain text
                text_content = rtf_to_text(rtf_content)
                break
            except:
                continue
        
        if text_content is None:
            raise ValueError("Could not decode RTF file with any supported encoding")
        
        records = []
        
        # Try EndNote-style format (e.g., "%T Title\n%A Author\n%J Journal\n")
        # Split by double newlines to get individual entries
        entries = re.split(r'\n\s*\n+', text_content)
        
        for entry_text in entries:
            entry_text = entry_text.strip()
            if not entry_text or not entry_text.startswith('%'):
                continue
                
            record = {
                'TI': '',        # 标题 (Title)
                'AB': '',        # 摘要 (Abstract)
                'T2': '',        # 期刊 (Journal/Source)
                'AU': '',        # 作者 (Author)
                'PY': '',        # 年份 (Year)
                'DO': '',        # DOI
                'KW': '',        # 关键词 (Keywords)
                'TY': '',        # 类型 (Type)
                'UR': '',        # URL
                'LA': '',        # 语言 (Language)
            }

            # 兼容旧字段名（用于前端显示）
            record['Title'] = ''
            record['Abstract'] = ''
            record['Source title'] = ''
            record['Authors'] = ''
            record['Year'] = ''
            record['DOI'] = ''
            record['Keywords'] = ''
            record['Type'] = ''
            record['URL'] = ''
            
            # Parse EndNote field codes
            lines = entry_text.split('\n')
            current_field = None
            current_value = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line starts with a field code
                if line.startswith('%'):
                    # Save previous field
                    if current_field and current_value:
                        value = ' '.join(current_value).strip()
                        if current_field == 'title':
                            record['TI'] = value
                            record['Title'] = value
                        elif current_field == 'abstract':
                            record['AB'] = value
                            record['Abstract'] = value
                        elif current_field == 'journal':
                            record['T2'] = value
                            record['Source title'] = value
                        elif current_field == 'author':
                            if record['AU']:
                                record['AU'] += '; ' + value
                            else:
                                record['AU'] = value
                            if record['Authors']:
                                record['Authors'] += '; ' + value
                            else:
                                record['Authors'] = value
                        elif current_field == 'year':
                            record['PY'] = value
                            record['Year'] = value
                        elif current_field == 'doi':
                            record['DO'] = value
                            record['DOI'] = value
                        elif current_field == 'keywords':
                            record['KW'] = value
                            record['Keywords'] = value
                        elif current_field == 'url':
                            record['UR'] = value
                            record['URL'] = value
                        elif current_field == 'type':
                            record['TY'] = value
                            record['Type'] = value
                        elif current_field == 'language':
                            record['LA'] = value
                    
                    # Start new field
                    current_value = []
                    field_code = line[1:2].upper()
                    field_content = line[2:].strip()
                    
                    # Map EndNote field codes (标准字段名: TI, AB, KW, PY, TY, LA, T2/J2, AU)
                    field_map = {
                        'T': 'title',        # TI - Title
                        'A': 'author',       # AU - Author
                        'J': 'journal',      # T2/J2 - Journal
                        'D': 'year',         # PY - Year
                        'K': 'keywords',     # KW - Keywords
                        'X': 'abstract',     # AB - Abstract
                        'N': 'abstract',     # AB - Abstract
                        'U': 'url',          # UR - URL
                        'R': 'doi',          # DO - DOI
                        '0': 'type',         # TY - Type
                        'L': 'language',     # LA - Language
                    }
                    
                    current_field = field_map.get(field_code)
                    if field_content:
                        current_value.append(field_content)
                else:
                    # Continuation of previous field
                    if current_field:
                        current_value.append(line)
            
            # Save last field
            if current_field and current_value:
                value = ' '.join(current_value).strip()
                if current_field == 'title':
                    record['TI'] = value
                    record['Title'] = value
                elif current_field == 'abstract':
                    record['AB'] = value
                    record['Abstract'] = value
                elif current_field == 'journal':
                    record['T2'] = value
                    record['Source title'] = value
                elif current_field == 'author':
                    if record['AU']:
                        record['AU'] += '; ' + value
                    else:
                        record['AU'] = value
                    if record['Authors']:
                        record['Authors'] += '; ' + value
                    else:
                        record['Authors'] = value
                elif current_field == 'year':
                    record['PY'] = value
                    record['Year'] = value
                elif current_field == 'doi':
                    record['DO'] = value
                    record['DOI'] = value
                elif current_field == 'keywords':
                    record['KW'] = value
                    record['Keywords'] = value
                elif current_field == 'url':
                    record['UR'] = value
                    record['URL'] = value
                elif current_field == 'type':
                    record['TY'] = value
                    record['Type'] = value
                elif current_field == 'language':
                    record['LA'] = value
            
            # Only add if has at least a title
            if record['Title']:
                records.append(record)
        
        # If EndNote parsing didn't work, try alternative formats
        if not records:
            # Try to parse as simple paragraph-separated entries
            # Split by double newlines or numbered entries
            paragraphs = re.split(r'\n\s*\n+', text_content)
            
            for para in paragraphs:
                para = para.strip()
                if len(para) < 50:  # Skip very short paragraphs
                    continue
                
                # Try to extract structured info from paragraph
                lines = [l.strip() for l in para.split('\n') if l.strip()]
                
                if lines:
                    # Heuristic: First line is often the title
                    # Look for year patterns, journal names, etc.
                    record = {
                        'Title': lines[0] if lines else '',
                        'Abstract': '',
                        'Source title': '',
                        'Authors': '',
                        'Year': '',
                        'DOI': '',
                        'Keywords': '',
                        'Type': '',
                        'URL': '',
                    }
                    
                    # Try to extract year (4 digits)
                    year_match = re.search(r'\b(19|20)\d{2}\b', para)
                    if year_match:
                        record['Year'] = year_match.group(0)
                    
                    # Try to find DOI
                    doi_match = re.search(r'10\.\d{4,}/[^\s]+', para)
                    if doi_match:
                        record['DOI'] = doi_match.group(0)
                    
                    # If we have remaining lines, treat as abstract or metadata
                    if len(lines) > 1:
                        # Join remaining lines as potential abstract
                        remaining = ' '.join(lines[1:])
                        if len(remaining) > 100:
                            record['Abstract'] = remaining[:1000]  # Limit length
                    
                    records.append(record)
        
        if not records:
            raise ValueError("Could not extract any bibliographic records from RTF file. The file may not be in a supported format.")
        
        df = pd.DataFrame(records)
        print(f"   RTF parser: Found {len(records)} entries, created DataFrame with {len(df)} rows", flush=True)
        return df
        
    except Exception as e:
        print(f"   RTF parser error: {str(e)}", flush=True)
        raise ValueError(f"Error parsing RTF file: {str(e)}")


def screen_literature_task(task_id, df, title_abstract_keywords, journal_keywords, api_key=None, ai_criteria=None, remove_duplicates_flag=False, **kwargs):
    """Background task for screening literature."""
    try:
        import time as time_module
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['progress'] = 0
        tasks[task_id]['message'] = 'Initializing...'
        tasks[task_id]['start_time'] = time_module.time()  # 记录开始时间
        tasks[task_id]['processed_count'] = 0  # 已处理数量
        tasks[task_id]['speed'] = 0  # 处理速度（条/秒）

        original_total = len(df)
        
        # Find relevant columns
        title_col = find_column(df, "title")
        abstract_col = find_column(df, "abstract")
        source_col = find_column(df, "source")
        
        # --- Step 0: Remove duplicates if requested ---
        dedup_info = None
        if remove_duplicates_flag:
            tasks[task_id]['message'] = 'Removing duplicates...'
            df, dedup_info = remove_duplicates(df, title_col=title_col or 'Title', method='doi_title')
            print(f"🔄 Deduplication: {dedup_info['duplicates_removed']} duplicates removed ({dedup_info['original_count']} → {dedup_info['final_count']})", flush=True)
        
        # Parse keywords
        ta_blacklist = [k.strip() for k in title_abstract_keywords.split('\n') if k.strip()]
        j_blacklist = [k.strip() for k in journal_keywords.split('\n') if k.strip()]
        
        # Initialize tracking columns
        df['_EXCLUDED'] = False
        df['_EXCLUSION_REASON'] = ''
        
        stats = {
            'original_total': int(original_total),
            'total': int(len(df)),
            'title_col': title_col,
            'abstract_col': abstract_col,
            'source_col': source_col,
            'title_abstract_excluded': 0,
            'journal_excluded': 0,
            'ai_excluded': 0,
            'deduplication': dedup_info
        }
        
        tasks[task_id]['message'] = 'Keyword Screening...'

        # 记录关键词筛选开始时间
        keyword_start_time = time_module.time()
        keyword_processed = 0
        total_for_keyword = len(df)

        # Helper function to add log entry
        def add_screening_log(idx, row, title_col, status, reason=''):
            """Add a log entry for screening progress."""
            nonlocal keyword_processed
            # Get title for display (try multiple column names)
            title = ''
            if title_col and title_col in row:
                title = str(row.get(title_col, ''))[:100]
            elif 'TI' in row:
                title = str(row.get('TI', ''))[:100]
            elif 'Title' in row:
                title = str(row.get('Title', ''))[:100]

            log_entry = {
                'idx': int(idx),
                'title': title,
                'status': status,  # 'kept' or 'excluded'
                'reason': reason,
                'timestamp': None  # 可以后续添加时间戳
            }

            # Limit log size to last 500 entries
            log = tasks[task_id].get('screening_log', [])
            log.append(log_entry)
            if len(log) > 500:
                log = log[-500:]
            tasks[task_id]['screening_log'] = log
            tasks[task_id]['screening_log_count'] = tasks[task_id].get('screening_log_count', 0) + 1
            keyword_processed += 1

            # 更新关键词筛选进度和预估时间
            progress_pct = int((keyword_processed / total_for_keyword) * 100)
            tasks[task_id]['progress'] = progress_pct

            # 计算预估剩余时间（精确到秒）
            elapsed = time_module.time() - keyword_start_time
            if keyword_processed > 0 and elapsed > 0:
                speed = keyword_processed / elapsed
                tasks[task_id]['speed'] = speed
                remaining = total_for_keyword - keyword_processed
                if remaining > 0 and speed > 0:
                    remaining_seconds = remaining / speed
                    if remaining_seconds < 60:
                        remaining_str = f"{int(remaining_seconds)}秒"
                    elif remaining_seconds < 3600:
                        mins = int(remaining_seconds / 60)
                        secs = int(remaining_seconds % 60)
                        remaining_str = f"{mins}分{secs}秒"
                    else:
                        hours = int(remaining_seconds / 3600)
                        mins = int((remaining_seconds % 3600) / 60)
                        secs = int(remaining_seconds % 60)
                        remaining_str = f"{hours}小时{mins}分{secs}秒"
                    tasks[task_id]['message'] = f"关键词筛选: {keyword_processed}/{total_for_keyword}, 剩余约 {remaining_str}"

        # --- Step 1: Keyword Screening ---
        for idx, row in df.iterrows():
            exclusion_reasons = []

            # Check Title
            if title_col:
                is_excluded, keyword = contains_blacklisted_keyword(row[title_col], ta_blacklist)
                if is_excluded:
                    exclusion_reasons.append(f"Title: '{keyword}'")

            # Check Abstract
            if abstract_col:
                is_excluded, keyword = contains_blacklisted_keyword(row[abstract_col], ta_blacklist)
                if is_excluded:
                    exclusion_reasons.append(f"Abstract: '{keyword}'")

            if exclusion_reasons:
                stats['title_abstract_excluded'] += 1

            # Check Source/Journal
            if source_col:
                is_excluded, keyword = contains_blacklisted_keyword(row[source_col], j_blacklist)
                if is_excluded:
                    exclusion_reasons.append(f"Journal: '{keyword}'")
                    if len(exclusion_reasons) == 1:
                        stats['journal_excluded'] += 1

            if exclusion_reasons:
                df.at[idx, '_EXCLUDED'] = True
                df.at[idx, '_EXCLUSION_REASON'] = ' | '.join(exclusion_reasons)
                # 添加排除日志
                add_screening_log(idx, row, title_col, 'excluded', ' | '.join(exclusion_reasons))
            else:
                # 添加保留日志
                add_screening_log(idx, row, title_col, 'kept', 'Passed keyword screening')

        # 关键词筛选完成，重置AI筛选的计数
        tasks[task_id]['processed_count'] = 0
        tasks[task_id]['screening_log_count'] = 0  # 重置日志计数，使前端显示从0开始

        # --- Step 2: AI Screening (Optional) ---
        if api_key and ai_criteria:
            try:
                import json
                import httpx
                
                tasks[task_id]['message'] = 'Connecting to AI...'
                
                # Determine which AI model to use
                ai_model = normalize_ai_model(kwargs.get('ai_model'))
                
                if ai_model == 'minimax':
                    # Use MiniMax-M2 with Anthropic SDK
                    import anthropic
                    import os
                    
                    # Set base URL for MiniMax
                    os.environ['ANTHROPIC_BASE_URL'] = 'https://api.minimaxi.com/anthropic'
                    os.environ['ANTHROPIC_API_KEY'] = api_key
                    
                    client = anthropic.Anthropic(
                        timeout=httpx.Timeout(60.0, connect=10.0)  # 60s total, 10s connect
                    )
                    model_name = "MiniMax-M2.1"
                    print(f"🤖 Using MiniMax-M2.1 model via Anthropic SDK", flush=True)
                else:
                    # Use DeepSeek with OpenAI SDK (default)
                    from openai import OpenAI
                    import httpx
                    
                    client = OpenAI(
                        api_key=api_key, 
                        base_url="https://api.deepseek.com",
                        timeout=httpx.Timeout(60.0, connect=10.0)  # 60s total, 10s connect
                    )
                    model_name = ai_model
                    print(f"🤖 Using DeepSeek model: {model_name}", flush=True)
                
                # Only screen papers that passed the keyword filter
                candidates = df[df['_EXCLUDED'] == False]
                total_candidates = len(candidates)
                
                print(f"🤖 Starting AI Screening for {total_candidates} papers...", flush=True)

                # AI 筛选开始时间
                ai_start_time = time_module.time()
                ai_processed = 0

                for i, (idx, row) in enumerate(candidates.iterrows()):
                    # Check if task was cancelled
                    if tasks[task_id].get('cancelled', False):
                        print(f"🛑 AI Screening cancelled at {i}/{total_candidates}", flush=True)
                        break
                    
                    # Update progress
                    progress_pct = int((i / total_candidates) * 100)
                    tasks[task_id]['progress'] = progress_pct

                    # 更新处理速度和剩余时间
                    ai_processed = i + 1
                    tasks[task_id]['processed_count'] = ai_processed

                    # 计算 AI 筛选的预估剩余时间
                    elapsed = time_module.time() - ai_start_time
                    if ai_processed > 0 and elapsed > 0:
                        speed = ai_processed / elapsed
                        tasks[task_id]['speed'] = speed
                        remaining = total_candidates - ai_processed
                        if remaining > 0 and speed > 0:
                            remaining_seconds = remaining / speed
                            if remaining_seconds < 60:
                                remaining_str = f"{int(remaining_seconds)}秒"
                            elif remaining_seconds < 3600:
                                mins = int(remaining_seconds / 60)
                                secs = int(remaining_seconds % 60)
                                remaining_str = f"{mins}分{secs}秒"
                            else:
                                hours = int(remaining_seconds / 3600)
                                mins = int((remaining_seconds % 3600) / 60)
                                secs = int(remaining_seconds % 60)
                                remaining_str = f"{hours}小时{mins}分{secs}秒"
                            tasks[task_id]['message'] = f"AI筛选: {ai_processed}/{total_candidates}, 剩余约 {remaining_str}"
                    
                    title = row[title_col] if title_col else "N/A"
                    abstract = row[abstract_col] if abstract_col else "N/A"
                    
                    prompt = f"""Screen this paper against exclusion criteria. Return JSON only.

EXCLUSION CRITERIA:
{ai_criteria}

PAPER:
Title: {title}
Abstract: {abstract}

RULES:
- If paper matches exclusion criteria → exclude=true
- If uncertain → exclude=true (be strict)
- Reason must be ≤12 words

JSON format:
{{"exclude": true/false, "reason": "brief reason"}}"""
                    
                    try:
                        if ai_model == 'minimax':
                            # MiniMax-M2 API call with retry mechanism
                            max_retries = 3
                            result = None
                            
                            for attempt in range(max_retries):
                                try:
                                    response = client.messages.create(
                                        model="MiniMax-M2.1",
                                        max_tokens=2000,  # Increased to prevent thinking truncation
                                        system="You are a paper screening assistant. Output ONLY valid JSON: {\"exclude\": true/false, \"reason\": \"text\"}. Be concise.",
                                        messages=[
                                            {
                                                "role": "user",
                                                "content": [
                                                    {
                                                        "type": "text",
                                                        "text": prompt
                                                    }
                                                ]
                                            }
                                        ]
                                    )
                                except (httpx.TimeoutException, httpx.ConnectTimeout) as te:
                                    if attempt < max_retries - 1:
                                        import time
                                        wait_time = (attempt + 1) * 5
                                        print(f"   ⚠️ Timeout (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...", flush=True)
                                        time.sleep(wait_time)
                                        continue
                                    else:
                                        raise te
                                
                                # Extract text from response blocks (skip 'thinking' blocks)
                                result_text = ""
                                for block in response.content:
                                    if block.type == "text":
                                        result_text += block.text
                                
                                # If we got text content, parse it and break
                                if result_text.strip():
                                    try:
                                        result = json.loads(result_text)
                                        break
                                    except json.JSONDecodeError as je:
                                        if attempt < max_retries - 1:
                                            print(f"   ⚠️ JSON parse error (attempt {attempt+1}/{max_retries}), retrying...", flush=True)
                                            continue
                                        else:
                                            raise je
                                elif attempt < max_retries - 1:
                                    print(f"   ⚠️ Empty response (attempt {attempt+1}/{max_retries}), retrying...", flush=True)
                                    continue
                            
                            # If still no result after retries, raise error
                            if result is None:
                                raise ValueError("MiniMax-M2.1 failed to return valid response after retries")
                            
                            # Now we have a valid result
                        else:
                            # DeepSeek API call with OpenAI SDK + retry
                            max_retries = 3
                            result = None
                            
                            for attempt in range(max_retries):
                                try:
                                    response = create_deepseek_completion(
                                        client,
                                        ai_model,
                                        prompt,
                                    )
                                    
                                    result = json.loads(response.choices[0].message.content)
                                    break
                                except (httpx.TimeoutException, httpx.ConnectTimeout) as te:
                                    if attempt < max_retries - 1:
                                        import time
                                        wait_time = (attempt + 1) * 5  # 5s, 10s backoff
                                        print(f"   ⚠️ Timeout (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...", flush=True)
                                        time.sleep(wait_time)
                                        continue
                                    else:
                                        raise te
                                except json.JSONDecodeError as je:
                                    if attempt < max_retries - 1:
                                        print(f"   ⚠️ JSON parse error (attempt {attempt+1}/{max_retries}), retrying...", flush=True)
                                        continue
                                    else:
                                        raise je
                            
                            if result is None:
                                raise ValueError("DeepSeek failed to return valid response after retries")
                        
                        if result.get('exclude', False):
                            df.at[idx, '_EXCLUDED'] = True
                            df.at[idx, '_EXCLUSION_REASON'] = f"AI: {result.get('reason', 'Criteria matched')}"
                            stats['ai_excluded'] += 1
                            print(f"   ❌ Excluded: {result.get('reason', 'Criteria matched')}", flush=True)
                            # 添加 AI 排除日志
                            add_screening_log(idx, row, title_col, 'excluded', f"AI: {result.get('reason', 'Criteria matched')}")
                        else:
                            print(f"   ✅ Kept: {result.get('reason', 'Passed screening')}", flush=True)
                            # 添加 AI 保留日志
                            add_screening_log(idx, row, title_col, 'kept', f"AI: {result.get('reason', 'Passed')}")
                            
                    except Exception as e:
                        print(f"   ⚠️ AI Error for row {idx}: {e}", flush=True)
                        continue
                
                print("🤖 AI Screening Completed.", flush=True)
                        
            except Exception as e:
                print(f"❌ AI Setup Error: {e}", flush=True)
                # Continue without AI if it fails, or maybe we should fail? 
                # For now, let's just log it and finish.

        # Split dataframes
        df_kept = df[df['_EXCLUDED'] == False].drop(columns=['_EXCLUDED', '_EXCLUSION_REASON'])
        df_removed = df[df['_EXCLUDED'] == True].copy()
        df_removed = df_removed.rename(columns={'_EXCLUSION_REASON': 'Exclusion_Reason'})
        df_removed = df_removed.drop(columns=['_EXCLUDED'])
        
        stats['kept'] = len(df_kept)
        stats['excluded'] = len(df_removed)
        
        # Store dataframes directly for later format conversion
        tasks[task_id]['result'] = {
            'stats': stats,
            'df_kept': df_kept,
            'df_removed': df_removed,
            'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
            'title_col': title_col,
            'abstract_col': abstract_col,
            'source_col': source_col
        }
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['message'] = 'Completed!'
        
    except Exception as e:
        print(f"❌ Task Error: {e}", flush=True)
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['error'] = str(e)


@app.route('/')
def index():
    """Serve the main page."""
    response = app.make_response(render_template('index.html',
                         default_ta='\n'.join(DEFAULT_TITLE_ABSTRACT_BLACKLIST),
                         default_journal='\n'.join(DEFAULT_JOURNAL_BLACKLIST)))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/screen', methods=['POST'])
def screen():
    """Start the screening process."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        files = request.files.getlist('file')
        if not files or files[0].filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get keywords from form
        ta_keywords = request.form.get('ta_keywords', '')
        journal_keywords = request.form.get('journal_keywords', '')
        api_key = request.form.get('api_key', '').strip()
        ai_criteria = request.form.get('ai_criteria', '').strip()
        ai_model = normalize_ai_model(
            request.form.get('ai_model', DEFAULT_AI_MODEL).strip()
        )
        
        # Read and merge files
        dfs = []
        
        # WoS to Standard Field Mapping (标准字段名: TI, AB, KW, PY, TY, LA, T2/J2, AU)
        WOS_MAPPING = {
            'TI': 'TI',           # Title -> TI
            'AB': 'AB',           # Abstract -> AB
            'AU': 'AU',           # Authors -> AU
            'SO': 'T2',           # Source title -> T2
            'PY': 'PY',           # Year -> PY
            'DE': 'KW',           # Author Keywords -> KW
            'ID': 'KW',           # Keywords Plus -> KW (also merge with DE)
            'DI': 'DO',           # DOI -> DO
            'DT': 'TY',           # Document Type -> TY
            'CR': 'References',
            'C1': 'Affiliations',
            'TC': 'Cited by',
            'SN': 'ISSN',
            'EI': 'EISSN',
            'LA': 'LA',           # Language -> LA
            'J2': 'T2',           # Journal Name -> T2
            'T2': 'T2',           # Journal Name -> T2
        }

        for file in files:
            filename = file.filename.lower()
            try:
                if filename.endswith('.xlsx'):
                    df = pd.read_excel(file, engine='openpyxl')
                elif filename.endswith('.xls'):
                    df = pd.read_excel(file, engine='xlrd')
                elif filename.endswith('.ris'):
                    # RIS file support
                    content = file.read()
                    df = parse_ris_file(content)
                    print(f"   Parsed RIS file: {filename}, {len(df)} records", flush=True)
                elif filename.endswith('.bib'):
                    # BibTeX file support
                    content = file.read()
                    df = parse_bibtex_file(content)
                    print(f"   Parsed BibTeX file: {filename}, {len(df)} records", flush=True)
                elif filename.endswith('.rtf'):
                    # RTF file support
                    content = file.read()
                    df = parse_rtf_file(content)
                    print(f"   Parsed RTF file: {filename}, {len(df)} records", flush=True)
                elif filename.endswith('.csv') or filename.endswith('.txt'):
                    # WoS exports often come as tab-delimited .txt or .csv
                    content = file.read()
                    
                    # Auto-detect RIS format in TXT files
                    try:
                        # Try multiple encodings to decode
                        preview = None
                        for enc in ['utf-8-sig', 'utf-8', 'latin-1']:
                            try:
                                preview = content.decode(enc, errors='ignore')[:2000]
                                break
                            except:
                                continue
                        
                        if preview:
                            # Remove BOM and check for RIS markers
                            preview_clean = preview.lstrip('\ufeff').strip()
                            # Check for RIS format indicators
                            has_ris_start = preview_clean.startswith('TY  -') or preview_clean.startswith('TY -')
                            has_ris_markers = 'TY  -' in preview or 'ER  -' in preview
                            has_ris_fields = ('AB  -' in preview or 'TI  -' in preview) and 'ER  -' in preview
                            
                            print(f"   File format detection: has_ris_start={has_ris_start}, has_ris_markers={has_ris_markers}, has_ris_fields={has_ris_fields}", flush=True)
                            
                            if has_ris_start or has_ris_fields:
                                print(f"   ✓ Detected RIS format in {filename}, parsing as RIS...", flush=True)
                                df = parse_ris_file(content)
                                if df is not None and len(df) > 0:
                                    print(f"   ✓ Successfully parsed RIS file: {filename}, {len(df)} records", flush=True)
                                    dfs.append(df)
                                    continue
                                else:
                                    print(f"   ✗ RIS parsing returned empty, trying CSV...", flush=True)
                    except Exception as e:
                        print(f"   ✗ RIS detection/parsing failed: {str(e)[:100]}, trying CSV...", flush=True)
                    
                    # Try different parsing strategies
                    df = None
                    parse_error = None
                    best_df = None
                    best_score = 0
                    
                    # Strategy 1: Tab-delimited with error handling (for WoS/Scopus exports)
                    # Extended encoding list including Windows and Mac formats
                    encodings_to_try = [
                        'utf-8', 'utf-8-sig',  # Standard UTF-8
                        'latin-1', 'iso-8859-1',  # Western European
                        'cp1252', 'windows-1252',  # Windows Western
                        'gbk', 'gb18030',  # Chinese
                        'utf-16', 'utf-16-le', 'utf-16-be',  # UTF-16 variants
                        'ascii'  # Pure ASCII fallback
                    ]
                    
                    for encoding in encodings_to_try:
                        try:
                            test_df = pd.read_csv(
                                io.BytesIO(content), 
                                sep='\t', 
                                encoding=encoding,
                                on_bad_lines='skip',  # Skip problematic lines
                                engine='python',  # More flexible parser
                                quoting=3,  # QUOTE_NONE - don't interpret quotes
                                escapechar='\\',
                                encoding_errors='ignore'  # Ignore encoding errors
                            )
                            # Calculate score: prefer more columns and presence of known fields
                            score = len(test_df.columns)
                            if 'TI' in test_df.columns or 'Title' in test_df.columns:
                                score += 100
                            if 'AB' in test_df.columns or 'Abstract' in test_df.columns:
                                score += 50
                            if 'SO' in test_df.columns or 'Source title' in test_df.columns or 'Source Title' in test_df.columns:
                                score += 30
                            
                            print(f"   Tab-delimited ({encoding}): {len(test_df)} rows, {len(test_df.columns)} cols, score={score}", flush=True)
                            
                            if score > best_score and len(test_df.columns) > 2:
                                best_df = test_df
                                best_score = score
                                df = test_df
                        except Exception as e:
                            parse_error = str(e)
                            # Don't print every failure, only important ones
                            if 'utf-8' in encoding or 'latin' in encoding:
                                print(f"   Tab-delimited ({encoding}): Failed - {str(e)[:80]}", flush=True)
                            continue
                    
                    # Strategy 2: Comma-delimited fallback (only if tab-delimited didn't work well)
                    if best_score < 50:  # Only try comma if no good tab result
                        for encoding in encodings_to_try:
                            try:
                                test_df = pd.read_csv(
                                    io.BytesIO(content),
                                    encoding=encoding,
                                    on_bad_lines='skip',
                                    engine='python',
                                    encoding_errors='ignore'
                                )
                                # Calculate score
                                score = len(test_df.columns)
                                if 'TI' in test_df.columns or 'Title' in test_df.columns:
                                    score += 100
                                if 'AB' in test_df.columns or 'Abstract' in test_df.columns:
                                    score += 50
                                
                                print(f"   Comma-delimited ({encoding}): {len(test_df)} rows, {len(test_df.columns)} cols, score={score}", flush=True)
                                
                                if score > best_score and len(test_df.columns) > 2:
                                    best_df = test_df
                                    best_score = score
                                    df = test_df
                            except Exception as e:
                                parse_error = str(e)
                                continue
                    
                    # If still no good result, the file might have issues
                    if df is None or len(df) == 0 or len(df.columns) <= 1:
                        error_msg = f'无法正确解析文件: {file.filename}。'
                        if len(df.columns) <= 1:
                            # Show first few lines for debugging
                            try:
                                preview = content.decode('utf-8', errors='ignore')[:500]
                                error_msg += f'\n\n文件似乎不是标准的CSV/TXT格式（只检测到{len(df.columns)}列）。'
                                error_msg += f'\n\n💡 建议：'
                                error_msg += f'\n1. 如果是从Excel导出的，请直接上传.xlsx文件'
                                error_msg += f'\n2. 如果是WoS/Scopus导出，请确保选择"制表符分隔"格式'
                                error_msg += f'\n3. 检查文件是否包含完整的文献数据（标题、摘要等列）'
                                print(f"\n⚠️  File parsing issue for {file.filename}:", flush=True)
                                print(f"   Columns detected: {len(df.columns)}", flush=True)
                                print(f"   Rows: {len(df)}", flush=True)
                                print(f"   First column name: {df.columns[0] if len(df.columns) > 0 else 'N/A'}", flush=True)
                                print(f"   File preview: {preview[:200]}...", flush=True)
                            except:
                                pass
                        elif parse_error:
                            error_msg += f' (错误: {parse_error})'
                        return jsonify({'error': error_msg}), 400
                    
                    # Sanity check: warn if too many rows (likely parsing error)
                    if len(df) > 50000:
                        print(f"   ⚠️  WARNING: Parsed {len(df)} rows - this seems unusually large!", flush=True)
                        print(f"   File might be improperly formatted. Columns found: {list(df.columns[:10])}", flush=True)
                else:
                    return jsonify({'error': f'Unsupported file format: {file.filename}'}), 400
                
                # Standardize Columns
                # Check if it looks like WoS (has TI and SO)
                if 'TI' in df.columns and 'SO' in df.columns:
                    print(f"   Detected WoS format for {filename}, standardizing...", flush=True)
                    df = df.rename(columns=WOS_MAPPING)

                # Add standard field names if not exist (标准字段名: TI, AB, KW, PY, TY, LA, T2/J2, AU)
                # Map standard field names to legacy names for frontend compatibility
                standard_to_legacy = {
                    'TI': 'Title',
                    'AB': 'Abstract',
                    'AU': 'Authors',
                    'T2': 'Source title',
                    'PY': 'Year',
                    'KW': 'Keywords',
                    'DO': 'DOI',
                    'TY': 'Type',
                    'UR': 'URL',
                    'LA': 'Language',
                }

                for std_col, legacy_col in standard_to_legacy.items():
                    if std_col in df.columns and legacy_col not in df.columns:
                        df[legacy_col] = df[std_col]

                # Ensure essential columns exist (for compatibility)
                required_cols = ['Title', 'Abstract', 'Source title']
                for col in required_cols:
                    if col not in df.columns:
                        # Try case-insensitive match
                        found = False
                        for existing_col in df.columns:
                            if existing_col.lower() == col.lower():
                                df = df.rename(columns={existing_col: col})
                                found = True
                                break
                        if not found:
                            df[col] = '' # Create empty if missing

                # Also ensure standard columns exist if legacy columns present
                legacy_to_standard = {
                    'Title': 'TI',
                    'Abstract': 'AB',
                    'Authors': 'AU',
                    'Source title': 'T2',
                    'Year': 'PY',
                    'Keywords': 'KW',
                    'DOI': 'DO',
                    'Type': 'TY',
                    'URL': 'UR',
                    'Language': 'LA',
                }

                for legacy_col, std_col in legacy_to_standard.items():
                    if legacy_col in df.columns and std_col not in df.columns:
                        df[std_col] = df[legacy_col]
                
                dfs.append(df)
            except Exception as e:
                return jsonify({'error': f'Error reading file {file.filename}: {str(e)}'}), 400
        
        if not dfs:
            return jsonify({'error': 'No valid files processed'}), 400
            
        # Merge all dataframes
        df = pd.concat(dfs, ignore_index=True)
        print(f"Merged {len(dfs)} files. Total rows: {len(df)}", flush=True)
        
        # Get deduplication preference
        remove_duplicates_flag = request.form.get('remove_duplicates', 'false').lower() == 'true'
        
        # Create task
        task_id = str(uuid.uuid4())
        tasks[task_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Queued...',
            'result': None,
            'screening_log': [],  # 记录每条文献的处理情况
            'screening_log_count': 0  # 已处理数量，用于限制日志长度
        }
        
        # Start background thread
        thread = threading.Thread(target=screen_literature_task, 
                                args=(task_id, df, ta_keywords, journal_keywords, api_key, ai_criteria, remove_duplicates_flag),
                                kwargs={'ai_model': ai_model})
        thread.daemon = True
        thread.start()
        
        return jsonify({'task_id': task_id})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/status/<task_id>')
def task_status(task_id):
    """Check the status of a task."""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    response = {
        'status': task['status'],
        'progress': task.get('progress', 0),
        'message': task.get('message', ''),
    }

    # 添加筛选日志（只返回最近100条）
    if 'screening_log' in task:
        response['screening_log'] = task['screening_log'][-100:]
        response['screening_log_count'] = task.get('screening_log_count', 0)

    if task['status'] == 'completed':
        response['stats'] = task['result']['stats']
    elif task['status'] == 'error':
        response['error'] = task.get('error', 'Unknown error')
        
    return jsonify(response)


@app.route('/cancel/<task_id>', methods=['POST'])
def cancel_task(task_id):
    """Cancel a running task."""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    if task['status'] == 'processing':
        task['cancelled'] = True
        task['status'] = 'error'
        task['error'] = 'Task cancelled by user'
        print(f"🛑 Task {task_id} cancelled by user", flush=True)
        return jsonify({'status': 'cancelled'})
    
    return jsonify({'status': task['status']})


@app.route('/download/<task_id>/<dataset>/<format>')
def download(task_id, dataset, format):
    """Download the processed files in various formats.
    
    Args:
        task_id: The task identifier
        dataset: 'cleaned', 'removed', or 'both'
        format: 'csv', 'xlsx', 'xls', 'txt', or 'ris'
    """
    print(f"📥 Download request: task_id={task_id}, dataset={dataset}, format={format}", flush=True)
    
    task = tasks.get(task_id)
    if not task:
        print(f"❌ Task not found: {task_id}", flush=True)
        return "Task not found", 404
        
    if task['status'] != 'completed':
        print(f"❌ Task not completed: {task['status']}", flush=True)
        return "Result not ready", 404
    
    try:
        result = task['result']
        timestamp = result['timestamp']
        df_kept = result['df_kept']
        df_removed = result['df_removed']
        title_col = result.get('title_col', 'Title')
        abstract_col = result.get('abstract_col', 'Abstract')
        source_col = result.get('source_col', 'Source title')
        
        # Helper function to convert df to requested format
        def df_to_buffer(df, fmt, filename_base):
            buffer = io.BytesIO()
            
            if fmt == 'csv':
                csv_str = df.to_csv(index=False, encoding='utf-8')
                buffer.write(csv_str.encode('utf-8-sig'))
                mimetype = 'text/csv'
                filename = f'{filename_base}.csv'
                
            elif fmt == 'xlsx':
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                filename = f'{filename_base}.xlsx'
                
            elif fmt == 'xls':
                # Use xlwt for old Excel format
                with pd.ExcelWriter(buffer, engine='xlwt') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                mimetype = 'application/vnd.ms-excel'
                filename = f'{filename_base}.xls'
                
            elif fmt == 'txt':
                # Tab-separated text file
                txt_str = df.to_csv(index=False, sep='\t', encoding='utf-8')
                buffer.write(txt_str.encode('utf-8-sig'))
                mimetype = 'text/plain'
                filename = f'{filename_base}.txt'
                
            elif fmt == 'ris':
                ris_str = df_to_ris(df, title_col, abstract_col, source_col)
                buffer.write(ris_str.encode('utf-8'))
                mimetype = 'application/x-research-info-systems'
                filename = f'{filename_base}.ris'
                
            elif fmt == 'bib':
                bib_str = df_to_bibtex(df, title_col, abstract_col, source_col)
                buffer.write(bib_str.encode('utf-8'))
                mimetype = 'application/x-bibtex'
                filename = f'{filename_base}.bib'
                
            else:
                raise ValueError(f"Unsupported format: {fmt}")
            
            buffer.seek(0)
            return buffer, filename, mimetype
        
        # Single file download
        if dataset == 'cleaned':
            buffer, filename, mimetype = df_to_buffer(df_kept, format, f'cleaned_data_{timestamp}')
            print(f"   Preparing cleaned data: {filename}", flush=True)
            return send_file(buffer, as_attachment=True, download_name=filename, mimetype=mimetype)
        
        elif dataset == 'removed':
            buffer, filename, mimetype = df_to_buffer(df_removed, format, f'removed_data_{timestamp}')
            print(f"   Preparing removed data: {filename}", flush=True)
            return send_file(buffer, as_attachment=True, download_name=filename, mimetype=mimetype)
        
        # Download both as ZIP
        elif dataset == 'both':
            print(f"   Preparing ZIP file with format: {format}", flush=True)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add cleaned file
                buffer_clean, filename_clean, _ = df_to_buffer(df_kept, format, f'cleaned_data_{timestamp}')
                zf.writestr(filename_clean, buffer_clean.read())
                
                # Add removed file
                buffer_removed, filename_removed, _ = df_to_buffer(df_removed, format, f'removed_data_{timestamp}')
                zf.writestr(filename_removed, buffer_removed.read())
            
            zip_buffer.seek(0)
            return send_file(zip_buffer, as_attachment=True,
                            download_name=f'screening_results_{timestamp}.zip',
                            mimetype='application/zip')
        
        print(f"❌ Invalid dataset: {dataset}", flush=True)
        return "Invalid dataset type", 400
        
    except Exception as e:
        print(f"❌ Download Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Server Error: {str(e)}", 500


def find_available_port(start_port=5000, max_attempts=10):
    """找到可用的端口"""
    import socket
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return None

if __name__ == '__main__':
    import os
    
    # 尝试从环境变量获取端口，否则自动查找可用端口
    requested_port = int(os.environ.get('PORT', 5000))
    port = find_available_port(requested_port)
    
    if port is None:
        print("\n❌ 错误：无法找到可用端口")
        print("   请检查防火墙设置或关闭其他占用端口的程序")
        exit(1)
    
    if port != requested_port:
        print(f"\n⚠️  端口 {requested_port} 已被占用")
        print(f"   自动切换到端口 {port}")
        if requested_port == 5000:
            print("\n💡 提示：macOS 用户可以在 系统设置 → 通用 → 隔空播放接收器 中关闭AirPlay")
    
    print("\n" + "=" * 50)
    print("📚 Literature Screening Web App")
    print("=" * 50)
    print(f"\n🌐 Open your browser and go to: http://127.0.0.1:{port}")
    print("   Press Ctrl+C to stop the server\n")
    app.run(debug=False, host='0.0.0.0', port=port)
