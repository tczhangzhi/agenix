# Extension System Architecture

## Overview

The agenix extension system follows a **Pi-Mono inspired architecture** where the agent core is minimal and immutable, while all features are implemented as composable extensions.

## Philosophy

### Unix Philosophy Applied
1. **Do one thing well**: Agent core = loop + events only
2. **Compose features**: Extensions subscribe to events
3. **Everything is an extension**: CLI, cron, memory, tools - no special cases

### Key Principles
- ✅ **Minimal Core**: Agent core ~500 lines (immutable)
- ✅ **Event-Driven**: Zero hardcoded dependencies
- ✅ **Controlled Access**: ExtensionContext instead of raw agent
- ✅ **Composable**: Mix and match extensions
- ✅ **Self-Editable**: Agent can modify extensions without touching core

## Architecture

```
cli.py (minimal bootstrap ~50 lines)
  ├─ Agent (core) ← IMMUTABLE
  │   └─ Events: SESSION_START, AGENT_START, TURN_START, CONTEXT, TOOL_CALL, ...
  │
  └─ Extension System
       ├─ Core Tools (read, write, edit, bash)
       │   └─ Fundamental operations
       │
       └─ Extensions (everything else)
            ├─ Built-in Extensions
            │   ├─ cli_channel.py - UI lifecycle hooks
            │   ├─ cron.py - Scheduled tasks
            │   ├─ memory.py - Memory tools
            │   ├─ heartbeat.py - Periodic checks
            │   └─ safety.py - Example safety extension
            │
            └─ User Extensions (third-party)
                 ├─ ~/.agenix/extensions/
                 └─ .agenix/extensions/
```

## Lifecycle Events

### Session Lifecycle
```
SESSION_START              → CLI starts
  └─ BEFORE_AGENT_START    → User submits prompt (can inject messages)
     └─ AGENT_START        → Agent loop starts
        └─ TURN_START      → Each LLM turn starts
           ├─ CONTEXT      → Before LLM call (can modify messages)
           ├─ TOOL_CALL    → Before tool execution (can block)
           ├─ TOOL_RESULT  → After tool execution
           └─ TURN_END     → Turn completes
        └─ AGENT_END       → Agent loop ends
SESSION_END                → Before cleanup
SESSION_SHUTDOWN           → Final cleanup
```

### Compaction Events
```
BEFORE_COMPACT             → Before compaction (can cancel/modify)
COMPACT                    → After compaction
```

## Event Powers

### Cancellable Events
Extensions can cancel operations by calling `event.cancel()`:

```python
@api.on(EventType.TOOL_CALL)
async def on_tool_call(event: ToolCallEvent, ctx):
    if event.tool_name == "bash" and "rm -rf" in event.args["command"]:
        event.cancel()
        ctx.notify("Blocked dangerous command", "warning")
```

### Modifiable Events
Extensions can modify event data:

```python
@api.on(EventType.BEFORE_COMPACT)
async def on_before_compact(event: BeforeCompactEvent, ctx):
    # Customize compaction instructions
    event.custom_instructions = "Preserve all file paths and tool names."

@api.on(EventType.CONTEXT)
async def on_context(event: ContextEvent, ctx):
    # Modify messages before LLM sees them
    event.messages.insert(0, SystemMessage(content="Be careful!"))
```

## Event Types

### Core Events
- `SESSION_START` - Session begins
- `SESSION_END` - Session ends
- `SESSION_SHUTDOWN` - Final cleanup
- `BEFORE_AGENT_START` - Before agent loop (cancellable)
- `AGENT_START` - Agent loop starts
- `AGENT_END` - Agent loop ends

### Turn Events
- `TURN_START` - Turn begins
- `TURN_END` - Turn ends
- `CONTEXT` - Before LLM call (modifiable)

### Tool Events
- `TOOL_CALL` - Before tool execution (cancellable)
- `TOOL_RESULT` - After tool execution

### Compaction Events
- `BEFORE_COMPACT` - Before compaction (cancellable, modifiable)
- `COMPACT` - After compaction

### Input/UI Events
- `USER_INPUT` - User input received
- `MESSAGE_START` - Message streaming starts
- `MESSAGE_UPDATE` - Message streaming update
- `MESSAGE_END` - Message streaming ends
- `MODEL_SELECT` - Model changed

## Extension API

### Setup Function
Every extension must export an `async def setup(api: ExtensionAPI)` function:

```python
async def setup(api: ExtensionAPI):
    """Setup extension."""

    # Register event handlers
    @api.on(EventType.SESSION_START)
    async def on_session_start(event, ctx):
        print("Session started!")

    # Register tools
    api.register_tool(ToolDefinition(
        name="MyTool",
        description="My custom tool",
        parameters={...},
        execute=my_tool_handler
    ))

    # Register commands
    api.register_command(CommandDefinition(
        name="mycommand",
        description="My custom command",
        handler=my_command_handler
    ))
```

