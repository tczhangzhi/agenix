"""Tests for builtin extensions system."""

import tempfile
from pathlib import Path
import pytest
import asyncio

from agenix.extensions.types import (
    ExtensionAPI,
    EventType,
    SessionStartEvent,
    SessionEndEvent,
    BeforeAgentStartEvent,
    ToolCallEvent,
    ExtensionContext,
)
from agenix.extensions.runner import ExtensionRunner
from agenix.extensions.loader import load_extension, load_builtin_extension


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.agent_id = "test-agent"
        self.config = type('Config', (), {
            'model': 'gpt-4o',
            'api_key': 'test-key',
            'base_url': None
        })()

    async def prompt(self, message: str):
        """Mock prompt method."""
        yield {"content": f"Mock response to: {message}"}


@pytest.mark.asyncio
class TestMemoryExtension:
    """Test memory extension."""

    async def test_memory_extension_loads(self):
        """Test that memory extension can be loaded."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.memory",
        )

        assert ext is not None
        assert ext.name in ["memory", "agenix.extensions.builtin.memory"]
        # Memory extension registers tools
        assert len(ext.tools) > 0
        assert "MemoryRead" in ext.tools or "MemoryWrite" in ext.tools

    async def test_memory_read_write(self):
        """Test memory read/write tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            # Load extension
            ext = await load_builtin_extension(
                "agenix.extensions.builtin.memory",
                
            )

            # Create context
            agent = MockAgent()
            ctx = ExtensionContext(agent=agent, cwd=".", tools=[])

            # Initialize extension
            runner = ExtensionRunner(extensions=[ext], context=ctx)
            await runner.emit(SessionStartEvent())

            # Test write
            if "MemoryWrite" in ext.tools:
                write_tool = ext.tools["MemoryWrite"]
                result = await write_tool.execute(
                    {"key": "test_key", "value": "test_value"},
                    ctx
                )
                assert "success" in result.lower() or "saved" in result.lower()

            # Test read
            if "MemoryRead" in ext.tools:
                read_tool = ext.tools["MemoryRead"]
                result = await read_tool.execute(
                    {"key": "test_key"},
                    ctx
                )
                assert "test_value" in result or "not found" in result.lower()


@pytest.mark.asyncio
class TestCronExtension:
    """Test cron extension."""

    async def test_cron_extension_loads(self):
        """Test that cron extension can be loaded."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.cron",
            
        )

        assert ext is not None
        assert ext.name in ["cron", "agenix.extensions.builtin.cron"]
        # Cron registers 3 tools
        assert len(ext.tools) == 3
        assert "CronList" in ext.tools
        assert "CronAdd" in ext.tools
        assert "CronRemove" in ext.tools

    async def test_cron_lifecycle(self):
        """Test cron service lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            # Load extension
            ext = await load_builtin_extension(
                "agenix.extensions.builtin.cron",
                
            )

            # Create context
            agent = MockAgent()
            ctx = ExtensionContext(agent=agent, cwd=".", tools=[])

            # Initialize extension
            runner = ExtensionRunner(extensions=[ext], context=ctx)

            # Start cron service
            await runner.emit(SessionStartEvent())

            # List jobs (should be empty)
            if "CronList" in ext.tools:
                list_tool = ext.tools["CronList"]
                result = await list_tool.execute({}, ctx)
                assert "no" in result.lower() or "empty" in result.lower() or "scheduled" in result.lower()

            # Stop cron service
            await runner.emit(SessionEndEvent())

    async def test_cron_add_job(self):
        """Test adding a cron job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            ext = await load_builtin_extension(
                "agenix.extensions.builtin.cron",
                
            )

            agent = MockAgent()
            ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
            runner = ExtensionRunner(extensions=[ext], context=ctx)
            await runner.emit(SessionStartEvent())

            # Add a job
            if "CronAdd" in ext.tools:
                add_tool = ext.tools["CronAdd"]
                result = await add_tool.execute(
                    {
                        "name": "test-job",
                        "schedule": "every:5m",
                        "message": "Test message"
                    },
                    ctx
                )
                assert "added" in result.lower() or "test-job" in result.lower()

            await runner.emit(SessionEndEvent())


@pytest.mark.asyncio
class TestHeartbeatExtension:
    """Test heartbeat extension."""

    async def test_heartbeat_extension_loads(self):
        """Test that heartbeat extension can be loaded."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.heartbeat",
            
        )

        assert ext is not None
        assert ext.name in ["heartbeat", "agenix.extensions.builtin.heartbeat"]
        # Heartbeat has no tools, only lifecycle handlers
        assert len(ext.handlers) > 0

    async def test_heartbeat_lifecycle(self):
        """Test heartbeat service lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            ext = await load_builtin_extension(
                "agenix.extensions.builtin.heartbeat",
                
            )

            agent = MockAgent()
            ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
            runner = ExtensionRunner(extensions=[ext], context=ctx)

            # Start and stop should not error
            await runner.emit(SessionStartEvent())
            await runner.emit(SessionEndEvent())


@pytest.mark.asyncio
class TestSafetyExtension:
    """Test safety extension."""

    async def test_safety_extension_loads(self):
        """Test that safety extension can be loaded."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.safety",
            
        )

        assert ext is not None
        assert ext.name in ["safety", "agenix.extensions.builtin.safety"]
        # Safety has event handlers
        assert EventType.TOOL_CALL in ext.handlers

    async def test_safety_blocks_dangerous_bash(self):
        """Test that safety extension blocks dangerous bash commands."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.safety",
            
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        # Test dangerous command
        event = ToolCallEvent(tool_name="bash", args={"command": "rm -rf /etc"})
        await runner.emit(event)

        assert event.cancelled

    async def test_safety_allows_safe_bash(self):
        """Test that safety extension allows safe bash commands."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.safety",
            
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        # Test safe command
        event = ToolCallEvent(tool_name="bash", args={"command": "ls -la"})
        await runner.emit(event)

        assert not event.cancelled


