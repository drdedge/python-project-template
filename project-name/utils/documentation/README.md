# Project Utilities

This directory contains utility scripts to help manage and document Python projects. All scripts output to stdout by default but can save to files using the `-o` or `--output` option.

## Documentation Utilities

Located in `utils/documentation/`, these scripts help analyze and document your codebase:

### 1. Dead Code Detector (`dead_code_finder.py`)

Finds unused functions, classes, imports, and orphaned files in your codebase.

**Usage:**
```bash
python utils/documentation/dead_code_finder.py

# Output to file
python utils/documentation/dead_code_finder.py --output dead_code_report.txt

# JSON format
python utils/documentation/dead_code_finder.py --format json -o dead_code.json

# Exclude additional directories
python utils/documentation/dead_code_finder.py --exclude tests docs
```

**Example Output:**
```
==============================================================================
DEAD CODE ANALYSIS REPORT
==============================================================================

UNUSED FUNCTIONS (3)
----------------------------------------
  src/utils.py:45 - old_function()
  src/helpers.py:23 - deprecated_helper()

UNUSED IMPORTS (5)
----------------------------------------
  src/main.py:10 - json (from json)
  src/utils.py:5 - Path (from pathlib)

ORPHANED FILES (2)
----------------------------------------
  src/legacy/old_module.py
  scripts/unused_script.py
```

### 2. TODO/FIXME Extractor (`todo_extractor.py`)

Scans code for TODO, FIXME, HACK, and other comment tags, with git blame integration.

**Usage:**
```bash
python utils/documentation/todo_extractor.py

# Markdown format with high priority only
python utils/documentation/todo_extractor.py --format markdown --priority high -o TODOs.md

# JSON format without git blame
python utils/documentation/todo_extractor.py --format json --no-git-blame

# Custom tags and file extensions
python utils/documentation/todo_extractor.py --tags TODO FIXME BUG --extensions .py .js
```

**Example Output:**
```
==============================================================================
TODO/FIXME EXTRACTION REPORT
==============================================================================
Generated on: 2024-01-07 10:30:45
Total items found: 15

SUMMARY BY TAG:
  TODO         8 items
  FIXME        5 items
  HACK         2 items

HIGH PRIORITY ITEMS:
----------------------------------------
  src/api/auth.py:156
    [TODO] Implement rate limiting URGENT
    Author: john.doe (2024-01-05)

  src/models/user.py:89
    [FIXME] SQL injection vulnerability - HIGH PRIORITY
    Author: jane.smith (2024-01-06)
```

### 3. Environment Variable Documenter (`env_documenter.py`)

Finds all environment variable usage and generates documentation.

**Usage:**
```bash
python utils/documentation/env_documenter.py

# With .env validation
python utils/documentation/env_documenter.py --env-file .env.example

# Markdown format
python utils/documentation/env_documenter.py --format markdown -o ENV_VARS.md

# Check for missing variables
python utils/documentation/env_documenter.py --check-missing
```

**Example Output:**
```
==============================================================================
ENVIRONMENT VARIABLES DOCUMENTATION
==============================================================================

REQUIRED VARIABLES (5):
----------------------------------------
DATABASE_URL
  Used in: src/db/connection.py:15
  Default: None
  Description: PostgreSQL connection string

API_KEY
  Used in: src/api/client.py:8, src/api/auth.py:22
  Default: None
  Description: External API authentication key

OPTIONAL VARIABLES (3):
----------------------------------------
LOG_LEVEL
  Used in: src/logging.py:12
  Default: "INFO"
  Description: Logging verbosity level

MISSING IN .env (2):
----------------------------------------
- DATABASE_URL
- API_KEY
```

### 4. Requirements Analyzer (`requirements_analyzer.py`)

Analyzes Python dependencies for unused packages, missing requirements, and security issues.

**Usage:**
```bash
python utils/documentation/requirements_analyzer.py

# Check specific requirements file
python utils/documentation/requirements_analyzer.py --requirements requirements-dev.txt

# Security check
python utils/documentation/requirements_analyzer.py --check-security

# JSON output
python utils/documentation/requirements_analyzer.py --format json -o deps.json
```

