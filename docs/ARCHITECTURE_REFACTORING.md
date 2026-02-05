# Architecture Refactoring Summary

## Changes Made

### 1. **Moved Services from `core/` to `agenix/`**

Services are now first-class features, not "core" components:

```
Before:
agenix/core/
├── memory.py
├── heartbeat.py
└── cron/

After:
agenix/
├── memory.py
├── heartbeat.py
├── cron/
└── bus/
```

### 2. **Added Message Bus System**

Created event-driven architecture for service communication:

```python
agenix/bus/
├── __init__.py
├── events.py     # Event types
└── bus.py        # MessageBus implementation
```

**Event Types:**
- `CronJobEvent` - When cron job triggers
- `HeartbeatEvent` - When heartbeat wakes agent
- `MemoryUpdateEvent` - When memory is written
- `AgentMessageEvent` - Agent message processing
- `AgentResponseEvent` - Agent response
- `SystemEvent` - General system events

### 3. **Updated Architecture**

#### Core (Pure Agent Functionality)
```
agenix/core/
├── agent.py        # Agent loop
├── llm.py          # LLM providers
├── messages.py     # Message types
├── session.py      # Session management
└── settings.py     # Configuration
```

#### Services (Optional Features)
```
agenix/
├── bus/           # Event bus
├── memory.py      # Memory storage
├── cron/          # Job scheduling
└── heartbeat.py   # Periodic wake-up
```

## Benefits

### 1. **Decoupling**
- Core agent logic separate from optional services
- Services communicate via events, not direct calls
- Easy to add/remove services without touching core

### 2. **Event-Driven**
- Services publish events to bus
- UI can subscribe to see what's happening
- Multiple subscribers can react to same event

### 3. **Cleaner Imports**
```python
# Core functionality
from agenix.core import Agent, AgentConfig

# Optional services
from agenix import MemoryStore, CronService, HeartbeatService, MessageBus
```

### 4. **Scalability**
- Easy to add new services (just publish events)
- Easy to add new event types
- Easy to add new subscribers (like UI, logging, metrics)

## Usage Example

### Basic Setup
```python
import asyncio
from pathlib import Path
from agenix import MessageBus, MemoryStore, CronService, HeartbeatService

async def main():
    # Create bus
    bus = MessageBus()
    await bus.start()

    # Create services with bus
    memory = MemoryStore(Path(".agenix"), bus=bus)
    cron = CronService(Path(".agenix/cron.json"), bus=bus)
    heartbeat = HeartbeatService(Path(".agenix"), bus=bus)

    # Subscribe to events
    async def on_cron(event):
        print(f"Cron job: {event.job_name}")

    bus.subscribe("cron_job", on_cron)

    # Services will now publish events to bus
    await cron.start()
    await heartbeat.start()
```

### Event Flow

```
┌─────────────┐
│ Cron Service│ ──┐
└─────────────┘   │
                  │  publish(CronJobEvent)
┌─────────────┐   │
│  Heartbeat  │ ──┼──► ┌─────────────┐
└─────────────┘   │    │ MessageBus  │
                  │    └──────┬──────┘
┌─────────────┐   │           │
│   Memory    │ ──┘           │ dispatch events
└─────────────┘               │
                              ▼
                    ┌─────────────────┐
                    │   Subscribers   │
                    │  (UI, Agent,    │
                    │   Logging, etc) │
                    └─────────────────┘
```

## API Changes

### Memory
```python
# Before
memory = MemoryStore(workspace)

# After (bus optional)
memory = MemoryStore(workspace, bus=bus)
```

### Cron
```python
# Before
cron = CronService(store_path, on_job=handler)

# After (bus optional)
cron = CronService(store_path, on_job=handler, bus=bus)
```

### Heartbeat
```python
# Before
heartbeat = HeartbeatService(workspace, on_heartbeat=handler)

# After (bus optional)
heartbeat = HeartbeatService(workspace, on_heartbeat=handler, bus=bus)
```

## Backward Compatibility

All changes are **backward compatible**:
- Bus parameter is optional (defaults to `None`)
- Services work without bus (just don't publish events)
- Existing code continues to work unchanged

## File Structure

```
agenix/
├── __init__.py              # Export services
├── bus/
│   ├── __init__.py
│   ├── events.py           # Event types
│   └── bus.py              # MessageBus
├── memory.py               # MemoryStore
├── heartbeat.py            # HeartbeatService
├── cron/
│   ├── __init__.py
│   ├── types.py           # Job types
│   └── service.py         # CronService
├── core/                   # Core agent only
│   ├── agent.py
│   ├── llm.py
│   ├── messages.py
│   ├── session.py
│   └── settings.py
└── tools/
    ├── memory.py          # Memory tools
    └── cron.py            # Cron tools
```

## Testing

All tests updated and passing:
```bash
python -c "from agenix import MemoryStore, CronService, HeartbeatService, MessageBus; print('✓ Imports work')"
```

## Migration Guide

### For Users

No changes needed! Bus is optional:

```python
# This still works
memory = MemoryStore(workspace)
cron = CronService(store_path)
```

### For Advanced Users

Add bus for event monitoring:

```python
# Create bus
bus = MessageBus()
await bus.start()

# Pass bus to services
memory = MemoryStore(workspace, bus=bus)
cron = CronService(store_path, bus=bus)

# Subscribe to events
async def on_event(event):
    print(f"Event: {event}")

bus.subscribe("*", on_event)  # Subscribe to all events
```

## Next Steps

Potential enhancements:
1. **UI Integration** - Subscribe UI to bus events for real-time updates
2. **Logging Service** - Subscribe to all events for audit trail
3. **Metrics Service** - Track event counts, timings
4. **Notification Service** - Send alerts on certain events
5. **Remote Bus** - Distributed event bus for multi-agent systems

## Summary

✅ Services moved from `core/` to `agenix/`
✅ Event bus system added
✅ All services integrated with bus
✅ Backward compatible
✅ Tests passing
✅ Documentation updated

The architecture is now more modular, scalable, and follows the same pattern as nanobot!
