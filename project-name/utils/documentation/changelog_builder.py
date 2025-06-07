#!/usr/bin/env python3
"""
Changelog Builder / Release Notes Generator
Generates changelogs from git commits using conventional commits
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from collections import defaultdict
import argparse
import json
from dataclasses import dataclass, field


@dataclass
class Commit:
    sha: str
    message: str
    author: str
    date: datetime
    type: str
    scope: Optional[str] = None
    description: str = ""
    body: Optional[str] = None
    breaking: bool = False
    breaking_description: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    
    
class ConventionalCommitParser:
    """Parse commits following Conventional Commits specification."""
    
    # Conventional commit pattern: type(scope): description
    COMMIT_PATTERN = re.compile(
        r'^(?P<type>\w+)(?:\((?P<scope>[\w\-\.]+)\))?\s*:\s*(?P<description>.+)$',
        re.MULTILINE
    )
    
    # Issue reference patterns
    ISSUE_PATTERNS = [
        re.compile(r'#(\d+)'),  # GitHub style: #123
        re.compile(r'(?:fixes|closes|resolves)\s+#(\d+)', re.IGNORECASE),
        re.compile(r'(?:JIRA|ISSUE)-(\d+)'),  # JIRA style
        re.compile(r'(?:fix|close|resolve)\s+(?:issue\s+)?(\d+)', re.IGNORECASE),
    ]
    
    # Breaking change patterns
    BREAKING_PATTERNS = [
        re.compile(r'BREAKING CHANGE:\s*(.+)', re.IGNORECASE),
        re.compile(r'BREAKING:\s*(.+)', re.IGNORECASE),
    ]
    
    # Valid commit types and their display names
    COMMIT_TYPES = {
        'feat': 'Features',
        'fix': 'Bug Fixes',
        'docs': 'Documentation',
        'style': 'Styles',
        'refactor': 'Code Refactoring',
        'perf': 'Performance Improvements',
        'test': 'Tests',
        'build': 'Build System',
        'ci': 'Continuous Integration',
        'chore': 'Chores',
        'revert': 'Reverts',
    }
    
    def parse(self, sha: str, message: str, author: str, date: datetime) -> Optional[Commit]:
        """Parse a commit message into a Commit object."""
        lines = message.strip().split('\n')
        if not lines:
            return None
            
        # Parse the first line
        match = self.COMMIT_PATTERN.match(lines[0])
        if not match:
            # Not a conventional commit
            return None
            
        commit = Commit(
            sha=sha,
            message=message,
            author=author,
            date=date,
            type=match.group('type'),
            scope=match.group('scope'),
            description=match.group('description').strip()
        )
        
        # Parse body and footer
        if len(lines) > 1:
            body_lines = []
            for line in lines[1:]:
                # Check for breaking changes
                for pattern in self.BREAKING_PATTERNS:
                    breaking_match = pattern.match(line)
                    if breaking_match:
                        commit.breaking = True
                        commit.breaking_description = breaking_match.group(1)
                        continue
                        
                # Check if commit type has ! suffix (alternative breaking change notation)
                if lines[0].find('!:') > -1:
                    commit.breaking = True
                    
                body_lines.append(line)
                
            commit.body = '\n'.join(body_lines).strip()
        
        # Extract issue references from entire message
        for pattern in self.ISSUE_PATTERNS:
            issues = pattern.findall(message)
            commit.issues.extend(issues)
            
        # Remove duplicates
        commit.issues = list(set(commit.issues))
        
        return commit


class GitLogReader:
    """Read and parse git log."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        
    def get_tags(self) -> List[Tuple[str, str]]:
        """Get all tags with their commit SHAs."""
        try:
            result = subprocess.run(
                ['git', 'tag', '--sort=-version:refname', '--format=%(refname:short) %(objectname)'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            tags = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(' ')
                    if len(parts) == 2:
                        tags.append((parts[0], parts[1]))
                        
            return tags
            
        except subprocess.CalledProcessError:
            return []
            
    def get_commits(self, from_ref: Optional[str] = None, 
                   to_ref: str = 'HEAD') -> List[Dict[str, str]]:
        """Get commits between two refs."""
        # Build git log command
        cmd = ['git', 'log', '--pretty=format:%H%n%an%n%aI%n%s%n%b%n==END==']
        
        if from_ref:
            cmd.append(f'{from_ref}..{to_ref}')
        else:
            cmd.append(to_ref)
            
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            commits = []
            entries = result.stdout.strip().split('\n==END==\n')
            
            for entry in entries:
                if not entry.strip():
                    continue
                    
                lines = entry.strip().split('\n')
                if len(lines) >= 4:
                    # Reconstruct the full message including body
                    message_lines = lines[3:]
                    message = '\n'.join(message_lines).strip()
                    
                    commits.append({
                        'sha': lines[0],
                        'author': lines[1],
                        'date': lines[2],
                        'message': message
                    })
                    
            return commits
            
        except subprocess.CalledProcessError as e:
            print(f"Error reading git log: {e}", file=sys.stderr)
            return []
            
    def get_remote_url(self) -> Optional[str]:
        """Get the remote repository URL."""
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except:
            return None


class ChangelogBuilder:
    """Build changelog from commits."""
    
    def __init__(self, repo_path: Path, repo_url: Optional[str] = None):
        self.repo_path = repo_path
        self.parser = ConventionalCommitParser()
        self.git_reader = GitLogReader(repo_path)
        self.repo_url = repo_url or self._detect_repo_url()
        
    def _detect_repo_url(self) -> Optional[str]:
        """Detect repository URL from git remote."""
        url = self.git_reader.get_remote_url()
        if url:
            # Convert SSH URLs to HTTPS
            if url.startswith('git@github.com:'):
                url = url.replace('git@github.com:', 'https://github.com/')
            if url.endswith('.git'):
                url = url[:-4]
        return url
        
    def _format_commit_link(self, sha: str) -> str:
        """Format a commit SHA as a link if repo URL is available."""
        short_sha = sha[:7]
        if self.repo_url:
            return f"[{short_sha}]({self.repo_url}/commit/{sha})"
        return short_sha
        
    def _format_issue_link(self, issue: str) -> str:
        """Format an issue number as a link if repo URL is available."""
        if self.repo_url and issue.isdigit():
            return f"[#{issue}]({self.repo_url}/issues/{issue})"
        return f"#{issue}"
        
    def build_changelog(self, from_tag: Optional[str] = None, 
                       to_ref: str = 'HEAD',
                       include_all: bool = False) -> str:
        """Build changelog for commits between tags/refs."""
        # Get commits
        commits_data = self.git_reader.get_commits(from_tag, to_ref)
        
        # Parse commits
        commits = []
        for data in commits_data:
            try:
                date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
            except:
                date = datetime.now()
                
            commit = self.parser.parse(
                sha=data['sha'],
                message=data['message'],
                author=data['author'],
                date=date
            )
            
            if commit and (include_all or commit.type in self.parser.COMMIT_TYPES):
                commits.append(commit)
                
        if not commits:
            return "No conventional commits found in the specified range.\n"
            
        # Group commits by type
        grouped = defaultdict(list)
        breaking_changes = []
        
        for commit in commits:
            if commit.breaking:
                breaking_changes.append(commit)
            grouped[commit.type].append(commit)
            
        # Build changelog
        lines = []
        
        # Add breaking changes section if any
        if breaking_changes:
            lines.append("### ⚠ BREAKING CHANGES\n")
            for commit in breaking_changes:
                desc = commit.breaking_description or commit.description
                lines.append(f"* {desc}")
                if commit.scope:
                    lines.append(f"  * Scope: {commit.scope}")
                lines.append(f"  * Commit: {self._format_commit_link(commit.sha)}")
                lines.append("")
                
        # Add sections for each commit type
        for commit_type, display_name in self.parser.COMMIT_TYPES.items():
            if commit_type in grouped and grouped[commit_type]:
                lines.append(f"### {display_name}\n")
                
                # Group by scope within type
                by_scope = defaultdict(list)
                no_scope = []
                
                for commit in grouped[commit_type]:
                    if commit.scope:
                        by_scope[commit.scope].append(commit)
                    else:
                        no_scope.append(commit)
                        
                # Format commits with scope
                for scope in sorted(by_scope.keys()):
                    lines.append(f"* **{scope}**")
                    for commit in by_scope[scope]:
                        lines.append(f"  * {commit.description} ({self._format_commit_link(commit.sha)})")
                        if commit.issues:
                            issues = ', '.join(self._format_issue_link(issue) for issue in commit.issues)
                            lines.append(f"    * Issues: {issues}")
                            
                # Format commits without scope
                for commit in no_scope:
                    lines.append(f"* {commit.description} ({self._format_commit_link(commit.sha)})")
                    if commit.issues:
                        issues = ', '.join(self._format_issue_link(issue) for issue in commit.issues)
                        lines.append(f"  * Issues: {issues}")
                        
                lines.append("")
                
        return '\n'.join(lines)
        
    def build_full_changelog(self, output_format: str = 'markdown') -> str:
        """Build a full changelog with all releases."""
        tags = self.git_reader.get_tags()
        
        if output_format == 'json':
            return self._build_json_changelog(tags)
            
        # Markdown format
        lines = []
        lines.append("# Changelog\n")
        lines.append("All notable changes to this project will be documented in this file.\n")
        lines.append("The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),")
        lines.append("and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n")
        
        # Add unreleased section if there are commits after the last tag
        if tags:
            unreleased = self.build_changelog(from_tag=tags[0][0], to_ref='HEAD')
            if unreleased.strip() and unreleased != "No conventional commits found in the specified range.\n":
                lines.append("## [Unreleased]\n")
                lines.append(unreleased)
                
        # Add sections for each release
        for i, (tag, _) in enumerate(tags):
            # Get the date of the tag
            try:
                result = subprocess.run(
                    ['git', 'log', '-1', '--format=%aI', tag],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                date_str = result.stdout.strip()
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                date_formatted = date.strftime('%Y-%m-%d')
            except:
                date_formatted = 'Unknown'
                
            lines.append(f"## [{tag}] - {date_formatted}\n")
            
            # Get commits for this release
            from_tag = tags[i + 1][0] if i + 1 < len(tags) else None
            changelog = self.build_changelog(from_tag=from_tag, to_ref=tag)
            lines.append(changelog)
            
        # Add links section
        if self.repo_url and tags:
            lines.append("\n")
            lines.append("[Unreleased]: " + 
                        f"{self.repo_url}/compare/{tags[0][0]}...HEAD")
            
            for i, (tag, _) in enumerate(tags):
                if i + 1 < len(tags):
                    prev_tag = tags[i + 1][0]
                    lines.append(f"[{tag}]: {self.repo_url}/compare/{prev_tag}...{tag}")
                else:
                    lines.append(f"[{tag}]: {self.repo_url}/releases/tag/{tag}")
                    
        return '\n'.join(lines)
        
    def _build_json_changelog(self, tags: List[Tuple[str, str]]) -> str:
        """Build changelog in JSON format."""
        releases = []
        
        # Add unreleased section
        if tags:
            commits_data = self.git_reader.get_commits(from_tag=tags[0][0], to_ref='HEAD')
            unreleased_commits = []
            
            for data in commits_data:
                try:
                    date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                except:
                    date = datetime.now()
                    
                commit = self.parser.parse(
                    sha=data['sha'],
                    message=data['message'],
                    author=data['author'],
                    date=date
                )
                
                if commit:
                    unreleased_commits.append({
                        'sha': commit.sha,
                        'type': commit.type,
                        'scope': commit.scope,
                        'description': commit.description,
                        'breaking': commit.breaking,
                        'issues': commit.issues,
                        'author': commit.author,
                        'date': commit.date.isoformat()
                    })
                    
            if unreleased_commits:
                releases.append({
                    'version': 'unreleased',
                    'date': None,
                    'commits': unreleased_commits
                })
                
        # Add tagged releases
        for i, (tag, sha) in enumerate(tags):
            from_tag = tags[i + 1][0] if i + 1 < len(tags) else None
            commits_data = self.git_reader.get_commits(from_tag=from_tag, to_ref=tag)
            
            release_commits = []
            for data in commits_data:
                try:
                    date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                except:
                    date = datetime.now()
                    
                commit = self.parser.parse(
                    sha=data['sha'],
                    message=data['message'],
                    author=data['author'],
                    date=date
                )
                
                if commit:
                    release_commits.append({
                        'sha': commit.sha,
                        'type': commit.type,
                        'scope': commit.scope,
                        'description': commit.description,
                        'breaking': commit.breaking,
                        'issues': commit.issues,
                        'author': commit.author,
                        'date': commit.date.isoformat()
                    })
                    
            # Get release date
            try:
                result = subprocess.run(
                    ['git', 'log', '-1', '--format=%aI', tag],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                release_date = result.stdout.strip()
            except:
                release_date = None
                
            releases.append({
                'version': tag,
                'date': release_date,
                'commits': release_commits
            })
            
        return json.dumps({
            'repository': self.repo_url,
            'releases': releases
        }, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate changelog from git commits using Conventional Commits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Generate full changelog
  %(prog)s --from v1.0.0             # Changes since v1.0.0
  %(prog)s --from v1.0.0 --to v2.0.0 # Changes between versions
  %(prog)s --format json             # Output as JSON
  %(prog)s --output CHANGELOG.md     # Save to file
  %(prog)s --include-all             # Include non-conventional commits
  
Conventional Commit Format:
  type(scope): description
  
  [body]
  
  [footer]
  
Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
"""
    )
    
    parser.add_argument("path", nargs="?", default=".",
                       help="Path to git repository (default: current directory)")
    parser.add_argument("--from", dest="from_ref",
                       help="Starting reference (tag/commit)")
    parser.add_argument("--to", default="HEAD",
                       help="Ending reference (default: HEAD)")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                       help="Output format (default: markdown)")
    parser.add_argument("--output", "-o",
                       help="Output file (default: stdout)")
    parser.add_argument("--include-all", action="store_true",
                       help="Include commits that don't follow Conventional Commits")
    parser.add_argument("--repo-url",
                       help="Repository URL for generating links")
    
    args = parser.parse_args()
    
    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"Error: Path {repo_path} does not exist", file=sys.stderr)
        sys.exit(1)
        
    # Check if it's a git repository
    if not (repo_path / '.git').exists():
        print(f"Error: {repo_path} is not a git repository", file=sys.stderr)
        sys.exit(1)
        
    # Build changelog
    builder = ChangelogBuilder(repo_path, args.repo_url)
    
    if args.from_ref:
        # Generate changelog for specific range
        output = builder.build_changelog(
            from_tag=args.from_ref,
            to_ref=args.to,
            include_all=args.include_all
        )
        
        if args.format == 'json':
            # Wrap in JSON structure
            output = json.dumps({
                'from': args.from_ref,
                'to': args.to,
                'changelog': output
            }, indent=2)
    else:
        # Generate full changelog
        output = builder.build_full_changelog(args.format)
        
    # Output results
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Changelog saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()