### ExtensionContext
Context passed to event handlers provides controlled access:

```python
class ExtensionContext:
    agent: Agent          # Full agent access (use carefully)
    cwd: str             # Working directory
    tools: List[Tool]    # Available tools
    messages: List[Message]  # Current conversation (read-only)

    def notify(message: str, type: str = "info") -> None:
        """Show notification to user"""
```

## Creating Extensions

### Built-in Extensions
Located in `agenix/extensions/builtin/`:

1. Create a Python file (e.g., `myext.py`)
2. Implement `async def setup(api: ExtensionAPI)`
3. Register handlers, tools, commands
4. Add to builtin list in `cli.py`

### User Extensions
Located in:
- Global: `~/.agenix/extensions/`
- Project: `.agenix/extensions/`

Auto-discovered and loaded at startup.

## Example: Safety Extension

```python
async def setup(api: ExtensionAPI):
    """Block dangerous operations."""

    DANGEROUS_PATHS = ["/etc", "/sys", "/usr"]

    @api.on(EventType.TOOL_CALL)
    async def on_tool_call(event: ToolCallEvent, ctx):
        # Block dangerous bash commands
        if event.tool_name == "bash":
            command = event.args.get("command", "")
            if any(path in command for path in DANGEROUS_PATHS):
                event.cancel()
                ctx.notify(f"Blocked: {command}", "warning")

        # Block system file modifications
        if event.tool_name in ["write", "edit"]:
            file_path = event.args.get("file_path", "")
            if any(file_path.startswith(p) for p in DANGEROUS_PATHS):
                event.cancel()
                ctx.notify(f"Blocked: {file_path}", "error")

    @api.on(EventType.BEFORE_COMPACT)
    async def on_before_compact(event: BeforeCompactEvent, ctx):
        # Preserve important info during compaction
        event.custom_instructions = (
            "Preserve all file paths and error messages."
        )
```

## Benefits

### Before (Hardcoded Services)
```
cli.py (398 lines of hardcoded logic)
  ├─ Hardcoded: CLI, CronService, MemoryStore, HeartbeatService
  ├─ Hardcoded: Tools initialization
  ├─ Hardcoded: Service lifecycle management
  └─ Agent (core)
```

❌ 398 lines of service wiring
❌ Can't modify without editing core
❌ Agent can't edit itself
❌ Hard to test individual services
❌ Tight coupling

### After (Extension System)
```
cli.py (minimal bootstrap)
  ├─ Agent (core) ← IMMUTABLE
  └─ Extensions (composable)
```

✅ Tiny core (~500 lines)
✅ Decoupled (events only)
✅ Self-editable (agent modifies extensions)
✅ Testable (each extension independent)
✅ Extensible (users add features)
✅ Hot-swappable (load/unload at runtime)
✅ Safe (ExtensionContext limits access)

## Migration Path

### Phase 1: Core (No Breaking Changes)
- ✅ Add lifecycle methods to Agent
- ✅ Add new event types
- ✅ Ensure events emitted consistently

### Phase 2: Extensions (Backward Compatible)
- ✅ Create built-in extensions
- ✅ Keep old code paths working
- ✅ Add extension loading to cli.py

### Phase 3: Cleanup (Breaking Changes)
- ⏳ Remove old service initialization from cli.py
- ⏳ Move all service logic to extensions
- ⏳ Update documentation

### Phase 4: Polish
- ⏳ Add extension documentation
- ⏳ Add example custom extensions
- ⏳ Add extension development guide

## Testing

### Test Extension Loading
```bash
python -c "
import asyncio
from agenix.extensions import discover_and_load_extensions

async def test():
    extensions = await discover_and_load_extensions(
        cwd='.',
        builtin_extensions=[
            'agenix.extensions.builtin.memory',
            'agenix.extensions.builtin.cron',
        ]
    )
    print(f'Loaded {len(extensions)} extensions')

asyncio.run(test())
"
```

### Test Event Cancellation
```python
from agenix.extensions import ToolCallEvent, EventType

event = ToolCallEvent("bash", {"command": "rm -rf /"})
assert not event.cancelled

event.cancel()
assert event.cancelled
```

## Success Criteria

✅ Agent core emits lifecycle events consistently
✅ Extensions loaded from built-in and user directories
✅ CLI, cron, memory, heartbeat work as extensions
✅ Extensions can cancel/modify operations via events
✅ ExtensionContext provides controlled access
✅ All existing tests pass

## Next Steps

1. Migrate CLI logic to cli_channel extension
2. Remove hardcoded service initialization from cli.py
3. Add more example extensions (git auto-commit, logging, etc.)
4. Document extension development workflow
5. Add hot-reload support for development
