#!/usr/bin/env python3
"""
Add Relative Filepath Comments
==============================

This utility adds relative filepath comments as the first line of all Python files
in the project. This helps developers quickly identify which file they're looking at
when viewing code snippets or working with multiple files.

The script:
- Finds all .py files in the project
- Adds a comment with the relative path from the project root
- Preserves existing content including shebangs
- Skips files that already have the filepath comment
- Handles different file encodings gracefully

Usage:
------
python utils/add_filepath_comments.py [--dry-run] [--root-dir /path/to/project]

Options:
    --dry-run: Show what would be changed without modifying files
    --root-dir: Specify the project root directory (default: current directory)

Example:
    # Preview changes
    python utils/add_filepath_comments.py --dry-run
    
    # Apply changes
    python utils/add_filepath_comments.py
"""

import os
import sys
import click
from pathlib import Path
from typing import List, Tuple, Optional


def get_relative_path_comment(file_path: Path, root_dir: Path) -> str:
    """
    Generate the relative filepath comment for a Python file.
    
    Args:
        file_path: Path to the Python file
        root_dir: Root directory of the project
        
    Returns:
        Comment string with relative path
    """
    try:
        relative_path = file_path.relative_to(root_dir)
        # Use forward slashes even on Windows for consistency
        relative_str = str(relative_path).replace('\\', '/')
        return f"# {relative_str}\n"
    except ValueError:
        # File is not under root_dir
        return f"# {file_path.name}\n"


def needs_filepath_comment(file_path: Path, root_dir: Path) -> bool:
    """
    Check if a file needs a filepath comment added.
    
    Args:
        file_path: Path to check
        root_dir: Root directory of the project
        
    Returns:
        True if the file needs a filepath comment
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            
        # Check if first line is already a filepath comment
        expected_comment = get_relative_path_comment(file_path, root_dir).strip()
        if first_line == expected_comment.strip():
            return False
            
        # Also check if it's a variation of the filepath comment
        relative_path = str(file_path.relative_to(root_dir)).replace('\\', '/')
        if first_line.startswith("#") and relative_path in first_line:
            return False
            
        return True
        
    except Exception:
        # If we can't read the file, assume it needs the comment
        return True


def add_filepath_comment_to_file(file_path: Path, root_dir: Path, dry_run: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Add filepath comment to a single Python file.
    
    Args:
        file_path: Path to the Python file
        root_dir: Root directory of the project
        dry_run: If True, don't actually modify the file
        
    Returns:
        Tuple of (success, error_message)
    """
    if not needs_filepath_comment(file_path, root_dir):
        return True, "Already has filepath comment"
        
    filepath_comment = get_relative_path_comment(file_path, root_dir)
    
    try:
        # Read the entire file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if file starts with shebang
        lines = content.splitlines(keepends=True)
        if not lines:
            # Empty file
            new_content = filepath_comment
        elif lines[0].startswith("#!"):
            # File has shebang, insert comment after it
            new_content = lines[0] + filepath_comment
            if len(lines) > 1:
                # Add blank line if the next line isn't already blank
                if lines[1].strip():
                    new_content += "\n"
                new_content += ''.join(lines[1:])
        else:
            # No shebang, add comment at the beginning
            new_content = filepath_comment
            # Add blank line if the first line isn't already blank
            if lines and lines[0].strip():
                new_content += "\n"
            new_content += content
            
        if dry_run:
            click.echo(f"Would add to {file_path}: {filepath_comment.strip()}")
        else:
            # Write the modified content back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            click.echo(f"Added to {file_path}: {filepath_comment.strip()}")
            
        return True, None
        
    except Exception as e:
        error_msg = f"Error processing {file_path}: {str(e)}"
        click.echo(f"ERROR: {error_msg}", err=True)
        return False, error_msg


def find_python_files(root_dir: Path, exclude_dirs: Optional[List[str]] = None) -> List[Path]:
    """
    Find all Python files in the project directory.
    
    Args:
        root_dir: Root directory to search
        exclude_dirs: List of directory names to exclude
        
    Returns:
        List of Python file paths
    """
    if exclude_dirs is None:
        exclude_dirs = [
            '__pycache__', '.git', '.venv', 'venv', 'env',
            'build', 'dist', '.tox', 'htmlcov', '.pytest_cache',
            '.mypy_cache', 'site-packages', '.idea', '.vscode',
            'node_modules', '.claude'
        ]
        
    python_files = []
    
    for file_path in root_dir.rglob('*.py'):
        # Check if file is in an excluded directory
        if any(excluded in file_path.parts for excluded in exclude_dirs):
            continue
            
        python_files.append(file_path)
        
    return sorted(python_files)


@click.command()
@click.option('--dry-run', is_flag=True, help='Preview changes without modifying files')
@click.option('--root-dir', type=click.Path(exists=True, path_type=Path), default=Path.cwd(),
              help='Root directory of the project (default: current directory)')
@click.option('--exclude', multiple=True, help='Additional directories to exclude')
def main(dry_run, root_dir, exclude):
    """Add relative filepath comments to all Python files in the project.
    
    Examples:
    
      add_filepath_comments.py                    # Add filepath comments to all .py files
    
      add_filepath_comments.py --dry-run          # Preview changes without modifying files
    
      add_filepath_comments.py --root-dir ../     # Use parent directory as root
    
    The script will:
    - Find all .py files in the project
    - Skip files that already have filepath comments
    - Add comments after shebangs if present
    - Preserve all existing content
    """
    # Resolve root directory
    root_dir = root_dir.resolve()
        
    click.echo(f"Project root: {root_dir}")
    if dry_run:
        click.echo("DRY RUN - No files will be modified")
    click.echo()
    
    # Find all Python files
    exclude_dirs = None
    if exclude:
        exclude_dirs = [
            '__pycache__', '.git', '.venv', 'venv', 'env',
            'build', 'dist', '.tox', 'htmlcov', '.pytest_cache',
            '.mypy_cache', 'site-packages', '.idea', '.vscode',
            'node_modules', '.claude'
        ] + list(exclude)
        
    python_files = find_python_files(root_dir, exclude_dirs)
    
    if not python_files:
        click.echo("No Python files found")
        return
        
    click.echo(f"Found {len(python_files)} Python files")
    click.echo()
    
    # Process each file
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for file_path in python_files:
        success, error_msg = add_filepath_comment_to_file(file_path, root_dir, dry_run)
        
        if success:
            if error_msg == "Already has filepath comment":
                skip_count += 1
            else:
                success_count += 1
        else:
            error_count += 1
            
    # Print summary
    click.echo()
    click.echo("Summary:")
    click.echo(f"  Files processed: {success_count}")
    click.echo(f"  Files skipped (already have comment): {skip_count}")
    click.echo(f"  Errors: {error_count}")
    
    if dry_run:
        click.echo("\nThis was a dry run. No files were modified.")
        click.echo("Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()