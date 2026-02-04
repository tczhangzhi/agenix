"""Agent runtime with tool execution loop."""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from ..tools.base import Tool
from .llm import LLMProvider, StreamEvent
from .messages import (AgentEndEvent, AgentStartEvent, AssistantMessage, Event,
                       Message, MessageEndEvent, MessageStartEvent,
                       MessageUpdateEvent, ReasoningContent, ReasoningStartEvent,
                       ReasoningUpdateEvent, ReasoningEndEvent, TextContent, ToolCall,
                       ToolExecutionEndEvent, ToolExecutionStartEvent,
                       ToolExecutionUpdateEvent, ToolResultMessage,
                       TurnEndEvent, TurnStartEvent, UserMessage)


@dataclass
class LoopState:
    """Agent loop state tracking."""
    turn: int = 0
    total_tool_calls: int = 0
    consecutive_errors: int = 0
    last_action: str = ""  # "text" | "tool_call" | "error"
    has_made_progress: bool = False  # Whether valid output was produced


@dataclass
class AgentConfig:
    """Agent configuration."""
    model: str
    api_key: str
    base_url: Optional[str] = None
    system_prompt: Optional[str] = None
    max_turns: int = 10  # Maximum conversation turns per prompt
    max_tool_calls_per_turn: int = 20  # Maximum tool calls per turn
    max_tokens: int = 16384  # Maximum tokens for LLM output (default: 16384 for modern models)

    def __post_init__(self):
        """Create provider after initialization."""
        # Auto-detect provider from base_url or model name
        try:
            # Check if using Anthropic (by base_url or model name)
            is_anthropic = (
                (self.base_url and "anthropic" in self.base_url.lower()) or
                (self.base_url and "aihubmix.com" in self.base_url.lower() and "claude" in self.model.lower()) or
                ("claude" in self.model.lower() and not self.base_url)
            )

            if is_anthropic:
                from .llm import AnthropicProvider
                self.provider = AnthropicProvider(
                    api_key=self.api_key, base_url=self.base_url)
            else:
                from .llm import OpenAIProvider
                self.provider = OpenAIProvider(
                    api_key=self.api_key, base_url=self.base_url)
        except Exception as e:
            raise ValueError(f"Failed to initialize LLM provider: {e}")


