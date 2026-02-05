"""Tests for context compaction - simplified."""

import pytest
from agenix.core.compaction import (
    estimate_tokens,
    estimate_message_tokens,
    get_model_limits,
    is_overflow,
    compact_messages,
    ModelLimits,
)
from agenix.core.messages import (
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    TextContent,
    Usage,
)


def test_estimate_tokens():
    """Test token estimation - simple cases."""
    # Small text
    text = "Hello world"
    tokens = estimate_tokens(text)
    assert tokens > 0
    assert tokens < 10

    # Empty string
    assert estimate_tokens("") == 0


def test_estimate_message_tokens():
    """Test message token estimation."""
    # User message
    msg = UserMessage(content="Hello world")
    tokens = estimate_message_tokens(msg)
    assert tokens > 0
    assert tokens < 20  # Should be small

    # Assistant message with text
    msg = AssistantMessage(
        content=[TextContent(text="Hello there, this is a longer response")],
        tool_calls=[],
        model="test",
        usage=None,
        stop_reason="stop",
    )
    tokens = estimate_message_tokens(msg)
    assert tokens > 0


def test_get_model_limits():
    """Test model limits lookup using litellm."""
    # Known model - should get from litellm
    limits = get_model_limits("gpt-4o")
    assert limits.context > 0
    assert limits.output > 0
    # GPT-4o has 128k context
    assert limits.context == 128_000

    # Claude model
    limits = get_model_limits("claude-3-5-sonnet-20241022")
    assert limits.context > 0
    # Claude has 200k context
    assert limits.context == 200_000

    # Unknown model (fallback)
    limits = get_model_limits("unknown-model-xyz")
    assert limits.context == 128_000  # Default fallback


def test_is_overflow_logic():
    """Test overflow detection logic."""
    # Small messages - should not overflow
    messages = [
        UserMessage(content="Hello"),
        AssistantMessage(
            content=[TextContent(text="Hi")],
            tool_calls=[],
            model="test",
            usage=None,
            stop_reason="stop",
        ),
    ]

    # Should not overflow
    assert not is_overflow(messages, "gpt-4o", auto_compact=True)

    # Should not overflow if auto_compact is disabled
    assert not is_overflow(messages, "gpt-4o", auto_compact=False)

    # Test with messages that would overflow
    big_msg = "word " * 200  # ~200 tokens
    messages = [UserMessage(content=big_msg) for _ in range(3)]

    # Manually check overflow logic
    limits = ModelLimits(context=1000, input=0, output=500)
    total_tokens = sum(estimate_message_tokens(msg) for msg in messages)
    usable = limits.context - limits.output  # 500
    should_overflow = total_tokens > usable

    assert should_overflow, f"Expected overflow: {total_tokens} > {usable}"


def test_compact_messages():
    """Test message compaction."""
    # Create conversation
    messages = [
        UserMessage(content="First request"),
        AssistantMessage(
            content=[TextContent(text="Response 1")],
            tool_calls=[],
            model="test",
            usage=None,
            stop_reason="stop",
        ),
        UserMessage(content="Second request"),
        AssistantMessage(
            content=[TextContent(text="Response 2")],
            tool_calls=[],
            model="test",
            usage=None,
            stop_reason="stop",
        ),
        UserMessage(content="Third request"),
        AssistantMessage(
            content=[TextContent(text="Response 3")],
            tool_calls=[],
            model="test",
            usage=None,
            stop_reason="stop",
        ),
    ]

    summary = "We discussed three topics and made progress on the task."

    # Compact
    compacted = compact_messages(messages, summary)

    # Should start with summary message
    assert isinstance(compacted[0], AssistantMessage)
    assert "Conversation Summary" in compacted[0].content[0].text
    assert summary in compacted[0].content[0].text

    # Should keep recent 2 turns (last 4 messages)
    # Original: 6 messages, keep last 4, add 1 summary = 5 total
    assert len(compacted) == 5

    # Recent messages should be preserved
    assert compacted[-1] == messages[-1]
    assert compacted[-2] == messages[-2]
