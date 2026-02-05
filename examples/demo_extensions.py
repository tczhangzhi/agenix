#!/usr/bin/env python3
"""Demo: Extension System in Action

This script demonstrates the power of the new extension system.
"""

import asyncio


async def demo_extension_system():
    """Demonstrate the extension system capabilities."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "EXTENSION SYSTEM DEMONSTRATION" + " " * 23 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    # 1. Load Extensions
    print("=" * 70)
    print("1. LOADING EXTENSIONS")
    print("=" * 70)

    from agenix.extensions import discover_and_load_extensions

    extensions = await discover_and_load_extensions(
        cwd='.',
        builtin_extensions=[
            'agenix.extensions.builtin.memory',
            'agenix.extensions.builtin.safety',
        ]
    )

    print(f"\n✓ Loaded {len(extensions)} extensions:\n")
    for ext in extensions:
        print(f"  📦 {ext.name}")
        if ext.tools:
            print(f"     Tools: {', '.join(ext.tools.keys())}")
        if ext.handlers:
            handlers = [str(et.value) for et in ext.handlers.keys()]
            print(f"     Events: {', '.join(handlers)}")
        print()

    # 2. Event Cancellation
    print("=" * 70)
    print("2. EVENT CANCELLATION (Safety Extension)")
    print("=" * 70)

    from agenix.extensions import (
        ExtensionRunner,
        ExtensionContext,
        ToolCallEvent
    )

    class MockAgent:
        messages = []

    ctx = ExtensionContext(agent=MockAgent(), cwd='.', tools=[])
    runner = ExtensionRunner(extensions, ctx)

    print("\nAttempting dangerous operations:\n")

    # Test 1: Dangerous bash command
    event1 = ToolCallEvent("bash", {"command": "rm -rf /etc"})
    await runner.emit(event1)
    status1 = "🚫 BLOCKED" if event1.cancelled else "✅ ALLOWED"
    print(f"  {status1}: bash 'rm -rf /etc'")

    # Test 2: Safe bash command
    event2 = ToolCallEvent("bash", {"command": "ls -la"})
    await runner.emit(event2)
    status2 = "🚫 BLOCKED" if event2.cancelled else "✅ ALLOWED"
    print(f"  {status2}: bash 'ls -la'")

    # Test 3: System file write
    event3 = ToolCallEvent("write", {"file_path": "/etc/hosts"})
    await runner.emit(event3)
    status3 = "🚫 BLOCKED" if event3.cancelled else "✅ ALLOWED"
    print(f"  {status3}: write '/etc/hosts'")

    # Test 4: Safe file write
    event4 = ToolCallEvent("write", {"file_path": "/tmp/test.txt"})
    await runner.emit(event4)
    status4 = "🚫 BLOCKED" if event4.cancelled else "✅ ALLOWED"
    print(f"  {status4}: write '/tmp/test.txt'")

    # 3. Event Modification
    print("\n" + "=" * 70)
    print("3. EVENT MODIFICATION (Custom Instructions)")
    print("=" * 70)

    from agenix.extensions import BeforeCompactEvent

    event = BeforeCompactEvent([])
    print("\n  Before: custom_instructions =", event.custom_instructions)

    await runner.emit(event)
    print("  After:  custom_instructions =", repr(event.custom_instructions))

    if event.custom_instructions:
        print("\n  ✓ Safety extension injected custom instructions")

    # 4. Tool Registration
    print("\n" + "=" * 70)
    print("4. DYNAMIC TOOL REGISTRATION (Memory Extension)")
    print("=" * 70)

    tools = runner.get_tools()
    print(f"\n  Registered {len(tools)} tools:\n")

    for tool_name, tool_def in tools.items():
        print(f"    🔧 {tool_name}")
        print(f"       {tool_def.description}")

    # 5. Summary
    print("\n" + "=" * 70)
    print("5. ARCHITECTURE BENEFITS")
    print("=" * 70)

    print("""
  ✅ Minimal Core      - Agent loop + events only (~500 lines)
  ✅ Event-Driven      - Zero hardcoded dependencies
  ✅ Self-Editable     - Agent can modify extensions
  ✅ Composable        - Mix and match extensions
  ✅ Safe              - Controlled access via ExtensionContext
  ✅ Extensible        - Drop files to add features

  Example: Block dangerous operations by creating:
    ~/.agenix/extensions/my_safety.py

  No core changes needed! 🎉
""")

    print("=" * 70)
    print()


async def demo_event_flow():
    """Show the event flow through the system."""
    print("=" * 70)
    print("6. EVENT FLOW VISUALIZATION")
    print("=" * 70)

    from agenix.extensions import EventType

    lifecycle_events = [
        ("SESSION_START", "CLI starts"),
        ("BEFORE_AGENT_START", "User submits prompt (can inject messages)"),
        ("AGENT_START", "Agent loop starts"),
        ("TURN_START", "LLM turn starts"),
        ("CONTEXT", "Before LLM call (can modify messages)"),
        ("TOOL_CALL", "Before tool execution (can block)"),
        ("TOOL_RESULT", "After tool execution"),
        ("TURN_END", "Turn completes"),
        ("AGENT_END", "Agent loop ends"),
        ("SESSION_END", "Before cleanup"),
        ("SESSION_SHUTDOWN", "Final cleanup"),
    ]

    print("\nAgent Lifecycle:\n")
    indent = 0
    for event, description in lifecycle_events:
        if event in ["AGENT_START", "TURN_START"]:
            indent += 2
        elif event in ["SESSION_END", "AGENT_END", "TURN_END"]:
            indent -= 2

        arrow = "  " * indent + "└─"
        print(f"{arrow} {event:20} → {description}")

    print("\nCompaction Flow:\n")
    print("  └─ BEFORE_COMPACT          → Extensions can cancel/customize")
    print("     └─ COMPACT              → Notification after compaction")

    print()


if __name__ == "__main__":
    asyncio.run(demo_extension_system())
    asyncio.run(demo_event_flow())
    print("✨ Extension system demonstration complete!\n")
