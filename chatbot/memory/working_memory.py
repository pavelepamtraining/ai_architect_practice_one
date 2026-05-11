from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any

@dataclass
class Message:
    """Represents a single message in the conversation."""
    role: str  # 'user', 'assistant', 'tool'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class WorkingMemory:
    """Efficient working memory that avoids sending full chat history."""

    def __init__(self, max_recent_messages: int = 3):
        self.max_recent_messages = max_recent_messages
        self.summary: str = ""
        self.recent_messages: List[Message] = []
        self.tool_results: Dict[str, Any] = {}  # tool_name -> last_result

    def add_message(self, role: str, content: str) -> None:
        """Add a message to recent history."""
        message = Message(role=role, content=content)
        self.recent_messages.append(message)

        # Trim to max size
        if len(self.recent_messages) > self.max_recent_messages:
            # Move oldest to summary if needed
            self.recent_messages = self.recent_messages[-self.max_recent_messages:]

    def add_tool_result(self, tool_name: str, result: Any) -> None:
        """Store tool execution result."""
        self.tool_results[tool_name] = result

    def update_summary(self, summary: str) -> None:
        """Update conversation summary."""
        self.summary = summary

    def get_context(self) -> List[Dict[str, str]]:
        """Build context for LLM with summary and recent messages.

        Returns:
            List of message dicts for LLM consumption
        """
        context = []

        # Add summary if exists
        if self.summary:
            context.append({
                "role": "system",
                "content": f"Conversation summary: {self.summary}"
            })

        # Add recent messages
        for msg in self.recent_messages:
            context.append({
                "role": msg.role,
                "content": msg.content
            })

        return context

    def clear(self) -> None:
        """Reset working memory."""
        self.summary = ""
        self.recent_messages = []
        self.tool_results = {}