class Agent:
    """Agent runtime with tool execution loop."""

    def __init__(
        self,
        config: AgentConfig,
        tools: Optional[List[Tool]] = None,
        agent_id: Optional[str] = None,
        parent_chain: Optional[List[str]] = None
    ):
        self.config = config
        self.tools = tools or []
        self.messages: List[Message] = []
        self.subscribers: List[Callable[[Event], None]] = []

        # Unique agent ID (for tracking agent hierarchy)
        self.agent_id = agent_id or str(uuid.uuid4())

        # Parent chain (list of ancestor agent IDs to prevent circular calls)
        self.parent_chain = parent_chain or []

        # Build tool lookup
        self.tool_map = {tool.name: tool for tool in self.tools}

        # Loop state tracking
        self.loop_state = LoopState()

    def subscribe(self, callback: Callable[[Event], None]) -> Callable[[], None]:
        """Subscribe to agent events.

        Returns:
            Unsubscribe function
        """
        self.subscribers.append(callback)
        return lambda: self.subscribers.remove(callback)

    def _emit(self, event: Event) -> None:
        """Emit event to all subscribers."""
        for callback in self.subscribers:
            try:
                callback(event)
            except Exception as e:
                # Don't let subscriber errors break the agent
                print(f"Error in event subscriber: {e}")

    async def prompt(self, user_message: str) -> AsyncIterator[Event]:
        """Process a user prompt through the agent loop.

        Args:
            user_message: User's message

        Yields:
            Agent events
        """
        # Add user message
        msg = UserMessage(content=user_message)
        self.messages.append(msg)

        # Run agent loop
        async for event in self._run_loop():
            yield event

    async def _run_loop(self) -> AsyncIterator[Event]:
        """Main agent loop with tool calling."""
        # Emit agent start
        event = AgentStartEvent()
        self._emit(event)
        yield event

        # Reset loop state
        self.loop_state = LoopState()

        for turn in range(self.config.max_turns):
            self.loop_state.turn = turn

            # Emit turn start
            turn_event = TurnStartEvent()
            self._emit(turn_event)
            yield turn_event

            # Get LLM response
            assistant_message = None
            async for msg_event in self._stream_llm_response():
                yield msg_event
                if isinstance(msg_event, MessageEndEvent):
                    assistant_message = msg_event.message

            if not assistant_message:
                break

            # Add to messages
            self.messages.append(assistant_message)

            # Track progress - has text or reasoning content
            if assistant_message.content:
                if isinstance(assistant_message.content, str):
                    if assistant_message.content.strip():
                        self.loop_state.has_made_progress = True
                        self.loop_state.last_action = "text"
                elif isinstance(assistant_message.content, list):
                    if any(isinstance(c, (TextContent, ReasoningContent)) and c.text.strip()
                           for c in assistant_message.content):
                        self.loop_state.has_made_progress = True
                        self.loop_state.last_action = "text"

            # Execute tools if any
            tool_results = []
            error_count = 0
            if assistant_message.tool_calls:
                self.loop_state.last_action = "tool_call"
                for tool_call in assistant_message.tool_calls[:self.config.max_tool_calls_per_turn]:
                    self.loop_state.total_tool_calls += 1

                    # Validate tool call has proper arguments before execution
                    if not tool_call.arguments or not isinstance(tool_call.arguments, dict):
                        # Invalid tool call - create detailed error message
                        error_msg = ToolResultMessage(
                            tool_call_id=tool_call.id,
                            name=tool_call.name,
                            content=f"Error: Tool '{tool_call.name}' called with invalid arguments. "
                                    f"Received: {tool_call.arguments}. "
                                    f"Please check the tool's required parameters and try again with valid arguments.",
                            is_error=True
                        )
                        tool_results.append(error_msg)
                        self.messages.append(error_msg)
                        error_count += 1
                        continue

                    # Execute valid tool call
                    async for tool_event in self._execute_tool(tool_call):
                        yield tool_event
                        if isinstance(tool_event, ToolExecutionEndEvent):
                            # Create tool result message
                            # Preserve structured content from ToolResult
                            from ..tools.base import ToolResult

                            result_content = tool_event.result
                            if isinstance(result_content, ToolResult):
                                # ToolResult object - extract the content field
                                result_content = result_content.content

                            result_msg = ToolResultMessage(
                                tool_call_id=tool_event.tool_call_id,
                                name=tool_event.tool_name,
                                content=result_content,  # Keep structure: str or List[TextContent|ImageContent]
                                is_error=tool_event.is_error
                            )
                            tool_results.append(result_msg)
                            self.messages.append(result_msg)

                            if tool_event.is_error:
                                error_count += 1

                # Update consecutive error count
                if error_count == len(tool_results) and error_count > 0:
                    # All tools failed
                    self.loop_state.consecutive_errors += 1
                    self.loop_state.last_action = "error"
                else:
                    # At least one tool succeeded
                    self.loop_state.consecutive_errors = 0
                    self.loop_state.has_made_progress = True

            # Emit turn end
            turn_end = TurnEndEvent(
                message=assistant_message, tool_results=tool_results)
            self._emit(turn_end)
            yield turn_end

            # Enhanced loop continuation logic
            if not self._should_continue_loop(assistant_message):
                break

        # Emit agent end
        end_event = AgentEndEvent(messages=self.messages)
        self._emit(end_event)
        yield end_event

    def _should_continue_loop(self, message: AssistantMessage) -> bool:
        """Enhanced loop continuation logic with state tracking."""
        # Stop if too many consecutive errors
        if self.loop_state.consecutive_errors >= 3:
            return False

        # Continue if there are tool calls to execute
        if message.tool_calls:
            return True

        # Continue if output was truncated
        if message.stop_reason == "length":
            return True

        # Stop if we've made progress (text/reasoning output) and no tool calls
        if self.loop_state.has_made_progress and not message.tool_calls:
            return False

        return False

    async def _stream_llm_response(self) -> AsyncIterator[Event]:
        """Stream LLM response."""
        # Prepare context
        tools_dict = [tool.to_dict()
                      for tool in self.tools] if self.tools else None

        try:
            # Start streaming
            message = AssistantMessage(content=[], model=self.config.model)

            start_event = MessageStartEvent(message=message)
            self._emit(start_event)
            yield start_event

            # Collect streaming content
            text_parts = []
            tool_calls_list = []
            reasoning_parts = {}  # Track reasoning blocks by ID
            finish_reason = None  # Capture actual finish reason from LLM

            # Stream from LLM
            stream = self.config.provider.stream(
                model=self.config.model,
                messages=self.messages,
                system_prompt=self.config.system_prompt,
                tools=tools_dict,
                max_tokens=self.config.max_tokens,
            )

            async for event in stream:
                if event.type == "text_delta":
                    text_parts.append(event.delta)
                    # Update message
                    message.content = [TextContent(text="".join(text_parts))]

                    # Emit update
                    update_event = MessageUpdateEvent(
                        message=message, delta=event.delta)
                    self._emit(update_event)
                    yield update_event

                elif event.type == "reasoning_delta":
                    # Handle reasoning content
                    reasoning_id = event.reasoning_block_id or "default"

                    if reasoning_id not in reasoning_parts:
                        # First chunk of this reasoning block
                        reasoning_parts[reasoning_id] = ""
                        reasoning_start = ReasoningStartEvent(reasoning_id=reasoning_id)
                        self._emit(reasoning_start)
                        yield reasoning_start

                    # Accumulate reasoning content
                    reasoning_parts[reasoning_id] += event.delta
                    reasoning_update = ReasoningUpdateEvent(
                        reasoning_id=reasoning_id,
                        delta=event.delta
                    )
                    self._emit(reasoning_update)
                    yield reasoning_update

                elif event.type == "tool_call" and event.tool_call:
                    # Complete tool call received
                    tool_calls_list.append(event.tool_call)

                elif event.type == "finish" and event.finish_reason:
                    # Capture finish reason from LLM
                    finish_reason = event.finish_reason

            # Emit reasoning end events and add to message content
            for reasoning_id, content in reasoning_parts.items():
                reasoning_end = ReasoningEndEvent(reasoning_id=reasoning_id, content=content)
                self._emit(reasoning_end)
                yield reasoning_end

            # Finalize message
            content_list = []

            # Add reasoning content first
            for reasoning_id, content in reasoning_parts.items():
                content_list.append(ReasoningContent(text=content, reasoning_id=reasoning_id))

            # Add text content
            if text_parts:
                content_list.append(TextContent(text="".join(text_parts)))

            message.content = content_list if content_list else []
            message.tool_calls = tool_calls_list

            # Note: We don't fetch usage info to avoid extra API call and delay
            # The streaming response should be sufficient for user interaction
            message.usage = None
            # Use actual finish_reason from LLM, fallback to inferring from content
            if finish_reason:
                message.stop_reason = finish_reason
            else:
                message.stop_reason = "stop" if not tool_calls_list else "tool_calls"

            # Emit end
            end_event = MessageEndEvent(message=message)
            self._emit(end_event)
            yield end_event

        except Exception as e:
            # Emit error
            error_msg = AssistantMessage(
                content=[TextContent(text=f"Error: {str(e)}")],
                model=self.config.model,
                stop_reason="error"
            )
            end_event = MessageEndEvent(message=error_msg)
            self._emit(end_event)
            yield end_event

    async def _execute_tool(self, tool_call: ToolCall) -> AsyncIterator[Event]:
        """Execute a tool call."""
        tool = self.tool_map.get(tool_call.name)

        # Emit start
        start_event = ToolExecutionStartEvent(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            args=tool_call.arguments
        )
        self._emit(start_event)
        yield start_event

        if not tool:
            # Tool not found
            end_event = ToolExecutionEndEvent(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                result=f"Error: Tool '{tool_call.name}' not found",
                is_error=True
            )
            self._emit(end_event)
            yield end_event
            return

        # Execute tool
        try:
            def on_update(partial_result: str):
                """Progress callback."""
                update_event = ToolExecutionUpdateEvent(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    partial_result=partial_result
                )
                self._emit(update_event)
                # Note: Not yielding update events to simplify async flow

            result = await tool.execute(
                tool_call_id=tool_call.id,
                arguments=tool_call.arguments,
                on_update=on_update
            )

            # Emit end
            end_event = ToolExecutionEndEvent(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                result=result.content,
                is_error=result.is_error
            )
            self._emit(end_event)
            yield end_event

        except Exception as e:
            # Tool execution error
            end_event = ToolExecutionEndEvent(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                result=f"Error executing tool: {str(e)}",
                is_error=True
            )
            self._emit(end_event)
            yield end_event

    def get_messages(self) -> List[Message]:
        """Get conversation messages."""
        return self.messages.copy()

    def clear_messages(self) -> None:
        """Clear conversation history."""
        self.messages.clear()
