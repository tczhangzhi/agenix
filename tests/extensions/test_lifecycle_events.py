"""Tests for lifecycle events and extension hooks."""

import pytest
import asyncio
from typing import List

from agenix.extensions.types import (
    ExtensionAPI,
    EventType,
    SessionStartEvent,
    SessionEndEvent,
    SessionShutdownEvent,
    BeforeAgentStartEvent,
    BeforeCompactEvent,
    CompactEvent,
    ToolCallEvent,
    ContextEvent,
    ExtensionContext,
    CancellableEvent,
)
from agenix.extensions.runner import ExtensionRunner, LoadedExtension


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.agent_id = "test-agent"
        self.config = type('Config', (), {
            'model': 'gpt-4o',
            'api_key': 'test-key',
            'base_url': None
        })()
        self.messages = []


@pytest.mark.asyncio
class TestLifecycleEvents:
    """Test lifecycle event emission and handling."""

    async def test_session_start_event(self):
        """Test SESSION_START event."""
        handler_called = []

        # Create mock extension
        api = ExtensionAPI()

        @api.on(EventType.SESSION_START)
        async def on_start(event, ctx):
            handler_called.append("started")
            assert isinstance(event, SessionStartEvent)
            assert isinstance(ctx, ExtensionContext)

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        await runner.emit(SessionStartEvent())

        assert len(handler_called) == 1
        assert handler_called[0] == "started"

    async def test_session_end_event(self):
        """Test SESSION_END event."""
        handler_called = []

        api = ExtensionAPI()

        @api.on(EventType.SESSION_END)
        async def on_end(event, ctx):
            handler_called.append("ended")

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        await runner.emit(SessionEndEvent())

        assert len(handler_called) == 1

    async def test_session_shutdown_event(self):
        """Test SESSION_SHUTDOWN event."""
        cleanup_called = []

        api = ExtensionAPI()

        @api.on(EventType.SESSION_SHUTDOWN)
        async def on_shutdown(event, ctx):
            cleanup_called.append("cleanup")

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        await runner.emit(SessionShutdownEvent())

        assert len(cleanup_called) == 1


@pytest.mark.asyncio
class TestBeforeAgentStartEvent:
    """Test BEFORE_AGENT_START event with message injection."""

    async def test_message_injection(self):
        """Test that extensions can inject messages before agent starts."""
        api = ExtensionAPI()

        @api.on(EventType.BEFORE_AGENT_START)
        async def inject_message(event: BeforeAgentStartEvent, ctx):
            event.messages_to_inject.append({
                "role": "system",
                "content": "Injected system message"
            })

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        event = BeforeAgentStartEvent(prompt="Test prompt")
        result = await runner.emit(event)

        assert len(result.messages_to_inject) == 1
        assert result.messages_to_inject[0]["content"] == "Injected system message"

    async def test_cancel_agent_start(self):
        """Test that extensions can cancel agent start."""
        api = ExtensionAPI()

        @api.on(EventType.BEFORE_AGENT_START)
        async def cancel_start(event: BeforeAgentStartEvent, ctx):
            event.cancel()

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        event = BeforeAgentStartEvent(prompt="Test")
        result = await runner.emit(event)

        assert result.cancelled


@pytest.mark.asyncio
class TestCompactionEvents:
    """Test compaction event handling."""

    async def test_before_compact_event(self):
        """Test BEFORE_COMPACT event."""
        api = ExtensionAPI()

        custom_instructions = []

        @api.on(EventType.BEFORE_COMPACT)
        async def on_before_compact(event: BeforeCompactEvent, ctx):
            event.custom_instructions = "Preserve all code examples"
            custom_instructions.append(event.custom_instructions)

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        event = BeforeCompactEvent(messages=[])
        result = await runner.emit(event)

        assert result.custom_instructions == "Preserve all code examples"
        assert len(custom_instructions) == 1

    async def test_cancel_compaction(self):
        """Test that extensions can cancel compaction."""
        api = ExtensionAPI()

        @api.on(EventType.BEFORE_COMPACT)
        async def cancel_compact(event: BeforeCompactEvent, ctx):
            event.cancel()

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        event = BeforeCompactEvent(messages=[])
        result = await runner.emit(event)

        assert result.cancelled

    async def test_compact_event(self):
        """Test COMPACT event (notification only)."""
        summaries = []

        api = ExtensionAPI()

        @api.on(EventType.COMPACT)
        async def on_compact(event: CompactEvent, ctx):
            summaries.append(event.summary)

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        event = CompactEvent(summary="Test summary")
        await runner.emit(event)

        assert len(summaries) == 1
        assert summaries[0] == "Test summary"


