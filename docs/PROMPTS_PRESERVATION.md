# 提示词保留和修改说明

## SOTA 提示词（完全保留）✅

### 1. Compaction System Prompt
**位置**: `agenix/core/compaction.py:197-209`

**内容**:
```python
COMPACTION_PROMPT = """You are a helpful AI assistant tasked with summarizing conversations.

When asked to summarize, provide a detailed but concise summary of the conversation.
Focus on information that would be helpful for continuing the conversation, including:

- What was done
- What is currently being worked on
- Which files are being modified
- What needs to be done next
- Key user requests, constraints, or preferences that should persist
- Important technical decisions and why they were made

Your summary should be comprehensive enough to provide context but concise enough to be quickly understood."""
```

**状态**: ✅ **完全保留**，未修改

## 用户消息提示词（已简化）

### Compaction User Prompt
**位置**: `agenix/core/compaction.py:235-241`

**修改前**（自己编写的）:
```python
base_prompt = """Please create a concise summary of the conversation so far.
Focus on:
- Key decisions and outcomes
- Important file paths and code locations
- Unresolved issues or next steps
- Critical context needed for continuing work

Keep it brief but preserve essential details."""
```

**修改后**（简化为接近原始）:
```python
user_prompt = "Please provide a detailed summary of our conversation so far. " \
             "Focus on what was done, what we're working on, which files were modified, " \
             "and what needs to be done next."
```

**变更说明**:
- ✅ 简化为单行提示
- ✅ 保持核心要点（done, working on, files, next）
- ✅ 支持扩展自定义指令（custom_instructions）

## 自定义提示词（保持现状）✅

### 1. Main Agent System Prompt
**位置**: `agenix/cli.py:198-210`

**内容**:
```python
"""You are an expert coding assistant operating inside Agenix, a coding agent harness.
You help users by reading files, executing commands, editing code, and writing new files.

Available tools:
{tools_list}

Guidelines:
{guidelines_text}

Current date and time: {date_time}
Current working directory: {cwd}"""
```

**状态**: ✅ **保持不变**
- 动态工具列表
- 基于可用工具的指南
- 上下文信息（日期、工作目录）

### 2. Subagent Task Prompt
**位置**: `agenix/tools/task.py:193-200`

**内容**:
```python
system_prompt = f"""You are a specialized subagent working on a focused task.

Your task: {task}

Important constraints:
- You have access to the same tools as the parent agent
- You should focus ONLY on this specific task
- Return your findings or results concisely
- Do not make changes outside the scope of this task

Working directory: {working_dir}"""
```

**状态**: ✅ **保持不变**
- 子代理专用提示词
- 明确任务范围和约束

## Pi-Mono 参考对比

### Pi-Mono Compaction Prompt
```typescript
export const SUMMARIZATION_SYSTEM_PROMPT = `You are a context summarization assistant.
Your task is to read a conversation between a user and an AI coding assistant,
then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation.
ONLY output the structured summary.`;
```

**对比**:
- Pi-Mono: 更简短，强调不继续对话
- Agenix: 更详细，说明要包含的信息
- **决定**: 保持 Agenix 的 COMPACTION_PROMPT（SOTA）

## 扩展自定义能力 ✅

### Custom Instructions 支持
扩展可以通过 `BeforeCompactEvent` 添加自定义压缩指令：

```python
@api.on(EventType.BEFORE_COMPACT)
async def on_before_compact(event: BeforeCompactEvent, ctx):
    event.custom_instructions = "Preserve all file paths and error messages."
```

**实现**:
```python
# agenix/core/compaction.py:244-246
if custom_instructions:
    user_prompt = f"{user_prompt}\n\nAdditional requirements:\n{custom_instructions}"
```

**好处**:
- ✅ 扩展可以定制压缩行为
- ✅ 不修改核心 COMPACTION_PROMPT
- ✅ 保持 SOTA 提示词不变

## 总结

### 完全保留的 SOTA 提示词
1. ✅ `COMPACTION_PROMPT` - 压缩系统提示（197-209 行）

### 简化的用户提示词
1. ✅ Compaction user prompt - 从多行简化为单行（235-241 行）

### 保持现状的自定义提示词
1. ✅ Main agent system prompt - 主代理提示词
2. ✅ Subagent task prompt - 子代理提示词

### 新增功能
1. ✅ `custom_instructions` 支持 - 扩展可定制压缩

## 验证

```bash
# 语法检查
python -c "import ast; ast.parse(open('agenix/core/compaction.py').read())"
# ✓ 通过

# 功能测试
python tests/test_extensions.py
# ✓ 5/5 通过
```

## 结论

所有 SOTA 提示词保持不变，扩展系统可以通过 `custom_instructions` 定制压缩行为，架构清晰且灵活。