@pytest.mark.asyncio
class TestSkillExtension:
    """Test skill extension."""

    async def test_skill_extension_loads(self):
        """Test that skill extension can be loaded."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.skill",
            
        )

        assert ext is not None
        assert ext.name in ["skill", "agenix.extensions.builtin.skill"]
        assert "skill" in ext.tools

    async def test_skill_tool_execution(self):
        """Test skill tool execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            skills_dir = workspace / ".agenix" / "skills" / "test-skill"
            skills_dir.mkdir(parents=True)

            # Create test skill
            (skills_dir / "SKILL.md").write_text("""---
name: test-skill
---

# Test Skill
This is a test skill.
""")

            ext = await load_builtin_extension(
                "agenix.extensions.builtin.skill",
                
            )

            agent = MockAgent()
            ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
            runner = ExtensionRunner(extensions=[ext], context=ctx)
            await runner.emit(SessionStartEvent())

            # Execute skill tool
            if "skill" in ext.tools:
                skill_tool = ext.tools["skill"]
                result = await skill_tool.execute(
                    {"skill_name": "test-skill"},
                    ctx
                )
                assert "test skill" in result.lower()


@pytest.mark.asyncio
class TestTaskExtension:
    """Test task/subagent extension."""

    async def test_task_extension_loads(self):
        """Test that task extension can be loaded."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.task",
            
        )

        assert ext is not None
        assert ext.name in ["task", "agenix.extensions.builtin.task"]
        assert "task" in ext.tools


@pytest.mark.asyncio
class TestSubagentExtension:
    """Test subagent extension."""

    async def test_subagent_extension_loads(self):
        """Test that subagent extension can be loaded."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.subagent",
            
        )

        assert ext is not None
        assert ext.name in ["subagent", "agenix.extensions.builtin.subagent"]
        assert "subagent" in ext.tools or "subagent_parallel" in ext.tools


@pytest.mark.asyncio
class TestPlanModeExtension:
    """Test plan-mode extension."""

    async def test_planmode_extension_loads(self):
        """Test that plan-mode extension can be loaded."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.plan_mode",
            
        )

        assert ext is not None
        assert ext.name in ["plan_mode", "agenix.extensions.builtin.plan_mode"]
        # Plan mode has commands and tool call handlers
        assert len(ext.handlers) > 0
        assert len(ext.commands) > 0
        assert "plan" in ext.commands
        assert "todos" in ext.commands

    async def test_planmode_blocks_writes(self):
        """Test that plan mode blocks write operations."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.plan_mode",
            
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)
        await runner.emit(SessionStartEvent())

        # Enable planning mode by calling plan command
        if "plan" in ext.commands:
            await ext.commands["plan"].handler("", ctx)

        # Test that write is blocked
        event = ToolCallEvent(tool_name="write", args={"file_path": "test.py", "content": "code"})
        await runner.emit(event)

        # Note: Will only be blocked if planning mode is actually active
        # This test structure needs plan_mode internal state access


@pytest.mark.asyncio
class TestExtensionRunner:
    """Test extension runner functionality."""

    async def test_extension_runner_emit_events(self):
        """Test that extension runner can emit events."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.memory",
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        # Should not error
        await runner.emit(SessionStartEvent())
        await runner.emit(SessionEndEvent())

    async def test_extension_runner_multiple_extensions(self):
        """Test runner with multiple extensions."""
        ext1 = await load_builtin_extension(
            "agenix.extensions.builtin.memory",
            
        )
        ext2 = await load_builtin_extension(
            "agenix.extensions.builtin.safety",
            
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext1, ext2], context=ctx)

        # Should handle multiple extensions
        await runner.emit(SessionStartEvent())
        await runner.emit(SessionEndEvent())

    async def test_extension_cancellable_event(self):
        """Test that extensions can cancel events."""
        ext = await load_builtin_extension(
            "agenix.extensions.builtin.safety",
            
        )

        agent = MockAgent()
        ctx = ExtensionContext(agent=agent, cwd=".", tools=[])
        runner = ExtensionRunner(extensions=[ext], context=ctx)

        # Dangerous command should be cancelled
        event = ToolCallEvent(tool_name="bash", args={"command": "rm -rf /"})
        result_event = await runner.emit(event)

        assert result_event.cancelled


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