@pytest.mark.asyncio
class TestToolCallEvent:
    """Test TOOL_CALL event with blocking capability."""

    async def test_block_tool_call(self):
        """Test that extensions can block tool calls."""
        api = ExtensionAPI()

        @api.on(EventType.TOOL_CALL)
        async def block_dangerous(event: ToolCallEvent, ctx):
            if event.tool_name == "bash" and "rm -rf" in event.args.get("command", ""):
                event.cancel()

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        event = ToolCallEvent(tool_name="bash", args={"command": "rm -rf /"})
        result = await runner.emit(event)

        assert result.cancelled

    async def test_allow_safe_tool_call(self):
        """Test that safe tool calls are allowed."""
        api = ExtensionAPI()

        @api.on(EventType.TOOL_CALL)
        async def block_dangerous(event: ToolCallEvent, ctx):
            if event.tool_name == "bash" and "rm -rf" in event.args.get("command", ""):
                event.cancel()

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        event = ToolCallEvent(tool_name="bash", args={"command": "ls -la"})
        result = await runner.emit(event)

        assert not result.cancelled


@pytest.mark.asyncio
class TestContextEvent:
    """Test CONTEXT event with message modification."""

    async def test_modify_context(self):
        """Test that extensions can modify context messages."""
        api = ExtensionAPI()

        @api.on(EventType.CONTEXT)
        async def modify_context(event: ContextEvent, ctx):
            # Add a system message
            event.messages.insert(0, {
                "role": "system",
                "content": "Modified context"
            })

        ext = LoadedExtension(
            name="test-ext",
            handlers=api._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        event = ContextEvent(messages=[{"role": "user", "content": "Hello"}])
        result = await runner.emit(event)

        assert len(result.messages) == 2
        assert result.messages[0]["content"] == "Modified context"


@pytest.mark.asyncio
class TestMultipleExtensionHandlers:
    """Test multiple extensions handling same event."""

    async def test_multiple_handlers_same_event(self):
        """Test that multiple extensions can handle same event."""
        calls = []

        api1 = ExtensionAPI()

        @api1.on(EventType.SESSION_START)
        async def handler1(event, ctx):
            calls.append("ext1")

        api2 = ExtensionAPI()

        @api2.on(EventType.SESSION_START)
        async def handler2(event, ctx):
            calls.append("ext2")

        ext1 = LoadedExtension(
            name="ext1",
            handlers=api1._handlers,
            tools={},
            commands={}
        )
        ext2 = LoadedExtension(
            name="ext2",
            handlers=api2._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext1, ext2], context=ctx)

        await runner.emit(SessionStartEvent())

        assert len(calls) == 2
        assert "ext1" in calls
        assert "ext2" in calls

    async def test_first_cancel_stops_chain(self):
        """Test that first extension cancelling stops the chain."""
        calls = []

        api1 = ExtensionAPI()

        @api1.on(EventType.TOOL_CALL)
        async def handler1(event: ToolCallEvent, ctx):
            calls.append("ext1")
            event.cancel()

        api2 = ExtensionAPI()

        @api2.on(EventType.TOOL_CALL)
        async def handler2(event: ToolCallEvent, ctx):
            calls.append("ext2")

        ext1 = LoadedExtension(
            name="ext1",
            handlers=api1._handlers,
            tools={},
            commands={}
        )
        ext2 = LoadedExtension(
            name="ext2",
            handlers=api2._handlers,
            tools={},
            commands={}
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext1, ext2], context=ctx)

        event = ToolCallEvent(tool_name="test", args={})
        result = await runner.emit(event)

        assert result.cancelled
        assert "ext1" in calls
        # ext2 should not be called after ext1 cancelled
        assert "ext2" not in calls


@pytest.mark.asyncio
class TestCancellableEvent:
    """Test CancellableEvent base class."""

    async def test_cancel_method(self):
        """Test that cancel() method works."""
        event = BeforeCompactEvent(messages=[])
        assert not event.cancelled

        event.cancel()
        assert event.cancelled

    async def test_cancellable_property(self):
        """Test cancelled property."""
        event = ToolCallEvent(tool_name="test", args={})
        assert not event.cancelled

        event.cancelled = True
        assert event.cancelled


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
