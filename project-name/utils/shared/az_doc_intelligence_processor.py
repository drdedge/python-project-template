"""
Azure Document Intelligence Processor
=====================================

This module provides a high-level interface for extracting structured content from documents
using Azure Document Intelligence (formerly Form Recognizer). It processes PDF, DOCX, and other
document formats to extract tables, text, and metadata with confidence scoring.

Key Features:
------------
- Extracts tables from documents and saves them as CSV files
- Converts documents to Markdown format with preserved structure
- Provides page-by-page document splitting
- Tracks extraction confidence scores at document and page levels
- Creates detailed JSON logs for each processed document
- Supports batch processing of entire directories
- Generates Excel workbooks from extracted tables with consolidation

Main Components:
---------------
- DocIntelligence: Main processor class that handles document analysis
- Table extraction: Identifies and extracts tables with cell-level content
- Markdown generation: Converts documents to markdown with embedded tables
- Confidence tracking: Monitors AI extraction confidence for quality assurance
- Logging system: Creates comprehensive logs with processing metadata
- Excel consolidation: Creates Excel workbooks with individual and consolidated table views

Directory Structure:
------------------
output_dir/
├── csv/                    # Extracted tables as CSV files
├── md/                     # Full document markdown files
│   └── md_pages/          # Individual page markdown files
├── [doc_name]_tables.xlsx  # Excel workbook with all tables
└── [doc_name]_processing_log.json  # Processing logs for each document

Usage Examples:
--------------

1. Basic single document processing:
   ```python
   from utils.utils_docint import DocIntelligence
   
   # Initialize processor
   processor = DocIntelligence(
       endpoint="https://your-endpoint.cognitiveservices.azure.com/",
       key="your-api-key",
       output_dir="outputs"
   )
   
   # Process a single document
   results = processor.process_document("path/to/document.pdf")
   print(f"Extracted {len(results['csv_files'])} tables")
   print(f"Markdown saved to: {results['md_file']}")
   print(f"Excel workbook saved to: {results.get('excel_file', 'No tables found')}")
   ```

2. Batch processing a directory:
   ```python
   # Process all PDFs in a directory
   results = processor.process_directory(
       input_dir="path/to/documents",
       output_dir="outputs",
       file_types=["pdf"]
   )
   
   # Check results
   for doc_path, result in results.items():
       if 'error' not in result:
           print(f"{doc_path}: {len(result['csv_files'])} tables extracted")
   ```


Note: This module requires valid Azure Document Intelligence credentials.

"""

import os
import csv
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd


from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat


class DocIntelligence:
    """Azure Document Intelligence processor for extracting content from documents."""
    
import os
import csv
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat


