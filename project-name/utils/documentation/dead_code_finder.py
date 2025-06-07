#!/usr/bin/env python3
"""
Dead Code Detector
Finds unused functions, classes, and imports across your codebase
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, Set, List, Tuple
from collections import defaultdict
import argparse
import json


class DeadCodeAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.defined_functions = {}
        self.defined_classes = {}
        self.defined_variables = {}
        self.imports = {}
        self.function_calls = set()
        self.class_uses = set()
        self.variable_uses = set()
        self.current_file = ""
        self.decorators = set()
        
    def visit_FunctionDef(self, node):
        if self.current_file:
            self.defined_functions[f"{self.current_file}:{node.name}"] = {
                "line": node.lineno,
                "name": node.name,
                "file": self.current_file
            }
        self.generic_visit(node)
        
    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)
        
    def visit_ClassDef(self, node):
        if self.current_file:
            self.defined_classes[f"{self.current_file}:{node.name}"] = {
                "line": node.lineno,
                "name": node.name,
                "file": self.current_file
            }
        self.generic_visit(node)
        
    def visit_Import(self, node):
        for alias in node.names:
            import_name = alias.asname if alias.asname else alias.name
            if self.current_file:
                self.imports[f"{self.current_file}:{import_name}"] = {
                    "line": node.lineno,
                    "name": import_name,
                    "module": alias.name,
                    "file": self.current_file
                }
                
    def visit_ImportFrom(self, node):
        for alias in node.names:
            import_name = alias.asname if alias.asname else alias.name
            if self.current_file:
                module = node.module if node.module else ""
                self.imports[f"{self.current_file}:{import_name}"] = {
                    "line": node.lineno,
                    "name": import_name,
                    "module": f"{module}.{alias.name}",
                    "file": self.current_file
                }
                
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.function_calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.function_calls.add(node.func.attr)
        self.generic_visit(node)
        
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.variable_uses.add(node.id)
            self.class_uses.add(node.id)
        elif isinstance(node.ctx, ast.Store) and self.current_file:
            self.defined_variables[f"{self.current_file}:{node.id}"] = {
                "line": node.lineno,
                "name": node.id,
                "file": self.current_file
            }
        self.generic_visit(node)
        
    def visit_Decorator(self, node):
        if isinstance(node, ast.Name):
            self.decorators.add(node.id)
        self.generic_visit(node)


def find_python_files(root_dir: Path, exclude_dirs: Set[str] = None) -> List[Path]:
    """Find all Python files in the project."""
    if exclude_dirs is None:
        exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', 'build', 'dist'}
    
    python_files = []
    for file_path in root_dir.rglob('*.py'):
        if not any(excluded in file_path.parts for excluded in exclude_dirs):
            python_files.append(file_path)
    return python_files


def analyze_file(file_path: Path, analyzer: DeadCodeAnalyzer) -> None:
    """Analyze a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        analyzer.current_file = str(file_path)
        analyzer.visit(tree)
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}", file=sys.stderr)


def find_unused_code(analyzer: DeadCodeAnalyzer) -> Dict[str, List[Dict]]:
    """Find all unused code elements."""
    unused = {
        "functions": [],
        "classes": [],
        "imports": [],
        "variables": []
    }
    
    # Check unused functions
    for key, func_info in analyzer.defined_functions.items():
        func_name = func_info["name"]
        if func_name not in analyzer.function_calls and not func_name.startswith('_'):
            # Skip special methods
            if not (func_name.startswith('__') and func_name.endswith('__')):
                # Skip decorated functions (they might be used by frameworks)
                if func_name not in analyzer.decorators:
                    unused["functions"].append(func_info)
    
    # Check unused classes
    for key, class_info in analyzer.defined_classes.items():
        class_name = class_info["name"]
        if class_name not in analyzer.class_uses:
            unused["classes"].append(class_info)
    
    # Check unused imports
    for key, import_info in analyzer.imports.items():
        import_name = import_info["name"]
        if import_name not in analyzer.variable_uses:
            unused["imports"].append(import_info)
    
    return unused


