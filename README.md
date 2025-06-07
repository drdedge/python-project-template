# Python Project Template

A comprehensive, production-ready template for Python projects with built-in documentation tools, best practices, and flexible architecture.

## Overview

This template provides a solid foundation for various types of Python projects including:
- Web applications (FastAPI, Flask, Streamlit)
- Data science and machine learning projects
- Command-line tools and scripts
- API services
- General Python packages

## Features

### 🏗️ Project Structure
```
project-name/
├── code/                   # Main application code
│   ├── apps/              # Application modules
│   ├── libs/              # Shared libraries
│   └── scripts/           # Utility scripts
├── prompts/               # AI prompt templates
│   ├── components/        # Reusable prompt components
│   └── user_prompts/      # User-facing prompts
├── data/                  # Data directory
│   ├── input/            # Input data
│   ├── output/           # Output data
│   └── logs/             # Application logs
├── docs/                  # Documentation
├── tests/                 # Test suite
│   ├── test_apps/        # Application tests
│   ├── test_libs/        # Library tests
│   └── test_scripts/     # Script tests
├── notebooks/             # Jupyter notebooks
├── pages/                 # UI pages (for Streamlit/web apps)
├── utils/                 # Utility tools
│   ├── documentation/    # Documentation generators
│   └── shared/           # Shared utilities
├── config.json.template   # Configuration template
├── .env.example          # Environment variables template
├── requirements.txt      # Python dependencies
├── pyproject.toml       # Project metadata and tool configuration
└── main.py              # Main entry point
```

### 🛠️ Built-in Documentation Tools

The template includes 9 powerful documentation and analysis tools in `utils/documentation/`:

1. **Dead Code Detector** - Find unused code and reduce bundle size
2. **TODO/FIXME Extractor** - Track technical debt with git blame integration
3. **Environment Variable Documenter** - Document all env vars usage
4. **Requirements Analyzer** - Find unused/missing dependencies
5. **API Documentation Generator** - Auto-generate API docs from code
6. **Tree Diagram Generator** - Create project structure diagrams
7. **Changelog Builder** - Generate changelogs from git commits
8. **API Key Scanner** - Find hardcoded secrets and credentials
9. **Dependency Graph Visualizer** - Visualize and analyze module dependencies

See [utils/documentation/README.md](project-name/utils/documentation/README.md) for detailed documentation.

### 🔧 Configuration

- **Environment-based**: Uses `.env` files for sensitive configuration
- **JSON config**: `config.json` for application settings
- **Type-safe**: Supports Pydantic settings for configuration validation
- **Multi-environment**: Easy setup for dev/staging/production

### 📦 Dependencies

The template includes a comprehensive set of commonly used packages:
- **Web frameworks**: FastAPI, Streamlit, Flask
- **Data processing**: Pandas, NumPy, OpenPyXL
- **AI/ML**: LangChain, OpenAI, LiteLLM
- **Visualization**: Matplotlib, Seaborn, Streamlit-AgGrid
- **Database**: SQLAlchemy, PyODBC
- **Cloud**: Azure SDK, Boto3
- **Documentation**: Sphinx-ready with docstring support
- **Testing**: Pytest with coverage support
- **Code quality**: Black, Flake8, MyPy

## Getting Started

### 1. Clone and Setup

```bash
# Clone the template
git clone <repository-url> my-project
cd my-project

# Remove template git history
rm -rf .git
git init

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Copy configuration template
cp config.json.template config.json

# Edit both files with your settings
```

### 3. Initialize Your Project

```bash
# Rename the project directory
mv project-name your-project-name

# Update project metadata in pyproject.toml
# Update README.md with your project information
```

### 4. Run Documentation Tools

```bash
# Check project structure
python utils/documentation/tree_generator.py --format markdown

# Scan for TODOs
python utils/documentation/todo_extractor.py

# Check for dead code
python utils/documentation/dead_code_finder.py

# Scan for hardcoded secrets
python utils/documentation/api_key_scanner.py
```