**Example Output:**
```
==============================================================================
REQUIREMENTS ANALYSIS REPORT
==============================================================================

UNUSED PACKAGES (3):
----------------------------------------
- pandas (not imported anywhere)
- matplotlib (not imported anywhere)
- selenium (not imported anywhere)

MISSING PACKAGES (2):
----------------------------------------
- requests (imported in 5 files)
- numpy (imported in 3 files)

VERSION CONFLICTS:
----------------------------------------
- urllib3: required by requests (>=1.26.0), boto3 (<1.27)

SECURITY VULNERABILITIES (1):
----------------------------------------
- django 2.2.0: Known SQL injection vulnerability (CVE-2023-XXXX)
  Recommended: upgrade to >=4.2.0
```

### 5. API Documentation Generator (`api_doc_generator.py`)

Automatically extracts and documents FastAPI/Flask endpoints.

**Usage:**
```bash
python utils/documentation/api_doc_generator.py

# Generate OpenAPI spec
python utils/documentation/api_doc_generator.py --format openapi -o openapi.json

# Markdown documentation
python utils/documentation/api_doc_generator.py --format markdown -o API.md

# Summary only
python utils/documentation/api_doc_generator.py --format summary

# Specify framework
python utils/documentation/api_doc_generator.py --framework fastapi
```

**Example Output (Markdown):**
```markdown
# API Documentation

## Authentication

### POST /auth/login
Login endpoint for user authentication.

**Function**: `login_user` in `src/api/auth.py:45`

**Parameters**:
- `username` (str, required)
- `password` (str, required)

**Response**: 200
- Model: `TokenResponse`

---

### GET /auth/verify ⚠️ **DEPRECATED**
Verify authentication token.

**Function**: `verify_token` in `src/api/auth.py:78`
```

### 6. Tree Diagram Generator (`tree_generator.py`)

Creates tree diagrams of project structure with gitignore support.

**Usage:**
```bash
python utils/documentation/tree_generator.py

# Markdown format
python utils/documentation/tree_generator.py --format markdown -o PROJECT_STRUCTURE.md

# Limit depth
python utils/documentation/tree_generator.py --max-depth 3

# Show only directories
python utils/documentation/tree_generator.py --no-files

# Include hidden files
python utils/documentation/tree_generator.py --show-hidden
```

**Example Output:**
```
project-name
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── endpoints.py
│   └── models/
│       ├── __init__.py
│       └── user.py
├── tests/
│   └── test_api.py
├── .env.example
├── requirements.txt
└── README.md
```

### 7. Changelog Builder (`changelog_builder.py`)

Generates changelogs from git commits using Conventional Commits format.

**Usage:**
```bash
# Generate full changelog
python utils/documentation/changelog_builder.py -o CHANGELOG.md

# Changes since last tag
python utils/documentation/changelog_builder.py --from v1.0.0

# Changes between versions
python utils/documentation/changelog_builder.py --from v1.0.0 --to v2.0.0

# JSON format
python utils/documentation/changelog_builder.py --format json

# Include all commits (not just conventional)
python utils/documentation/changelog_builder.py --include-all
```

**Example Output:**
```markdown
# Changelog

## [Unreleased]

### ⚠ BREAKING CHANGES

* Remove deprecated API endpoints
  * Commit: [a1b2c3d](https://github.com/user/repo/commit/a1b2c3d)

### Features

* **auth**
  * Add OAuth2 support ([d4e5f6g](https://github.com/user/repo/commit/d4e5f6g))
  * Implement refresh tokens ([h7i8j9k](https://github.com/user/repo/commit/h7i8j9k))

### Bug Fixes

* Fix memory leak in cache manager ([l0m1n2o](https://github.com/user/repo/commit/l0m1n2o))
  * Issues: [#123](https://github.com/user/repo/issues/123)
```

### 8. API Key Scanner (`api_key_scanner.py`)

Searches for hardcoded API keys, secrets, and sensitive information in code.

**Usage:**
```bash
python utils/documentation/api_key_scanner.py

# JSON output with high confidence only
python utils/documentation/api_key_scanner.py --format json --confidence high -o secrets.json

# Exclude additional directories
python utils/documentation/api_key_scanner.py --exclude tests docs

# Add custom pattern
python utils/documentation/api_key_scanner.py --add-pattern "MY_SECRET_[A-Z]+" "Custom Secret" "Use environment variables"
```

