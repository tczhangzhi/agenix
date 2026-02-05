"""Context compaction for managing conversation length.

Design Philosophy:
- Trust the model - let LLM decide what's important
- Simple is beautiful - no complex rules
- Only intervene when truly necessary (overflow)
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

from .messages import Message, UserMessage, AssistantMessage, ToolResultMessage, TextContent

logger = logging.getLogger(__name__)


@dataclass
class ModelLimits:
    """Model context limits."""
    context: int = 0  # Total context window
    input: int = 0    # Max input tokens (0 = use context - output)
    output: int = 16384  # Max output tokens


def get_model_limits(model: str) -> ModelLimits:
    """Get model limits using litellm's model database.

    Args:
        model: Model name/ID

    Returns:
        Model limits
    """
    try:
        import litellm

        # Try to get model info from litellm
        if model in litellm.model_cost:
            info = litellm.model_cost[model]
            max_input = info.get('max_input_tokens', 0)
            max_output = info.get('max_output_tokens', 16384)

            # Calculate context window
            # Some models provide max_tokens (total), others provide max_input_tokens
            context = max_input or info.get('max_tokens', 128_000)

            return ModelLimits(
                context=context,
                input=max_input,
                output=max_output
            )

        # Try prefix match for versioned models
        for key in litellm.model_cost.keys():
            if model.startswith(key) or key.startswith(model):
                info = litellm.model_cost[key]
                max_input = info.get('max_input_tokens', 0)
                max_output = info.get('max_output_tokens', 16384)
                context = max_input or info.get('max_tokens', 128_000)

                logger.info(f"Matched model {model} to {key}")
                return ModelLimits(
                    context=context,
                    input=max_input,
                    output=max_output
                )

    except ImportError:
        logger.warning("litellm not available, using default limits")
    except Exception as e:
        logger.warning(f"Error getting model info from litellm: {e}")

    # Fallback to conservative default
    logger.warning(f"Unknown model {model}, using default limits (128k context)")
    return ModelLimits(context=128_000, input=0, output=16_384)


def estimate_tokens(text: str) -> int:
    """Estimate token count from text.

    Uses tiktoken for OpenAI models if available, otherwise uses
    rough heuristic of 4 characters per token.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Try tiktoken for more accurate estimation (OpenAI models)
    try:
        import tiktoken
        # Use cl100k_base encoding (used by gpt-4, gpt-3.5-turbo)
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"tiktoken failed: {e}, falling back to heuristic")

    # Fallback: 4 characters per token heuristic
    return len(text) // 4


def estimate_message_tokens(message: Message) -> int:
    """Estimate tokens in a message.

    Args:
        message: Message to estimate

    Returns:
        Estimated token count
    """
    tokens = 0

    if isinstance(message, UserMessage):
        if isinstance(message.content, str):
            tokens += estimate_tokens(message.content)
        elif isinstance(message.content, list):
            for item in message.content:
                if isinstance(item, TextContent):
                    tokens += estimate_tokens(item.text)
                elif hasattr(item, 'text'):
                    tokens += estimate_tokens(item.text)

    elif isinstance(message, AssistantMessage):
        # Text content
        for item in message.content:
            if isinstance(item, TextContent):
                tokens += estimate_tokens(item.text)
            elif hasattr(item, 'text'):
                tokens += estimate_tokens(item.text)

        # Tool calls (arguments)
        for tc in message.tool_calls:
            import json
            tokens += estimate_tokens(json.dumps(tc.arguments))

    elif isinstance(message, ToolResultMessage):
        if isinstance(message.content, str):
            tokens += estimate_tokens(message.content)
        elif isinstance(message.content, list):
            for item in message.content:
                if isinstance(item, TextContent):
                    tokens += estimate_tokens(item.text)
                elif hasattr(item, 'text'):
                    tokens += estimate_tokens(item.text)

    # Add overhead for message structure
    tokens += 10

    return tokens




def is_overflow(messages: List[Message], model: str, auto_compact: bool = True) -> bool:
    """Check if message history would overflow model context.

    Args:
        messages: Message history
        model: Model name
        auto_compact: Whether auto compaction is enabled

    Returns:
        True if overflow would occur
    """
    if not auto_compact:
        return False

    limits = get_model_limits(model)
    if limits.context == 0:
        return False

    # Calculate total tokens
    total_tokens = sum(estimate_message_tokens(msg) for msg in messages)

    # Calculate usable input context
    usable_input = limits.input if limits.input > 0 else (limits.context - limits.output)

    # Check overflow
    overflow = total_tokens > usable_input

    if overflow:
        logger.info(
            f"Context overflow detected: {total_tokens:,} tokens > {usable_input:,} usable "
            f"(model: {model}, context: {limits.context:,}, output: {limits.output:,})"
        )

    return overflow


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


async def create_summary(
    messages: List[Message],
    provider,  # LLMProvider instance
    model: str,
    system_prompt: str,
    custom_instructions: Optional[str] = None
) -> Optional[str]:
    """Create a summary of the conversation.

    Args:
        messages: Message history to summarize
        provider: LLMProvider instance for generating summary
        model: Model to use for summary
        system_prompt: System prompt for summary
        custom_instructions: Optional custom instructions from extensions

    Returns:
        Summary text or None if failed
    """
    logger.info("Creating conversation summary")

    try:
        # Build user prompt for summarization
        user_prompt = "Please provide a detailed summary of our conversation so far. " \
                     "Focus on what was done, what we're working on, which files were modified, " \
                     "and what needs to be done next."

        # Add custom instructions if provided by extension
        if custom_instructions:
            user_prompt = f"{user_prompt}\n\nAdditional requirements:\n{custom_instructions}"

        # Add compaction prompt at the end
        summary_messages = messages + [
            UserMessage(
                content=user_prompt,
                timestamp=0
            )
        ]

        # Generate summary using provider
        response = await provider.complete(
            model=model,
            messages=summary_messages,
            system_prompt=COMPACTION_PROMPT,
            max_tokens=4096
        )

        # Extract text
        summary = ""
        for item in response.content:
            if isinstance(item, TextContent):
                summary += item.text

        if summary:
            logger.info(f"Generated summary: {len(summary)} chars, ~{estimate_tokens(summary)} tokens")
            return summary.strip()

        return None

    except Exception as e:
        logger.error(f"Failed to create summary: {e}")
        return None


def compact_messages(
    messages: List[Message],
    summary: str
) -> List[Message]:
    """Compact message history by replacing old messages with summary.

    Keeps the most recent 2 user turns, replaces everything before with summary.

    Args:
        messages: Original message history
        summary: Summary to insert

    Returns:
        Compacted message history
    """
    logger.info("Compacting message history")

    # Find the start of recent 2 turns
    user_turns = 0
    keep_from_index = len(messages)

    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], UserMessage):
            user_turns += 1
            if user_turns >= 2:
                keep_from_index = i
                break

    # Create compacted history: [summary] + [recent messages]
    summary_message = AssistantMessage(
        content=[TextContent(text=f"[Conversation Summary]\n\n{summary}")],
        tool_calls=[],
        model="compaction",
        usage=None,
        stop_reason="end_turn",
        timestamp=0
    )

    compacted = [summary_message] + messages[keep_from_index:]

    old_tokens = sum(estimate_message_tokens(m) for m in messages)
    new_tokens = sum(estimate_message_tokens(m) for m in compacted)
    saved = old_tokens - new_tokens

    logger.info(
        f"Compaction complete: {len(messages)} -> {len(compacted)} messages, "
        f"{old_tokens:,} -> {new_tokens:,} tokens (saved {saved:,})"
    )

    return compacted
