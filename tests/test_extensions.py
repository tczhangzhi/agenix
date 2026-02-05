#!/usr/bin/env python3
"""Test the extension system implementation."""

import asyncio
import sys


async def test_extension_loading():
    """Test that all built-in extensions load correctly."""
    print("=" * 60)
    print("TEST 1: Extension Loading")
    print("=" * 60)

    from agenix.extensions import discover_and_load_extensions

    builtin = [
        'agenix.extensions.builtin.cli_channel',
        'agenix.extensions.builtin.cron',
        'agenix.extensions.builtin.memory',
        'agenix.extensions.builtin.heartbeat',
        'agenix.extensions.builtin.safety',
    ]

    extensions = await discover_and_load_extensions(
        cwd='.',
        builtin_extensions=builtin
    )

    print(f"✓ Loaded {len(extensions)} extensions")
    assert len(extensions) == 5, f"Expected 5 extensions, got {len(extensions)}"

    for ext in extensions:
        print(f"  ✓ {ext.name:15} - Tools: {len(ext.tools)}, Handlers: {len(ext.handlers)}")

    print()
    return True


async def test_event_types():
    """Test that all new event types are available."""
    print("=" * 60)
    print("TEST 2: Event Types")
    print("=" * 60)

    from agenix.extensions import EventType

    expected_events = [
        'SESSION_START', 'SESSION_END', 'SESSION_SHUTDOWN',
        'BEFORE_AGENT_START', 'AGENT_START', 'AGENT_END',
        'TURN_START', 'TURN_END',
        'TOOL_CALL', 'TOOL_RESULT',
        'CONTEXT', 'BEFORE_COMPACT', 'COMPACT',
        'USER_INPUT',
        'MESSAGE_START', 'MESSAGE_UPDATE', 'MESSAGE_END',
        'MODEL_SELECT'
    ]

    available = [e.name for e in EventType]

    for event in expected_events:
        assert event in available, f"Missing event type: {event}"

    print(f"✓ All {len(expected_events)} event types available")
    print()
    return True


async def test_cancellable_events():
    """Test that cancellable events work correctly."""
    print("=" * 60)
    print("TEST 3: Cancellable Events")
    print("=" * 60)

    from agenix.extensions import (
        BeforeAgentStartEvent,
        BeforeCompactEvent,
        ToolCallEvent
    )

    # Test BeforeAgentStartEvent
    event1 = BeforeAgentStartEvent("test prompt")
    assert not event1.cancelled
    event1.cancel()
    assert event1.cancelled
    print("✓ BeforeAgentStartEvent cancellation works")

    # Test BeforeCompactEvent
    event2 = BeforeCompactEvent([])
    assert not event2.cancelled
    event2.cancel()
    assert event2.cancelled
    assert event2.custom_instructions is None
    event2.custom_instructions = "Test instructions"
    assert event2.custom_instructions == "Test instructions"
    print("✓ BeforeCompactEvent cancellation and modification works")

    # Test ToolCallEvent
    event3 = ToolCallEvent("bash", {"command": "ls"})
    assert not event3.cancelled
    event3.cancel()
    assert event3.cancelled
    print("✓ ToolCallEvent cancellation works")

    print()
    return True


async def test_extension_runner():
    """Test extension runner with cancellable events."""
    print("=" * 60)
    print("TEST 4: Extension Runner")
    print("=" * 60)

    from agenix.extensions import (
        ExtensionRunner,
        ExtensionContext,
        ToolCallEvent,
        EventType
    )
    from agenix.extensions.loader import load_builtin_extension

    # Load safety extension
    safety_ext = await load_builtin_extension('agenix.extensions.builtin.safety')
    assert safety_ext is not None

    # Create mock context
    class MockAgent:
        messages = []

    ctx = ExtensionContext(
        agent=MockAgent(),
        cwd='.',
        tools=[]
    )

    runner = ExtensionRunner([safety_ext], ctx)

    # Test that dangerous commands are blocked
    event = ToolCallEvent("bash", {"command": "rm -rf /etc"})
    await runner.emit(event)
    assert event.cancelled, "Expected dangerous command to be blocked"
    print("✓ Safety extension blocks dangerous commands")

    # Test that safe commands are not blocked
    event2 = ToolCallEvent("bash", {"command": "ls -la"})
    await runner.emit(event2)
    assert not event2.cancelled, "Expected safe command to pass"
    print("✓ Safety extension allows safe commands")

    # Test that system file writes are blocked
    event3 = ToolCallEvent("write", {"file_path": "/etc/hosts"})
    await runner.emit(event3)
    assert event3.cancelled, "Expected system file write to be blocked"
    print("✓ Safety extension blocks system file writes")

    print()
    return True


async def test_memory_extension():
    """Test memory extension tools."""
    print("=" * 60)
    print("TEST 5: Memory Extension")
    print("=" * 60)

    from agenix.extensions.loader import load_builtin_extension

    memory_ext = await load_builtin_extension('agenix.extensions.builtin.memory')
    assert memory_ext is not None

    # Check that tools are registered
    assert 'MemoryRead' in memory_ext.tools
    assert 'MemoryWrite' in memory_ext.tools
    print("✓ Memory tools registered")

    # Check tool definitions
    read_tool = memory_ext.tools['MemoryRead']
    assert read_tool.name == 'MemoryRead'
    assert 'scope' in read_tool.parameters['properties']
    print("✓ MemoryRead tool definition correct")

    write_tool = memory_ext.tools['MemoryWrite']
    assert write_tool.name == 'MemoryWrite'
    assert 'scope' in write_tool.parameters['properties']
    assert 'content' in write_tool.parameters['properties']
    print("✓ MemoryWrite tool definition correct")

    print()
    return True


async def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "EXTENSION SYSTEM TESTS" + " " * 25 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    tests = [
        test_extension_loading,
        test_event_types,
        test_cancellable_events,
        test_extension_runner,
        test_memory_extension,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    print()

    if failed > 0:
        sys.exit(1)
    else:
        print("✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
