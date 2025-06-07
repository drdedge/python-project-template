#!/usr/bin/env python3
"""
TODO/FIXME Extractor
Scans all code files for TODO, FIXME, HACK, NOTE comments
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
import click
import json
from collections import defaultdict


class TodoItem:
    def __init__(self, file_path: str, line_number: int, tag: str, 
                 content: str, author: Optional[str] = None, 
                 date: Optional[str] = None, priority: str = "medium"):
        self.file_path = file_path
        self.line_number = line_number
        self.tag = tag
        self.content = content
        self.author = author
        self.date = date
        self.priority = priority
        
    def to_dict(self) -> Dict:
        return {
            "file": self.file_path,
            "line": self.line_number,
            "tag": self.tag,
            "content": self.content,
            "author": self.author,
            "date": self.date,
            "priority": self.priority
        }


class TodoExtractor:
    # Common tags to search for
    DEFAULT_TAGS = ["TODO", "FIXME", "HACK", "NOTE", "XXX", "OPTIMIZE", "REFACTOR", "WARNING"]
    
    # File extensions to scan
    CODE_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', 
        '.hpp', '.cs', '.go', '.rs', '.swift', '.kt', '.rb', '.php', '.scala',
        '.sh', '.bash', '.zsh', '.yaml', '.yml', '.json', '.xml', '.html',
        '.css', '.scss', '.sass', '.less', '.sql', '.r', '.m', '.mm'
    }
    
    # Priority patterns
    PRIORITY_PATTERNS = {
        "high": re.compile(r'(?:urgent|critical|high|asap|important|!!!)', re.IGNORECASE),
        "low": re.compile(r'(?:low|minor|trivial|sometime|eventually)', re.IGNORECASE)
    }
    
    def __init__(self, tags: Optional[List[str]] = None, 
                 extensions: Optional[Set[str]] = None):
        self.tags = tags or self.DEFAULT_TAGS
        self.extensions = extensions or self.CODE_EXTENSIONS
        self.pattern = self._build_pattern()
        
    def _build_pattern(self) -> re.Pattern:
        """Build regex pattern for finding tags."""
        tags_pattern = '|'.join(re.escape(tag) for tag in self.tags)
        # Match TAG: or TAG( or TAG - followed by content
        return re.compile(
            rf'(?P<tag>{tags_pattern})\s*[:\(\-]\s*(?P<content>.*?)(?:\*/|$)',
            re.IGNORECASE
        )
    
    def _get_git_blame(self, file_path: Path, line_number: int) -> Tuple[Optional[str], Optional[str]]:
        """Get author and date from git blame."""
        try:
            result = subprocess.run(
                ['git', 'blame', '-L', f'{line_number},{line_number}', '--porcelain', str(file_path)],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                author = None
                date = None
                
                for line in lines:
                    if line.startswith('author '):
                        author = line[7:].strip()
                    elif line.startswith('author-time '):
                        timestamp = int(line[12:].strip())
                        date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                
                return author, date
        except:
            pass
        
        return None, None
    
    def _determine_priority(self, content: str) -> str:
        """Determine priority based on content patterns."""
        content_lower = content.lower()
        
        if self.PRIORITY_PATTERNS["high"].search(content_lower):
            return "high"
        elif self.PRIORITY_PATTERNS["low"].search(content_lower):
            return "low"
        
        return "medium"
    
    def extract_from_file(self, file_path: Path, use_git_blame: bool = True) -> List[TodoItem]:
        """Extract TODOs from a single file."""
        todos = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    match = self.pattern.search(line)
                    if match:
                        tag = match.group('tag').upper()
                        content = match.group('content').strip()
                        
                        # Skip empty TODOs
                        if not content:
                            continue
                        
                        # Get git blame info if requested
                        author, date = None, None
                        if use_git_blame:
                            author, date = self._get_git_blame(file_path, line_num)
                        
                        # Determine priority
                        priority = self._determine_priority(content)
                        
                        todo = TodoItem(
                            file_path=str(file_path),
                            line_number=line_num,
                            tag=tag,
                            content=content,
                            author=author,
                            date=date,
                            priority=priority
                        )
                        todos.append(todo)
        
        except Exception as e:
            click.echo(f"Error reading {file_path}: {e}", err=True)
        
        return todos
    
    def extract_from_directory(self, root_dir: Path, 
                             exclude_dirs: Optional[Set[str]] = None,
                             use_git_blame: bool = True) -> List[TodoItem]:
        """Extract TODOs from all files in a directory."""
        if exclude_dirs is None:
            exclude_dirs = {'.git', '.venv', 'venv', 'env', '__pycache__', 
                          'node_modules', 'build', 'dist', '.tox'}
        
        todos = []
        
        for file_path in root_dir.rglob('*'):
            # Skip directories
            if file_path.is_dir():
                continue
            
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue
            
            # Check file extension
            if file_path.suffix not in self.extensions:
                continue
            
            file_todos = self.extract_from_file(file_path, use_git_blame)
            todos.extend(file_todos)
        
        return todos


def group_todos(todos: List[TodoItem]) -> Dict[str, List[TodoItem]]:
    """Group TODOs by various criteria."""
    groups = {
        "by_tag": defaultdict(list),
        "by_file": defaultdict(list),
        "by_author": defaultdict(list),
        "by_priority": defaultdict(list)
    }
    
    for todo in todos:
        groups["by_tag"][todo.tag].append(todo)
        groups["by_file"][todo.file_path].append(todo)
        groups["by_priority"][todo.priority].append(todo)
        if todo.author:
            groups["by_author"][todo.author].append(todo)
    
    return groups


def generate_report(todos: List[TodoItem], groups: Dict[str, Dict], 
                   root_dir: Path, format: str = "text") -> str:
    """Generate a report of found TODOs."""
    if format == "json":
        return json.dumps({
            "summary": {
                "total": len(todos),
                "by_tag": {tag: len(items) for tag, items in groups["by_tag"].items()},
                "by_priority": {priority: len(items) for priority, items in groups["by_priority"].items()}
            },
            "todos": [todo.to_dict() for todo in todos]
        }, indent=2)
    
    elif format == "markdown":
        report = []
        report.append("# TODO/FIXME Report")
        report.append(f"\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total items: {len(todos)}\n")
        
        # Summary by tag
        report.append("## Summary by Tag")
        for tag, items in sorted(groups["by_tag"].items()):
            report.append(f"- **{tag}**: {len(items)} items")
        
        # High priority items
        high_priority = groups["by_priority"].get("high", [])
        if high_priority:
            report.append("\n## High Priority Items")
            for todo in high_priority:
                rel_path = Path(todo.file_path).relative_to(root_dir)
                report.append(f"\n### {todo.tag}: {todo.content}")
                report.append(f"- **File**: `{rel_path}:{todo.line_number}`")
                if todo.author:
                    report.append(f"- **Author**: {todo.author}")
                if todo.date:
                    report.append(f"- **Date**: {todo.date}")
        
        # All items by file
        report.append("\n## All Items by File")
        for file_path, items in sorted(groups["by_file"].items()):
            rel_path = Path(file_path).relative_to(root_dir)
            report.append(f"\n### {rel_path}")
            for todo in sorted(items, key=lambda x: x.line_number):
                report.append(f"- **Line {todo.line_number}** [{todo.tag}]: {todo.content}")
                if todo.priority == "high":
                    report.append("  - 🚨 **HIGH PRIORITY**")
        
        return "\n".join(report)
    
    else:  # text format
        report = []
        report.append("=" * 80)
        report.append("TODO/FIXME EXTRACTION REPORT")
        report.append("=" * 80)
        report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total items found: {len(todos)}")
        report.append("")
        
        # Summary by tag
        report.append("SUMMARY BY TAG:")
        for tag, items in sorted(groups["by_tag"].items()):
            report.append(f"  {tag:10} {len(items):4} items")
        report.append("")
        
        # Summary by priority
        report.append("SUMMARY BY PRIORITY:")
        for priority in ["high", "medium", "low"]:
            count = len(groups["by_priority"].get(priority, []))
            report.append(f"  {priority:10} {count:4} items")
        report.append("")
        
        # High priority items
        high_priority = groups["by_priority"].get("high", [])
        if high_priority:
            report.append("HIGH PRIORITY ITEMS:")
            report.append("-" * 40)
            for todo in high_priority:
                rel_path = Path(todo.file_path).relative_to(root_dir)
                report.append(f"  {rel_path}:{todo.line_number}")
                report.append(f"    [{todo.tag}] {todo.content}")
                if todo.author:
                    report.append(f"    Author: {todo.author} ({todo.date or 'unknown date'})")
                report.append("")
        
        # All items grouped by file
        report.append("ALL ITEMS BY FILE:")
        report.append("-" * 40)
        for file_path, items in sorted(groups["by_file"].items()):
            rel_path = Path(file_path).relative_to(root_dir)
            report.append(f"\n{rel_path}:")
            for todo in sorted(items, key=lambda x: x.line_number):
                priority_marker = " [!]" if todo.priority == "high" else ""
                report.append(f"  Line {todo.line_number:4}: [{todo.tag}] {todo.content}{priority_marker}")
        
        return "\n".join(report)


@click.command()
@click.argument('path', default='.', type=click.Path(exists=True))
@click.option('--tags', multiple=True, help='Custom tags to search for (default: TODO, FIXME, HACK, etc.)')
@click.option('--format', 'output_format', type=click.Choice(['text', 'json', 'markdown']), default='text',
              help='Output format (default: text)')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
@click.option('--no-git-blame', is_flag=True, help='Disable git blame lookup for author/date')
@click.option('--priority', type=click.Choice(['all', 'high', 'medium', 'low']), default='all',
              help='Filter by priority (default: all)')
@click.option('--extensions', multiple=True, help='File extensions to scan (e.g., .py .js)')
def main(path, tags, output_format, output, no_git_blame, priority, extensions):
    """Extract TODO/FIXME comments from code."""
    root_dir = Path(path).resolve()
    
    # Create extractor
    extensions_set = None
    if extensions:
        extensions_set = set(ext if ext.startswith('.') else f'.{ext}' for ext in extensions)
    
    extractor = TodoExtractor(tags=list(tags) if tags else None, extensions=extensions_set)
    
    # Extract TODOs
    click.echo(f"Scanning {root_dir} for {', '.join(extractor.tags)}...", err=True)
    todos = extractor.extract_from_directory(root_dir, use_git_blame=not no_git_blame)
    
    # Filter by priority if requested
    if priority != "all":
        todos = [todo for todo in todos if todo.priority == priority]
    
    if not todos:
        click.echo("No TODO items found.", err=True)
        sys.exit(0)
    
    # Group TODOs
    groups = group_todos(todos)
    
    # Generate report
    report = generate_report(todos, groups, root_dir, output_format)
    
    # Output report
    if output:
        with open(output, 'w') as f:
            f.write(report)
        click.echo(f"Report saved to {output}", err=True)
    else:
        click.echo(report)


if __name__ == "__main__":
    main()