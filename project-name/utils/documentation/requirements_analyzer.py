#!/usr/bin/env python3
"""
Requirements Analyzer
Detects unused dependencies, missing dependencies, and security issues
"""

import ast
import os
import sys
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import argparse
from collections import defaultdict
import pkg_resources
import importlib.metadata


class RequirementsAnalyzer:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.installed_packages = self._get_installed_packages()
        self.import_to_package_map = self._build_import_to_package_map()
        
    def _get_installed_packages(self) -> Dict[str, str]:
        """Get all installed packages and their versions."""
        packages = {}
        try:
            for dist in pkg_resources.working_set:
                packages[dist.project_name.lower()] = dist.version
        except:
            # Fallback to importlib.metadata for Python 3.8+
            try:
                for dist in importlib.metadata.distributions():
                    name = dist.metadata.get('Name')
                    version = dist.metadata.get('Version')
                    if name and version:
                        packages[name.lower()] = version
            except:
                pass
        return packages
    
    def _build_import_to_package_map(self) -> Dict[str, str]:
        """Build a mapping of import names to package names."""
        # Common mappings that differ from package names
        known_mappings = {
            'cv2': 'opencv-python',
            'PIL': 'pillow',
            'sklearn': 'scikit-learn',
            'yaml': 'pyyaml',
            'MySQLdb': 'mysqlclient',
            'psycopg2': 'psycopg2-binary',
            'bs4': 'beautifulsoup4',
            'dotenv': 'python-dotenv',
            'jwt': 'pyjwt',
            'openai': 'openai',
            'dateutil': 'python-dateutil',
            'magic': 'python-magic',
            'ldap': 'python-ldap',
            'memcache': 'python-memcached',
            'redis': 'redis',
            'flask': 'flask',
            'django': 'django',
            'fastapi': 'fastapi',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'matplotlib': 'matplotlib',
            'seaborn': 'seaborn',
            'scipy': 'scipy',
            'tensorflow': 'tensorflow',
            'torch': 'torch',
            'transformers': 'transformers',
            'requests': 'requests',
            'pytest': 'pytest',
            'black': 'black',
            'flake8': 'flake8',
            'mypy': 'mypy',
            'streamlit': 'streamlit',
            'gradio': 'gradio',
            'sqlalchemy': 'sqlalchemy',
            'alembic': 'alembic',
            'pydantic': 'pydantic',
            'uvicorn': 'uvicorn',
            'gunicorn': 'gunicorn',
            'celery': 'celery',
            'boto3': 'boto3',
            'httpx': 'httpx',
            'aiohttp': 'aiohttp',
            'click': 'click',
            'typer': 'typer',
            'rich': 'rich',
            'tqdm': 'tqdm',
            'loguru': 'loguru',
            'cryptography': 'cryptography',
            'passlib': 'passlib',
            'python_jose': 'python-jose',
            'stripe': 'stripe',
            'twilio': 'twilio',
            'sendgrid': 'sendgrid',
            'jinja2': 'jinja2',
            'markdown': 'markdown',
            'pygments': 'pygments',
            'lxml': 'lxml',
            'openpyxl': 'openpyxl',
            'xlrd': 'xlrd',
            'xlwt': 'xlwt',
            'reportlab': 'reportlab',
            'fpdf': 'fpdf',
            'qrcode': 'qrcode',
            'barcode': 'python-barcode',
            'geopy': 'geopy',
            'folium': 'folium',
            'plotly': 'plotly',
            'dash': 'dash',
            'bokeh': 'bokeh',
            'altair': 'altair',
            'spacy': 'spacy',
            'nltk': 'nltk',
            'gensim': 'gensim',
            'textblob': 'textblob',
        }
        
        # Try to get more mappings from installed packages
        try:
            for dist in pkg_resources.working_set:
                if hasattr(dist, '_provider'):
                    for module in dist._provider._module_names:
                        if '.' not in module:  # Top-level modules only
                            known_mappings[module] = dist.project_name.lower()
        except:
            pass
            
        return known_mappings
    
    def find_imports(self, exclude_dirs: Optional[Set[str]] = None) -> Dict[str, Set[str]]:
        """Find all imports in Python files."""
        if exclude_dirs is None:
            exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', 
                          'build', 'dist', '.tox', 'node_modules'}
        
        imports_by_file = defaultdict(set)
        all_imports = set()
        
        for file_path in self.root_dir.rglob('*.py'):
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name.split('.')[0]
                            imports_by_file[str(file_path)].add(module_name)
                            all_imports.add(module_name)
                            
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module.split('.')[0]
                            imports_by_file[str(file_path)].add(module_name)
                            all_imports.add(module_name)
                            
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}", file=sys.stderr)
        
        return dict(imports_by_file), all_imports
    
    def parse_requirements_file(self, req_file: Path) -> Dict[str, Optional[str]]:
        """Parse a requirements.txt file."""
        requirements = {}
        
        try:
            with open(req_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Handle different requirement formats
                        if '>=' in line or '==' in line or '<=' in line or '>' in line or '<' in line:
                            match = re.match(r'^([a-zA-Z0-9\-_\.]+)', line)
                            if match:
                                package_name = match.group(1).lower()
                                requirements[package_name] = line
                        else:
                            # No version specifier
                            package_name = line.split('[')[0].lower()  # Handle extras
                            requirements[package_name] = line
                            
        except Exception as e:
            print(f"Error reading {req_file}: {e}", file=sys.stderr)
            
        return requirements
    
    def parse_pyproject_toml(self, pyproject_file: Path) -> Dict[str, Optional[str]]:
        """Parse dependencies from pyproject.toml."""
        requirements = {}
        
        try:
            import toml
        except ImportError:
            print("Warning: toml package not installed. Cannot parse pyproject.toml", file=sys.stderr)
            return requirements
            
        try:
            with open(pyproject_file, 'r', encoding='utf-8') as f:
                data = toml.load(f)
                
            # Check different possible locations for dependencies
            deps = []
            
            # Poetry style
            if 'tool' in data and 'poetry' in data['tool']:
                if 'dependencies' in data['tool']['poetry']:
                    deps.extend(data['tool']['poetry']['dependencies'].items())
                if 'dev-dependencies' in data['tool']['poetry']:
                    deps.extend(data['tool']['poetry']['dev-dependencies'].items())
                    
            # PEP 621 style
            if 'project' in data:
                if 'dependencies' in data['project']:
                    for dep in data['project']['dependencies']:
                        if '>=' in dep or '==' in dep:
                            name = re.match(r'^([a-zA-Z0-9\-_\.]+)', dep).group(1)
                            deps.append((name, dep))
                        else:
                            deps.append((dep, dep))
                            
                if 'optional-dependencies' in data['project']:
                    for group_deps in data['project']['optional-dependencies'].values():
                        for dep in group_deps:
                            if '>=' in dep or '==' in dep:
                                name = re.match(r'^([a-zA-Z0-9\-_\.]+)', dep).group(1)
                                deps.append((name, dep))
                            else:
                                deps.append((dep, dep))
                                
            # Process dependencies
            for name, version in deps:
                if name.lower() not in ['python', 'pip']:
                    requirements[name.lower()] = str(version) if version else name
                    
        except Exception as e:
            print(f"Error parsing {pyproject_file}: {e}", file=sys.stderr)
            
        return requirements
    
    def map_import_to_package(self, import_name: str) -> Optional[str]:
        """Map an import name to its package name."""
        # Check known mappings
        if import_name in self.import_to_package_map:
            return self.import_to_package_map[import_name]
            
        # Check if it's a standard library module
        if self.is_stdlib_module(import_name):
            return None
            
        # Try direct mapping (many packages have same import name)
        if import_name.lower() in self.installed_packages:
            return import_name.lower()
            
        # Try with underscores replaced by hyphens
        hyphenated = import_name.replace('_', '-').lower()
        if hyphenated in self.installed_packages:
            return hyphenated
            
        # Try to find in installed packages
        for package_name in self.installed_packages:
            if package_name.replace('-', '_') == import_name.lower():
                return package_name
                
        return import_name.lower()  # Best guess
    
    def is_stdlib_module(self, module_name: str) -> bool:
        """Check if a module is part of the standard library."""
        stdlib_modules = {
            'abc', 'argparse', 'array', 'ast', 'asyncio', 'atexit', 'base64',
            'binascii', 'bisect', 'builtins', 'calendar', 'cmath', 'cmd', 'code',
            'codecs', 'collections', 'colorsys', 'configparser', 'contextlib',
            'copy', 'csv', 'ctypes', 'curses', 'dataclasses', 'datetime', 'decimal',
            'difflib', 'dis', 'doctest', 'email', 'enum', 'errno', 'faulthandler',
            'filecmp', 'fileinput', 'fnmatch', 'fractions', 'functools', 'gc',
            'getopt', 'getpass', 'glob', 'gzip', 'hashlib', 'heapq', 'hmac',
            'html', 'http', 'imaplib', 'importlib', 'inspect', 'io', 'ipaddress',
            'itertools', 'json', 'keyword', 'linecache', 'locale', 'logging',
            'lzma', 'mailbox', 'math', 'mimetypes', 'mmap', 'multiprocessing',
            'numbers', 'operator', 'os', 'pathlib', 'pickle', 'platform', 'plistlib',
            'poplib', 'pprint', 'profile', 'pstats', 'pty', 'pwd', 'py_compile',
            'queue', 'quopri', 'random', 're', 'readline', 'reprlib', 'resource',
            'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex',
            'shutil', 'signal', 'site', 'smtplib', 'socket', 'socketserver',
            'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'struct', 'subprocess',
            'sys', 'sysconfig', 'tarfile', 'tempfile', 'textwrap', 'threading',
            'time', 'timeit', 'tkinter', 'token', 'tokenize', 'trace', 'traceback',
            'tracemalloc', 'types', 'typing', 'unicodedata', 'unittest', 'urllib',
            'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref', 'webbrowser',
            'xml', 'xmlrpc', 'zipfile', 'zipimport', 'zlib', '_thread',
            'setuptools', 'pkg_resources', 'pip', 'wheel', 'future', 'past',
            'six', 'backports', '__future__', '__main__',
        }
        return module_name in stdlib_modules
    
    def check_security_vulnerabilities(self, requirements: Dict[str, str]) -> List[Dict]:
        """Check for known security vulnerabilities using pip-audit."""
        vulnerabilities = []
        
        # Check if pip-audit is available
        try:
            result = subprocess.run(
                ['pip-audit', '--format', 'json', '--desc'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                audit_data = json.loads(result.stdout)
                for vuln in audit_data:
                    package_name = vuln.get('name', '').lower()
                    if package_name in requirements:
                        vulnerabilities.append({
                            'package': package_name,
                            'installed_version': vuln.get('version'),
                            'vulnerability': vuln.get('id'),
                            'description': vuln.get('description', ''),
                            'fix_version': vuln.get('fix_versions', [])
                        })
        except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
            # pip-audit not available or failed
            pass
            
        return vulnerabilities
    
    def analyze_dependencies(self) -> Dict:
        """Perform complete dependency analysis."""
        analysis = {
            'declared_dependencies': {},
            'imported_modules': set(),
            'missing_dependencies': set(),
            'unused_dependencies': set(),
            'security_vulnerabilities': [],
            'version_conflicts': [],
            'stats': {}
        }
        
        # Find all requirement files
        req_files = []
        for pattern in ['requirements*.txt', 'requirements/*.txt']:
            req_files.extend(self.root_dir.glob(pattern))
            
        pyproject = self.root_dir / 'pyproject.toml'
        
        # Parse requirements
        for req_file in req_files:
            reqs = self.parse_requirements_file(req_file)
            analysis['declared_dependencies'].update(reqs)
            
        if pyproject.exists():
            reqs = self.parse_pyproject_toml(pyproject)
            analysis['declared_dependencies'].update(reqs)
            
        # Find all imports
        _, all_imports = self.find_imports()
        analysis['imported_modules'] = all_imports
        
        # Map imports to packages
        imported_packages = set()
        for import_name in all_imports:
            if not self.is_stdlib_module(import_name):
                package_name = self.map_import_to_package(import_name)
                if package_name:
                    imported_packages.add(package_name)
                    
        # Find missing dependencies
        for package in imported_packages:
            if package not in analysis['declared_dependencies']:
                # Check if it's a sub-package of a declared dependency
                is_subpackage = False
                for declared in analysis['declared_dependencies']:
                    if package.startswith(declared + '-') or declared.startswith(package + '-'):
                        is_subpackage = True
                        break
                        
                if not is_subpackage:
                    analysis['missing_dependencies'].add(package)
                    
        # Find unused dependencies
        for declared in analysis['declared_dependencies']:
            # Skip common dev tools that might not be imported
            dev_tools = {'pytest', 'black', 'flake8', 'mypy', 'coverage', 
                        'sphinx', 'tox', 'pre-commit', 'pip-tools', 'wheel',
                        'setuptools', 'twine', 'build'}
            
            if declared not in dev_tools:
                # Check if any import uses this package
                is_used = False
                for imported in imported_packages:
                    if (imported == declared or 
                        imported.startswith(declared + '-') or 
                        declared.startswith(imported + '-')):
                        is_used = True
                        break
                        
                if not is_used:
                    analysis['unused_dependencies'].add(declared)
                    
        # Check security vulnerabilities
        if analysis['declared_dependencies']:
            analysis['security_vulnerabilities'] = self.check_security_vulnerabilities(
                analysis['declared_dependencies']
            )
            
        # Calculate stats
        analysis['stats'] = {
            'total_declared': len(analysis['declared_dependencies']),
            'total_imported': len(imported_packages),
            'missing': len(analysis['missing_dependencies']),
            'unused': len(analysis['unused_dependencies']),
            'vulnerabilities': len(analysis['security_vulnerabilities'])
        }
        
        return analysis


def generate_report(analysis: Dict, format: str = "text") -> str:
    """Generate a dependency analysis report."""
    if format == "json":
        output = {
            'summary': analysis['stats'],
            'declared_dependencies': list(analysis['declared_dependencies'].keys()),
            'missing_dependencies': list(analysis['missing_dependencies']),
            'unused_dependencies': list(analysis['unused_dependencies']),
            'security_vulnerabilities': analysis['security_vulnerabilities']
        }
        return json.dumps(output, indent=2)
    
    elif format == "markdown":
        report = []
        report.append("# Dependencies Analysis Report")
        report.append("")
        report.append("## Summary")
        report.append(f"- Total declared dependencies: {analysis['stats']['total_declared']}")
        report.append(f"- Total imported packages: {analysis['stats']['total_imported']}")
        report.append(f"- Missing dependencies: {analysis['stats']['missing']}")
        report.append(f"- Unused dependencies: {analysis['stats']['unused']}")
        report.append(f"- Security vulnerabilities: {analysis['stats']['vulnerabilities']}")
        report.append("")
        
        if analysis['missing_dependencies']:
            report.append("## Missing Dependencies")
            report.append("These packages are imported but not declared in requirements:")
            report.append("")
            for package in sorted(analysis['missing_dependencies']):
                report.append(f"- `{package}`")
            report.append("")
            
        if analysis['unused_dependencies']:
            report.append("## Unused Dependencies")
            report.append("These packages are declared but appear to be unused:")
            report.append("")
            for package in sorted(analysis['unused_dependencies']):
                report.append(f"- `{package}`")
            report.append("")
            
        if analysis['security_vulnerabilities']:
            report.append("## Security Vulnerabilities")
            report.append("")
            for vuln in analysis['security_vulnerabilities']:
                report.append(f"### {vuln['package']} {vuln['installed_version']}")
                report.append(f"- **Vulnerability**: {vuln['vulnerability']}")
                report.append(f"- **Description**: {vuln['description']}")
                if vuln['fix_version']:
                    report.append(f"- **Fix available**: {', '.join(vuln['fix_version'])}")
                report.append("")
                
        report.append("## Recommendations")
        report.append("")
        if analysis['missing_dependencies']:
            report.append("1. **Add missing dependencies** to your requirements file:")
            report.append("   ```bash")
            for package in sorted(analysis['missing_dependencies'])[:5]:
                report.append(f"   pip install {package}")
            report.append("   ```")
            report.append("")
            
        if analysis['unused_dependencies']:
            report.append("2. **Review unused dependencies** and remove if truly unused")
            report.append("")
            
        if analysis['security_vulnerabilities']:
            report.append("3. **Update vulnerable packages** immediately")
            report.append("")
            
        return "\n".join(report)
    
    else:  # text format
        report = []
        report.append("=" * 80)
        report.append("DEPENDENCY ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")
        report.append(f"Total declared dependencies: {analysis['stats']['total_declared']}")
        report.append(f"Total imported packages:     {analysis['stats']['total_imported']}")
        report.append(f"Missing dependencies:        {analysis['stats']['missing']}")
        report.append(f"Unused dependencies:         {analysis['stats']['unused']}")
        report.append(f"Security vulnerabilities:    {analysis['stats']['vulnerabilities']}")
        report.append("")
        
        if analysis['missing_dependencies']:
            report.append("MISSING DEPENDENCIES:")
            report.append("-" * 40)
            for package in sorted(analysis['missing_dependencies']):
                report.append(f"  - {package}")
            report.append("")
            
        if analysis['unused_dependencies']:
            report.append("UNUSED DEPENDENCIES:")
            report.append("-" * 40)
            for package in sorted(analysis['unused_dependencies']):
                report.append(f"  - {package}")
            report.append("")
            
        if analysis['security_vulnerabilities']:
            report.append("SECURITY VULNERABILITIES:")
            report.append("-" * 40)
            for vuln in analysis['security_vulnerabilities']:
                report.append(f"  Package: {vuln['package']} {vuln['installed_version']}")
                report.append(f"  Vulnerability: {vuln['vulnerability']}")
                report.append(f"  Description: {vuln['description'][:60]}...")
                if vuln['fix_version']:
                    report.append(f"  Fix available: {', '.join(vuln['fix_version'])}")
                report.append("")
                
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Analyze Python project dependencies")
    parser.add_argument("path", nargs="?", default=".",
                       help="Path to analyze (default: current directory)")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text",
                       help="Output format (default: text)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--fix", action="store_true",
                       help="Generate commands to fix issues")
    
    args = parser.parse_args()
    
    root_dir = Path(args.path).resolve()
    if not root_dir.exists():
        print(f"Error: Path {root_dir} does not exist", file=sys.stderr)
        sys.exit(1)
    
    # Analyze dependencies
    print(f"Analyzing dependencies in {root_dir}...", file=sys.stderr)
    analyzer = RequirementsAnalyzer(root_dir)
    analysis = analyzer.analyze_dependencies()
    
    # Generate report
    report = generate_report(analysis, args.format)
    
    # Output report
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(report)
        
    # Generate fix commands if requested
    if args.fix and (analysis['missing_dependencies'] or analysis['security_vulnerabilities']):
        print("\n" + "=" * 80, file=sys.stderr)
        print("SUGGESTED FIXES:", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        
        if analysis['missing_dependencies']:
            print("\n# Install missing dependencies:", file=sys.stderr)
            print("pip install " + " ".join(sorted(analysis['missing_dependencies'])), file=sys.stderr)
            
        if analysis['security_vulnerabilities']:
            print("\n# Update vulnerable packages:", file=sys.stderr)
            for vuln in analysis['security_vulnerabilities']:
                if vuln['fix_version']:
                    print(f"pip install --upgrade {vuln['package']}>={vuln['fix_version'][0]}", file=sys.stderr)


if __name__ == "__main__":
    main()