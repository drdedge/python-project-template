#!/usr/bin/env python3
"""
Tree Diagram Generator
Outputs a tree diagram of the project structure suitable for markdown
"""

import os
import sys
from pathlib import Path
from typing import List, Set, Optional, Tuple
import click
import fnmatch
from dataclasses import dataclass


@dataclass
class TreeNode:
    name: str
    path: Path
    is_dir: bool
    is_ignored: bool = False
    children: List['TreeNode'] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class GitignoreParser:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.patterns = []
        self.negation_patterns = []
        self._load_gitignore()
        
    def _load_gitignore(self):
        """Load patterns from .gitignore file."""
        gitignore_path = self.root_dir / '.gitignore'
        if not gitignore_path.exists():
            return
            
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                        
                    # Handle negation patterns
                    if line.startswith('!'):
                        self.negation_patterns.append(line[1:])
                    else:
                        self.patterns.append(line)
        except Exception as e:
            click.echo(f"Warning: Could not read .gitignore: {e}", err=True)
    
    def is_ignored(self, path: Path) -> bool:
        """Check if a path should be ignored based on gitignore patterns."""
        # Get relative path from root
        try:
            rel_path = path.relative_to(self.root_dir)
        except ValueError:
            return False
            
        path_str = str(rel_path).replace('\\', '/')
        path_parts = path_str.split('/')
        
        # Check against patterns
        for pattern in self.patterns:
            # Directory-only pattern
            if pattern.endswith('/'):
                pattern = pattern[:-1]
                if path.is_dir():
                    if self._matches_pattern(path_str, pattern, path_parts):
                        # Check negation patterns
                        for neg_pattern in self.negation_patterns:
                            if self._matches_pattern(path_str, neg_pattern, path_parts):
                                return False
                        return True
            else:
                if self._matches_pattern(path_str, pattern, path_parts):
                    # Check negation patterns
                    for neg_pattern in self.negation_patterns:
                        if self._matches_pattern(path_str, neg_pattern, path_parts):
                            return False
                    return True
                    
        return False
    
    def _matches_pattern(self, path_str: str, pattern: str, path_parts: List[str]) -> bool:
        """Check if a path matches a gitignore pattern."""
        # Exact match
        if path_str == pattern:
            return True
            
        # Pattern with ** (matches any number of directories)
        if '**' in pattern:
            pattern = pattern.replace('**', '*')
            
        # Pattern starting with / (root-relative)
        if pattern.startswith('/'):
            pattern = pattern[1:]
            return fnmatch.fnmatch(path_str, pattern)
            
        # Pattern might match any part of the path
        if '/' in pattern:
            return fnmatch.fnmatch(path_str, pattern)
        else:
            # Pattern without / matches any file/dir with that name
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
                    
        return False


