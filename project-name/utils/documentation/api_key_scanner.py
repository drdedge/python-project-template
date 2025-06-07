#!/usr/bin/env python3
"""
API Key Scanner
Searches for hardcoded API keys, secrets, and sensitive information in code
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import click
import json
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class SecurityFinding:
    file_path: str
    line_number: int
    line_content: str
    finding_type: str
    confidence: str  # high, medium, low
    pattern_name: str
    recommendation: str
    
    def to_dict(self) -> Dict:
        return {
            "file": self.file_path,
            "line": self.line_number,
            "content": self.line_content.strip(),
            "type": self.finding_type,
            "confidence": self.confidence,
            "pattern": self.pattern_name,
            "recommendation": self.recommendation
        }


class SecurityPatterns:
    """Collection of patterns to detect various types of secrets."""
    
    # High confidence patterns - very likely to be actual secrets
    HIGH_CONFIDENCE_PATTERNS = [
        # AWS
        (r'AKIA[0-9A-Z]{16}', 'AWS Access Key ID', 'Remove AWS access key and use environment variables or AWS IAM roles'),
        (r'[0-9a-zA-Z/+=]{40}', 'AWS Secret Key (context-dependent)', 'Remove AWS secret key and use environment variables or AWS IAM roles'),
        
        # Azure
        (r'DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[^;]+;', 'Azure Storage Connection String', 'Use Azure Key Vault or environment variables'),
        
        # Private Keys
        (r'-----BEGIN RSA PRIVATE KEY-----', 'RSA Private Key', 'Never commit private keys. Use key management services'),
        (r'-----BEGIN OPENSSH PRIVATE KEY-----', 'SSH Private Key', 'Never commit SSH keys. Use SSH agent or key management'),
        (r'-----BEGIN DSA PRIVATE KEY-----', 'DSA Private Key', 'Never commit private keys. Use key management services'),
        (r'-----BEGIN EC PRIVATE KEY-----', 'EC Private Key', 'Never commit private keys. Use key management services'),
        
        # API Keys with specific formats
        (r'sk-[a-zA-Z0-9]{48}', 'OpenAI API Key', 'Use environment variables: os.getenv("OPENAI_API_KEY")'),
        (r'AIza[0-9A-Za-z\\-_]{35}', 'Google API Key', 'Use environment variables or Google Secret Manager'),
        (r'[0-9a-f]{32}-us[0-9]{1,2}', 'Mailchimp API Key', 'Use environment variables for Mailchimp keys'),
        (r'key-[0-9a-zA-Z]{32}', 'Generic API Key Format', 'Move API keys to environment variables'),
        (r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID (possible secret)', 'Verify if this UUID is sensitive'),
        
        # Tokens
        (r'ghp_[0-9a-zA-Z]{36}', 'GitHub Personal Access Token', 'Use GitHub secrets or environment variables'),
        (r'ghs_[0-9a-zA-Z]{36}', 'GitHub Server Token', 'Use GitHub secrets or environment variables'),
        (r'github_pat_[0-9a-zA-Z_]{82}', 'GitHub Fine-grained PAT', 'Use GitHub secrets or environment variables'),
    ]
    
    # Medium confidence patterns - might be secrets depending on context
    MEDIUM_CONFIDENCE_PATTERNS = [
        # Variable assignments that look like secrets
        (r'(?:api[_-]?key|apikey)\s*=\s*["\']([^"\']+)["\']', 'API Key Assignment', 'Use os.getenv() or config management'),
        (r'(?:secret|password|passwd|pwd)\s*=\s*["\']([^"\']+)["\']', 'Secret/Password Assignment', 'Never hardcode passwords. Use environment variables'),
        (r'(?:token|auth[_-]?token)\s*=\s*["\']([^"\']+)["\']', 'Token Assignment', 'Use environment variables for tokens'),
        (r'(?:private[_-]?key|priv[_-]?key)\s*=\s*["\']([^"\']+)["\']', 'Private Key Assignment', 'Use key management services'),
        
        # URLs with embedded credentials
        (r'https?://[^:]+:[^@]+@[^/]+', 'URL with embedded credentials', 'Remove credentials from URLs. Use proper authentication'),
        (r'ftp://[^:]+:[^@]+@[^/]+', 'FTP URL with credentials', 'Use secure credential storage for FTP'),
        (r'mongodb://[^:]+:[^@]+@[^/]+', 'MongoDB URL with credentials', 'Use environment variables for database URLs'),
        (r'postgresql://[^:]+:[^@]+@[^/]+', 'PostgreSQL URL with credentials', 'Use environment variables for database URLs'),
        (r'mysql://[^:]+:[^@]+@[^/]+', 'MySQL URL with credentials', 'Use environment variables for database URLs'),
        
        # Base64 encoded strings (might contain secrets)
        (r'[A-Za-z0-9+/]{40,}={0,2}', 'Base64 encoded string (possible secret)', 'Verify content and move to secure storage if sensitive'),
        
        # Hexadecimal strings (common for keys/tokens)
        (r'[0-9a-fA-F]{32,}', 'Hex string (possible key/token)', 'Verify if this is a secret and move to environment variables'),
    ]
    
    # Low confidence patterns - need context to determine if they're actual secrets
    LOW_CONFIDENCE_PATTERNS = [
        # Generic key-like patterns
        (r'["\'][0-9a-zA-Z]{32,}["\']', 'Long string (possible key)', 'Verify if this is a secret'),
        (r'[A-Z_]{2,}_KEY\s*=', 'Key-like variable name', 'Check if value contains actual secret'),
        (r'[A-Z_]{2,}_SECRET\s*=', 'Secret-like variable name', 'Check if value contains actual secret'),
        (r'[A-Z_]{2,}_TOKEN\s*=', 'Token-like variable name', 'Check if value contains actual secret'),
        
        # Configuration that might contain secrets
        (r'(?:config|settings)\[["\'](?:.*key.*|.*secret.*|.*token.*)["\']]\s*=', 'Config assignment with secret-like key', 'Use environment variables for sensitive config'),
    ]
    
    # File extensions to scan
    SCAN_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rb', '.php',
        '.cs', '.cpp', '.c', '.h', '.swift', '.kt', '.scala', '.rs',
        '.sh', '.bash', '.zsh', '.ps1', '.psm1',
        '.yml', '.yaml', '.json', '.xml', '.ini', '.conf', '.config',
        '.env', '.env.example', '.env.local', '.env.development',
        '.properties', '.toml'
    }
    
    # Paths to always exclude
    EXCLUDE_PATHS = {
        '.git', '.venv', 'venv', 'env', '__pycache__', 'node_modules',
        'build', 'dist', '.tox', 'htmlcov', '.pytest_cache', '.mypy_cache',
        'site-packages', '.idea', '.vscode'
    }


class APIKeyScanner:
    """Scanner for finding hardcoded API keys and secrets."""
    
    def __init__(self, exclude_paths: Optional[Set[str]] = None,
                 additional_patterns: Optional[List[Tuple[str, str, str]]] = None):
        self.patterns = SecurityPatterns()
        self.exclude_paths = self.patterns.EXCLUDE_PATHS
        if exclude_paths:
            self.exclude_paths.update(exclude_paths)
            
        # Compile all patterns for efficiency
        self.compiled_patterns = {
            'high': [(re.compile(p, re.IGNORECASE), name, rec) 
                    for p, name, rec in self.patterns.HIGH_CONFIDENCE_PATTERNS],
            'medium': [(re.compile(p, re.IGNORECASE), name, rec) 
                      for p, name, rec in self.patterns.MEDIUM_CONFIDENCE_PATTERNS],
            'low': [(re.compile(p, re.IGNORECASE), name, rec) 
                   for p, name, rec in self.patterns.LOW_CONFIDENCE_PATTERNS]
        }
        
        # Add any additional custom patterns
        if additional_patterns:
            for pattern, name, recommendation in additional_patterns:
                self.compiled_patterns['medium'].append(
                    (re.compile(pattern, re.IGNORECASE), name, recommendation)
                )
    
    def should_scan_file(self, file_path: Path) -> bool:
        """Check if a file should be scanned."""
        # Skip excluded directories
        if any(excluded in file_path.parts for excluded in self.exclude_paths):
            return False
            
        # Check file extension
        if file_path.suffix not in self.patterns.SCAN_EXTENSIONS:
            # Also scan files with no extension (like Dockerfile)
            if file_path.suffix and file_path.name not in ['Dockerfile', 'Makefile', 'Rakefile']:
                return False
                
        # Skip obviously non-sensitive files
        skip_files = {
            'package-lock.json', 'yarn.lock', 'poetry.lock', 'Pipfile.lock',
            'requirements.txt', 'go.sum', 'Cargo.lock'
        }
        if file_path.name in skip_files:
            return False
            
        return True
    
    def scan_line(self, line: str, line_number: int, file_path: str) -> List[SecurityFinding]:
        """Scan a single line for potential secrets."""
        findings = []
        
        # Skip common false positives
        if self._is_likely_false_positive(line):
            return findings
            
        # Check each pattern category
        for confidence, patterns in self.compiled_patterns.items():
            for pattern, pattern_name, recommendation in patterns:
                if pattern.search(line):
                    # Additional context checks for medium/low confidence
                    if confidence in ['medium', 'low']:
                        if not self._has_suspicious_context(line, pattern_name):
                            continue
                            
                    finding = SecurityFinding(
                        file_path=file_path,
                        line_number=line_number,
                        line_content=line,
                        finding_type="Potential Secret",
                        confidence=confidence,
                        pattern_name=pattern_name,
                        recommendation=recommendation
                    )
                    findings.append(finding)
                    
        return findings
    
    def _is_likely_false_positive(self, line: str) -> bool:
        """Check if a line is likely a false positive."""
        line_lower = line.lower().strip()
        
        # Skip comments (basic check)
        if line_lower.startswith('#') or line_lower.startswith('//'):
            return True
            
        # Skip lines that are clearly examples or documentation
        false_positive_indicators = [
            'example', 'sample', 'demo', 'test', 'fake', 'dummy',
            'xxx', 'todo', 'fixme', 'your-', 'my-', '<your',
            'placeholder', 'changeme', 'replace', 'configure'
        ]
        
        for indicator in false_positive_indicators:
            if indicator in line_lower:
                return True
                
        # Skip lines with obvious placeholder patterns
        if re.search(r'[<\[{].*[key|token|secret|password].*[>\]}]', line_lower):
            return True
            
        return False
    
    def _has_suspicious_context(self, line: str, pattern_name: str) -> bool:
        """Check if the context suggests this might be a real secret."""
        line_lower = line.lower()
        
        # Look for assignment patterns
        if '=' in line or ':' in line:
            # Check if the value part looks like a real secret
            parts = line.split('=', 1) if '=' in line else line.split(':', 1)
            if len(parts) > 1:
                value = parts[1].strip().strip('"\'')
                # Real secrets usually have certain characteristics
                if len(value) > 10 and not value.startswith('${') and not value.startswith('%('):
                    return True
                    
        return False
    
    def scan_file(self, file_path: Path) -> List[SecurityFinding]:
        """Scan a single file for secrets."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_number, line in enumerate(f, 1):
                    line_findings = self.scan_line(line, line_number, str(file_path))
                    findings.extend(line_findings)
                    
        except Exception as e:
            click.echo(f"Error scanning {file_path}: {e}", err=True)
            
        return findings
    
    def scan_directory(self, root_path: Path) -> List[SecurityFinding]:
        """Scan entire directory tree for secrets."""
        all_findings = []
        files_scanned = 0
        
        for file_path in root_path.rglob('*'):
            if file_path.is_file() and self.should_scan_file(file_path):
                findings = self.scan_file(file_path)
                all_findings.extend(findings)
                files_scanned += 1
                
        click.echo(f"Scanned {files_scanned} files", err=True)
        return all_findings