**Example Output:**
```
==============================================================================
API KEY/SECRET SCANNER REPORT
==============================================================================

Total findings: 12
  High confidence: 3
  Medium confidence: 7
  Low confidence: 2

HIGH CONFIDENCE FINDINGS (Likely actual secrets)
--------------------------------------------------------------------------------

src/config.py:45
Pattern: OpenAI API Key
Line: OPENAI_KEY = "sk-proj1234567890abcdefghijklmnopqrstuvwxyz12345678"
Recommendation: Use environment variables: os.getenv("OPENAI_API_KEY")

src/aws_client.py:12
Pattern: AWS Access Key ID
Line: aws_access_key = "AKIAIOSFODNN7EXAMPLE"
Recommendation: Remove AWS access key and use environment variables or AWS IAM roles

GENERAL RECOMMENDATIONS:
----------------------------------------
1. Never commit API keys, passwords, or secrets to version control
2. Use environment variables: os.getenv('API_KEY')
3. Use secret management services (AWS Secrets Manager, Azure Key Vault, etc.)
4. Add sensitive files to .gitignore
5. Use git-secrets or similar pre-commit hooks
6. Rotate any exposed credentials immediately
```

### 9. Dependency Graph Visualizer (`dependency_visualizer.py`)

Creates visual graphs showing module dependencies and identifies circular dependencies.

**Usage:**
```bash
# Text report
python utils/documentation/dependency_visualizer.py

# Mermaid diagram (GitHub-compatible)
python utils/documentation/dependency_visualizer.py --format mermaid -o deps.mmd

# Graphviz DOT format
python utils/documentation/dependency_visualizer.py --format graphviz -o deps.dot

# Include external dependencies
python utils/documentation/dependency_visualizer.py --format mermaid --show-external

# JSON data
python utils/documentation/dependency_visualizer.py --format json -o deps.json
```

**Example Output (Text Report):**
```
==============================================================================
DEPENDENCY ANALYSIS REPORT
==============================================================================

Total modules: 25
Total dependencies: 47
Circular dependency groups: 2

CIRCULAR DEPENDENCIES:
----------------------------------------
1. src.models.user -> src.models.role -> src.models.user
2. src.api.auth -> src.api.users -> src.api.auth

MOST COMPLEX MODULES:
----------------------------------------
Module                                             Score     Deps   Used By
------------------------------------------------------------------------------
src.api.endpoints                                   15.5        8        12
src.models.base                                     12.0        5        15
src.utils.helpers                                   10.5        6         9

EXTERNAL DEPENDENCIES (12 unique):
----------------------------------------
  fastapi: 8 imports
  sqlalchemy: 6 imports
  pydantic: 5 imports
```

**Example Mermaid Output:**
```mermaid
graph TD
    src_api_auth["src.api.auth"]:::circular
    src_api_users["src.api.users"]:::circular
    src_models_user["src.models.user"]
    src_utils_crypto["src.utils.crypto"]
    
    src_api_auth -->|circular| src_api_users
    src_api_users -->|circular| src_api_auth
    src_api_auth --> src_models_user
    src_api_auth --> src_utils_crypto
    
    classDef circular fill:#ff6b6b,stroke:#c92a2a,stroke-width:2px
    classDef complex fill:#ffe066,stroke:#f59f00,stroke-width:2px
```

## Output Options

All scripts support the following common options:

- `--output`, `-o`: Save output to a file instead of printing to stdout
- `--format`: Choose output format (varies by script, typically: text, json, markdown)
- `--help`, `-h`: Show detailed help and examples

## Integration Examples

### Pre-commit Hook
```bash
#!/bin/bash
# Check for TODOs before commit
python utils/documentation/todo_extractor.py --priority high --format json | \
  jq -e '.todos | length == 0' || \
  (echo "High priority TODOs found! Please resolve before committing." && exit 1)
```

### CI/CD Pipeline
```yaml
# GitHub Actions example
- name: Check for dead code
  run: |
    python utils/documentation/dead_code_finder.py --format json -o dead_code.json
    if [ -s dead_code.json ]; then
      echo "Dead code detected!"
      cat dead_code.json
      exit 1
    fi
```

