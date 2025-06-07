#!/usr/bin/env python3
"""
API Documentation Generator
Extracts FastAPI/Flask endpoints and generates documentation
"""

import ast
import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
import argparse
from collections import defaultdict
from dataclasses import dataclass, asdict


@dataclass
class EndpointInfo:
    path: str
    method: str
    function_name: str
    file_path: str
    line_number: int
    description: Optional[str] = None
    parameters: List[Dict[str, Any]] = None
    response_model: Optional[str] = None
    status_code: Optional[int] = None
    tags: List[str] = None
    deprecated: bool = False
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []
        if self.tags is None:
            self.tags = []


class APIAnalyzer(ast.NodeVisitor):
    def __init__(self, file_path: str, framework: str = "auto"):
        self.file_path = file_path
        self.framework = framework
        self.endpoints = []
        self.current_class = None
        self.imports = {}
        self.routers = {}
        self.app_instances = set()
        
    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports[name] = alias.name
            
    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            module = node.module or ""
            self.imports[name] = f"{module}.{alias.name}"
            
    def visit_Assign(self, node):
        # Detect app instances and routers
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name):
                func_name = node.value.func.id
                
                # FastAPI app or router
                if func_name in ['FastAPI', 'APIRouter']:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if func_name == 'FastAPI':
                                self.app_instances.add(target.id)
                            else:
                                self.routers[target.id] = self._extract_router_prefix(node.value)
                                
                # Flask app
                elif func_name == 'Flask':
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.app_instances.add(target.id)
                            
        self.generic_visit(node)
        
    def visit_ClassDef(self, node):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_FunctionDef(self, node):
        # Check decorators for route definitions
        for decorator in node.decorator_list:
            endpoint_info = self._analyze_decorator(decorator, node)
            if endpoint_info:
                self.endpoints.append(endpoint_info)
                
        self.generic_visit(node)
        
    def _extract_router_prefix(self, call_node) -> str:
        """Extract prefix from APIRouter() call."""
        for keyword in call_node.keywords:
            if keyword.arg == 'prefix':
                if isinstance(keyword.value, ast.Constant):
                    return keyword.value.value
                elif isinstance(keyword.value, ast.Str):
                    return keyword.value.s
        return ""
        
    def _analyze_decorator(self, decorator, func_node) -> Optional[EndpointInfo]:
        """Analyze decorator to extract endpoint information."""
        method = None
        path = None
        tags = []
        status_code = None
        response_model = None
        deprecated = False
        
        # Handle different decorator patterns
        if isinstance(decorator, ast.Call):
            # @app.get("/path") or @router.post("/path")
            if isinstance(decorator.func, ast.Attribute):
                instance_name = None
                if isinstance(decorator.func.value, ast.Name):
                    instance_name = decorator.func.value.id
                    
                method = decorator.func.attr.upper()
                
                # Check if this is a valid HTTP method
                if method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                    # Extract path
                    if decorator.args:
                        path = self._get_string_value(decorator.args[0])
                        
                    # Extract additional parameters from keywords
                    for keyword in decorator.keywords:
                        if keyword.arg == 'tags' and isinstance(keyword.value, ast.List):
                            tags = [self._get_string_value(elt) for elt in keyword.value.elts]
                        elif keyword.arg == 'status_code':
                            status_code = self._get_int_value(keyword.value)
                        elif keyword.arg == 'response_model':
                            response_model = self._get_name_value(keyword.value)
                        elif keyword.arg == 'deprecated':
                            deprecated = self._get_bool_value(keyword.value)
                            
                    # Add router prefix if applicable
                    if instance_name in self.routers and path:
                        prefix = self.routers[instance_name]
                        if prefix and not path.startswith(prefix):
                            path = prefix + path
                            
            # Flask @app.route decorator
            elif isinstance(decorator.func, ast.Name) and decorator.func.id == 'route':
                if decorator.args:
                    path = self._get_string_value(decorator.args[0])
                    # Extract methods from keywords
                    for keyword in decorator.keywords:
                        if keyword.arg == 'methods' and isinstance(keyword.value, ast.List):
                            methods = [self._get_string_value(elt) for elt in keyword.value.elts]
                            method = methods[0] if methods else 'GET'
                            
        # Handle simple decorators like @deprecated
        elif isinstance(decorator, ast.Name):
            if decorator.id == 'deprecated':
                deprecated = True
                
        if path and method:
            # Extract function documentation
            description = ast.get_docstring(func_node)
            
            # Extract parameters
            parameters = self._extract_parameters(func_node)
            
            return EndpointInfo(
                path=path,
                method=method,
                function_name=func_node.name,
                file_path=self.file_path,
                line_number=func_node.lineno,
                description=description,
                parameters=parameters,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                deprecated=deprecated
            )
            
        return None
        
    def _extract_parameters(self, func_node) -> List[Dict[str, Any]]:
        """Extract function parameters and their types."""
        parameters = []
        
        for arg in func_node.args.args:
            if arg.arg not in ['self', 'cls']:
                param = {
                    'name': arg.arg,
                    'type': None,
                    'default': None,
                    'required': True
                }
                
                # Extract type annotation
                if arg.annotation:
                    param['type'] = self._get_annotation_string(arg.annotation)
                    
                parameters.append(param)
                
        # Check for default values
        defaults_start = len(func_node.args.args) - len(func_node.args.defaults)
        for i, default in enumerate(func_node.args.defaults):
            param_index = defaults_start + i
            if param_index < len(parameters):
                parameters[param_index]['default'] = self._get_default_value(default)
                parameters[param_index]['required'] = False
                
        return parameters
        
    def _get_string_value(self, node) -> Optional[str]:
        """Extract string value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):
            return node.s
        return None
        
    def _get_int_value(self, node) -> Optional[int]:
        """Extract integer value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        elif isinstance(node, ast.Num):
            return node.n
        return None
        
    def _get_bool_value(self, node) -> bool:
        """Extract boolean value from AST node."""
        if isinstance(node, ast.Constant):
            return bool(node.value)
        elif isinstance(node, ast.NameConstant):
            return bool(node.value)
        return False
        
    def _get_name_value(self, node) -> Optional[str]:
        """Extract name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name_value(node.value)}.{node.attr}"
        return None
        
    def _get_annotation_string(self, node) -> str:
        """Convert annotation AST node to string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Subscript):
            value = self._get_annotation_string(node.value)
            slice_value = self._get_annotation_string(node.slice)
            return f"{value}[{slice_value}]"
        elif isinstance(node, ast.Attribute):
            value = self._get_annotation_string(node.value)
            return f"{value}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        return "Any"
        
    def _get_default_value(self, node) -> Any:
        """Extract default value from AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.List):
            return []
        elif isinstance(node, ast.Dict):
            return {}
        return None


def detect_framework(root_dir: Path) -> str:
    """Detect which web framework is being used."""
    # Check imports in Python files
    framework_indicators = {
        'fastapi': ['from fastapi', 'import fastapi', 'FastAPI('],
        'flask': ['from flask', 'import flask', 'Flask('],
        'django': ['from django', 'import django', 'django.urls'],
        'starlette': ['from starlette', 'import starlette'],
        'aiohttp': ['from aiohttp', 'import aiohttp'],
    }
    
    framework_scores = defaultdict(int)
    
    for py_file in root_dir.rglob('*.py'):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for framework, indicators in framework_indicators.items():
                for indicator in indicators:
                    if indicator in content:
                        framework_scores[framework] += 1
                        
        except:
            pass
            
    # Check requirements files
    req_files = list(root_dir.glob('requirements*.txt')) + [root_dir / 'pyproject.toml']
    for req_file in req_files:
        if req_file.exists():
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    
                for framework in framework_indicators:
                    if framework in content:
                        framework_scores[framework] += 5
                        
            except:
                pass
                
    if framework_scores:
        return max(framework_scores, key=framework_scores.get)
        
    return 'unknown'


def analyze_api_files(root_dir: Path, framework: str = "auto", 
                     exclude_dirs: Optional[Set[str]] = None) -> List[EndpointInfo]:
    """Analyze all Python files for API endpoints."""
    if exclude_dirs is None:
        exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', 
                       'build', 'dist', '.tox', 'node_modules'}
    
    if framework == "auto":
        framework = detect_framework(root_dir)
        print(f"Detected framework: {framework}", file=sys.stderr)
        
    all_endpoints = []
    
    for py_file in root_dir.rglob('*.py'):
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            analyzer = APIAnalyzer(str(py_file), framework)
            analyzer.visit(tree)
            
            all_endpoints.extend(analyzer.endpoints)
            
        except Exception as e:
            print(f"Error analyzing {py_file}: {e}", file=sys.stderr)
            
    return all_endpoints


def generate_openapi_spec(endpoints: List[EndpointInfo], project_name: str = "API") -> Dict:
    """Generate OpenAPI specification from endpoints."""
    openapi = {
        "openapi": "3.0.0",
        "info": {
            "title": project_name,
            "version": "1.0.0",
            "description": f"API documentation for {project_name}"
        },
        "paths": {},
        "components": {
            "schemas": {}
        },
        "tags": []
    }
    
    # Collect all unique tags
    all_tags = set()
    for endpoint in endpoints:
        all_tags.update(endpoint.tags)
        
    openapi["tags"] = [{"name": tag} for tag in sorted(all_tags)]
    
    # Group endpoints by path
    paths = defaultdict(dict)
    
    for endpoint in endpoints:
        method = endpoint.method.lower()
        
        operation = {
            "operationId": endpoint.function_name,
            "summary": endpoint.function_name.replace('_', ' ').title(),
            "tags": endpoint.tags,
            "deprecated": endpoint.deprecated
        }
        
        if endpoint.description:
            operation["description"] = endpoint.description
            
        # Add parameters
        if endpoint.parameters:
            operation["parameters"] = []
            for param in endpoint.parameters:
                param_spec = {
                    "name": param["name"],
                    "in": "query",  # Simplified - would need more analysis
                    "required": param["required"],
                    "schema": {"type": "string"}  # Simplified
                }
                if param["type"]:
                    param_spec["schema"]["type"] = _map_python_type_to_openapi(param["type"])
                    
                operation["parameters"].append(param_spec)
                
        # Add response
        operation["responses"] = {
            str(endpoint.status_code or 200): {
                "description": "Successful response"
            }
        }
        
        paths[endpoint.path][method] = operation
        
    openapi["paths"] = dict(paths)
    
    return openapi


def _map_python_type_to_openapi(python_type: str) -> str:
    """Map Python type hints to OpenAPI types."""
    type_mapping = {
        'str': 'string',
        'int': 'integer',
        'float': 'number',
        'bool': 'boolean',
        'list': 'array',
        'dict': 'object',
        'List': 'array',
        'Dict': 'object',
    }
    
    for py_type, openapi_type in type_mapping.items():
        if python_type.startswith(py_type):
            return openapi_type
            
    return 'string'  # Default


def generate_markdown_docs(endpoints: List[EndpointInfo], root_dir: Path) -> str:
    """Generate Markdown documentation for endpoints."""
    doc = []
    doc.append("# API Documentation")
    doc.append("")
    
    # Group endpoints by tags
    tagged_endpoints = defaultdict(list)
    untagged_endpoints = []
    
    for endpoint in endpoints:
        if endpoint.tags:
            for tag in endpoint.tags:
                tagged_endpoints[tag].append(endpoint)
        else:
            untagged_endpoints.append(endpoint)
            
    # Document tagged endpoints
    for tag in sorted(tagged_endpoints.keys()):
        doc.append(f"## {tag}")
        doc.append("")
        
        for endpoint in sorted(tagged_endpoints[tag], key=lambda e: (e.path, e.method)):
            _add_endpoint_to_doc(doc, endpoint, root_dir)
            
    # Document untagged endpoints
    if untagged_endpoints:
        doc.append("## Other Endpoints")
        doc.append("")
        
        for endpoint in sorted(untagged_endpoints, key=lambda e: (e.path, e.method)):
            _add_endpoint_to_doc(doc, endpoint, root_dir)
            
    return "\n".join(doc)


def _add_endpoint_to_doc(doc: List[str], endpoint: EndpointInfo, root_dir: Path):
    """Add a single endpoint to the documentation."""
    # Header
    deprecated = " ⚠️ **DEPRECATED**" if endpoint.deprecated else ""
    doc.append(f"### {endpoint.method} {endpoint.path}{deprecated}")
    doc.append("")
    
    # Description
    if endpoint.description:
        doc.append(endpoint.description)
        doc.append("")
        
    # Implementation details
    rel_path = Path(endpoint.file_path).relative_to(root_dir)
    doc.append(f"**Function**: `{endpoint.function_name}` in `{rel_path}:{endpoint.line_number}`")
    doc.append("")
    
    # Parameters
    if endpoint.parameters:
        doc.append("**Parameters**:")
        doc.append("")
        for param in endpoint.parameters:
            required = "required" if param["required"] else "optional"
            param_type = param["type"] or "any"
            default = f" = {param['default']}" if param["default"] is not None else ""
            doc.append(f"- `{param['name']}` ({param_type}, {required}){default}")
        doc.append("")
        
    # Response
    status = endpoint.status_code or 200
    doc.append(f"**Response**: {status}")
    if endpoint.response_model:
        doc.append(f"- Model: `{endpoint.response_model}`")
    doc.append("")
    doc.append("---")
    doc.append("")


def find_undocumented_endpoints(endpoints: List[EndpointInfo]) -> List[EndpointInfo]:
    """Find endpoints that lack documentation."""
    return [e for e in endpoints if not e.description]


def main():
    parser = argparse.ArgumentParser(description="Generate API documentation")
    parser.add_argument("path", nargs="?", default=".",
                       help="Path to analyze (default: current directory)")
    parser.add_argument("--format", choices=["markdown", "openapi", "json", "summary"],
                       default="markdown", help="Output format")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--framework", choices=["auto", "fastapi", "flask", "django"],
                       default="auto", help="Web framework to analyze")
    parser.add_argument("--project-name", default="API",
                       help="Project name for documentation")
    
    args = parser.parse_args()
    
    root_dir = Path(args.path).resolve()
    if not root_dir.exists():
        print(f"Error: Path {root_dir} does not exist", file=sys.stderr)
        sys.exit(1)
        
    # Analyze API files
    print(f"Analyzing API endpoints in {root_dir}...", file=sys.stderr)
    endpoints = analyze_api_files(root_dir, args.framework)
    
    if not endpoints:
        print("No API endpoints found.", file=sys.stderr)
        sys.exit(0)
        
    print(f"Found {len(endpoints)} endpoints", file=sys.stderr)
    
    # Generate output based on format
    output = ""
    
    if args.format == "markdown":
        output = generate_markdown_docs(endpoints, root_dir)
    elif args.format == "openapi":
        spec = generate_openapi_spec(endpoints, args.project_name)
        output = json.dumps(spec, indent=2)
    elif args.format == "json":
        output = json.dumps([asdict(e) for e in endpoints], indent=2)
    elif args.format == "summary":
        # Generate summary
        undocumented = find_undocumented_endpoints(endpoints)
        
        summary = []
        summary.append("API SUMMARY")
        summary.append("=" * 40)
        summary.append(f"Total endpoints: {len(endpoints)}")
        summary.append(f"Undocumented endpoints: {len(undocumented)}")
        summary.append("")
        
        # Group by method
        by_method = defaultdict(int)
        for e in endpoints:
            by_method[e.method] += 1
            
        summary.append("Endpoints by method:")
        for method in sorted(by_method):
            summary.append(f"  {method}: {by_method[method]}")
            
        summary.append("")
        
        # List undocumented
        if undocumented:
            summary.append("Undocumented endpoints:")
            for e in undocumented:
                rel_path = Path(e.file_path).relative_to(root_dir)
                summary.append(f"  {e.method} {e.path} ({rel_path}:{e.line_number})")
                
        output = "\n".join(summary)
        
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Documentation saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()