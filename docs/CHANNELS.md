# Multi-Channel Architecture

## Overview

Agenix now supports multiple communication channels (TUI, Telegram, WhatsApp, etc.) through a unified architecture inspired by nanobot.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    MessageBus                        │
│            (Event-Driven Communication)              │
└───────┬─────────────────────────────────┬───────────┘
        │                                  │
        │ Events                           │ Events
        ▼                                  ▼
┌────────────────┐                  ┌────────────────┐
│   Channels     │                  │     Agent      │
│                │                  │                │
│ • TUI          │                  │ • Process      │
│ • Telegram     │                  │ • Execute      │
│ • WhatsApp     │                  │ • Respond      │
└────────────────┘                  └────────────────┘
```

## Components

### 1. BaseChannel (Abstract)

Base class for all channel implementations:

```python
class BaseChannel(ABC):
    async def start() -> None         # Start listening
    async def stop() -> None          # Stop and cleanup
    async def send(content) -> None   # Send message
```

### 2. ChannelManager

Manages multiple channels and coordinates message routing:

```python
manager = ChannelManager(bus=bus)
manager.register(TUIChannel(config, bus))
manager.register(TelegramChannel(config, bus))
await manager.start_all()
```

### 3. Supported Channels

#### TUI (Terminal User Interface)
- Interactive readline-based CLI
- Always available, no dependencies
- Great for development and testing

```python
from agenix.channel import TUIChannel, TUIConfig

config = TUIConfig(enabled=True, prompt="You")
tui = TUIChannel(config, bus=bus)
```

#### Telegram
- Telegram Bot API integration
- Requires `python-telegram-bot` package
- Supports markdown formatting

```python
from agenix.channel import TelegramChannel, TelegramConfig

config = TelegramConfig(
    enabled=True,
    bot_token="YOUR_BOT_TOKEN",
    allow_from=["123456789"]  # Optional whitelist
)
telegram = TelegramChannel(config, bus=bus)
```

#### WhatsApp
- WhatsApp Web integration via Node.js bridge
- Requires `websockets` package
- Requires separate Node.js bridge server

```python
from agenix.channel import WhatsAppChannel, WhatsAppConfig

config = WhatsAppConfig(
    enabled=True,
    bridge_url="ws://localhost:3000",
    allow_from=["+1234567890"]  # Optional whitelist
)
whatsapp = WhatsAppChannel(config, bus=bus)
```

## Event Flow

### Incoming Messages

```
User Input (Channel)
    ↓
Channel receives message
    ↓
Channel checks permissions (is_allowed)
    ↓
Channel publishes AgentMessageEvent to bus
    ↓
Agent subscribes to bus and receives event
    ↓
Agent processes message
    ↓
Agent publishes AgentResponseEvent to bus
    ↓
Channel receives response event
    ↓
Channel sends response back to user
```

### Event Types

**AgentMessageEvent**
```python
{
    "message": "User's question",
    "session_id": "telegram:123456",
    "context": {
        "channel": "telegram",
        "sender_id": "123456",
        "chat_id": "123456"
    }
}
```

**AgentResponseEvent**
```python
{
    "response": "Agent's answer",
    "session_id": "telegram:123456",
    "context": {
        "channel": "telegram",
        "chat_id": "123456"
    }
}
```

## Usage Examples

### Basic Setup

```python
import asyncio
from agenix import MessageBus, Agent, AgentConfig
from agenix.channel import ChannelManager, TUIChannel, TUIConfig

async def main():
    # Create bus
    bus = MessageBus()
    await bus.start()

    # Create agent
    agent = Agent(AgentConfig(model="gpt-4o", api_key="..."))

    # Subscribe agent to incoming messages
    async def on_message(event):
        response = await agent.run(event.message)
        await bus.publish(AgentResponseEvent(
            response=response,
            session_id=event.session_id,
            context=event.context
        ))

    bus.subscribe("agent_message", on_message)

    # Setup channels
    manager = ChannelManager(bus=bus)
    manager.register(TUIChannel(TUIConfig(), bus=bus))

    # Start everything
    await manager.start_all()
    await manager.wait_for_all()

asyncio.run(main())
```

### Multi-Channel Setup

```python
# Enable multiple channels
manager = ChannelManager(bus=bus)

# TUI for development
manager.register(TUIChannel(TUIConfig(prompt="You"), bus=bus))