def generate_report(findings: List[SecurityFinding], root_path: Path, 
                   format: str = "text") -> str:
    """Generate a report from security findings."""
    if format == "json":
        return json.dumps({
            "summary": {
                "total_findings": len(findings),
                "high_confidence": len([f for f in findings if f.confidence == "high"]),
                "medium_confidence": len([f for f in findings if f.confidence == "medium"]),
                "low_confidence": len([f for f in findings if f.confidence == "low"]),
            },
            "findings": [f.to_dict() for f in findings]
        }, indent=2)
        
    # Text format
    lines = []
    lines.append("=" * 80)
    lines.append("API KEY/SECRET SCANNER REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    # Summary
    high_findings = [f for f in findings if f.confidence == "high"]
    medium_findings = [f for f in findings if f.confidence == "medium"]
    low_findings = [f for f in findings if f.confidence == "low"]
    
    lines.append(f"Total findings: {len(findings)}")
    lines.append(f"  High confidence: {len(high_findings)}")
    lines.append(f"  Medium confidence: {len(medium_findings)}")
    lines.append(f"  Low confidence: {len(low_findings)}")
    lines.append("")
    
    # Group findings by confidence
    if high_findings:
        lines.append("HIGH CONFIDENCE FINDINGS (Likely actual secrets)")
        lines.append("-" * 80)
        for finding in high_findings:
            rel_path = Path(finding.file_path).relative_to(root_path)
            lines.append(f"\n{rel_path}:{finding.line_number}")
            lines.append(f"Pattern: {finding.pattern_name}")
            lines.append(f"Line: {finding.line_content.strip()}")
            lines.append(f"Recommendation: {finding.recommendation}")
        lines.append("")
        
    if medium_findings:
        lines.append("MEDIUM CONFIDENCE FINDINGS (Possible secrets, review needed)")
        lines.append("-" * 80)
        for finding in medium_findings[:20]:  # Limit to first 20 to avoid spam
            rel_path = Path(finding.file_path).relative_to(root_path)
            lines.append(f"\n{rel_path}:{finding.line_number}")
            lines.append(f"Pattern: {finding.pattern_name}")
            lines.append(f"Line: {finding.line_content.strip()[:100]}...")
            lines.append(f"Recommendation: {finding.recommendation}")
        
        if len(medium_findings) > 20:
            lines.append(f"\n... and {len(medium_findings) - 20} more medium confidence findings")
        lines.append("")
        
    if low_findings and len(findings) < 50:  # Only show low if not too many findings
        lines.append("LOW CONFIDENCE FINDINGS (Needs context)")
        lines.append("-" * 80)
        for finding in low_findings[:10]:
            rel_path = Path(finding.file_path).relative_to(root_path)
            lines.append(f"\n{rel_path}:{finding.line_number}")
            lines.append(f"Pattern: {finding.pattern_name}")
            
    # Recommendations
    lines.append("")
    lines.append("GENERAL RECOMMENDATIONS:")
    lines.append("-" * 40)
    lines.append("1. Never commit API keys, passwords, or secrets to version control")
    lines.append("2. Use environment variables: os.getenv('API_KEY')")
    lines.append("3. Use secret management services (AWS Secrets Manager, Azure Key Vault, etc.)")
    lines.append("4. Add sensitive files to .gitignore")
    lines.append("5. Use git-secrets or similar pre-commit hooks")
    lines.append("6. Rotate any exposed credentials immediately")
    
    return "\n".join(lines)


@click.command()
@click.argument('path', default='.', type=click.Path(exists=True))
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text',
              help='Output format (default: text)')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
