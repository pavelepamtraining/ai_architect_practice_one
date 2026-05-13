import re

from dataclasses import dataclass
from typing import Optional, Tuple


MAX_INPUT_LENGTH = 100


@dataclass
class ValidationResult:
    passed: bool
    reason: Optional[str] = None


class SecurityGuardrails:
    """Security validation layer for the agent."""

    def detect_injection_patterns(
        self,
        user_input: str
    ) -> Tuple[bool, Optional[str]]:
        """Detect common prompt injection patterns."""

        suspicious_patterns = [
            ("ignore", "previous"),
            ("disregard", "instructions"),
            ("forget", "above"),
            ("new instructions", ""),
            ("system prompt", ""),
            ("###", "###"),
            ("repeat everything", ""),
            ("initial instructions", ""),
        ]

        input_lower = user_input.lower()

        for pattern1, pattern2 in suspicious_patterns:

            if (
                pattern1 in input_lower
                and (
                    not pattern2
                    or pattern2 in input_lower
                )
            ):

                return (
                    True,
                    f"Detected injection pattern: '{pattern1}'"
                )

        special_char_ratio = (
            sum(
                1
                for c in user_input
                if c in "#*_\n\r"
            )
            / max(len(user_input), 1)
        )

        if special_char_ratio > 0.2:

            return (
                True,
                "Excessive special characters detected"
            )

        return False, None

    def redact_sensitive_output(
        self,
        output: str
    ) -> str:
        """Remove sensitive information from LLM output."""

        # API keys
        output = re.sub(
            r"sk-[a-zA-Z0-9-]{20,}",
            "[REDACTED_API_KEY]",
            output
        )

        # Passwords
        output = re.sub(
            r"(password|passwd|pwd)\s*[:=]\s*\S+",
            r"\1: [REDACTED]",
            output,
            flags=re.IGNORECASE
        )

        # Email patterns
        output = re.sub(
            r"[a-zA-Z0-9._%+-]+@securecorp\.internal",
            "[REDACTED_EMAIL]",
            output
        )

        # Specific secrets
        output = output.replace(
            "admin_pass_2024",
            "[REDACTED]"
        )

        output = output.replace(
            "sk-proj-abc123xyz789",
            "[REDACTED]"
        )

        if "CONFIDENTIAL INFORMATION" in output:

            output = (
                "I cannot disclose internal "
                "system configuration."
            )

        return output

    def validate_factual_response(
        self,
        query: str,
        response: str
    ) -> Tuple[bool, str]:
        """Detect overconfident responses on unknown topics."""

        internal_keywords = [
            "securecorp",
            "last patched",
            "pto policy",
            "maximum pto",
            "ceo",
            "who was",
            "when was"
        ]

        query_lower = query.lower()

        asks_internal = any(
            keyword in query_lower
            for keyword in internal_keywords
        )

        if asks_internal:

            uncertainty_markers = [
                "don't know",
                "uncertain",
                "unable to",
                "no information",
                "cannot confirm",
                "not sure",
                "don't have access",
                "cannot provide"
            ]

            admits_uncertainty = any(
                marker in response.lower()
                for marker in uncertainty_markers
            )

            if not admits_uncertainty:

                safe_response = (
                    "I don't have access to "
                    "specific internal company data. "
                    "Please consult official "
                    "documentation or contact "
                    "your manager."
                )

                return False, safe_response

        return True, response

    def enforce_resource_limits(
        self,
        user_input: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if input violates resource limits."""

        if len(user_input) > MAX_INPUT_LENGTH:

            return (
                False,
                f"Input too long "
                f"({len(user_input)} chars). "
                f"Maximum: {MAX_INPUT_LENGTH}"
            )

        unbounded_patterns = [
            "list every",
            "list all",
            "enumerate all",
            "generate all"
        ]

        if any(
            pattern in user_input.lower()
            for pattern in unbounded_patterns
        ):

            return (
                False,
                "Request appears unbounded. "
                "Please be more specific."
            )

        return True, None
