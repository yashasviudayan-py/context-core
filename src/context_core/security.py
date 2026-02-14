"""Security utilities for detecting and filtering sensitive data."""

import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class SecretPattern:
    """A pattern for detecting secrets."""

    name: str
    pattern: Pattern[str]
    description: str


class SecretDetector:
    """Detects sensitive data patterns in text using regex matching."""

    # Compiled regex patterns for common secret types
    PATTERNS: list[SecretPattern] = [
        SecretPattern(
            name="api_key",
            pattern=re.compile(
                r'(?i)(?:api[_-]?key|apikey|x-api-key)["\s:=]+[a-zA-Z0-9_\-]{20,}',
                re.MULTILINE,
            ),
            description="API keys and authentication tokens",
        ),
        SecretPattern(
            name="password",
            pattern=re.compile(
                r'(?i)(?:(?:password|passwd|pwd)["\s:=]+\S{8,}|(?:^|\s)-[pP]\s+\S{8,})',
                re.MULTILINE,
            ),
            description="Passwords in various formats",
        ),
        SecretPattern(
            name="bearer_token",
            pattern=re.compile(
                r'(?i)(?:bearer|token|auth(?:_?token)?)["\s:=]+[a-zA-Z0-9_\-\.]{20,}',
                re.MULTILINE,
            ),
            description="Bearer tokens and authentication tokens",
        ),
        SecretPattern(
            name="aws_access_key",
            pattern=re.compile(r'\bAKIA[0-9A-Z]{16}\b', re.MULTILINE),
            description="AWS Access Key IDs",
        ),
        SecretPattern(
            name="aws_secret_key",
            pattern=re.compile(
                r'(?i)aws[_-]?secret[_-]?(?:access[_-]?)?key["\s:=]+[a-zA-Z0-9/+=]{40}',
                re.MULTILINE,
            ),
            description="AWS Secret Access Keys",
        ),
        SecretPattern(
            name="private_key",
            pattern=re.compile(
                r'-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----',
                re.MULTILINE,
            ),
            description="Private cryptographic keys (RSA, EC, SSH)",
        ),
        SecretPattern(
            name="jwt",
            pattern=re.compile(
                r'\beyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\b',
                re.MULTILINE,
            ),
            description="JSON Web Tokens (JWT)",
        ),
        SecretPattern(
            name="github_token",
            pattern=re.compile(r'\bgh[pousr]_[A-Za-z0-9_]{36,}\b', re.MULTILINE),
            description="GitHub Personal Access Tokens",
        ),
        SecretPattern(
            name="github_oauth",
            pattern=re.compile(r'\bgho_[A-Za-z0-9_]{36,}\b', re.MULTILINE),
            description="GitHub OAuth Tokens",
        ),
        SecretPattern(
            name="slack_token",
            pattern=re.compile(r'\bxox[baprs]-[0-9a-zA-Z\-]{10,}\b', re.MULTILINE),
            description="Slack API tokens",
        ),
        SecretPattern(
            name="env_secret",
            pattern=re.compile(
                r'(?i)(?:export\s+)?(?:[\w]*(?:KEY|TOKEN|PASS|SECRET|AUTH)[\w]*)\s*=\s*["\']?[a-zA-Z0-9_\-+=]{20,}',
                re.MULTILINE,
            ),
            description="Environment variables with secret-like names",
        ),
        SecretPattern(
            name="google_api_key",
            pattern=re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b', re.MULTILINE),
            description="Google API Keys",
        ),
        SecretPattern(
            name="stripe_key",
            pattern=re.compile(r'\b[sr]k_live_[0-9a-zA-Z]{24,}\b', re.MULTILINE),
            description="Stripe API keys (live)",
        ),
        SecretPattern(
            name="database_url",
            pattern=re.compile(
                r'(?i)(?:mysql|postgres|mongodb|redis)://[a-zA-Z0-9_\-]+:[a-zA-Z0-9_\-@!#$%^&*()+=]{8,}@',
                re.MULTILINE,
            ),
            description="Database connection strings with credentials",
        ),
        SecretPattern(
            name="generic_secret",
            pattern=re.compile(
                r'(?i)(?:secret|credentials?|creds)["\s:=]+[a-zA-Z0-9_\-+=]{20,}',
                re.MULTILINE,
            ),
            description="Generic secret patterns",
        ),
    ]

    def __init__(self, custom_patterns: list[SecretPattern] | None = None):
        """Initialize the SecretDetector.

        Args:
            custom_patterns: Optional list of custom SecretPattern objects to add
        """
        self.patterns = self.PATTERNS.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)

    def contains_secret(self, text: str) -> bool:
        """Check if text contains any known secret patterns.

        Args:
            text: The text to scan for secrets

        Returns:
            True if any secret pattern is detected, False otherwise
        """
        if not text or not text.strip():
            return False

        for pattern_obj in self.patterns:
            if pattern_obj.pattern.search(text):
                return True
        return False

    def get_matched_patterns(self, text: str) -> list[str]:
        """Get a list of pattern names that matched in the text.

        Args:
            text: The text to scan for secrets

        Returns:
            List of pattern names that matched (e.g., ['api_key', 'password'])
        """
        if not text or not text.strip():
            return []

        matched = []
        for pattern_obj in self.patterns:
            if pattern_obj.pattern.search(text):
                matched.append(pattern_obj.name)
        return matched

    def get_pattern_descriptions(self, pattern_names: list[str]) -> list[str]:
        """Get human-readable descriptions for matched pattern names.

        Args:
            pattern_names: List of pattern names returned by get_matched_patterns

        Returns:
            List of human-readable descriptions
        """
        pattern_map = {p.name: p.description for p in self.patterns}
        return [pattern_map.get(name, name) for name in pattern_names]

    def scan(self, text: str) -> dict[str, list[str]]:
        """Comprehensive scan that returns matched patterns and their descriptions.

        Args:
            text: The text to scan for secrets

        Returns:
            Dictionary with 'matched_patterns' and 'descriptions' keys
        """
        matched = self.get_matched_patterns(text)
        descriptions = self.get_pattern_descriptions(matched)
        return {"matched_patterns": matched, "descriptions": descriptions}
