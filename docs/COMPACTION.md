# Context Compaction

Agenix automatically manages conversation context when it becomes too long.

**Design Philosophy**: Trust the model. Only intervene when truly necessary. Let the LLM decide what's important.

## How it works

When context overflows:
1. ✅ **Detect overflow** - Check if messages exceed model's context limit
2. ✅ **LLM summarizes** - Let the model decide what's important
3. ✅ **Compact messages** - Replace old messages with summary, keep recent 2 turns

**That's it.** No complex rules, no pruning, no human-designed heuristics.

## Why this approach?

### Trust the Model
```
❌ Human rules: "Delete tool outputs older than 40k tokens"
   → Might remove something the model needs

✅ LLM decision: "Summarize what matters for continuing"
   → Model knows what's important for the task
```

### Models are getting better
- **Gemini**: 2M context
- **Claude**: 200K context
- **GPT-4**: 128K context

Context limits are growing. Overflow is increasingly rare.

### Simplicity
```python
# The entire logic:
if overflow:
    summary = llm.summarize(messages)
    messages = [summary] + recent_2_turns
```

No complex conditions, no thresholds, no edge cases.

## Token Counting

Agenix uses sophisticated token counting:

- **tiktoken** - OpenAI's official tokenizer (precise for GPT models)
- **Fallback heuristic** - 4 chars/token for other models
- Automatic selection based on model type

## Model Limits

Uses **litellm's built-in database**:
- ✅ 2400+ models supported
- ✅ Automatically updated
- ✅ Zero maintenance

Example models:

| Model | Context Window | Output Limit |
|-------|---------------|--------------|
| claude-3-5-sonnet-20241022 | 200k | 8k |
| gpt-4o | 128k | 16k |
| gemini-1.5-pro | 2M | 8k |
| deepseek-chat | 64k | 8k |

## Configuration

Control compaction in your settings file (`.agenix/settings.json` or `~/.agenix/settings.json`):

```json
{
  "auto_compact": true  // Enable automatic compaction (default: true)
}
```

Or via environment variable:

```bash
export AGENIX_AUTO_COMPACT=true
```

## Disabling compaction

```json
{
  "auto_compact": false
}
```

Or:

```bash
export AGENIX_AUTO_COMPACT=false
```

**Note**: If disabled and context overflows, the LLM API will return an error.

## Summary Prompt

The LLM receives this prompt when summarizing:

> "You are a helpful AI assistant tasked with summarizing conversations.
>
> When asked to summarize, provide a detailed but concise summary of the conversation.
> Focus on information that would be helpful for continuing the conversation, including:
>
> - What was done
> - What is currently being worked on
> - Which files are being modified
> - What needs to be done next
> - Key user requests, constraints, or preferences that should persist
> - Important technical decisions and why they were made
>
> Your summary should be comprehensive enough to provide context but concise enough to be quickly understood."

## Implementation

```python
# Core logic (simplified)
if is_overflow(messages, model):
    # Let LLM summarize
    summary = await llm.generate_summary(messages)

    # Keep recent 2 turns + summary
    recent_turns = messages[-4:]  # ~2 user turns
    messages = [summary] + recent_turns
```

## Philosophy

**Simple. Trustworthy. Effective.**

- No complex rules trying to guess what's important
- The LLM knows better than any heuristic
- Only intervene when truly necessary
- Models are smart - trust them
