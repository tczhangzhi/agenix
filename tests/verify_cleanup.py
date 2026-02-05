#!/usr/bin/env python3
"""Verify cleanup is complete and working."""

import asyncio
import sys


async def verify_cleanup():
    """Verify that cleanup was successful."""
    print("\n" + "=" * 70)
    print("CLEANUP VERIFICATION")
    print("=" * 70 + "\n")

    errors = []
    checks_passed = 0

    # Check 1: Old tool files are deleted
    print("1. Checking old tool files are deleted...")
    import os
    old_files = [
        "agenix/tools/memory.py",
        "agenix/tools/cron.py"
    ]
    for file_path in old_files:
        if os.path.exists(file_path):
            errors.append(f"  ✗ Old file still exists: {file_path}")
        else:
            print(f"  ✓ Deleted: {file_path}")
            checks_passed += 1

    # Check 2: Service class files still exist (needed by extensions)
    print("\n2. Checking service class files exist...")
    service_files = [
        "agenix/heartbeat.py",
        "agenix/memory.py",
        "agenix/cron/service.py"
    ]
    for file_path in service_files:
        if os.path.exists(file_path):
            print(f"  ✓ Exists: {file_path}")
            checks_passed += 1
        else:
            errors.append(f"  ✗ Missing service file: {file_path}")

    # Check 3: Extensions can load
    print("\n3. Checking extensions load correctly...")
    try:
        from agenix.extensions import discover_and_load_extensions

        extensions = await discover_and_load_extensions(
            cwd='.',
            builtin_extensions=[
                'agenix.extensions.builtin.memory',
                'agenix.extensions.builtin.cron',
                'agenix.extensions.builtin.heartbeat',
            ]
        )

        if len(extensions) == 3:
            print(f"  ✓ Loaded {len(extensions)} extensions")
            checks_passed += 1
        else:
            errors.append(f"  ✗ Expected 3 extensions, got {len(extensions)}")

        # Check tools are registered
        from agenix.extensions import ExtensionRunner, ExtensionContext

        class MockAgent:
            messages = []

        ctx = ExtensionContext(agent=MockAgent(), cwd='.', tools=[])
        runner = ExtensionRunner(extensions, ctx)

        tools = runner.get_tools()
        expected_tools = {"MemoryRead", "MemoryWrite", "CronList", "CronAdd", "CronRemove"}
        actual_tools = set(tools.keys())

        if expected_tools == actual_tools:
            print(f"  ✓ All {len(expected_tools)} tools registered correctly")
            checks_passed += 1
        else:
            missing = expected_tools - actual_tools
            extra = actual_tools - expected_tools
            if missing:
                errors.append(f"  ✗ Missing tools: {missing}")
            if extra:
                errors.append(f"  ✗ Extra tools: {extra}")

    except Exception as e:
        errors.append(f"  ✗ Extension loading failed: {e}")
        import traceback
        traceback.print_exc()

    # Check 4: Imports don't reference old tools
    print("\n4. Checking old tool imports are removed...")
    try:
        import agenix
        import agenix.tools

        old_tools = ["MemoryReadTool", "MemoryWriteTool", "CronListTool", "CronAddTool", "CronRemoveTool"]

        for tool_name in old_tools:
            if hasattr(agenix, tool_name):
                errors.append(f"  ✗ Old tool still exported from agenix: {tool_name}")
            elif hasattr(agenix.tools, tool_name):
                errors.append(f"  ✗ Old tool still exported from agenix.tools: {tool_name}")
            else:
                print(f"  ✓ {tool_name} not exported")
                checks_passed += 1

    except Exception as e:
        errors.append(f"  ✗ Import check failed: {e}")

    # Check 5: CLI.py syntax is valid
    print("\n5. Checking cli.py syntax...")
    try:
        import ast
        with open('agenix/cli.py', 'r') as f:
            ast.parse(f.read())
        print("  ✓ cli.py syntax valid")
        checks_passed += 1
    except Exception as e:
        errors.append(f"  ✗ cli.py syntax error: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if errors:
        print(f"\n❌ {len(errors)} errors found:\n")
        for error in errors:
            print(error)
        print(f"\n✓ {checks_passed} checks passed")
        print(f"✗ {len(errors)} checks failed\n")
        return False
    else:
        print(f"\n✅ All {checks_passed} checks passed!")
        print("\nCleanup verification complete:")
        print("  • Old tool files deleted")
        print("  • Service classes preserved")
        print("  • Extensions load correctly")
        print("  • Tools registered via extensions")
        print("  • Old imports removed")
        print("  • Syntax valid\n")
        return True


if __name__ == "__main__":
    success = asyncio.run(verify_cleanup())
    sys.exit(0 if success else 1)
