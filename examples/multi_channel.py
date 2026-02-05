"""Example: Multi-channel integration with Telegram and WhatsApp.

Note: TUI/CLI is for direct agent interaction (not via bus).
This example shows how to set up Telegram and WhatsApp channels
that communicate with the agent through the message bus.
"""

import asyncio
from pathlib import Path

from agenix import (
    Agent,
    AgentConfig,
    MessageBus,
    MemoryStore,
    CronService,
    HeartbeatService,
    AgentResponseEvent,
)
from agenix.channel import (
    ChannelManager,
    TelegramChannel,
    TelegramConfig,
    WhatsAppChannel,
    WhatsAppConfig,
)
from agenix.tools import (
    ReadTool,
    WriteTool,
    EditTool,
    BashTool,
    GrepTool,
    GlobTool,
    MemoryReadTool,
    MemoryWriteTool,
)


async def main():
    """Run agenix with multiple channels."""

    # Setup workspace
    workspace = Path(".agenix")
    workspace.mkdir(exist_ok=True)

    # Initialize message bus
    bus = MessageBus()
    await bus.start()
    print("✓ Message bus started\n")

    # Initialize services
    memory = MemoryStore(workspace, bus=bus)
    cron = CronService(workspace / "cron.json", bus=bus)
    heartbeat = HeartbeatService(workspace, bus=bus)

    # Initialize agent
    config = AgentConfig(
        model="gpt-4o",
        api_key="your-api-key",  # Replace with actual key
        max_turns=10,
    )

    tools = [
        ReadTool(),
        WriteTool(),
        EditTool(),
        BashTool(),
        GrepTool(),
        GlobTool(),
        MemoryReadTool(memory),
        MemoryWriteTool(memory),
    ]

    agent = Agent(config=config, tools=tools)

    # Subscribe agent to bus events
    async def on_agent_message(event):
        """Handle incoming messages from channels."""
        print(f"[AGENT] Processing: {event.message[:50]}...")

        # Run agent (simplified for demo)
        # In production, you'd actually run the agent:
        # response = await agent.run(event.message)

        # For demo, just echo
        response = f"Echo: {event.message}"

        # Publish response back to bus
        await bus.publish(AgentResponseEvent(
            response=response,
            session_id=event.session_id,
            context=event.context
        ))

    bus.subscribe("agent_message", on_agent_message)

    # Initialize channel manager
    channel_manager = ChannelManager(bus=bus)

    # Register Telegram channel (optional)
    telegram_enabled = False  # Set to True and add token to enable
    if telegram_enabled:
        telegram_config = TelegramConfig(
            enabled=True,
            bot_token="YOUR_BOT_TOKEN_HERE"
        )
        telegram_channel = TelegramChannel(telegram_config, bus=bus)
        channel_manager.register(telegram_channel)

    # Register WhatsApp channel (optional)
    whatsapp_enabled = False  # Set to True and run bridge to enable
    if whatsapp_enabled:
        whatsapp_config = WhatsAppConfig(
            enabled=True,
            bridge_url="ws://localhost:3000"
        )
        whatsapp_channel = WhatsAppChannel(whatsapp_config, bus=bus)
        channel_manager.register(whatsapp_channel)

    if not channel_manager.enabled_channels:
        print("="*60)
        print("No channels enabled!")
        print("="*60)
        print()
        print("To enable channels:")
        print("  1. Telegram: Set telegram_enabled=True and add bot token")
        print("  2. WhatsApp: Set whatsapp_enabled=True and run bridge server")
        print()
        print("Note: For interactive CLI, use: python main.py")
        print("="*60)
        return

    print("="*60)
    print("Multi-Channel Agenix")
    print("="*60)
    print(f"Active channels: {', '.join(channel_manager.enabled_channels)}")
    print()

    # Start all channels
    try:
        await channel_manager.start_all()
        await channel_manager.wait_for_all()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        await channel_manager.stop_all()
        bus.stop()
        print("✓ All services stopped")


if __name__ == "__main__":
    asyncio.run(main())
