"""Session management with persistence."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .messages import AssistantMessage, Message, ToolResultMessage, UserMessage


class SessionManager:
    """Manage persistent agent sessions."""

    def __init__(self, session_dir: str = ".agenix"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)

    def create_session(self, name: Optional[str] = None) -> str:
        """Create a new session.

        Args:
            name: Optional session name

        Returns:
            Session ID
        """
        session_id = name or datetime.now().strftime("%Y%m%d_%H%M%S")
        session_path = self.session_dir / f"{session_id}.jsonl"

        # Create session file with header
        header = {
            "type": "session_header",
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }

        with open(session_path, 'w') as f:
            f.write(json.dumps(header) + '\n')

        return session_id

    def save_message(self, session_id: str, message: Message) -> None:
        """Save a message to session.

        Args:
            session_id: Session ID
            message: Message to save
        """
        session_path = self.session_dir / f"{session_id}.jsonl"

        entry = {
            "type": "message",
            "timestamp": datetime.now().isoformat(),
            "message": self._message_to_dict(message)
        }

        with open(session_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def load_session(self, session_id: str) -> List[Message]:
        """Load session messages.

        Args:
            session_id: Session ID

        Returns:
            List of messages
        """
        session_path = self.session_dir / f"{session_id}.jsonl"

        if not session_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        messages = []
        with open(session_path, 'r') as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("type") == "message":
                    msg = self._dict_to_message(entry["message"])
                    if msg:
                        messages.append(msg)

        return messages

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions.

        Returns:
            List of session metadata
        """
        sessions = []

        for path in self.session_dir.glob("*.jsonl"):
            try:
                with open(path, 'r') as f:
                    header = json.loads(f.readline())
                    if header.get("type") == "session_header":
                        sessions.append({
                            "session_id": header["session_id"],
                            "created_at": header["created_at"],
                            "path": str(path)
                        })
            except:
                continue

        return sorted(sessions, key=lambda s: s["created_at"], reverse=True)

    def delete_session(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: Session ID
        """
        session_path = self.session_dir / f"{session_id}.jsonl"
        if session_path.exists():
            session_path.unlink()

    def _message_to_dict(self, message: Message) -> Dict[str, Any]:
        """Convert message to dictionary."""
        if isinstance(message, UserMessage):
            return {
                "role": "user",
                "content": message.content,
                "timestamp": message.timestamp
            }
        elif isinstance(message, AssistantMessage):
            return {
                "role": "assistant",
                "content": self._content_to_dict(message.content),
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments
                    }
                    for tc in message.tool_calls
                ],
                "model": message.model,
                "usage": {
                    "input_tokens": message.usage.input_tokens if message.usage else 0,
                    "output_tokens": message.usage.output_tokens if message.usage else 0,
                },
                "stop_reason": message.stop_reason,
                "timestamp": message.timestamp
            }
        elif isinstance(message, ToolResultMessage):
            return {
                "role": "tool",
                "tool_call_id": message.tool_call_id,
                "name": message.name,
                "content": self._content_to_dict(message.content),
                "is_error": message.is_error,
                "timestamp": message.timestamp
            }
        return {}

    def _content_to_dict(self, content: Any) -> Any:
        """Convert content to dictionary for serialization."""
        from .messages import TextContent, ImageContent, ToolCall, ReasoningContent

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            result = []
            for item in content:
                if isinstance(item, TextContent):
                    result.append({
                        "type": "text",
                        "text": item.text
                    })
                elif isinstance(item, ImageContent):
                    # Save image data
                    result.append({
                        "type": "image",
                        "source": item.source
                    })
                elif isinstance(item, ReasoningContent):
                    # Save reasoning content
                    result.append({
                        "type": "reasoning",
                        "text": item.text,
                        "reasoning_id": item.reasoning_id
                    })
                elif isinstance(item, ToolCall):
                    result.append({
                        "type": "tool_call",
                        "id": item.id,
                        "name": item.name,
                        "arguments": item.arguments
                    })
                else:
                    # Fallback: convert to string
                    result.append({
                        "type": "text",
                        "text": str(item)
                    })
            return result
        return str(content)

    def _content_from_dict(self, data: Any) -> Any:
        """Convert dictionary back to content objects."""
        from .messages import TextContent, ImageContent, ToolCall, ReasoningContent

        if isinstance(data, str):
            return data
        elif isinstance(data, list):
            result = []
            for item in data:
                if not isinstance(item, dict):
                    result.append(item)
                    continue

                item_type = item.get("type")
                if item_type == "text":
                    result.append(TextContent(text=item.get("text", "")))
                elif item_type == "image":
                    result.append(ImageContent(source=item.get("source", {})))
                elif item_type == "reasoning":
                    result.append(ReasoningContent(
                        text=item.get("text", ""),
                        reasoning_id=item.get("reasoning_id")
                    ))
                elif item_type == "tool_call":
                    result.append(ToolCall(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        arguments=item.get("arguments", {})
                    ))
                else:
                    # Unknown type: create TextContent
                    result.append(TextContent(text=str(item)))
            return result if result else data
        return data

    def _dict_to_message(self, data: Dict[str, Any]) -> Optional[Message]:
        """Convert dictionary to message."""
        role = data.get("role")

        if role == "user":
            content = self._content_from_dict(data.get("content", ""))
            return UserMessage(
                content=content,
                timestamp=data.get("timestamp", 0)
            )
        elif role == "assistant":
            from .messages import TextContent, ToolCall, Usage

            tool_calls = []
            for tc in data.get("tool_calls", []):
                tool_calls.append(ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("name", ""),
                    arguments=tc.get("arguments", {})
                ))

            usage_data = data.get("usage", {})
            usage = Usage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0)
            )

            # Parse content
            content_data = data.get("content", "")
            if isinstance(content_data, str):
                content = [TextContent(text=content_data)]
            else:
                content = []
                for item in content_data:
                    item_type = item.get("type")
                    if item_type == "text":
                        content.append(TextContent(text=item.get("text", "")))
                    elif item_type == "reasoning":
                        from .messages import ReasoningContent
                        content.append(ReasoningContent(
                            text=item.get("text", ""),
                            reasoning_id=item.get("reasoning_id")
                        ))

            return AssistantMessage(
                content=content,
                tool_calls=tool_calls,
                model=data.get("model", ""),
                usage=usage,
                stop_reason=data.get("stop_reason"),
                timestamp=data.get("timestamp", 0)
            )
        elif role == "tool":
            content = self._content_from_dict(data.get("content", ""))
            return ToolResultMessage(
                tool_call_id=data.get("tool_call_id", ""),
                name=data.get("name", ""),
                content=content,
                is_error=data.get("is_error", False),
                timestamp=data.get("timestamp", 0)
            )

        return None