class TreeGenerator:
    def __init__(self, show_hidden: bool = False, max_depth: Optional[int] = None,
                 exclude_patterns: Optional[List[str]] = None, show_files: bool = True,
                 use_gitignore: bool = True):
        self.show_hidden = show_hidden
        self.max_depth = max_depth
        self.exclude_patterns = exclude_patterns or []
        self.show_files = show_files
        self.use_gitignore = use_gitignore
        self.gitignore_parser = None
        
    def generate_tree(self, root_path: Path) -> TreeNode:
        """Generate a tree structure starting from root_path."""
        if self.use_gitignore:
            self.gitignore_parser = GitignoreParser(root_path)
            
        return self._build_tree(root_path, depth=0)
    
    def _build_tree(self, path: Path, depth: int) -> TreeNode:
        """Recursively build tree structure."""
        is_ignored = self.gitignore_parser.is_ignored(path) if self.gitignore_parser else False
        node = TreeNode(name=path.name, path=path, is_dir=path.is_dir(), is_ignored=is_ignored)
        
        # Check depth limit
        if self.max_depth is not None and depth >= self.max_depth:
            return node
            
        # Process directory contents
        if path.is_dir():
            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                
                for item in items:
                    # Skip hidden files/dirs if not showing them
                    if not self.show_hidden and item.name.startswith('.'):
                        continue
                        
                    # Skip based on exclude patterns
                    if any(fnmatch.fnmatch(item.name, pattern) for pattern in self.exclude_patterns):
                        continue
                        
                    # Skip files if not showing them
                    if not self.show_files and item.is_file():
                        continue
                        
                    child_node = self._build_tree(item, depth + 1)
                    node.children.append(child_node)
                    
            except PermissionError:
                pass
                
        return node
    
    def format_tree(self, node: TreeNode, prefix: str = "", is_last: bool = True, 
                    is_root: bool = True) -> List[str]:
        """Format tree structure for display."""
        lines = []
        
        # Format current node
        if is_root:
            display_name = node.name
            if node.is_ignored:
                display_name += " *.gitignore"
            lines.append(display_name)
        else:
            connector = "└── " if is_last else "├── "
            display_name = node.name
            if node.is_dir:
                display_name += "/"
            if node.is_ignored:
                display_name += " *.gitignore"
            lines.append(prefix + connector + display_name)
        
        # Format children
        if node.children:
            extension = "    " if is_last else "│   "
            child_prefix = prefix + extension if not is_root else ""
            
            for i, child in enumerate(node.children):
                is_last_child = i == len(node.children) - 1
                child_lines = self.format_tree(child, child_prefix, is_last_child, False)
                lines.extend(child_lines)
                
        return lines
    
    def format_markdown_tree(self, node: TreeNode, indent: int = 0, 
                           is_root: bool = True) -> List[str]:
        """Format tree structure for markdown with proper indentation."""
        lines = []
        
        # Format current node
        if is_root:
            display_name = f"**{node.name}**"
            if node.is_ignored:
                display_name += " *(gitignored)*"
            lines.append(display_name)
        else:
            indent_str = "  " * indent
            display_name = node.name
            if node.is_dir:
                display_name = f"**{display_name}/**"
            if node.is_ignored:
                display_name += " *(gitignored)*"
            lines.append(f"{indent_str}- {display_name}")
        
        # Format children
        if node.children:
            child_indent = 0 if is_root else indent + 1
            for child in node.children:
                child_lines = self.format_markdown_tree(child, child_indent, False)
                lines.extend(child_lines)
                
        return lines


def generate_tree_output(root_path: Path, format: str = "tree", **kwargs) -> str:
    """Generate tree output in specified format."""
    generator = TreeGenerator(**kwargs)
    tree = generator.generate_tree(root_path)
    
    if format == "markdown":
        lines = generator.format_markdown_tree(tree)
    else:  # tree format
        lines = generator.format_tree(tree)
        
    return "\n".join(lines)


@click.command()
@click.argument('path', default='.', type=click.Path(exists=True, file_okay=False))
@click.option('--format', 'output_format', type=click.Choice(['tree', 'markdown']), default='tree',
              help='Output format (default: tree)')
@click.option('--max-depth', type=int, help='Maximum depth to traverse')
@click.option('--no-files', is_flag=True, help='Show only directories')
@click.option('--show-hidden', is_flag=True, help='Show hidden files and directories')
@click.option('--no-gitignore', is_flag=True, help="Don't use .gitignore patterns")
@click.option('--exclude', multiple=True, help='Additional patterns to exclude')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
def main(path, output_format, max_depth, no_files, show_hidden, no_gitignore, exclude, output):
    """Generate a tree diagram of project structure.
    
    Examples:
    
      tree_generator                     # Show tree of current directory
    
      tree_generator /path/to/project    # Show tree of specific directory
    
      tree_generator --no-files          # Show only directories
    
      tree_generator --max-depth 2       # Limit depth to 2 levels
    
      tree_generator --format markdown   # Output in markdown format
    
      tree_generator --show-hidden       # Include hidden files/directories
    
      tree_generator --no-gitignore      # Don't use .gitignore patterns
    """
    root_path = Path(path).resolve()
    
    # Generate tree
    output_content = generate_tree_output(
        root_path,
        format=output_format,
        show_files=not no_files,
        show_hidden=show_hidden,
        max_depth=max_depth,
        exclude_patterns=list(exclude) if exclude else [],
        use_gitignore=not no_gitignore
    )
    
    # Output results
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(output_content)
        click.echo(f"Tree saved to {output}", err=True)
    else:
        click.echo(output_content)


if __name__ == "__main__":
    main()