### Documentation Generation
```bash
#!/bin/bash
# Generate all documentation
python utils/documentation/tree_generator.py --format markdown > docs/PROJECT_STRUCTURE.md
python utils/documentation/api_doc_generator.py --format markdown > docs/API.md
python utils/documentation/env_documenter.py --format markdown > docs/ENVIRONMENT.md
python utils/documentation/changelog_builder.py > CHANGELOG.md
```

## Project Maintenance Utilities

Located in `utils/`, these scripts help maintain code quality and consistency:

### 1. Add Filepath Comments (`add_filepath_comments.py`)

Adds relative filepath comments as the first line of all Python files for better code navigation.

**Usage:**
```bash
# Preview changes without modifying files
python utils/add_filepath_comments.py --dry-run

# Add filepath comments to all Python files
python utils/add_filepath_comments.py

# Use a different root directory
python utils/add_filepath_comments.py --root-dir /path/to/project
```

**Example Result:**
```python
# utils/shared/document_formatter.py

#!/usr/bin/env python3
"""Module docstring..."""
```

## Shared Utilities

Located in `utils/shared/`, these are reusable utilities for various tasks:

### 1. Document Formatter (`document_formatter.py`)

Converts Markdown or HTML content to formatted Word documents with customizable styling.

**Usage:**
```python
from utils.shared import WordDocFormatter

# Basic usage
formatter = WordDocFormatter()
formatter.markdown_to_docx("# Hello World", "output.docx")

# Custom styling
formatter = WordDocFormatter(
    font_name="Arial",
    font_size=12,
    heading_color="#FF0000",
    page_orientation="landscape"
)

# Convert to memory (for web apps)
binary_data = formatter.to_memory("# My Document")

# Auto-detect format
formatter.to_docx(content, "output.docx")  # Auto-detects HTML vs Markdown
```

**Features:**
- Converts Markdown or HTML to Word documents
- Customizable fonts, sizes, and colors
- Consistent styling for body text, headings, and lists
- Custom table formatting with styled headers
- Page orientation and margin control
- In-memory or file-based output

### 2. Azure Document Intelligence Processor (`az_doc_intelligence_processor.py`)

Extracts structured content from documents using Azure Document Intelligence (formerly Form Recognizer).

**Usage:**
```python
from utils.shared.az_doc_intelligence_processor import DocIntelligence

# Initialize processor
processor = DocIntelligence(
    endpoint="https://your-endpoint.cognitiveservices.azure.com/",
    key="your-api-key",
    output_dir="outputs"
)

# Process a single document
results = processor.process_document("document.pdf")
print(f"Extracted {len(results['csv_files'])} tables")
print(f"Excel workbook: {results.get('excel_file', 'No tables found')}")

# Process entire directory
results = processor.process_directory(
    input_dir="documents/",
    output_dir="outputs/",
    file_types=["pdf", "docx"]
)
```

**Features:**
- Extracts tables from PDFs, DOCX, and other formats
- Converts documents to Markdown with structure preserved
- Generates CSV files for each extracted table
- Creates Excel workbooks with consolidated table views
- Tracks extraction confidence scores
- Creates confidence dashboards and visualizations
- Provides detailed JSON logs for each processed document
- Supports batch processing of directories

**Output Structure:**
```
output_dir/
├── csv/                    # Individual table CSV files
├── md/                     # Full document markdown files
│   └── md_pages/          # Individual page markdown files
├── [doc]_tables.xlsx      # Excel workbook with all tables
├── [doc]_confidence_dashboard.png  # Confidence visualizations
└── [doc]_processing_log.json      # Processing metadata
```

## Requirements

All documentation scripts require Python 3.7+ and only use standard library modules, except:
- Git must be installed for scripts using git functionality (changelog_builder, todo_extractor with blame)
- Some visualization formats may require additional tools to render (e.g., Graphviz for DOT files)

The shared utilities have additional requirements:
- `document_formatter.py`: Requires `python-docx`, `mistune`, and `htmldocx` packages
- `az_doc_intelligence_processor.py`: Requires `azure-ai-documentintelligence`, `azure-core`, `pandas`, `numpy`, `matplotlib`, `seaborn`, and `openpyxl` packages