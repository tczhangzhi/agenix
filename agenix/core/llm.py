"""Unified LLM interface supporting multiple providers."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from .messages import (AssistantMessage, ImageContent, Message, TextContent,
                       ToolCall, ToolResultMessage, Usage, UserMessage)


@dataclass
class StreamEvent:
    """LLM stream event."""
    type: str  # "text_delta" | "tool_call" | "finish" | "reasoning_delta"
    delta: str = ""
    tool_call: Optional[ToolCall] = None
    finish_reason: Optional[str] = None  # "stop", "length", "tool_calls", "content_filter"
    reasoning_block_id: Optional[str] = None  # For tracking reasoning blocks


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def stream(
        self,
        model: str,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Stream LLM responses."""
        pass

    @abstractmethod
    async def complete(
        self,
        model: str,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ) -> AssistantMessage:
        """Complete LLM request (non-streaming)."""
        pass

    def _messages_to_dict(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert messages to API format."""
        result = []
        for msg in messages:
            if isinstance(msg, UserMessage):
                result.append({
                    "role": "user",
                    "content": msg.content if isinstance(msg.content, str) else self._format_content(msg.content)
                })
            elif isinstance(msg, AssistantMessage):
                entry = {"role": "assistant"}
                if isinstance(msg.content, str):
                    entry["content"] = msg.content
                else:
                    # Extract text content
                    text_parts = [
                        c.text for c in msg.content if isinstance(c, TextContent)]
                    if text_parts:
                        entry["content"] = "\n".join(text_parts)
                    else:
                        # No text content - set empty string to satisfy API requirements
                        entry["content"] = ""

                    # Add tool calls if present
                    if msg.tool_calls:
                        entry["tool_calls"] = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments)
                                }
                            }
                            for tc in msg.tool_calls
                        ]
                result.append(entry)
            elif isinstance(msg, ToolResultMessage):
                formatted_content = msg.content
                if isinstance(msg.content, list):
                    formatted_content = self._format_content(msg.content)
                    # If _format_content returns a list (contains images), we need to:
                    # 1. First send a tool message with text only (to satisfy OpenAI's requirement)
                    # 2. Then send a user message with images
                    if isinstance(formatted_content, list):
                        # Extract text parts for tool response
                        text_parts = [item["text"] for item in formatted_content if item["type"] == "text"]
                        tool_response = "\n".join(text_parts) if text_parts else "[Image content]"

                        # Add tool message (required by OpenAI API)
                        result.append({
                            "role": "tool",
                            "tool_call_id": msg.tool_call_id,
                            "content": tool_response
                        })

                        # Add user message with images
                        result.append({
                            "role": "user",
                            "content": formatted_content
                        })
                        continue

                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": formatted_content if isinstance(formatted_content, str) else str(formatted_content)
                })
        return result

    def _format_content(self, content: List[Any]) -> Union[str, List[Dict]]:
        """Format mixed content, preserving images."""
        from .messages import TextContent, ImageContent

        # Check if content is text-only (more generic than has_images)
        is_text_only = all(isinstance(item, TextContent) for item in content)

        if is_text_only:
            # Text-only: return simple string for backward compatibility
            return "\n".join([item.text for item in content])

        # Rich content: build list of content blocks
        result = []
        for item in content:
            if isinstance(item, TextContent):
                result.append({
                    "type": "text",
                    "text": item.text
                })
            elif isinstance(item, ImageContent):
                # OpenAI format: data URL with base64
                result.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{item.source['media_type']};base64,{item.source['data']}"
                    }
                })
            else:
                # Fallback for unknown content types: convert to text
                # This allows future extensions without breaking
                result.append({
                    "type": "text",
                    "text": str(item) if not hasattr(item, 'text') else item.text
                })

        return result


class OpenAIProvider(LLMProvider):
    """OpenAI/compatible API provider."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv(
                "OPENAI_BASE_URL") or "https://api.openai.com/v1"
        )

        # Validate API key
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

    async def stream(
        self,
        model: str,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Stream OpenAI responses."""
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package required. Install with: pip install openai")

        try:
            client = openai.AsyncOpenAI(
                api_key=self.api_key, base_url=self.base_url)
        except Exception as e:
            raise ValueError(f"Failed to create OpenAI client: {e}")

        try:
            api_messages = []
            if system_prompt:
                api_messages.append(
                    {"role": "system", "content": system_prompt})
            api_messages.extend(self._messages_to_dict(messages))

            kwargs = {
                "model": model,
                "messages": api_messages,
                "max_tokens": max_tokens,
                "stream": True,
            }

            if tools:
                kwargs["tools"] = [self._convert_tool(t) for t in tools]

            stream = await client.chat.completions.create(**kwargs)

            # Accumulate tool calls during streaming
            tool_calls_accumulator = {}  # index -> {id, name, arguments_str}
            finish_reason = None  # Capture finish reason from last chunk

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Capture finish_reason when available
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                if delta.content:
                    yield StreamEvent(type="text_delta", delta=delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        # Tool calls come in increments, need to accumulate
                        # Use index as key since id might not be in every delta
                        tc_index = tc.index if tc.index is not None else 0
                        tc_id = tc.id or f"call_{tc_index}"

                        if tc_index not in tool_calls_accumulator:
                            tool_calls_accumulator[tc_index] = {
                                "id": tc_id,
                                "name": "",
                                "arguments": ""
                            }

                        # Update id if provided
                        if tc.id:
                            tool_calls_accumulator[tc_index]["id"] = tc.id

                        if tc.function:
                            if tc.function.name:
                                tool_calls_accumulator[tc_index]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_accumulator[tc_index]["arguments"] += tc.function.arguments

            # After stream ends, yield complete tool calls
            for tc_data in tool_calls_accumulator.values():
                # Parse arguments - no repair, let LLM retry on failure
                if not tc_data["arguments"] or not tc_data["arguments"].strip():
                    # Empty arguments
                    arguments = {}
                else:
                    try:
                        arguments = json.loads(tc_data["arguments"])
                    except json.JSONDecodeError as e:
                        # JSON parsing failed - return empty dict, LLM will see error and retry
                        import sys
                        args_preview = tc_data["arguments"][:100] if len(tc_data["arguments"]) > 100 else tc_data["arguments"]
                        print(f"Warning: Invalid JSON for tool '{tc_data['name']}': {args_preview}",
                              file=sys.stderr)
                        print(f"  Error: {e}", file=sys.stderr)
                        arguments = {}

                yield StreamEvent(
                    type="tool_call",
                    tool_call=ToolCall(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=arguments
                    )
                )

            # Yield finish_reason as final event
            if finish_reason:
                yield StreamEvent(type="finish", finish_reason=finish_reason)
        except Exception as e:
            # Re-raise to be handled by caller
            raise
        finally:
            # Close the client properly
            await client.close()

    async def complete(
        self,
        model: str,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ) -> AssistantMessage:
        """Complete OpenAI request."""
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package required. Install with: pip install openai")

        try:
            client = openai.AsyncOpenAI(
                api_key=self.api_key, base_url=self.base_url)
        except Exception as e:
            raise ValueError(f"Failed to create OpenAI client: {e}")

        try:
            api_messages = []
            if system_prompt:
                api_messages.append(
                    {"role": "system", "content": system_prompt})
            api_messages.extend(self._messages_to_dict(messages))

            kwargs = {
                "model": model,
                "messages": api_messages,
                "max_tokens": max_tokens,
            }

            if tools:
                kwargs["tools"] = [self._convert_tool(t) for t in tools]

            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]

            # Build assistant message
            content_parts = []
            tool_calls = []

            if choice.message.content:
                content_parts.append(TextContent(text=choice.message.content))

            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments)
                    ))

            usage = None
            if response.usage:
                usage = Usage(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                )

            return AssistantMessage(
                content=content_parts,
                tool_calls=tool_calls,
                model=model,
                usage=usage,
                stop_reason=choice.finish_reason,
            )
        finally:
            # Close the client properly
            await client.close()

    def _convert_tool(self, tool: Dict[str, Any]) -> Dict[str, Any]:
        """Convert tool definition to OpenAI format."""
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters", {})
            }
        }


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            base_url=base_url
        )

        # Validate API key
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. Please set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        # Clean up base_url: Anthropic API doesn't use /v1 suffix
        if self.base_url and self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]  # Remove /v1

    async def stream(
        self,
        model: str,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamEvent]:
        """Stream Anthropic responses."""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package required. Install with: pip install anthropic")

        try:
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            client = anthropic.AsyncAnthropic(**kwargs)
        except Exception as e:
            raise ValueError(f"Failed to create Anthropic client: {e}")

        kwargs = {
            "model": model,
            "messages": self._anthropic_messages(messages),
            "max_tokens": max_tokens,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        # Enable thinking for models that support it
        if "think" in model.lower():
            # Thinking requires:
            # 1. budget_tokens >= 1024
            # 2. max_tokens > budget_tokens
            # Reserve at least 2048 tokens for output (1024 thinking + 1024 response)
            if max_tokens >= 2048:
                thinking_budget = min(10000, max_tokens - 1024)
                if thinking_budget >= 1024:
                    kwargs["thinking"] = {
                        "type": "enabled",
                        "budget_tokens": thinking_budget
                    }

        async with client.messages.stream(**kwargs) as stream:
            # Track tool calls being built
            tool_calls_map = {}
            # Track reasoning blocks
            reasoning_buffer = {}

            async for event in stream:
                if event.type == "content_block_start":
                    if hasattr(event.content_block, "type"):
                        if event.content_block.type == "tool_use":
                            # Tool call started - initialize tracking
                            tool_calls_map[event.index] = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": ""
                            }
                        elif event.content_block.type == "thinking":
                            # Reasoning block started
                            reasoning_buffer[event.index] = {
                                "id": f"reasoning_{event.index}",
                                "content": ""
                            }

                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        # Check if this is reasoning text
                        if event.index in reasoning_buffer:
                            # This is reasoning content
                            delta_text = event.delta.text
                            reasoning_buffer[event.index]["content"] += delta_text
                            yield StreamEvent(
                                type="reasoning_delta",
                                delta=delta_text,
                                reasoning_block_id=reasoning_buffer[event.index]["id"]
                            )
                        else:
                            # Regular text content
                            yield StreamEvent(type="text_delta", delta=event.delta.text)
                    elif hasattr(event.delta, "thinking"):
                        # ThinkingDelta - has .thinking instead of .text
                        if event.index in reasoning_buffer:
                            delta_text = event.delta.thinking
                            reasoning_buffer[event.index]["content"] += delta_text
                            yield StreamEvent(
                                type="reasoning_delta",
                                delta=delta_text,
                                reasoning_block_id=reasoning_buffer[event.index]["id"]
                            )
                    elif hasattr(event.delta, "partial_json"):
                        # Tool call input in progress
                        if event.index in tool_calls_map:
                            tool_calls_map[event.index]["input"] += event.delta.partial_json

                elif event.type == "content_block_stop":
                    # Content block finished
                    if event.index in tool_calls_map:
                        # Tool call completed - parse JSON and yield
                        import json
                        tool_data = tool_calls_map[event.index]
                        try:
                            arguments = json.loads(tool_data["input"])
                        except json.JSONDecodeError:
                            arguments = {}

                        yield StreamEvent(
                            type="tool_call",
                            tool_call=ToolCall(
                                id=tool_data["id"],
                                name=tool_data["name"],
                                arguments=arguments
                            )
                        )
                    elif event.index in reasoning_buffer:
                        # Reasoning block completed - just clean up, will be handled by agent
                        pass

            # Get final message to extract stop_reason
            final_message = await stream.get_final_message()
            if final_message and hasattr(final_message, 'stop_reason'):
                # Map Anthropic stop_reason to OpenAI-style
                # Anthropic: "end_turn", "max_tokens", "stop_sequence", "tool_use"
                # OpenAI: "stop", "length", "content_filter", "tool_calls"
                stop_reason_map = {
                    "end_turn": "stop",
                    "max_tokens": "length",
                    "tool_use": "tool_calls",
                    "stop_sequence": "stop"
                }
                finish_reason = stop_reason_map.get(final_message.stop_reason, final_message.stop_reason)
                yield StreamEvent(type="finish", finish_reason=finish_reason)

    async def complete(
        self,
        model: str,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ) -> AssistantMessage:
        """Complete Anthropic request."""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package required. Install with: pip install anthropic")

        try:
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            client = anthropic.AsyncAnthropic(**kwargs)
        except Exception as e:
            raise ValueError(f"Failed to create Anthropic client: {e}")

        kwargs = {
            "model": model,
            "messages": self._anthropic_messages(messages),
            "max_tokens": max_tokens,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        # Enable thinking for models that support it
        if "think" in model.lower():
            # Thinking requires:
            # 1. budget_tokens >= 1024
            # 2. max_tokens > budget_tokens
            # Reserve at least 2048 tokens for output (1024 thinking + 1024 response)
            if max_tokens >= 2048:
                thinking_budget = min(10000, max_tokens - 1024)
                if thinking_budget >= 1024:
                    kwargs["thinking"] = {
                        "type": "enabled",
                        "budget_tokens": thinking_budget
                    }

        response = await client.messages.create(**kwargs)

        # Parse response
        content_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(TextContent(text=block.text))
            elif block.type == "thinking":
                # Add thinking content as ReasoningContent
                from .messages import ReasoningContent
                content_parts.append(ReasoningContent(
                    text=block.thinking,
                    reasoning_id="thinking"
                ))
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input
                ))

        usage = None
        if response.usage:
            usage = Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        return AssistantMessage(
            content=content_parts,
            tool_calls=tool_calls,
            model=model,
            usage=usage,
            stop_reason=response.stop_reason,
        )

    def _anthropic_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert messages to Anthropic format."""
        result = []
        for msg in messages:
            if isinstance(msg, UserMessage):
                result.append({
                    "role": "user",
                    "content": msg.content if isinstance(msg.content, str) else self._format_content(msg.content)
                })
            elif isinstance(msg, AssistantMessage):
                content = []
                # Add text content
                if isinstance(msg.content, str):
                    content.append({"type": "text", "text": msg.content})
                else:
                    for item in msg.content:
                        if isinstance(item, TextContent):
                            content.append({"type": "text", "text": item.text})

                # Add tool calls
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments
                    })

                result.append({"role": "assistant", "content": content})
            elif isinstance(msg, ToolResultMessage):
                content = msg.content

                # Handle mixed content with images
                if isinstance(content, list):
                    tool_result_content = []
                    for item in content:
                        if isinstance(item, TextContent):
                            tool_result_content.append({
                                "type": "text",
                                "text": item.text
                            })
                        elif isinstance(item, ImageContent):
                            # Anthropic native image format
                            tool_result_content.append({
                                "type": "image",
                                "source": item.source  # Already in correct format!
                            })

                    result.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": tool_result_content,  # List of text/image blocks
                                "is_error": msg.is_error
                            }
                        ]
                    })
                else:
                    # Simple string content - existing logic
                    result.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": content,
                                "is_error": msg.is_error
                            }
                        ]
                    })
        return result

    def _convert_tool(self, tool: Dict[str, Any]) -> Dict[str, Any]:
        """Convert tool definition to Anthropic format."""
        return {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool.get("parameters", {})
        }


# Registry of providers
PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def get_provider(provider_name: str, **kwargs) -> LLMProvider:
    """Get LLM provider by name."""
    provider_class = PROVIDERS.get(provider_name)
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}")
    return provider_class(**kwargs)
