#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test RTF with actual app function
"""
import sys
import os

# Set Flask to not auto-run
os.environ['FLASK_RUN_FROM_CLI'] = 'false'

# Import the parse function
sys.path.insert(0, '/Users/liyutong/Nutstore Files/我的坚果云/2026-2027春季学期课程文件/元分析/review searching/Literature-Screening-Tool')

# Import only what we need, not the whole app
from striprtf.striprtf import rtf_to_text
import pandas as pd
import re

# Copy the parse_rtf_file function directly
def parse_rtf_file(file_content):
    """Parse RTF file content and convert to DataFrame."""
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
                'Title': '',
                'Abstract': '',
                'Source title': '',
                'Authors': '',
                'Year': '',
                'DOI': '',
                'Keywords': '',
                'Type': '',
                'URL': '',
            }
            
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
                            record['Title'] = value
                        elif current_field == 'abstract':
                            record['Abstract'] = value
                        elif current_field == 'journal':
                            record['Source title'] = value
                        elif current_field == 'author':
                            if record['Authors']:
                                record['Authors'] += '; ' + value
                            else:
                                record['Authors'] = value
                        elif current_field == 'year':
                            record['Year'] = value
                        elif current_field == 'doi':
                            record['DOI'] = value
                        elif current_field == 'keywords':
                            record['Keywords'] = value
                        elif current_field == 'url':
                            record['URL'] = value
                        elif current_field == 'type':
                            record['Type'] = value
                    
                    # Start new field
                    current_value = []
                    field_code = line[1:2].upper()
                    field_content = line[2:].strip()
                    
                    # Map EndNote field codes
                    field_map = {
                        'T': 'title',
                        'A': 'author',
                        'J': 'journal',
                        'D': 'year',
                        'K': 'keywords',
                        'X': 'abstract',
                        'N': 'abstract',
                        'U': 'url',
                        'R': 'doi',
                        '0': 'type',
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
                    record['Title'] = value
                elif current_field == 'abstract':
                    record['Abstract'] = value
                elif current_field == 'journal':
                    record['Source title'] = value
                elif current_field == 'author':
                    if record['Authors']:
                        record['Authors'] += '; ' + value
                    else:
                        record['Authors'] = value
                elif current_field == 'year':
                    record['Year'] = value
                elif current_field == 'doi':
                    record['DOI'] = value
                elif current_field == 'keywords':
                    record['Keywords'] = value
                elif current_field == 'url':
                    record['URL'] = value
                elif current_field == 'type':
                    record['Type'] = value
            
            # Only add if has at least a title
            if record['Title']:
                records.append(record)
        
        if not records:
            raise ValueError("Could not extract any bibliographic records from RTF file")
        
        df = pd.DataFrame(records)
        print(f"   RTF parser: Found {len(records)} entries, created DataFrame with {len(df)} rows", flush=True)
        return df
        
    except Exception as e:
        print(f"   RTF parser error: {str(e)}", flush=True)
        raise ValueError(f"Error parsing RTF file: {str(e)}")


if __name__ == "__main__":
    from pathlib import Path

    rtf_file = Path(__file__).resolve().parents[1] / "data" / "test_data.rtf"
    with rtf_file.open("rb") as f:
        content = f.read()

    df = parse_rtf_file(content)
    print("\nSUCCESS!")
    print(f"Parsed {len(df)} records")
    print("\nDataFrame:")
    print(df[['Title', 'Year', 'Authors', 'Source title']])
