# 代码重组完成状态

## 已完成 ✅

### 1. Builtin 扩展文件夹化
所有 builtin 扩展现在都是文件夹结构：

```
agenix/extensions/builtin/
├── channel/
│   └── __init__.py              # CLI channel extension
├── cron/
│   ├── __init__.py              # Extension interface
│   ├── service.py               # CronService class
│   └── types.py                 # Cron types
├── memory/
│   ├── __init__.py              # Extension interface
│   └── service.py               # MemoryStore class
├── heartbeat/
│   ├── __init__.py              # Extension interface
│   └── service.py               # HeartbeatService class
└── safety/
    └── __init__.py              # Safety extension
```

### 2. Tools 重组
核心工具移到 builtin 文件夹：

```
agenix/tools/
├── builtin/
│   ├── __init__.py
│   ├── base.py                  # Tool base class
│   ├── bash.py
│   ├── edit.py
│   ├── glob.py
│   ├── grep.py
│   ├── read.py
│   └── write.py
├── skill.py                     # Skill tool
├── task.py                      # Task tool
└── __init__.py                  # Main exports
```

### 3. 服务类整合
- ✅ HeartbeatService 移到 `extensions/builtin/heartbeat/service.py`
- ✅ MemoryStore 移到 `extensions/builtin/memory/service.py`
- ✅ CronService 保留在 `extensions/builtin/cron/service.py`

### 4. 导入更新
- ✅ `tools/__init__.py` 从 `builtin` 子包导入
- ✅ `tools/builtin/__init__.py` 导出核心工具

## 待完成 ⏳

### 1. Skill 和 Task 扩展化

**目标**: 将 `skill.py` 和 `task.py` 从 tools 移到 extensions/builtin

```
agenix/extensions/builtin/
├── skill/
│   ├── __init__.py              # Skill extension
│   └── tool.py                  # SkillTool implementation
└── task/
    ├── __init__.py              # Task extension (subagent)
    └── tool.py                  # TaskTool implementation
```

**原因**: Skill 和 Task 不是核心文件操作工具，更适合作为扩展。

### 2. Subagent 扩展

**参考**: pi-mono `packages/coding-agent/examples/extensions/subagent/`

**结构**:
```
agenix/extensions/builtin/subagent/
├── __init__.py                  # Extension setup
├── agents.py                    # Agent discovery logic
├── tool.py                      # SubagentTool implementation
├── agents/                      # Agent definitions
│   ├── scout.md                 # Fast reconnaissance
│   ├── planner.md               # Create plans
│   ├── reviewer.md              # Code review
│   └── worker.md                # General-purpose
└── prompts/                     # Workflow templates
    ├── implement.md
    ├── scout-and-plan.md
    └── implement-and-review.md
```

**核心功能**:
- 隔离上下文窗口
- 并行执行支持
- 流式输出
- 使用统计

**工具定义**:
```python
api.register_tool(ToolDefinition(
    name="Subagent",
    description="Delegate tasks to specialized subagents",
    parameters={
        "type": "object",
        "properties": {
            "agent": {"type": "string", "description": "Agent name"},
            "task": {"type": "string", "description": "Task description"},
            "parallel": {"type": "boolean", "default": False},
            "chain": {"type": "array", "items": {"type": "object"}}
        }
    },
    execute=subagent_execute
))
```

### 3. Plan Mode 扩展

**参考**: pi-mono `packages/coding-agent/examples/extensions/plan-mode/`

**结构**:
```
agenix/extensions/builtin/plan_mode/
├── __init__.py                  # Extension setup
├── utils.py                     # Plan extraction utilities
└── commands.py                  # /plan, /todos commands
```

**核心功能**:
- 只读模式（read, bash allowlist, grep, find, ls）
- 计划提取（`Plan:` 部分）
- 进度追踪（`[DONE:n]` 标记）
- 会话持久化

**命令**:
- `/plan` - Toggle plan mode
- `/todos` - Show plan progress

**Bash 白名单**:
```python
ALLOWED_COMMANDS = [
    # File inspection
    "cat", "head", "tail", "less", "more",
    # Search
    "grep", "find", "rg", "fd",
    # Directory
    "ls", "pwd", "tree",
    # Git read-only
    "git status", "git log", "git diff", "git branch",
]
```

**工作流程**:
1. 进入 plan mode (`/plan`)
2. Agent 分析代码创建计划
3. 用户确认执行
4. Agent 执行步骤，标记 `[DONE:n]`
5. 进度窗口显示完成状态

## 更新 CLI 加载路径

**文件**: `agenix/cli.py`

