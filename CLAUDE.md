# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Setup
```bash
# Copy configuration templates
cp .env.example .env
cp config.json.template config.json

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"  # Install with development tools
```

### Code Quality Commands
```bash
# Format code (line-length: 88)
black .

# Lint code
flake8

# Type check (strict mode)
mypy .

# Run tests
pytest
pytest --cov  # Run with coverage report
pytest tests/test_apps/test_specific.py  # Run specific test file
pytest -k "test_function_name"  # Run specific test by name
```

### Documentation Utilities
```bash
# Extract TODO/FIXME comments with priorities
python utils/documentation/todo_extractor.py

# Generate API documentation (for FastAPI/Flask apps)
python utils/documentation/api_doc_generator.py

# Find dead/unused code
python utils/documentation/dead_code_finder.py

# Document environment variables
python utils/documentation/env_documenter.py

# Analyze project dependencies
python utils/documentation/requirements_analyzer.py
```

## Architecture

This is a general-purpose Python project template with modular architecture:

- **code/apps/**: Application modules - main business logic and features
- **code/libs/**: Shared libraries - reusable components across apps
- **code/scripts/**: Utility scripts - standalone tools and helpers
- **prompts/**: AI prompt templates organized into components and user-facing prompts
- **tests/**: Test suite mirroring the code structure (test_apps/, test_libs/, test_scripts/)
- **utils/documentation/**: Custom documentation generation and code analysis tools

The project uses environment-based configuration (.env files) and JSON configuration (config.json). The main entry point is `main.py` which sets up the Python path and loads environment variables.