def find_orphaned_files(root_dir: Path, python_files: List[Path]) -> List[str]:
    """Find Python files that aren't imported anywhere."""
    imported_files = set()
    file_imports = defaultdict(set)
    
    # Build import graph
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        file_imports[str(file_path)].add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        file_imports[str(file_path)].add(node.module)
        except:
            pass
    
    # Check which files are imported
    for file_path in python_files:
        module_name = file_path.stem
        parent_parts = file_path.parent.parts
        
        # Check various import patterns
        for imports in file_imports.values():
            if module_name in imports:
                imported_files.add(str(file_path))
                break
            
            # Check for package imports
            for i in range(len(parent_parts)):
                potential_import = '.'.join(parent_parts[i:] + (module_name,))
                if potential_import in imports:
                    imported_files.add(str(file_path))
                    break
    
    # Find orphaned files (excluding main entry points)
    orphaned = []
    for file_path in python_files:
        if str(file_path) not in imported_files:
            if file_path.name not in ['__main__.py', 'main.py', 'setup.py', 'manage.py']:
                if not file_path.name.startswith('test_'):
                    orphaned.append(str(file_path.relative_to(root_dir)))
    
    return orphaned


def generate_report(unused: Dict[str, List[Dict]], orphaned_files: List[str], 
                   output_format: str = "text") -> str:
    """Generate a report of dead code."""
    if output_format == "json":
        return json.dumps({
            "unused": unused,
            "orphaned_files": orphaned_files
        }, indent=2)
    
    # Text format
    report = []
    report.append("=" * 80)
    report.append("DEAD CODE ANALYSIS REPORT")
    report.append("=" * 80)
    report.append("")
    
    # Unused functions
    if unused["functions"]:
        report.append(f"UNUSED FUNCTIONS ({len(unused['functions'])})")
        report.append("-" * 40)
        for func in unused["functions"]:
            report.append(f"  {func['file']}:{func['line']} - {func['name']}()")
        report.append("")
    
    # Unused classes
    if unused["classes"]:
        report.append(f"UNUSED CLASSES ({len(unused['classes'])})")
        report.append("-" * 40)
        for cls in unused["classes"]:
            report.append(f"  {cls['file']}:{cls['line']} - class {cls['name']}")
        report.append("")
    
    # Unused imports
    if unused["imports"]:
        report.append(f"UNUSED IMPORTS ({len(unused['imports'])})")
        report.append("-" * 40)
        for imp in unused["imports"]:
            report.append(f"  {imp['file']}:{imp['line']} - {imp['name']} (from {imp['module']})")
        report.append("")
    
    # Orphaned files
    if orphaned_files:
        report.append(f"ORPHANED FILES ({len(orphaned_files)})")
        report.append("-" * 40)
        for file_path in orphaned_files:
            report.append(f"  {file_path}")
        report.append("")
    
    # Summary
    total_issues = (len(unused["functions"]) + len(unused["classes"]) + 
                   len(unused["imports"]) + len(orphaned_files))
    report.append(f"Total issues found: {total_issues}")
    
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Find dead code in Python projects")
    parser.add_argument("path", nargs="?", default=".", 
                       help="Path to analyze (default: current directory)")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                       help="Output format (default: text)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--exclude", nargs="*", default=[],
                       help="Additional directories to exclude")
    
    args = parser.parse_args()
    
    root_dir = Path(args.path).resolve()
    if not root_dir.exists():
        print(f"Error: Path {root_dir} does not exist", file=sys.stderr)
        sys.exit(1)
    
    # Find all Python files
    exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', 'build', 'dist'}
    exclude_dirs.update(args.exclude)
    python_files = find_python_files(root_dir, exclude_dirs)
    
    if not python_files:
        print("No Python files found to analyze", file=sys.stderr)
        sys.exit(0)
    
    # Analyze files
    analyzer = DeadCodeAnalyzer()
    for file_path in python_files:
        analyze_file(file_path, analyzer)
    
    # Find unused code and orphaned files
    unused = find_unused_code(analyzer)
    orphaned_files = find_orphaned_files(root_dir, python_files)
    
    # Generate report
    report = generate_report(unused, orphaned_files, args.format)
    
    # Output report
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()