**当前**:
```python
builtin_extensions=[
    'agenix.extensions.builtin.memory',
    'agenix.extensions.builtin.cron',
    'agenix.extensions.builtin.heartbeat',
]
```

**需要更新为**:
```python
builtin_extensions=[
    'agenix.extensions.builtin.channel',
    'agenix.extensions.builtin.memory',
    'agenix.extensions.builtin.cron',
    'agenix.extensions.builtin.heartbeat',
    'agenix.extensions.builtin.safety',      # Optional: safety checks
    'agenix.extensions.builtin.subagent',    # TODO: implement
    'agenix.extensions.builtin.plan_mode',   # TODO: implement
]
```

## 目录对比

### 之前
```
agenix/
├── extensions/builtin/
│   ├── cli_channel.py           # Single file
│   ├── cron.py                  # Single file
│   ├── memory.py                # Single file
│   ├── heartbeat.py             # Single file
│   └── safety.py                # Single file
├── heartbeat.py                 # Service in root
├── memory.py                    # Service in root
├── cron/                        # Service folder
└── tools/
    ├── base.py
    ├── bash.py
    ├── ...
    ├── skill.py                 # Should be extension
    └── task.py                  # Should be extension
```

### 之后（目标）
```
agenix/
├── extensions/builtin/
│   ├── channel/                 # ✅ Folder with __init__.py
│   ├── cron/                    # ✅ Service + extension interface
│   ├── memory/                  # ✅ Service + extension interface
│   ├── heartbeat/               # ✅ Service + extension interface
│   ├── safety/                  # ✅ Folder with __init__.py
│   ├── subagent/                # ⏳ TODO
│   ├── plan_mode/               # ⏳ TODO
│   ├── skill/                   # ⏳ TODO: move from tools
│   └── task/                    # ⏳ TODO: move from tools
└── tools/
    ├── builtin/                 # ✅ Core file tools only
    │   ├── __init__.py
    │   ├── base.py
    │   ├── bash.py
    │   ├── edit.py
    │   ├── glob.py
    │   ├── grep.py
    │   ├── read.py
    │   └── write.py
    ├── skill.py                 # ⏳ Will move to extensions
    └── task.py                  # ⏳ Will move to extensions
```

## 测试状态

需要更新测试以适应新结构：

```bash
# Update import paths
python tests/test_extensions.py
python tests/verify_cleanup.py

# Test extension loading with new folder structure
python -c "
from agenix.extensions import discover_and_load_extensions
import asyncio

async def test():
    exts = await discover_and_load_extensions(
        cwd='.',
        builtin_extensions=[
            'agenix.extensions.builtin.memory',
            'agenix.extensions.builtin.cron',
            'agenix.extensions.builtin.heartbeat',
        ]
    )
    print(f'Loaded {len(exts)} extensions')

asyncio.run(test())
"
```

## 下一步优先级

1. **高优先级**:
   - ✅ 完成当前重组（已完成）
   - ⏳ 更新测试
   - ⏳ 验证扩展加载

2. **中优先级**:
   - ⏳ 将 skill 和 task 移到 extensions
   - ⏳ 更新 cli.py 扩展加载列表

3. **低优先级** (功能增强):
   - ⏳ 实现 subagent 扩展
   - ⏳ 实现 plan_mode 扩展

## 参考资源

- Pi-Mono Subagent: `/Users/geovanni/Work/pi-mono/packages/coding-agent/examples/extensions/subagent/`
- Pi-Mono Plan Mode: `/Users/geovanni/Work/pi-mono/packages/coding-agent/examples/extensions/plan-mode/`
- Extension 文档: `docs/EXTENSION_SYSTEM.md`
- 快速参考: `docs/EXTENSION_QUICK_REFERENCE.md`

## 文件清理

**可以删除的旧文件**:
- ✅ `agenix/extensions/builtin/*.py` (单文件，已移到文件夹)
- ✅ `agenix/heartbeat.py` (已移到 extensions/builtin/heartbeat/service.py)
- ✅ `agenix/memory.py` (已移到 extensions/builtin/memory/service.py)
- ⏳ `agenix/cron/` 文件夹 (可删除，已复制到 extensions/builtin/cron/)

## 总结

重组工作已完成 60%：
- ✅ 扩展文件夹化
- ✅ 服务整合到扩展
- ✅ 核心工具移到 builtin
- ⏳ Skill/Task 扩展化（待实现）
- ⏳ Subagent 扩展（待实现）
- ⏳ Plan Mode 扩展（待实现）

架构现在更清晰：
- Core tools: `tools/builtin/` (文件操作)
- Extensions: `extensions/builtin/` (所有其他功能)
- 每个扩展都是文件夹（不是单文件）
- 服务实现包含在扩展文件夹内