# Telegram for users
if telegram_enabled:
    manager.register(TelegramChannel(TelegramConfig(
        bot_token=os.getenv("TELEGRAM_TOKEN")
    ), bus=bus))

# WhatsApp for users
if whatsapp_enabled:
    manager.register(WhatsAppChannel(WhatsAppConfig(
        bridge_url="ws://localhost:3000"
    ), bus=bus))

# All channels share the same agent via the bus
await manager.start_all()
```

## WhatsApp Bridge Setup

The WhatsApp channel requires a separate Node.js bridge server.

### Install Bridge

```bash
# Clone or create bridge directory
mkdir whatsapp-bridge
cd whatsapp-bridge

# Install dependencies
npm init -y
npm install @whiskeysockets/baileys ws
```

### Bridge Server Code

```javascript
// server.js
const { default: makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const WebSocket = require('ws');

const wss = new WebSocket.Server({ port: 3000 });

async function connectToWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState('auth_info');
  const sock = makeWASocket({
    auth: state,
    printQRInTerminal: true
  });

  sock.ev.on('creds.update', saveCreds);

  // Broadcast to all Python clients
  function broadcast(data) {
    wss.clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(JSON.stringify(data));
      }
    });
  }

  // Handle incoming messages
  sock.ev.on('messages.upsert', async ({ messages }) => {
    const msg = messages[0];
    if (!msg.message || msg.key.fromMe) return;

    broadcast({
      type: 'message',
      sender: msg.key.remoteJid,
      content: msg.message.conversation || '',
      id: msg.key.id,
      timestamp: msg.messageTimestamp
    });
  });

  // Handle Python -> WhatsApp
  wss.on('connection', (ws) => {
    ws.on('message', async (data) => {
      const payload = JSON.parse(data);
      if (payload.type === 'send') {
        await sock.sendMessage(payload.to, { text: payload.text });
      }
    });
  });
}

connectToWhatsApp();
```

### Run Bridge

```bash
node server.js
```

## Directory Structure

```
agenix/
├── channel/              # Multi-channel support
│   ├── __init__.py
│   ├── base.py          # BaseChannel abstract class
│   ├── manager.py       # ChannelManager
│   ├── tui_channel.py   # TUI implementation
│   ├── telegram.py      # Telegram implementation
│   ├── whatsapp.py      # WhatsApp implementation
│   └── tui.py           # Legacy CLIRenderer (compat)
├── bus/                 # Event bus
│   ├── events.py
│   └── bus.py
└── ...
```

## Migration from UI to Channel

### Before (Old UI)
```python
from agenix.ui import CLI, CLIRenderer

cli = CLI(agent)
cli.run()
```

### After (New Channel)
```python
from agenix.channel import ChannelManager, TUIChannel, TUIConfig

manager = ChannelManager(bus=bus)
manager.register(TUIChannel(TUIConfig(), bus=bus))
await manager.start_all()
```

### Backward Compatibility

The old `CLIRenderer` is still available:

```python
from agenix.channel import CLIRenderer  # Works!
```

## Benefits

1. **Unified Interface**: Same agent works across all channels
2. **Event-Driven**: Loose coupling via message bus
3. **Extensible**: Easy to add new channels (Discord, Slack, etc.)
4. **Parallel**: Multiple channels can run simultaneously
5. **Permission Control**: Per-channel whitelisting support

## Adding New Channels

To add a new channel (e.g., Discord):

1. **Create channel class**:
```python
from agenix.channel import BaseChannel

class DiscordChannel(BaseChannel):
    name = "discord"

    async def start(self):
        # Connect to Discord
        # Listen for messages
        # Forward to bus via _handle_incoming_message()
        pass

    async def stop(self):
        # Cleanup
        pass

    async def send(self, content, **kwargs):
        # Send message to Discord
        pass
```

2. **Register with manager**:
```python
manager.register(DiscordChannel(config, bus=bus))
```

3. **That's it!** The agent will automatically work with your channel.

## Next Steps

- Add more channels (Discord, Slack, WeChat, etc.)
- Add voice support (speech-to-text, text-to-speech)
- Add media handling (images, files, etc.)
- Add group chat support
- Add channel-specific features

## See Also

- `examples/multi_channel.py` - Complete multi-channel example
- `examples/bus_integration.py` - Bus integration example
- `docs/ARCHITECTURE_REFACTORING.md` - Architecture overview