@click.option('--confidence', type=click.Choice(['all', 'high', 'medium', 'low']), default='all',
              help='Minimum confidence level to report')
@click.option('--exclude', multiple=True, help='Additional directories to exclude')
@click.option('--add-pattern', 'add_patterns', multiple=True, nargs=3,
              help='Add custom pattern: REGEX NAME RECOMMENDATION (can be used multiple times)')
def main(path, output_format, output, confidence, exclude, add_patterns):
    """Scan codebase for hardcoded API keys and secrets.
    
    Examples:
    
      api_key_scanner                     # Scan current directory
    
      api_key_scanner /path/to/project    # Scan specific directory
    
      api_key_scanner --format json       # Output as JSON
    
      api_key_scanner --confidence high   # Show only high confidence findings
    
      api_key_scanner --exclude tests     # Exclude additional directories
    
    Security Tips:
      - Never commit secrets to version control
      - Use environment variables for all credentials
      - Enable pre-commit hooks to catch secrets
      - Regularly scan your codebase for exposed secrets
      - Rotate any credentials that may have been exposed
    """
    root_path = Path(path).resolve()
        
    # Create scanner
    exclude_paths = set(exclude) if exclude else None
    additional_patterns = list(add_patterns) if add_patterns else None
    
    scanner = APIKeyScanner(exclude_paths=exclude_paths, 
                          additional_patterns=additional_patterns)
    
    # Scan directory
    click.echo(f"Scanning {root_path} for API keys and secrets...", err=True)
    findings = scanner.scan_directory(root_path)
    
    # Filter by confidence if requested
    if confidence != "all":
        if confidence == "high":
            findings = [f for f in findings if f.confidence == "high"]
        elif confidence == "medium":
            findings = [f for f in findings if f.confidence in ["high", "medium"]]
        elif confidence == "low":
            findings = findings  # Show all
            
    if not findings:
        click.echo("No potential secrets found!", err=True)
        sys.exit(0)
        
    # Generate report
    report = generate_report(findings, root_path, output_format)
    
    # Output report
    if output:
        with open(output, 'w') as f:
            f.write(report)
        click.echo(f"Report saved to {output}", err=True)
    else:
        click.echo(report)
        
    # Exit with error code if high confidence findings
    if any(f.confidence == "high" for f in findings):
        sys.exit(1)


if __name__ == "__main__":
    main()