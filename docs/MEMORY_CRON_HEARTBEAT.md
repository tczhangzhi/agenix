# Memory, Cron, and Heartbeat Features

This document describes the memory, cron scheduling, and heartbeat features added to agenix.

## Table of Contents

- [Memory System](#memory-system)
- [Cron Service](#cron-service)
- [Heartbeat Service](#heartbeat-service)
- [Quick Start](#quick-start)

## Memory System

The memory system provides persistent storage for agent notes and long-term memory.

### Features

- **Daily Notes**: Automatic date-based notes in `memory/YYYY-MM-DD.md`
- **Long-term Memory**: Persistent knowledge in `MEMORY.md`
- **Memory Context**: Combine recent and long-term memories for agent context

### API

```python
from pathlib import Path
from agenix.core import MemoryStore

# Initialize
memory = MemoryStore(Path(".agenix"))

# Write to today's notes (appends)
memory.append_today("- Completed task X")
memory.append_today("- Started working on feature Y")

# Read today's notes
notes = memory.read_today()

# Write long-term memory (replaces)
memory.write_long_term("""
# Project Knowledge

## Architecture
- Service A handles authentication
- Service B handles data processing

## Important Decisions
- Using PostgreSQL for primary database
- Redis for caching
""")

# Read long-term memory
knowledge = memory.read_long_term()

# Get recent memories (last N days)
recent = memory.get_recent_memories(days=7)

# Get full memory context for agent
context = memory.get_memory_context()
```

### Tools

The memory system includes two tools for agent use:

- **MemoryRead**: Read memory (today, long_term, recent, all)
- **MemoryWrite**: Write to memory (today, long_term)

```python
from agenix.tools import MemoryReadTool, MemoryWriteTool

tools = [
    MemoryReadTool(memory),
    MemoryWriteTool(memory),
]
```

## Cron Service

The cron service allows scheduling tasks to run at specific times or intervals.

### Features

- **Multiple Schedule Types**:
  - `at`: Run once at specific timestamp
  - `every`: Run repeatedly at interval
  - `cron`: Use cron expressions (requires `croniter` package)
- **Persistent Storage**: Jobs saved to JSON file
- **Job Management**: Enable/disable, list, remove jobs
- **Automatic Execution**: Background async task runner

### API

```python
from pathlib import Path
from agenix.core import CronService, CronSchedule

# Initialize with callback
async def on_job(job):
    """Handler called when job executes."""
    print(f"Executing: {job.name}")
    # Send job.payload.message to agent
    return "Job completed"

cron = CronService(
    store_path=Path(".agenix/cron.json"),
    on_job=on_job
)

# Start service
await cron.start()

# Add job - run every 1 hour
job = cron.add_job(
    name="Hourly check",
    schedule=CronSchedule(kind="every", every_ms=60*60*1000),
    message="Check for updates and summarize"
)

# Add job - run at specific time
from datetime import datetime
future_time = datetime(2026, 2, 10, 14, 30)  # 2:30 PM
at_ms = int(future_time.timestamp() * 1000)

job = cron.add_job(
    name="Meeting reminder",
    schedule=CronSchedule(kind="at", at_ms=at_ms),
    message="Team meeting in 5 minutes",
    delete_after_run=True
)

# Add job - cron expression (requires croniter)
job = cron.add_job(
    name="Daily report",
    schedule=CronSchedule(kind="cron", expr="0 9 * * *"),  # 9 AM daily
    message="Generate daily report"
)

# List jobs
jobs = cron.list_jobs(include_disabled=False)

# Remove job
cron.remove_job(job_id="abc123")

# Enable/disable job
cron.enable_job(job_id="abc123", enabled=False)

# Manually run job
await cron.run_job(job_id="abc123", force=True)

# Stop service
cron.stop()
```

### Tools

The cron service includes three tools for agent use:

- **CronList**: List scheduled jobs
- **CronAdd**: Add new scheduled job
- **CronRemove**: Remove scheduled job

```python
from agenix.tools import CronListTool, CronAddTool, CronRemoveTool

tools = [
    CronListTool(cron),
    CronAddTool(cron),
    CronRemoveTool(cron),
]
```

#### CronAdd Tool Usage

The agent can add jobs using natural time formats:

```python
# Every interval: "30s", "5m", "2h", "1d"
{
    "name": "Quick check",
    "message": "Check system status",
    "schedule_type": "every",
    "time_value": "30m"
}

# At specific time: ISO timestamp
{
    "name": "Meeting reminder",
    "message": "Team meeting starting",
    "schedule_type": "at",
    "time_value": "2026-02-10T14:30:00",
    "delete_after_run": true
}

# Cron expression
{
    "name": "Daily backup",
    "message": "Run backup procedure",
    "schedule_type": "cron",
    "time_value": "0 2 * * *"
}
```

## Heartbeat Service

The heartbeat service periodically wakes the agent to check for tasks in `HEARTBEAT.md`.

### Features

- **Periodic Wake-up**: Configurable interval (default: 30 minutes)
- **Task File**: Reads tasks from `HEARTBEAT.md` in workspace
- **Smart Skipping**: Skips if file is empty or has no actionable content
- **Manual Trigger**: Can trigger heartbeat on-demand

### API

```python
from pathlib import Path
from agenix.core import HeartbeatService

# Initialize with callback
async def on_heartbeat(prompt):
    """Handler called on each heartbeat."""
    # Send prompt to agent
    # Agent will read HEARTBEAT.md and execute tasks
    return agent_response

heartbeat = HeartbeatService(
    workspace=Path(".agenix"),
    on_heartbeat=on_heartbeat,
    interval_s=30*60,  # 30 minutes (default)
    enabled=True
)

# Start service
await heartbeat.start()

# Manually trigger
response = await heartbeat.trigger_now()

# Stop service
heartbeat.stop()
```

### HEARTBEAT.md Format

Create a `HEARTBEAT.md` file in your workspace with tasks:

```markdown
# Heartbeat Tasks

## Pending Tasks
- [ ] Review pull requests
- [ ] Update documentation
- [ ] Check system logs

## Completed
- [x] Fixed critical bug
- [x] Deployed to staging

## Notes
Any additional context or instructions for the agent.
```

The agent will:
1. Read the file
2. Execute pending tasks
3. Reply with `HEARTBEAT_OK` if nothing needs attention

## Quick Start

Complete example integrating all three features:

```python
import asyncio
from pathlib import Path
from agenix.core import (
    Agent, AgentConfig,
    MemoryStore, CronService, CronSchedule, HeartbeatService
)
from agenix.tools import (
    MemoryReadTool, MemoryWriteTool,
    CronListTool, CronAddTool, CronRemoveTool
)

async def main():
    workspace = Path(".agenix")

    # Setup memory
    memory = MemoryStore(workspace)

    # Setup cron
    async def on_cron_job(job):
        # Execute job with agent
        return await agent.run(job.payload.message)

    cron = CronService(workspace / "cron.json", on_job=on_cron_job)
    await cron.start()

    # Setup heartbeat
    async def on_heartbeat(prompt):
        return await agent.run(prompt)

    heartbeat = HeartbeatService(
        workspace=workspace,
        on_heartbeat=on_heartbeat,
        interval_s=30*60
    )
    await heartbeat.start()

    # Create agent with tools
    config = AgentConfig(model="gpt-4o", api_key="...")
    agent = Agent(
        config=config,
        tools=[
            MemoryReadTool(memory),
            MemoryWriteTool(memory),
            CronListTool(cron),
            CronAddTool(cron),
            CronRemoveTool(cron),
            # ... other tools
        ]
    )

    # Run agent
    await agent.run("What's in my memory?")

if __name__ == "__main__":
    asyncio.run(main())
```

## Dependencies

- **croniter** (optional): Required for cron expression support
  ```bash
  pip install croniter
  ```

## File Structure

```
.agenix/
├── memory/
│   ├── 2026-02-05.md      # Daily notes
│   ├── 2026-02-04.md
│   └── MEMORY.md          # Long-term memory
├── cron.json              # Cron jobs storage
├── HEARTBEAT.md           # Heartbeat tasks
└── settings.json          # Agent settings
```

## Configuration

You can configure services via settings:

```json
{
  "memory": {
    "enabled": true
  },
  "cron": {
    "enabled": true,
    "store_path": ".agenix/cron.json"
  },
  "heartbeat": {
    "enabled": true,
    "interval_s": 1800
  }
}
```

## Best Practices

1. **Memory**:
   - Use daily notes for temporary, date-specific information
   - Use long-term memory for persistent knowledge
   - Periodically review and consolidate daily notes into long-term memory

2. **Cron**:
   - Use `delete_after_run=True` for one-time reminders
   - Use reasonable intervals to avoid overloading the agent
   - Test cron expressions before deploying

3. **Heartbeat**:
   - Set appropriate interval based on task urgency
   - Keep HEARTBEAT.md organized and up-to-date
   - Use checkboxes for task tracking

## Troubleshooting

### Cron jobs not running

- Check `cron.json` exists and is readable
- Verify service is started with `await cron.start()`
- Check job is enabled and has valid schedule

### Heartbeat not triggering

- Verify `HEARTBEAT.md` has content (not empty or just headers)
- Check service is enabled and started
- Verify callback is properly configured

### Memory not persisting

- Ensure workspace directory has write permissions
- Check memory directory was created correctly
- Verify file encoding is UTF-8
