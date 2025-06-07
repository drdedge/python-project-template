#!/usr/bin/env python3
"""
Dependency Graph Visualizer
Creates visual graphs showing module dependencies
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional, Any
from collections import defaultdict, deque
import click
import json
import textwrap
from dataclasses import dataclass, field


@dataclass
class Module:
    name: str
    path: Path
    imports: Set[str] = field(default_factory=set)
    imported_by: Set[str] = field(default_factory=set)
    external_imports: Set[str] = field(default_factory=set)
    complexity_score: float = 0.0
    
    
@dataclass 
class DependencyEdge:
    source: str
    target: str
    import_names: List[str] = field(default_factory=list)
    is_circular: bool = False


class ImportAnalyzer(ast.NodeVisitor):
    """Analyze imports in a Python file."""
    
    def __init__(self, module_name: str, package_root: Path):
        self.module_name = module_name
        self.package_root = package_root
        self.imports = set()
        self.external_imports = set()
        self.import_details = defaultdict(list)
        
    def visit_Import(self, node):
        for alias in node.names:
            import_name = alias.name
            self.import_details[import_name].append(alias.asname or alias.name)
            
            if self._is_internal_module(import_name):
                self.imports.add(import_name)
            else:
                self.external_imports.add(import_name)
                
    def visit_ImportFrom(self, node):
        if node.module:
            # Handle relative imports
            if node.level > 0:
                # Relative import
                parts = self.module_name.split('.')
                if node.level <= len(parts):
                    base = '.'.join(parts[:-node.level])
                    if node.module:
                        import_name = f"{base}.{node.module}"
                    else:
                        import_name = base
                else:
                    import_name = node.module
            else:
                import_name = node.module
                
            # Record what was imported
            for alias in node.names:
                if alias.name != '*':
                    self.import_details[import_name].append(alias.name)
                    
            if self._is_internal_module(import_name):
                self.imports.add(import_name)
            else:
                self.external_imports.add(import_name)
                
    def _is_internal_module(self, module_name: str) -> bool:
        """Check if a module is internal to the project."""
        # Check if it's a relative import pattern
        if module_name.startswith('.'):
            return True
            
        # Check if the module exists in the package root
        parts = module_name.split('.')
        path = self.package_root
        
        for part in parts:
            path = path / part
            if path.with_suffix('.py').exists() or (path.is_dir() and (path / '__init__.py').exists()):
                continue
            else:
                return False
                
        return True


class DependencyGraphBuilder:
    """Build a dependency graph for a Python project."""
    
    def __init__(self, root_path: Path, exclude_dirs: Optional[Set[str]] = None):
        self.root_path = root_path
        self.exclude_dirs = exclude_dirs or {'.venv', 'venv', 'env', '__pycache__', 
                                           '.git', 'build', 'dist', '.tox', 'node_modules'}
        self.modules: Dict[str, Module] = {}
        self.edges: List[DependencyEdge] = []
        self.circular_dependencies: List[List[str]] = []
        
    def build_graph(self) -> Tuple[Dict[str, Module], List[DependencyEdge]]:
        """Build the dependency graph."""
        # First pass: discover all modules
        self._discover_modules()
        
        # Second pass: analyze imports
        self._analyze_imports()
        
        # Detect circular dependencies
        self._detect_circular_dependencies()
        
        # Calculate complexity scores
        self._calculate_complexity_scores()
        
        return self.modules, self.edges
        
    def _discover_modules(self):
        """Discover all Python modules in the project."""
        for py_file in self.root_path.rglob('*.py'):
            if any(excluded in py_file.parts for excluded in self.exclude_dirs):
                continue
                
            module_name = self._path_to_module_name(py_file)
            if module_name:
                self.modules[module_name] = Module(name=module_name, path=py_file)
                
    def _path_to_module_name(self, path: Path) -> Optional[str]:
        """Convert file path to module name."""
        try:
            rel_path = path.relative_to(self.root_path)
            
            # Remove .py extension
            if rel_path.suffix == '.py':
                rel_path = rel_path.with_suffix('')
                
            # Convert path to module name
            parts = list(rel_path.parts)
            
            # Handle __init__.py
            if parts[-1] == '__init__':
                parts = parts[:-1]
                
            if not parts:
                return None
                
            return '.'.join(parts)
            
        except ValueError:
            return None
            
    def _analyze_imports(self):
        """Analyze imports in all modules."""
        for module_name, module in self.modules.items():
            try:
                with open(module.path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                analyzer = ImportAnalyzer(module_name, self.root_path)
                analyzer.visit(tree)
                
                # Update module imports
                module.imports = analyzer.imports
                module.external_imports = analyzer.external_imports
                
                # Create edges
                for imported_module in analyzer.imports:
                    if imported_module in self.modules:
                        # Update imported_by
                        self.modules[imported_module].imported_by.add(module_name)
                        
                        # Create edge
                        edge = DependencyEdge(
                            source=module_name,
                            target=imported_module,
                            import_names=analyzer.import_details.get(imported_module, [])
                        )
                        self.edges.append(edge)
                        
            except Exception as e:
                click.echo(f"Error analyzing {module.path}: {e}", err=True)
                
    def _detect_circular_dependencies(self):
        """Detect circular dependencies using DFS."""
        # Build adjacency list
        graph = defaultdict(set)
        for edge in self.edges:
            graph[edge.source].add(edge.target)
            
        # Track visited nodes
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
                    
                    # Mark edges as circular
                    for i in range(len(cycle) - 1):
                        for edge in self.edges:
                            if edge.source == cycle[i] and edge.target == cycle[i + 1]:
                                edge.is_circular = True
                                
            rec_stack.remove(node)
            
        # Run DFS from each unvisited node
        for module in self.modules:
            if module not in visited:
                dfs(module, [])
                
        self.circular_dependencies = cycles
        
    def _calculate_complexity_scores(self):
        """Calculate complexity scores for modules."""
        for module_name, module in self.modules.items():
            # Factors for complexity:
            # 1. Number of dependencies
            # 2. Number of dependents
            # 3. External dependencies
            # 4. Circular dependencies
            
            score = 0.0
            
            # Direct dependencies
            score += len(module.imports) * 1.0
            
            # Modules that depend on this
            score += len(module.imported_by) * 0.5
            
            # External dependencies (higher weight)
            score += len(module.external_imports) * 2.0
            
            # Circular dependencies (highest weight)
            circular_count = sum(1 for edge in self.edges 
                               if edge.source == module_name and edge.is_circular)
            score += circular_count * 5.0
            
            module.complexity_score = score


class DependencyVisualizer:
    """Generate various visualization formats for dependencies."""
    
    def __init__(self, modules: Dict[str, Module], edges: List[DependencyEdge], 
                 circular_deps: List[List[str]]):
        self.modules = modules
        self.edges = edges
        self.circular_deps = circular_deps
        
    def to_mermaid(self, show_external: bool = False) -> str:
        """Generate Mermaid diagram."""
        lines = ["graph TD"]
        
        # Add nodes
        for module_name, module in self.modules.items():
            label = module_name.replace('.', '_')
            
            # Style based on characteristics
            if any(module_name in cycle for cycle in self.circular_deps):
                lines.append(f'    {label}["{module_name}"]:::circular')
            elif module.complexity_score > 10:
                lines.append(f'    {label}["{module_name}"]:::complex')
            else:
                lines.append(f'    {label}["{module_name}"]')
                
        # Add edges
        for edge in self.edges:
            source = edge.source.replace('.', '_')
            target = edge.target.replace('.', '_')
            
            if edge.is_circular:
                lines.append(f'    {source} -->|circular| {target}')
            else:
                lines.append(f'    {source} --> {target}')
                
        # Add external dependencies if requested
        if show_external:
            external_nodes = set()
            for module in self.modules.values():
                for ext in module.external_imports:
                    external_nodes.add(ext)
                    
            for ext in external_nodes:
                label = ext.replace('.', '_')
                lines.append(f'    {label}("{ext}"):::external')
                
            for module_name, module in self.modules.items():
                source = module_name.replace('.', '_')
                for ext in module.external_imports:
                    target = ext.replace('.', '_')
                    lines.append(f'    {source} -.-> {target}')
                    
        # Add styles
        lines.extend([
            '',
            '    classDef circular fill:#ff6b6b,stroke:#c92a2a,stroke-width:2px',
            '    classDef complex fill:#ffe066,stroke:#f59f00,stroke-width:2px', 
            '    classDef external fill:#e9ecef,stroke:#868e96,stroke-width:1px,stroke-dasharray: 5 5'
        ])
        
        return '\n'.join(lines)
        
    def to_graphviz(self, show_external: bool = False) -> str:
        """Generate Graphviz DOT format."""
        lines = ['digraph dependencies {']
        lines.append('    rankdir=TB;')
        lines.append('    node [shape=box];')
        lines.append('')
        
        # Add nodes with styling
        for module_name, module in self.modules.items():
            attrs = []
            
            if any(module_name in cycle for cycle in self.circular_deps):
                attrs.extend(['fillcolor="#ff6b6b"', 'style=filled'])
            elif module.complexity_score > 10:
                attrs.extend(['fillcolor="#ffe066"', 'style=filled'])
                
            if attrs:
                lines.append(f'    "{module_name}" [{", ".join(attrs)}];')
                
        # Add edges
        for edge in self.edges:
            attrs = []
            if edge.is_circular:
                attrs.extend(['color=red', 'penwidth=2'])
                
            if attrs:
                lines.append(f'    "{edge.source}" -> "{edge.target}" [{", ".join(attrs)}];')
            else:
                lines.append(f'    "{edge.source}" -> "{edge.target}";')
                
        # Add external dependencies if requested
        if show_external:
            lines.append('')
            lines.append('    // External dependencies')
            
            external_nodes = set()
            for module in self.modules.values():
                external_nodes.update(module.external_imports)
                
            for ext in external_nodes:
                lines.append(f'    "{ext}" [shape=ellipse, style=dashed];')
                
            for module_name, module in self.modules.items():
                for ext in module.external_imports:
                    lines.append(f'    "{module_name}" -> "{ext}" [style=dashed];')
                    
        lines.append('}')
        
        return '\n'.join(lines)
        
    def to_json(self) -> str:
        """Generate JSON representation."""
        nodes = []
        links = []
        
        # Create nodes
        for module_name, module in self.modules.items():
            node = {
                'id': module_name,
                'imports': list(module.imports),
                'imported_by': list(module.imported_by),
                'external_imports': list(module.external_imports),
                'complexity_score': module.complexity_score,
                'is_circular': any(module_name in cycle for cycle in self.circular_deps)
            }
            nodes.append(node)
            
        # Create links
        for edge in self.edges:
            link = {
                'source': edge.source,
                'target': edge.target,
                'imports': edge.import_names,
                'is_circular': edge.is_circular
            }
            links.append(link)
            
        return json.dumps({
            'nodes': nodes,
            'links': links,
            'circular_dependencies': self.circular_deps
        }, indent=2)
        
    def to_text_report(self) -> str:
        """Generate a text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("DEPENDENCY ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary
        lines.append(f"Total modules: {len(self.modules)}")
        lines.append(f"Total dependencies: {len(self.edges)}")
        lines.append(f"Circular dependency groups: {len(self.circular_deps)}")
        lines.append("")
        
        # Circular dependencies
        if self.circular_deps:
            lines.append("CIRCULAR DEPENDENCIES:")
            lines.append("-" * 40)
            for i, cycle in enumerate(self.circular_deps, 1):
                lines.append(f"{i}. {' -> '.join(cycle)}")
            lines.append("")
            
        # Most complex modules
        complex_modules = sorted(self.modules.values(), 
                               key=lambda m: m.complexity_score, 
                               reverse=True)[:10]
                               
        lines.append("MOST COMPLEX MODULES:")
        lines.append("-" * 40)
        lines.append(f"{'Module':<50} {'Score':>10} {'Deps':>8} {'Used By':>8}")
        lines.append("-" * 80)
        
        for module in complex_modules:
            if module.complexity_score > 0:
                lines.append(
                    f"{module.name:<50} {module.complexity_score:>10.1f} "
                    f"{len(module.imports):>8} {len(module.imported_by):>8}"
                )
                
        lines.append("")
        
        # Tightly coupled components
        lines.append("TIGHTLY COUPLED COMPONENTS:")
        lines.append("-" * 40)
        
        # Find modules that import each other
        coupled = set()
        for edge in self.edges:
            reverse_edge = next((e for e in self.edges 
                               if e.source == edge.target and e.target == edge.source), None)
            if reverse_edge and (edge.target, edge.source) not in coupled:
                coupled.add((edge.source, edge.target))
                lines.append(f"- {edge.source} <-> {edge.target}")
                
        if not coupled:
            lines.append("No tightly coupled components found.")
            
        lines.append("")
        
        # External dependencies summary
        all_external = set()
        for module in self.modules.values():
            all_external.update(module.external_imports)
            
        lines.append(f"EXTERNAL DEPENDENCIES ({len(all_external)} unique):")
        lines.append("-" * 40)
        
        # Group by package
        by_package = defaultdict(int)
        for ext in all_external:
            package = ext.split('.')[0]
            by_package[package] += 1
            
        for package in sorted(by_package.keys()):
            lines.append(f"  {package}: {by_package[package]} imports")
            
        return '\n'.join(lines)


@click.command()
@click.argument('path', default='.', type=click.Path(exists=True))
@click.option('--format', 'output_format', type=click.Choice(['text', 'mermaid', 'graphviz', 'json']),
              default='text', help='Output format (default: text)')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
@click.option('--show-external', is_flag=True, help='Include external dependencies in visualization')
@click.option('--exclude', multiple=True, help='Additional directories to exclude')
def main(path, output_format, output, show_external, exclude):
    """Visualize Python project dependencies.
    
    Examples:
    
      dependency_visualizer                          # Generate text report
    
      dependency_visualizer --format mermaid         # Generate Mermaid diagram
    
      dependency_visualizer --format graphviz        # Generate Graphviz DOT file
    
      dependency_visualizer --format json            # Generate JSON data
    
      dependency_visualizer --show-external          # Include external dependencies
    
      dependency_visualizer --output graph.dot       # Save to file
    
    Output formats:
      text     - Human-readable analysis report
      mermaid  - Mermaid diagram (can be rendered on GitHub)
      graphviz - DOT format for Graphviz
      json     - Machine-readable JSON data
    """
    root_path = Path(path).resolve()
        
    # Build dependency graph
    exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', 
                   'build', 'dist', '.tox', 'node_modules'}
    exclude_dirs.update(exclude)
    
    click.echo(f"Analyzing dependencies in {root_path}...", err=True)
    builder = DependencyGraphBuilder(root_path, exclude_dirs)
    modules, edges = builder.build_graph()
    
    if not modules:
        click.echo("No Python modules found.", err=True)
        sys.exit(0)
        
    click.echo(f"Found {len(modules)} modules with {len(edges)} dependencies", err=True)
    
    # Generate visualization
    visualizer = DependencyVisualizer(modules, edges, builder.circular_dependencies)
    
    if output_format == "text":
        output_content = visualizer.to_text_report()
    elif output_format == "mermaid":
        output_content = visualizer.to_mermaid(show_external)
    elif output_format == "graphviz":
        output_content = visualizer.to_graphviz(show_external)
    elif output_format == "json":
        output_content = visualizer.to_json()
        
    # Output results
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(output_content)
        click.echo(f"Output saved to {output}", err=True)
    else:
        click.echo(output_content)


if __name__ == "__main__":
    main()