## Development Workflow

### Code Quality

```bash
# Format code
black .

# Lint code
flake8

# Type check
mypy .

# Run all quality checks
black . && flake8 && mypy .
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_apps/test_module.py

# Run tests matching pattern
pytest -k "test_function_name"
```

### Documentation

```bash
# Generate API documentation
python utils/documentation/api_doc_generator.py --format markdown -o docs/API.md

# Create project structure diagram
python utils/documentation/tree_generator.py --format markdown -o docs/STRUCTURE.md

# Document environment variables
python utils/documentation/env_documenter.py --format markdown -o docs/ENV_VARS.md

# Build changelog
python utils/documentation/changelog_builder.py -o CHANGELOG.md
```

### Pre-commit Checks

Add this to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Check for high-priority TODOs
python utils/documentation/todo_extractor.py --priority high --format json | \
  python -c "import sys, json; data=json.load(sys.stdin); sys.exit(1 if data['todos'] else 0)" || \
  (echo "⚠️  High priority TODOs found!" && exit 1)

# Scan for secrets
python utils/documentation/api_key_scanner.py --confidence high || \
  (echo "🚨 Potential secrets detected!" && exit 1)

# Run formatters and linters
black --check . && flake8 && mypy .
```

## Project Organization Tips

### Code Organization

- **apps/**: Self-contained application modules with their own logic
- **libs/**: Shared code used across multiple apps
- **scripts/**: Standalone scripts for specific tasks
- **utils/**: Project-wide utilities and tools

### Testing Strategy

- Mirror the code structure in tests/
- Use pytest fixtures for common test data
- Aim for >80% code coverage
- Test edge cases and error conditions

### Documentation

- Keep README.md updated with setup instructions
- Document all environment variables
- Use docstrings for all public functions/classes
- Generate API docs regularly
- Maintain a CHANGELOG.md

### Security

- Never commit secrets or API keys
- Use environment variables for all credentials
- Regularly run the API key scanner
- Keep dependencies updated
- Use `.gitignore` properly

## Common Use Cases

### Web Application
```python
# main.py
from code.apps.web_app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Data Processing Pipeline
```python
# code/apps/data_pipeline.py
from code.libs.data_processor import DataProcessor
from code.libs.database import Database

def run_pipeline():
    processor = DataProcessor()
    db = Database()
    
    data = processor.load_data("data/input/raw_data.csv")
    processed = processor.transform(data)
    db.save(processed)
```

### CLI Tool
```python
# code/scripts/cli_tool.py
import argparse
from code.libs.utils import setup_logging

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    
    # Your CLI logic here
```

## Contributing

When contributing to projects using this template:

1. Follow the existing code structure
2. Add tests for new functionality
3. Update documentation as needed
4. Run all quality checks before committing
5. Use conventional commits for clear history

## License

This template is provided as-is for use in your projects. Customize the license as needed for your specific project.

## Maintenance

### Regular Tasks

- **Weekly**: Run dependency analyzer to check for updates
- **Before releases**: Generate changelog and update version
- **Monthly**: Run dead code finder to keep codebase clean
- **Always**: Run secret scanner before pushing to remote

### Upgrading Dependencies

```bash
# Check for outdated packages
pip list --outdated

# Update requirements
pip install --upgrade package-name
pip freeze > requirements.txt

# Run tests to ensure nothing broke
pytest
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're running from the project root with `python main.py`
2. **Missing dependencies**: Run `pip install -r requirements.txt`
3. **Environment variables**: Check `.env` file exists and is properly formatted
4. **Config issues**: Validate `config.json` against the template

### Getting Help

- Check the documentation in `docs/`
- Review examples in `notebooks/`
- Use the built-in analysis tools to diagnose issues
- Refer to individual package documentation

---

This template is designed to grow with your project. Start small and expand as needed. Happy coding! 🚀