# Extension Quick Reference

## Create a New Extension

### 1. Create Extension File

**Location:**
- Built-in: `agenix/extensions/builtin/myext.py`
- User global: `~/.agenix/extensions/myext.py`
- Project local: `.agenix/extensions/myext.py`

**Template:**
```python
"""My extension description."""

from ..types import ExtensionAPI, EventType

async def setup(api: ExtensionAPI):
    """Setup extension."""

    # State (if needed)
    my_state = {}

    # Event handlers
    @api.on(EventType.SESSION_START)
    async def on_session_start(event, ctx):
        print("Session started!")

    # Register tools
    api.register_tool(ToolDefinition(
        name="MyTool",
        description="Does something useful",
        parameters={
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input data"}
            },
            "required": ["input"]
        },
        execute=lambda params, ctx: f"Result: {params['input']}"
    ))

    # Register commands
    api.register_command(CommandDefinition(
        name="mycommand",
        description="Execute my command",
        handler=lambda ctx, args: print(f"Command: {args}")
    ))
```

### 2. Enable Built-in Extension

Add to `cli.py` builtin list:
```python
builtin_extensions = [
    "agenix.extensions.builtin.myext",
    # ... other extensions
]
```

## Event Reference

### Cancellable Events
```python
# Can call event.cancel() to block operation
BEFORE_AGENT_START  # Block agent loop from starting
TOOL_CALL          # Block tool execution
BEFORE_COMPACT     # Cancel compaction
```

### Modifiable Events
```python
# Can modify event data
CONTEXT           # event.messages (modify before LLM)
BEFORE_COMPACT    # event.custom_instructions
```

### Notification Events
```python
# Read-only, for observation
SESSION_START
SESSION_END
SESSION_SHUTDOWN
AGENT_START
AGENT_END
TURN_START
TURN_END
TOOL_RESULT
COMPACT
USER_INPUT
MESSAGE_START
MESSAGE_UPDATE
MESSAGE_END
MODEL_SELECT
```

## Common Patterns

### Block Dangerous Tools
```python
@api.on(EventType.TOOL_CALL)
async def on_tool_call(event: ToolCallEvent, ctx):
    if should_block(event.tool_name, event.args):
        event.cancel()
        ctx.notify("Operation blocked", "warning")
```

### Modify Context
```python
@api.on(EventType.CONTEXT)
async def on_context(event: ContextEvent, ctx):
    # Inject system message
    event.messages.insert(0, SystemMessage(content="..."))
```

### Customize Compaction
```python
@api.on(EventType.BEFORE_COMPACT)
async def on_before_compact(event: BeforeCompactEvent, ctx):
    event.custom_instructions = "Preserve file paths and errors"
```

### Service Lifecycle
```python
service = None

@api.on(EventType.SESSION_START)
async def on_start(event, ctx):
    nonlocal service
    service = MyService()
    await service.start()

@api.on(EventType.SESSION_END)
async def on_end(event, ctx):
    if service:
        service.stop()
```

### Register Dynamic Tools
```python
@api.on(EventType.SESSION_START)
async def on_start(event, ctx):
    # Create service
    service = MyService()

    # Register tools that use the service
    api.register_tool(ToolDefinition(
        name="MyTool",
        description="Tool using service",
        parameters={...},
        execute=lambda params, ctx: service.handle(params)
    ))
```

## Testing

### Test Extension Loading
```python
import asyncio
from agenix.extensions.loader import load_builtin_extension

async def test():
    ext = await load_builtin_extension('agenix.extensions.builtin.myext')
    assert ext is not None
    print(f"Tools: {list(ext.tools.keys())}")
    print(f"Commands: {list(ext.commands.keys())}")
    print(f"Handlers: {list(ext.handlers.keys())}")

asyncio.run(test())
```

### Test Event Cancellation
```python
from agenix.extensions import ToolCallEvent

event = ToolCallEvent("bash", {"command": "rm -rf /"})
assert not event.cancelled

event.cancel()
assert event.cancelled
```

## Debugging

### Print All Events
```python
@api.on(EventType.TOOL_CALL)
async def log_tool_call(event, ctx):
    print(f"Tool: {event.tool_name}, Args: {event.args}")

@api.on(EventType.TURN_START)
async def log_turn(event, ctx):
    print(f"Turn {event.turn_index} starting")
```

### Inspect Context
```python
@api.on(EventType.AGENT_START)
async def inspect(event, ctx):
    print(f"CWD: {ctx.cwd}")
    print(f"Tools: {[t.name for t in ctx.tools]}")
    print(f"Messages: {len(ctx.messages)}")
```

## Common Mistakes

### ❌ Don't Access Agent Directly
```python
# Bad - tight coupling
ctx.agent.messages.append(...)
```

### ✅ Use Context Methods
```python
# Good - controlled access
ctx.notify("Message", "info")
```

### ❌ Don't Block in Handlers
```python
# Bad - blocks event loop
import time
time.sleep(10)
```

### ✅ Use Async/Await
```python
# Good - async
await asyncio.sleep(10)
```

### ❌ Don't Modify Immutable Events
```python
# Bad - trying to modify read-only event
event.data["something"] = "new"
```

### ✅ Use Provided Mutation Points
```python
# Good - use modifiable attributes
event.messages.append(...)
event.custom_instructions = "..."
```

## Extension Development Workflow

1. Create extension file
2. Implement `setup(api)` function
3. Test loading: `python -c "..."`
4. Add to builtin list (if built-in)
5. Test with full agent
6. Document in extension docstring

## Resources

- Architecture: `docs/EXTENSION_SYSTEM.md`
- Event Types: `agenix/extensions/types.py`
- Example Extensions: `agenix/extensions/builtin/`
- Extension Loader: `agenix/extensions/loader.py`
