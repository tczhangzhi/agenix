"""Extension runner - executes extensions and manages their lifecycle."""

import traceback
from typing import Any, Dict, List, Optional

from .types import (CommandDefinition, Event, EventType, ExtensionContext,
                    LoadedExtension, ToolDefinition)


class ExtensionRunner:
    """Manages execution of loaded extensions."""

    def __init__(
        self,
        extensions: List[LoadedExtension],
        context: ExtensionContext
    ):
        self.extensions = extensions
        self.context = context

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """Get all registered custom tools from extensions."""
        tools = {}
        for ext in self.extensions:
            tools.update(ext.tools)
        return tools

    def get_commands(self) -> Dict[str, CommandDefinition]:
        """Get all registered commands from extensions."""
        commands = {}
        for ext in self.extensions:
            commands.update(ext.commands)
        return commands

    async def emit(self, event: Event) -> Event:
        """Emit an event to all registered handlers.

        Args:
            event: The event to emit.

        Returns:
            The potentially modified event.
            Extensions can:
            - Set event.cancelled = True to cancel operation
            - Modify event data (e.g., event.messages, event.custom_instructions)
        """
        event_type = event.type

        for ext in self.extensions:
            handlers = ext.handlers.get(event_type, [])

            for handler in handlers:
                try:
                    await handler(event, self.context)

                    # Check if cancelled
                    if hasattr(event, 'cancelled') and event.cancelled:
                        break
                except Exception as e:
                    print(
                        f"Error in extension {ext.name} handling {event_type}: {e}")
                    traceback.print_exc()

            # Stop if cancelled
            if hasattr(event, 'cancelled') and event.cancelled:
                break

        return event

    async def execute_command(self, command_name: str, args: str) -> bool:
        """Execute a registered extension command.

        Args:
            command_name: Name of the command
            args: Command arguments as string

        Returns:
            True if command was found and executed, False otherwise.
        """
        for ext in self.extensions:
            command = ext.commands.get(command_name)
            if command:
                try:
                    await command.handler(self.context, args)
                    return True
                except Exception as e:
                    print(f"Error executing command {command_name}: {e}")
                    traceback.print_exc()
                    return True  # Command was found, but failed

        return False  # Command not found

    def has_handlers(self, event_type: EventType) -> bool:
        """Check if any extension has handlers for an event type."""
        for ext in self.extensions:
            if event_type in ext.handlers and len(ext.handlers[event_type]) > 0:
                return True
        return False

    def get_extension_paths(self) -> List[str]:
        """Get list of loaded extension paths."""
        return [ext.path for ext in self.extensions]

    def get_extension_names(self) -> List[str]:
        """Get list of loaded extension names."""
        return [ext.name for ext in self.extensions]

    async def emit_tool_call(self, tool_name: str, args: dict) -> bool:
        """Emit tool_call event.

        Returns:
            True if allowed, False if blocked by an extension.
        """
        from .types import ToolCallEvent
        event = ToolCallEvent(tool_name=tool_name, args=args)
        await self.emit(event)
        return not (hasattr(event, 'cancelled') and event.cancelled)