class DocIntelligence:
    """Azure Document Intelligence processor for extracting content from documents."""
    
    def __init__(self, endpoint: str, key: str, output_dir: str = "doc_int_outputs", 
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the Document Intelligence processor.

        Args:
            endpoint: Azure Document Intelligence endpoint URL
            key: Azure API key
            output_dir: Base directory for outputs
            logger: Optional logger instance. If not provided, creates a default logger.
        """
        # Set up logging
        if logger:
            self.logger = logger
        else:
            # Create a default logger
            self.logger = logging.getLogger(__name__)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)
        
        # Create directory structure
        self.paths = self._create_output_dirs(output_dir, ["csv", "md", "md/md_pages"])
        
        # Initialize Azure client
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint, 
            credential=AzureKeyCredential(key)
        )
        
        # Initialize state
        self.table_index_tracker = {"index": 0}
        self.markdown_tables = []

    def _create_output_dirs(self, base_dir: str, subdirs: List[str]) -> Dict[str, str]:
        """
        Create output directory structure.
        
        Args:
            base_dir: Base output directory
            subdirs: List of subdirectories to create
            
        Returns:
            Dictionary mapping directory names to their full paths
        """
        paths = {}
        
        # Create base directory
        os.makedirs(base_dir, exist_ok=True)
        paths["base"] = base_dir
        
        # Create subdirectories
        for subdir in subdirs:
            full_path = os.path.join(base_dir, subdir)
            os.makedirs(full_path, exist_ok=True)
            paths[subdir] = full_path
            
        self.logger.info(f"Created output directory structure at: {base_dir}")
        return paths

    def calculate_confidence_statistics(self, result) -> Dict[str, Any]:
        """
        Extract and calculate word-level confidence statistics from the document analysis result.
        
        Returns:
            Dictionary containing confidence statistics at document and page level
        """
        all_confidence_scores = []
        page_confidences = {}
        
        # Extract confidence scores from words in pages
        if hasattr(result, 'pages') and result.pages:
            for page in result.pages:
                page_num = getattr(page, 'pageNumber', 1)
                
                if hasattr(page, 'words') and page.words:
                    page_scores = []
                    for word in page.words:
                        if hasattr(word, 'confidence') and word.confidence is not None:
                            confidence_value = float(word.confidence)
                            all_confidence_scores.append(confidence_value)
                            page_scores.append(confidence_value)
                    
                    if page_scores:
                        page_confidences[page_num] = page_scores
        
        # Calculate statistics
        stats = {
            "document_level": {},
            "page_level_summary": {},
            "low_confidence_pages": []
        }
        
        if all_confidence_scores:
            np_scores = np.array(all_confidence_scores)
            stats["document_level"] = {
                "mean": float(np.mean(np_scores)),
                "median": float(np.median(np_scores)),
                "std": float(np.std(np_scores)),
                "min": float(np.min(np_scores)),
                "max": float(np.max(np_scores)),
                "q1": float(np.percentile(np_scores, 25)),
                "q3": float(np.percentile(np_scores, 75)),
                "total_words": len(all_confidence_scores)
            }
            
            # Calculate page-level statistics
            page_averages = []
            for page_num, page_scores in sorted(page_confidences.items()):
                if page_scores:
                    avg_confidence = np.mean(page_scores)
                    page_averages.append(avg_confidence)
                    
                    # Track pages with average confidence below 0.85
                    if avg_confidence < 0.85:
                        stats["low_confidence_pages"].append({
                            "page": page_num,
                            "average_confidence": float(avg_confidence),
                            "min_confidence": float(np.min(page_scores)),
                            "max_confidence": float(np.max(page_scores)),
                            "word_count": len(page_scores),
                            "words_below_85": sum(1 for score in page_scores if score < 0.85)
                        })
            
            # Summary of page-level averages
            if page_averages:
                stats["page_level_summary"] = {
                    "total_pages": len(page_averages),
                    "mean_page_confidence": float(np.mean(page_averages)),
                    "min_page_confidence": float(np.min(page_averages)),
                    "max_page_confidence": float(np.max(page_averages)),
                    "pages_below_85": len(stats["low_confidence_pages"])
                }
        else:
            # No confidence scores found
            stats["document_level"] = {
                "mean": None,
                "median": None,
                "std": None,
                "min": None,
                "max": None,
                "q1": None,
                "q3": None,
                "total_words": 0
            }
            stats["page_level_summary"] = {
                "total_pages": 0,
                "mean_page_confidence": None,
                "min_page_confidence": None,
                "max_page_confidence": None,
                "pages_below_85": 0
            }
        
        return stats
    
    def save_raw_response(self, result, doc_name: str) -> str:
        """
        Save the raw Azure Document Intelligence response as text for debugging.
        
        Args:
            result: The raw result from Azure Document Intelligence
            doc_name: Base name of the document
            
        Returns:
            Path to the saved debug file
        """
        debug_filename = f"{doc_name}_raw_response_debug.txt"
        debug_path = os.path.join(os.path.dirname(self.paths["csv"]), debug_filename)  # Save in main output dir
        
        try:
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(f"Azure Document Intelligence Response Debug\n")
                f.write(f"Document: {doc_name}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write("="*80 + "\n\n")
                
                # Write object type
                f.write(f"Result object type: {type(result)}\n\n")
                
                # List all available attributes
                f.write("Available attributes:\n")
                attrs = [attr for attr in dir(result) if not attr.startswith('_')]
                for attr in attrs:
                    f.write(f"  - {attr}\n")
                f.write("\n" + "="*80 + "\n\n")
                
                # Try to write detailed content for each attribute
                for attr in attrs:
                    try:
                        f.write(f"\n{attr}:\n")
                        f.write("-"*40 + "\n")
                        value = getattr(result, attr)
                        
                        # Special handling for different types
                        if value is None:
                            f.write("None\n")
                        elif callable(value):
                            f.write(f"<method/function>\n")
                        elif isinstance(value, str):
                            f.write(f"{value}\n")
                        elif isinstance(value, (list, tuple)):
                            f.write(f"Type: {type(value).__name__}, Length: {len(value)}\n")
                            if len(value) > 0:
                                f.write(f"First item type: {type(value[0])}\n")
                                # For small lists, show content
                                if len(value) <= 5:
                                    for i, item in enumerate(value):
                                        f.write(f"  [{i}]: {str(item)[:200]}{'...' if len(str(item)) > 200 else ''}\n")
                        else:
                            # Use str() for other types, truncate if too long
                            str_value = str(value)
                            if len(str_value) > 1000:
                                f.write(f"{str_value[:1000]}...\n[Truncated - full length: {len(str_value)}]\n")
                            else:
                                f.write(f"{str_value}\n")
                    except Exception as e:
                        f.write(f"Error accessing attribute: {str(e)}\n")
                
                # If result has to_dict method, also save that
                if hasattr(result, 'to_dict'):
                    f.write("\n" + "="*80 + "\n")
                    f.write("\nFull to_dict() output:\n")
                    f.write("-"*40 + "\n")
                    try:
                        import json
                        dict_repr = result.to_dict()
                        f.write(json.dumps(dict_repr, indent=2, default=str))
                    except Exception as e:
                        f.write(f"Error converting to dict: {str(e)}\n")
            
            self.logger.info(f"Saved raw response debug to: {debug_path}")
            return debug_path
            
        except Exception as e:
            self.logger.error(f"Failed to save debug response: {str(e)}")
            return ""

    def save_table_to_csv(self, doc_name: str, file_extension: str, table: Dict, table_index: int) -> str:
        """
        Save a table to CSV format.

        Args:
            doc_name: Name of the document
            file_extension: File extension
            table: Table data dictionary
            table_index: Index of the table

        Returns:
            Path to saved CSV file
        """
        rows = table['rowCount']
        cols = table['columnCount']
        table_data = [["" for _ in range(cols)] for _ in range(rows)]

        for cell in table['cells']:
            r = cell['rowIndex']
            c = cell['columnIndex']
            content = cell.get('content', '')
            table_data[r][c] = content

        page_number = table.get('boundingRegions', [{}])[0].get('pageNumber', 1)
        filename = f"{doc_name}_{file_extension}_page{page_number}_table{table_index}.csv"
        csv_path = os.path.join(self.paths["csv"], filename)

        try:
            with open(csv_path, "w", newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(table_data)
            #self.logger.info(f"Saved table to {csv_path}")
        except Exception as e:
            self.logger.error(f"Failed to save table to CSV: {str(e)}")
            raise

        return csv_path

    def table_to_markdown(self, table: Dict) -> str:
        """Convert a table to Markdown format."""
        rows = table['rowCount']
        cols = table['columnCount']
        table_data = [["" for _ in range(cols)] for _ in range(rows)]
        headers_found = False

        for cell in table['cells']:
            r, c = cell['rowIndex'], cell['columnIndex']
            content = cell.get('content', '')
            table_data[r][c] = content
            if cell.get('kind') == 'columnHeader':
                headers_found = True

        markdown_lines = []
        if table.get('caption'):
            markdown_lines.append(f"**Table Caption:** {table['caption']}\n")

        header_row = table_data[0]
        markdown_lines.append("|" + "|".join(header_row) + "|")
        markdown_lines.append("|" + "|".join(["---"] * cols) + "|")

        start_row = 1 if headers_found and rows > 1 else (1 if rows > 1 else 0)
        for r in range(start_row, rows):
            markdown_lines.append("|" + "|".join(table_data[r]) + "|")

        return "\n".join(markdown_lines)

    def process_tables(self, result, doc_name: str, file_extension: str) -> tuple:
        """Process tables from analysis result."""
        csv_files = []
        csv_files_info = []  # New: store info for logging
        markdown_tables = []

        if not result.tables:
            self.logger.info("No tables detected in the document.")
            return csv_files, markdown_tables, csv_files_info

        for i, table in enumerate(result.tables):
            csv_path = self.save_table_to_csv(doc_name, file_extension, table, i)
            page_number = table.get('boundingRegions', [{}])[0].get('pageNumber', 1)
            
            #self.logger.info(f"Saved table {i} to {csv_path}")
            csv_files.append(csv_path)
            csv_files_info.append({
                "path": csv_path,
                "page_number": page_number,
                "table_index": i
            })
            markdown_tables.append(self.table_to_markdown(table))

        return csv_files, markdown_tables, csv_files_info

    def consolidate_tables_to_excel(self, json_log_path: str, excel_output_dir: str) -> Optional[str]:
        """
        Consolidate CSV tables from a processing log into a single Excel file with a consolidated view.
        
        Args:
            json_log_path: Path to the JSON log file
            excel_output_dir: Directory where the Excel file will be saved
            
        Returns:
            Path to the created Excel file or None if no tables
        """
        if not os.path.exists(json_log_path):
            if self.logger:
                self.logger.warning(f"JSON log file not found for Excel consolidation: {json_log_path}")
            return None
        
        try:
            # Read the JSON log file
            with open(json_log_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            # Extract CSV file information
            csv_files_info = log_data.get("outputs", {}).get("csv_files", [])
            
            if not csv_files_info:
                if self.logger:
                    self.logger.info("No CSV files found in log, skipping Excel creation")
                return None
            
            # Generate Excel filename from base_name
            base_name = log_data.get("input_file", {}).get("base_name", "consolidated_tables")
            excel_filename = f"{base_name}_tables.xlsx"
            excel_path = os.path.join(excel_output_dir, excel_filename)
            
            # First, collect all dataframes and find max columns
            all_tables = []
            max_cols = 0
            
            for csv_info in csv_files_info:
                csv_path = csv_info.get("path", "")
                if os.path.exists(csv_path):
                    try:
                        df = pd.read_csv(csv_path, encoding='utf-8')
                        if not df.empty:
                            max_cols = max(max_cols, len(df.columns))
                            all_tables.append({
                                'df': df,
                                'page_number': csv_info.get("page_number", 1),
                                'table_index': csv_info.get("table_index", 0),
                                'tab_name': f"page{csv_info.get('page_number', 1):02d}_table{csv_info.get('table_index', 0):02d}"
                            })
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"Failed to read CSV {csv_path}: {str(e)}")
            
            if not all_tables:
                if self.logger:
                    self.logger.warning("No valid tables found to consolidate")
                return None
            
            # Create Excel writer object
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                # First, create the consolidated sheet
                consolidated_rows = []
                
                for table_info in all_tables:
                    df = table_info['df']
                    tab_name = table_info['tab_name']
                    
                    # Ensure all tables have the same number of columns for consolidation
                    if len(df.columns) < max_cols:
                        # Add empty columns to match max_cols
                        for i in range(len(df.columns), max_cols):
                            df[f'_col_{i}'] = ''
                    
                    # Add header row with tab name
                    header_row = [tab_name] + [''] * (max_cols - 1)
                    consolidated_rows.append(header_row)
                    
                    # Add blank row
                    consolidated_rows.append([''] * max_cols)
                    
                    # Add table data
                    for _, row in df.iterrows():
                        consolidated_rows.append(row.tolist()[:max_cols])
                    
                    # Add blank row after table
                    consolidated_rows.append([''] * max_cols)
                
                # Create consolidated dataframe with generic column names
                col_names = [f'Column_{i+1}' for i in range(max_cols)]
                consolidated_df = pd.DataFrame(consolidated_rows, columns=col_names)
                
                # Write consolidated sheet first
                consolidated_df.to_excel(writer, sheet_name='consolidated', index=False)
                
                # Then write individual sheets
                for table_info in all_tables:
                    df = table_info['df']
                    tab_name = table_info['tab_name']
                    
                    # Remove any temporary columns we added
                    original_cols = [col for col in df.columns if not col.startswith('_col_')]
                    df = df[original_cols]
                    
                    # Write to individual sheet
                    sanitized_tab_name = self._sanitize_sheet_name(tab_name)
                    df.to_excel(writer, sheet_name=sanitized_tab_name, index=False)
                    
                    if self.logger:
                        self.logger.info(f"Added sheet '{sanitized_tab_name}'")
                
                # Get the workbook and ensure consolidated is first
                workbook = writer.book
                # Get all sheet names
                sheet_names = workbook.sheetnames
                
                # If consolidated is not first, move it
                if sheet_names[0] != 'consolidated':
                    # Find consolidated sheet
                    consolidated_idx = sheet_names.index('consolidated')
                    # Move it to the front
                    workbook.move_sheet('consolidated', offset=-(consolidated_idx))
                
                if self.logger:
                    self.logger.info("Created consolidated view of all tables")
            
            if self.logger:
                self.logger.info(f"Successfully created Excel file with consolidated sheet: {excel_path}")
            
            return excel_path
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create Excel file: {str(e)}")
            return None
    
    def _sanitize_sheet_name(self, name: str) -> str:
        """Sanitize sheet name for Excel compatibility."""
        # Remove or replace invalid characters
        invalid_chars = ['\\', '/', '*', '[', ']', ':', '?']
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # Truncate to 31 characters (Excel limit)
        if len(name) > 31:
            name = name[:31]
        
        # Ensure it's not empty
        if not name.strip():
            name = "Sheet1"
        
        return name

    def create_individual_log(self, document_path: str, doc_name: str, file_ext: str, 
                        results: Dict, csv_files_info: List[Dict], status: str = "success") -> str:
        """
        Create an individual JSON log file for the processed document.
        
        Args:
            document_path: Path to the input document
            doc_name: Base name of the document
            file_ext: File extension
            results: Processing results dictionary
            csv_files_info: List of CSV file information
            status: Processing status
            
        Returns:
            Path to the created log file
        """
        # Get file size
        file_size = os.path.getsize(document_path) if os.path.exists(document_path) else 0
        
        # Extract confidence stats from results
        confidence_stats = results.get("confidence_stats", {
            "document_level": {},
            "low_confidence_pages": []
        })
        
        # Create log structure
        log_data = {
            "input_file": {
                "path": document_path,
                "name": os.path.basename(document_path),
                "base_name": doc_name,
                "extension": file_ext,
                "status": status,
                "processed_timestamp": datetime.now().isoformat() + "Z"
            },
            "outputs": {
                "csv_files": csv_files_info,
                "markdown_files": {
                    "main_document": results.get("md_file", ""),
                    "pages": results.get("md_pages", [])
                },
                "excel_file": results.get("excel_file", "")
            },
            "statistics": {
                "total_pages": len(results.get("md_pages", [])),
                "total_csv_files": len(csv_files_info),
                "total_md_pages": len(results.get("md_pages", [])),
                "extraction_confidence": confidence_stats
            }
        }
        
        # Save log file
        log_filename = f"{doc_name}_processing_log.json"
        log_path = os.path.join(os.path.dirname(self.paths["csv"]), log_filename)
        
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2)
            self.logger.info(f"Created individual log file: {log_path}")
        except Exception as e:
            self.logger.error(f"Failed to create individual log file: {str(e)}")
            
        return log_path

    def process_document(self, document_path: str) -> Dict:
        """Process a single document."""
        if not os.path.exists(document_path):
            raise FileNotFoundError(f"The file {document_path} does not exist.")
        
        self.logger.info(f"Processing file: {document_path}")
        base_name = os.path.basename(document_path)
        doc_name, file_ext = os.path.splitext(base_name)
        file_ext = file_ext.strip('.').lower() if file_ext else "pdf"
                                   
        try:
            with open(document_path, "rb") as doc_file:
                poller = self.client.begin_analyze_document(
                    "prebuilt-layout",
                    body=AnalyzeDocumentRequest(bytes_source=doc_file.read()),
                    output_content_format=DocumentContentFormat.MARKDOWN
                )

                self.logger.info("Waiting for analysis result...")
                result = poller.result()
                
                return self._process_results(result, doc_name, file_ext, document_path)
        except Exception as e:
            # Create error log
            error_results = {"csv_files": [], "md_file": "", "md_pages": [], "excel_file": ""}
            self.create_individual_log(document_path, doc_name, file_ext, error_results, [], "error")
            raise

    def _process_results(self, result, doc_name: str, file_ext: str, document_path: str) -> Dict:
        """Process analysis results and save outputs."""
        self.markdown_tables = []
        self.table_index_tracker["index"] = 0

        # Optional: Save raw response for debugging (comment out when not needed)
        # self.save_raw_response(result, doc_name)
        
        csv_files, self.markdown_tables, csv_files_info = self.process_tables(result, doc_name, file_ext)
        
        # Calculate confidence statistics from word-level data
        confidence_stats = self.calculate_confidence_statistics(result)
        
        # Log confidence summary
        if confidence_stats["document_level"].get("mean") is not None:
            self.logger.info(f"Document confidence - Mean: {confidence_stats['document_level']['mean']:.3f}, " +
                            f"Min: {confidence_stats['document_level']['min']:.3f}, " +
                            f"Pages below 0.85: {len(confidence_stats['low_confidence_pages'])}")
        
        # Replace table markers with markdown
        content = result.content
        table_pattern = re.compile(r"<table>.*?</table>", re.DOTALL)
        replaced_content = re.sub(
            table_pattern, 
            lambda m: self.markdown_tables[self.table_index_tracker["index"]],
            content
        )

        # Save main markdown file
        md_filename = f"{doc_name}.{file_ext}.md"
        md_path = os.path.join(self.paths["md"], md_filename)
        with open(md_path, "w", encoding='utf-8') as md_file:
            md_file.write(replaced_content)

        # Split into pages
        md_pages = self._split_into_pages(replaced_content, doc_name, file_ext)
        
        results = {
            "csv_files": csv_files,
            "md_file": md_path,
            "md_pages": md_pages,
            "confidence_stats": confidence_stats,  # Add confidence stats to results
            "excel_file": ""  # Will be populated if tables exist
        }
        
        # Create Excel consolidation if tables were extracted
        excel_path = ""
        if csv_files:
            # First create the log file
            log_path = self.create_individual_log(document_path, doc_name, file_ext, results, csv_files_info)
            
            # Then create Excel file
            excel_path = self.consolidate_tables_to_excel(log_path, os.path.dirname(self.paths["csv"]))
            if excel_path:
                results["excel_file"] = excel_path
                # Update the log with Excel file path
                self.create_individual_log(document_path, doc_name, file_ext, results, csv_files_info)
        else:
            # Create log even if no tables
            self.create_individual_log(document_path, doc_name, file_ext, results, csv_files_info)
        
        return results

    def _split_into_pages(self, content: str, doc_name: str, file_ext: str) -> List[str]:
        """Split content into separate page files."""
        pages = [p.strip() for p in content.split("<!-- PageBreak -->") if p.strip()]
        saved_files = []

        for i, page in enumerate(pages, start=1):
            page_filename = f"{doc_name}_{file_ext}_page{i}.md"
            output_path = os.path.join(self.paths["md/md_pages"], page_filename)
            with open(output_path, "w", encoding='utf-8') as f:
                f.write(page)
            saved_files.append(output_path)

        self.logger.info(f"Split into {len(saved_files)} markdown pages")
        return saved_files

    def process_directory(self, input_dir: str, output_dir: str, file_types: Optional[List[str]] = None) -> Dict:
        """
        Process all documents in a directory with specified output directory and file type filtering.
        
        Args:
            input_dir: Directory containing documents to process
            output_dir: Directory where outputs will be saved
            file_types: Optional list of file extensions to filter (e.g., ['.pdf', '.docx']). 
                    If None, processes all files.
        
        Returns:
            Dictionary containing processing results for each file
        """
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Reinitialize paths with new output directory
        self.paths = self.paths = self._create_output_dirs(
            output_dir, 
            ["csv", "md", "md/md_pages"]
        )
        
        # Validate input directory
        if not os.path.exists(input_dir):
            raise FileNotFoundError(f"Input directory {input_dir} does not exist.")
        
        # Get all files in directory
        all_files = [f for f in os.listdir(input_dir) 
                    if os.path.isfile(os.path.join(input_dir, f))]
        
        # Filter by file types if specified
        if file_types:
            # Normalize file types (ensure they start with '.')
            normalized_types = [ft if ft.startswith('.') else f'.{ft}' for ft in file_types]
            filtered_files = [f for f in all_files 
                            if any(f.lower().endswith(ft.lower()) for ft in normalized_types)]
            self.logger.info(f"Filtering for file types: {normalized_types}")
            self.logger.info(f"Found {len(filtered_files)} matching files out of {len(all_files)} total files")
        else:
            filtered_files = all_files
            self.logger.info(f"Processing all {len(filtered_files)} files (no file type filter applied)")
        
        if not filtered_files:
            self.logger.warning("No files found matching the criteria")
            return {}
        
        processed_files = {}
        
        for file in filtered_files:
            document_path = os.path.join(input_dir, file)
            try:
                self.logger.info(f"Processing file: {file}")
                processed_files[document_path] = self.process_document(document_path)
            except Exception as e:
                self.logger.error(f"Failed to process {file}: {str(e)}")
                processed_files[document_path] = {"error": str(e)}
        
        # Save processing results
        log_output_path = os.path.join(self.paths["md"], "log.json")
        with open(log_output_path, 'w', encoding='utf-8') as f:
            json.dump(processed_files, f, indent=4)
        
        self.logger.info(f"All files processed and logged to {log_output_path}")
        return processed_files