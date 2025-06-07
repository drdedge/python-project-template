#!/usr/bin/env python3
"""
Environment Variable Documenter
Finds all environment variable usage and generates documentation
"""

import ast
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import click
import json
from collections import defaultdict


class EnvVarUsage:
    def __init__(self, name: str, file_path: str, line_number: int, 
                 usage_type: str, default_value: Optional[str] = None,
                 context: Optional[str] = None):
        self.name = name
        self.file_path = file_path
        self.line_number = line_number
        self.usage_type = usage_type  # 'get', 'getenv', 'environ', 'config'
        self.default_value = default_value
        self.context = context
        
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "file": self.file_path,
            "line": self.line_number,
            "type": self.usage_type,
            "default": self.default_value,
            "context": self.context
        }


class EnvVarAnalyzer(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.env_vars = []
        self.current_function = None
        self.source_lines = []
        
    def set_source_lines(self, lines: List[str]):
        """Set source lines for context extraction."""
        self.source_lines = lines
        
    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
        
    def visit_Call(self, node):
        # Check for os.environ.get()
        if (isinstance(node.func, ast.Attribute) and
            isinstance(node.func.value, ast.Attribute) and
            isinstance(node.func.value.value, ast.Name) and
            node.func.value.value.id == 'os' and
            node.func.value.attr == 'environ' and
            node.func.attr == 'get'):
            self._handle_environ_get(node)
            
        # Check for os.getenv()
        elif (isinstance(node.func, ast.Attribute) and
              isinstance(node.func.value, ast.Name) and
              node.func.value.id == 'os' and
              node.func.attr == 'getenv'):
            self._handle_getenv(node)
            
        # Check for getenv() (imported directly)
        elif isinstance(node.func, ast.Name) and node.func.id == 'getenv':
            self._handle_getenv(node)
            
        # Check for environ.get() (imported directly)
        elif (isinstance(node.func, ast.Attribute) and
              isinstance(node.func.value, ast.Name) and
              node.func.value.id == 'environ' and
              node.func.attr == 'get'):
            self._handle_environ_get(node)
            
        self.generic_visit(node)
        
    def visit_Subscript(self, node):
        # Check for os.environ['KEY']
        if (isinstance(node.value, ast.Attribute) and
            isinstance(node.value.value, ast.Name) and
            node.value.value.id == 'os' and
            node.value.attr == 'environ'):
            self._handle_environ_subscript(node)
            
        # Check for environ['KEY'] (imported directly)
        elif isinstance(node.value, ast.Name) and node.value.id == 'environ':
            self._handle_environ_subscript(node)
            
        self.generic_visit(node)
        
    def _get_string_value(self, node) -> Optional[str]:
        """Extract string value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # For older Python versions
            return node.s
        return None
        
    def _get_context(self, line_number: int) -> str:
        """Get surrounding context for a line."""
        if not self.source_lines:
            return ""
        
        start = max(0, line_number - 2)
        end = min(len(self.source_lines), line_number + 1)
        
        context_lines = []
        for i in range(start, end):
            if i < len(self.source_lines):
                context_lines.append(f"{i+1}: {self.source_lines[i].rstrip()}")
        
        return "\n".join(context_lines)
        
    def _handle_environ_get(self, node):
        """Handle os.environ.get() calls."""
        if node.args:
            var_name = self._get_string_value(node.args[0])
            if var_name:
                default_value = None
                if len(node.args) > 1:
                    default_value = self._get_string_value(node.args[1])
                    
                usage = EnvVarUsage(
                    name=var_name,
                    file_path=self.file_path,
                    line_number=node.lineno,
                    usage_type='environ.get',
                    default_value=default_value,
                    context=self._get_context(node.lineno)
                )
                self.env_vars.append(usage)
                
    def _handle_getenv(self, node):
        """Handle os.getenv() calls."""
        if node.args:
            var_name = self._get_string_value(node.args[0])
            if var_name:
                default_value = None
                if len(node.args) > 1:
                    default_value = self._get_string_value(node.args[1])
                    
                usage = EnvVarUsage(
                    name=var_name,
                    file_path=self.file_path,
                    line_number=node.lineno,
                    usage_type='getenv',
                    default_value=default_value,
                    context=self._get_context(node.lineno)
                )
                self.env_vars.append(usage)
                
    def _handle_environ_subscript(self, node):
        """Handle os.environ['KEY'] access."""
        var_name = self._get_string_value(node.slice)
        if var_name:
            usage = EnvVarUsage(
                name=var_name,
                file_path=self.file_path,
                line_number=node.lineno,
                usage_type='environ[]',
                default_value=None,  # No default with subscript access
                context=self._get_context(node.lineno)
            )
            self.env_vars.append(usage)


def analyze_python_file(file_path: Path) -> List[EnvVarUsage]:
    """Analyze a Python file for environment variable usage."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
            
        tree = ast.parse(content)
        analyzer = EnvVarAnalyzer(str(file_path))
        analyzer.set_source_lines(lines)
        analyzer.visit(tree)
        
        return analyzer.env_vars
    except Exception as e:
        click.echo(f"Error analyzing {file_path}: {e}", err=True)
        return []


def analyze_config_files(root_dir: Path) -> Dict[str, List[str]]:
    """Analyze common config files for environment variables."""
    config_vars = defaultdict(list)
    
    # Check .env files
    env_files = ['.env', '.env.example', '.env.sample', '.env.template']
    for env_file in env_files:
        file_path = root_dir / env_file
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if '=' in line:
                                var_name = line.split('=', 1)[0].strip()
                                config_vars[env_file].append(var_name)
            except Exception as e:
                click.echo(f"Error reading {file_path}: {e}", err=True)
                
    # Check docker-compose files
    compose_files = ['docker-compose.yml', 'docker-compose.yaml']
    for compose_file in compose_files:
        file_path = root_dir / compose_file
        if file_path.exists():
            try:
                # Simple regex-based extraction
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Find environment variables in format ${VAR_NAME}
                    env_refs = re.findall(r'\$\{([A-Z_][A-Z0-9_]*)\}', content)
                    config_vars[compose_file].extend(env_refs)
            except Exception as e:
                click.echo(f"Error reading {file_path}: {e}", err=True)
                
    return dict(config_vars)


def find_all_env_vars(root_dir: Path, exclude_dirs: Optional[Set[str]] = None) -> Tuple[List[EnvVarUsage], Dict[str, List[str]]]:
    """Find all environment variable usage in a project."""
    if exclude_dirs is None:
        exclude_dirs = {'.git', '.venv', 'venv', 'env', '__pycache__', 
                       'node_modules', 'build', 'dist', '.tox'}
    
    all_env_vars = []
    
    # Analyze Python files
    for file_path in root_dir.rglob('*.py'):
        if not any(excluded in file_path.parts for excluded in exclude_dirs):
            env_vars = analyze_python_file(file_path)
            all_env_vars.extend(env_vars)
    
    # Analyze config files
    config_vars = analyze_config_files(root_dir)
    
    return all_env_vars, config_vars


def analyze_env_vars(env_vars: List[EnvVarUsage], config_vars: Dict[str, List[str]]) -> Dict:
    """Analyze environment variables to categorize them."""
    analysis = {
        "all_vars": set(),
        "required_vars": set(),  # No default value
        "optional_vars": set(),  # Has default value
        "config_defined": set(),  # Defined in config files
        "missing_from_config": set(),
        "unused_config_vars": set(),
        "by_file": defaultdict(list),
        "by_var": defaultdict(list)
    }
    
    # Process code usage
    for usage in env_vars:
        analysis["all_vars"].add(usage.name)
        
        if usage.default_value is None and usage.usage_type == 'environ[]':
            analysis["required_vars"].add(usage.name)
        elif usage.default_value is not None:
            analysis["optional_vars"].add(usage.name)
        else:
            # getenv/environ.get without default are optional (return None)
            analysis["optional_vars"].add(usage.name)
            
        analysis["by_file"][usage.file_path].append(usage)
        analysis["by_var"][usage.name].append(usage)
    
    # Process config files
    for config_file, vars in config_vars.items():
        analysis["config_defined"].update(vars)
    
    # Find missing and unused
    analysis["missing_from_config"] = analysis["all_vars"] - analysis["config_defined"]
    analysis["unused_config_vars"] = analysis["config_defined"] - analysis["all_vars"]
    
    return analysis


def generate_documentation(analysis: Dict, config_vars: Dict[str, List[str]], 
                         root_dir: Path, format: str = "markdown") -> str:
    """Generate environment variable documentation."""
    if format == "json":
        output = {
            "summary": {
                "total": len(analysis["all_vars"]),
                "required": len(analysis["required_vars"]),
                "optional": len(analysis["optional_vars"]),
                "missing_from_config": len(analysis["missing_from_config"]),
                "unused_in_config": len(analysis["unused_config_vars"])
            },
            "variables": {}
        }
        
        for var_name in sorted(analysis["all_vars"]):
            usages = analysis["by_var"][var_name]
            output["variables"][var_name] = {
                "required": var_name in analysis["required_vars"],
                "in_config": var_name in analysis["config_defined"],
                "usages": [usage.to_dict() for usage in usages]
            }
            
        return json.dumps(output, indent=2)
    
    elif format == "markdown":
        doc = []
        doc.append("# Environment Variables Documentation")
        doc.append("")
        doc.append("## Summary")
        doc.append(f"- Total variables: {len(analysis['all_vars'])}")
        doc.append(f"- Required variables: {len(analysis['required_vars'])}")
        doc.append(f"- Optional variables: {len(analysis['optional_vars'])}")
        doc.append(f"- Missing from config: {len(analysis['missing_from_config'])}")
        doc.append(f"- Unused in config: {len(analysis['unused_config_vars'])}")
        doc.append("")
        
        # Required variables
        if analysis["required_vars"]:
            doc.append("## Required Environment Variables")
            doc.append("These variables must be set as they have no default values:")
            doc.append("")
            
            for var_name in sorted(analysis["required_vars"]):
                doc.append(f"### `{var_name}`")
                in_config = "✅" if var_name in analysis["config_defined"] else "❌"
                doc.append(f"- **In config files**: {in_config}")
                doc.append("- **Usage**:")
                
                for usage in analysis["by_var"][var_name]:
                    rel_path = Path(usage.file_path).relative_to(root_dir)
                    doc.append(f"  - `{rel_path}:{usage.line_number}` ({usage.usage_type})")
                doc.append("")
        
        # Optional variables
        if analysis["optional_vars"]:
            doc.append("## Optional Environment Variables")
            doc.append("These variables have default values or return None if not set:")
            doc.append("")
            
            for var_name in sorted(analysis["optional_vars"]):
                doc.append(f"### `{var_name}`")
                in_config = "✅" if var_name in analysis["config_defined"] else "❌"
                doc.append(f"- **In config files**: {in_config}")
                
                # Show default values
                defaults = set()
                for usage in analysis["by_var"][var_name]:
                    if usage.default_value is not None:
                        defaults.add(usage.default_value)
                
                if defaults:
                    doc.append(f"- **Default values**: {', '.join(f'`{d}`' for d in defaults)}")
                
                doc.append("- **Usage**:")
                for usage in analysis["by_var"][var_name]:
                    rel_path = Path(usage.file_path).relative_to(root_dir)
                    doc.append(f"  - `{rel_path}:{usage.line_number}` ({usage.usage_type})")
                doc.append("")
        
        # Missing from config
        if analysis["missing_from_config"]:
            doc.append("## Variables Missing from Config Files")
            doc.append("These variables are used in code but not defined in any config files:")
            doc.append("")
            for var_name in sorted(analysis["missing_from_config"]):
                doc.append(f"- `{var_name}`")
            doc.append("")
        
        # Unused config variables
        if analysis["unused_config_vars"]:
            doc.append("## Unused Config Variables")
            doc.append("These variables are defined in config files but not used in code:")
            doc.append("")
            for var_name in sorted(analysis["unused_config_vars"]):
                doc.append(f"- `{var_name}`")
                for config_file, vars in config_vars.items():
                    if var_name in vars:
                        doc.append(f"  - Defined in: `{config_file}`")
        
        return "\n".join(doc)
    
    else:  # text format
        doc = []
        doc.append("=" * 80)
        doc.append("ENVIRONMENT VARIABLES DOCUMENTATION")
        doc.append("=" * 80)
        doc.append("")
        doc.append(f"Total variables found: {len(analysis['all_vars'])}")
        doc.append(f"Required (no default): {len(analysis['required_vars'])}")
        doc.append(f"Optional (has default): {len(analysis['optional_vars'])}")
        doc.append("")
        
        # Required variables
        if analysis["required_vars"]:
            doc.append("REQUIRED ENVIRONMENT VARIABLES:")
            doc.append("-" * 40)
            for var_name in sorted(analysis["required_vars"]):
                in_config = "[IN CONFIG]" if var_name in analysis["config_defined"] else "[NOT IN CONFIG]"
                doc.append(f"  {var_name:30} {in_config}")
                for usage in analysis["by_var"][var_name][:3]:  # Show first 3 usages
                    rel_path = Path(usage.file_path).relative_to(root_dir)
                    doc.append(f"    - {rel_path}:{usage.line_number}")
            doc.append("")
        
        # Optional variables
        if analysis["optional_vars"]:
            doc.append("OPTIONAL ENVIRONMENT VARIABLES:")
            doc.append("-" * 40)
            for var_name in sorted(analysis["optional_vars"]):
                in_config = "[IN CONFIG]" if var_name in analysis["config_defined"] else "[NOT IN CONFIG]"
                doc.append(f"  {var_name:30} {in_config}")
                
                # Show defaults
                defaults = []
                for usage in analysis["by_var"][var_name]:
                    if usage.default_value is not None:
                        defaults.append(usage.default_value)
                if defaults:
                    doc.append(f"    Defaults: {', '.join(set(defaults))}")
            doc.append("")
        
        # Issues
        if analysis["missing_from_config"] or analysis["unused_config_vars"]:
            doc.append("ISSUES FOUND:")
            doc.append("-" * 40)
            
            if analysis["missing_from_config"]:
                doc.append("  Missing from config files:")
                for var_name in sorted(analysis["missing_from_config"]):
                    doc.append(f"    - {var_name}")
                doc.append("")
            
            if analysis["unused_config_vars"]:
                doc.append("  Defined but unused:")
                for var_name in sorted(analysis["unused_config_vars"]):
                    doc.append(f"    - {var_name}")
        
        return "\n".join(doc)


def validate_env_files(analysis: Dict, root_dir: Path) -> List[str]:
    """Validate environment files and return warnings."""
    warnings = []
    
    # Check if .env.example exists
    env_example = root_dir / '.env.example'
    if not env_example.exists() and analysis["all_vars"]:
        warnings.append("No .env.example file found. Consider creating one for documentation.")
    
    # Check for sensitive variable patterns
    sensitive_patterns = ['KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'CREDENTIAL']
    for var_name in analysis["all_vars"]:
        if any(pattern in var_name.upper() for pattern in sensitive_patterns):
            if var_name in analysis["config_defined"]:
                warnings.append(f"Sensitive variable '{var_name}' found in config. Ensure it's not committed.")
    
    return warnings


@click.command()
@click.argument('path', default='.', type=click.Path(exists=True))
@click.option('--format', 'output_format', type=click.Choice(['text', 'markdown', 'json']), default='markdown',
              help='Output format (default: markdown)')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
@click.option('--validate', is_flag=True, help='Validate environment configuration')
def main(path, output_format, output, validate):
    """Document environment variables in a project."""
    root_dir = Path(path).resolve()
    
    # Find all environment variables
    click.echo(f"Analyzing environment variables in {root_dir}...", err=True)
    env_vars, config_vars = find_all_env_vars(root_dir)
    
    if not env_vars and not config_vars:
        click.echo("No environment variables found.", err=True)
        sys.exit(0)
    
    # Analyze the variables
    analysis = analyze_env_vars(env_vars, config_vars)
    
    # Generate documentation
    documentation = generate_documentation(analysis, config_vars, root_dir, output_format)
    
    # Validate if requested
    if validate:
        warnings = validate_env_files(analysis, root_dir)
        if warnings:
            click.echo("\nValidation Warnings:", err=True)
            for warning in warnings:
                click.echo(f"  - {warning}", err=True)
    
    # Output documentation
    if output:
        with open(output, 'w') as f:
            f.write(documentation)
        click.echo(f"Documentation saved to {output}", err=True)
    else:
        click.echo(documentation)


if __name__ == "__main__":
    main()