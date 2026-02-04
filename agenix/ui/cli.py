"""CLI interface for agenix."""

import os
import sys
from typing import Optional, Dict

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..core.messages import (Event, ImageContent, MessageEndEvent,
                             MessageStartEvent, MessageUpdateEvent,
                             ReasoningStartEvent, ReasoningUpdateEvent,
                             ReasoningEndEvent, TextContent,
                             ToolExecutionEndEvent, ToolExecutionStartEvent,
                             ToolExecutionUpdateEvent, TurnEndEvent,
                             TurnStartEvent)
from ..tools.base import ToolResult


class CLIRenderer:
    """Render agent events to terminal."""

    def __init__(self):
        self.console = Console()
        self.current_message = ""
        self.current_tool = None
        self.current_tool_args = None  # Store tool args
        self.message_buffer = []  # For buffering streaming content
        self.in_live_mode = False
        self.tool_output_lines = []  # Store tool output lines
        self.current_reasoning = {}  # Track reasoning blocks

        # Initialize prompt session with better unicode support
        self.prompt_session = PromptSession(
            style=Style.from_dict({
                'prompt': '#0066cc bold',  # Blue bold for prompt
            })
        )

    def render_event(self, event: Event) -> None:
        """Render an event to the console."""
        if isinstance(event, TurnStartEvent):
            pass  # Don't show separator

        elif isinstance(event, ReasoningStartEvent):
            # Don't show anything - will render inline with message
            self.current_reasoning[event.reasoning_id] = ""

        elif isinstance(event, ReasoningUpdateEvent):
            if event.reasoning_id in self.current_reasoning:
                self.current_reasoning[event.reasoning_id] += event.delta
                # Stream reasoning in dim style
                self.console.print(f"[dim]{event.delta}[/dim]", end="")

        elif isinstance(event, ReasoningEndEvent):
            # Add newline after reasoning, before text
            if event.content:
                self.console.print()  # Newline to separate from text
            if event.reasoning_id in self.current_reasoning:
                del self.current_reasoning[event.reasoning_id]

        elif isinstance(event, MessageStartEvent):
            self.current_message = ""
            self.message_buffer = []
            # Print indicator for Assistant message (Claude Code style)
            self.console.print()
            self.console.print("⏺ ", end="")

        elif isinstance(event, MessageUpdateEvent):
            # Accumulate message and stream output in real-time
            self.current_message += event.delta
            self.message_buffer.append(event.delta)
            # Stream the delta immediately
            self.console.print(event.delta, end="")

        elif isinstance(event, MessageEndEvent):
            # End streaming with newline
            if self.current_message:
                self.console.print()  # Final newline
            self.current_message = ""
            self.message_buffer = []

        elif isinstance(event, ToolExecutionStartEvent):
            self.current_tool = event.tool_name
            self.current_tool_args = event.args if hasattr(event, 'args') else None
            self.tool_output_lines = []
            # Display tool invocation in Claude Code style
            self.console.print()
            args_str = self._format_tool_args(event.tool_name, event.args)
            self.console.print(f"⏺ [cyan]{event.tool_name}[/cyan]({args_str})")

        elif isinstance(event, ToolExecutionUpdateEvent):
            # Collect tool output
            if event.partial_result:
                result_str = str(event.partial_result)
                lines = result_str.split('\n')
                self.tool_output_lines.extend(lines)

        elif isinstance(event, ToolExecutionEndEvent):
            # Show tool result in Claude Code style
            if event.result:
                # Extract result text
                content = event.result
                if isinstance(content, list):
                    result_parts = []
                    for item in content:
                        if isinstance(item, TextContent):
                            result_parts.append(item.text)
                        elif isinstance(item, ImageContent):
                            media_type = item.source.get('media_type', 'image')
                            result_parts.append(f"[Image: {media_type}]")
                        else:
                            if hasattr(item, 'text'):
                                result_parts.append(item.text)
                            else:
                                result_parts.append(str(item))
                    result_str = '\n'.join(result_parts)
                elif isinstance(content, ToolResult):
                    if isinstance(content.content, list):
                        result_parts = []
                        for item in content.content:
                            if isinstance(item, TextContent):
                                result_parts.append(item.text)
                            elif isinstance(item, ImageContent):
                                media_type = item.source.get('media_type', 'image')
                                result_parts.append(f"[Image: {media_type}]")
                        result_str = '\n'.join(result_parts)
                    else:
                        result_str = str(content.content)
                else:
                    result_str = str(content)

                # Show result summary
                self._render_tool_result(self.current_tool, self.current_tool_args, result_str, event.is_error)

            self.current_tool = None
            self.current_tool_args = None
            self.tool_output_lines = []

        elif isinstance(event, TurnEndEvent):
            # Show token usage
            if event.message and event.message.usage:
                usage = event.message.usage
                total_tokens = usage.input_tokens + usage.output_tokens
                self.console.print(
                    f"[dim]{total_tokens:,} tokens[/dim]"
                )

    def render_message(self, role: str, content: str, is_error: bool = False) -> None:
        """Render a complete message in a box."""
        if role == "user":
            self.console.print()
            self.console.print(Panel(
                content,
                border_style="blue",
                box=box.ROUNDED,
                padding=(0, 1),
                title="[bold blue]You[/bold blue]",
                title_align="left"
            ))
        elif role == "assistant":
            self.console.print()
            self.console.print(Panel(
                content,
                border_style="green",
                box=box.ROUNDED,
                padding=(0, 1),
                title="[bold green]Assistant[/bold green]",
                title_align="left"
            ))
        elif role == "system":
            style = "red" if is_error else "yellow"
            self.console.print()
            self.console.print(Panel(
                content,
                border_style=style,
                box=box.ROUNDED,
                padding=(0, 1),
                title=f"[bold {style}]System[/bold {style}]",
                title_align="left"
            ))

    def render_error(self, error: str) -> None:
        """Render an error."""
        error_text = error if error and error.strip() else "Unknown error occurred"
        self.console.print(Panel(
            f"[bold red]Error:[/bold red] {error_text}",
            border_style="red",
            padding=(1, 2)
        ))

    def _format_tool_args(self, tool_name: str, args: Optional[Dict]) -> str:
        """Format tool arguments for display."""
        if not args:
            return ""

        # Show key argument based on tool type
        if 'file_path' in args:
            return args['file_path']
        elif 'pattern' in args:
            return args['pattern']
        elif 'command' in args:
            cmd = args['command']
            return cmd[:50] + "..." if len(cmd) > 50 else cmd
        elif 'content' in args:
            return "..."

        # Fallback: show first key
        if args:
            key = list(args.keys())[0]
            val = str(args[key])
            return val[:50] + "..." if len(val) > 50 else val

        return ""

    def _render_tool_result(self, tool_name: str, args: Optional[Dict], result_text: str, is_error: bool):
        """Render tool result in Claude Code style."""
        # Result indicator
        if is_error:
            self.console.print("  [red]⎿  Error[/red]", end="")
            self.console.print(f": {result_text[:100]}")
            return

        self.console.print("  [green]⎿[/green]  ", end="")

        # Result summary based on tool type
        if tool_name in ["Write", "write"] and args:
            file_path = args.get('file_path', '')
            content = args.get('content', '')
            if content:
                content_lines = content.split('\n')
                # Filter out empty lines for count
                non_empty = [l for l in content_lines if l.strip()]
                num_lines = len(content_lines)
                self.console.print(f"Wrote {num_lines} lines to {file_path}")

                # Show first 5 lines with line numbers
                for i, line in enumerate(content_lines[:5], 1):
                    # Escape markup in the line content
                    escaped_line = line.replace('[', '\\[').replace(']', '\\]')
                    self.console.print(f"     {i:3} {escaped_line[:77]}")

                # Show remaining count
                if len(content_lines) > 5:
                    remaining = len(content_lines) - 5
                    self.console.print(f"     … +{remaining} lines")
            else:
                self.console.print(result_text)

        elif tool_name in ["Edit", "edit"] and args:
            file_path = args.get('file_path', '')
            self.console.print(f"Edited {file_path}")

        elif tool_name in ["Read", "read"] and not is_error:
            lines = result_text.split('\n')
            num_lines = len([l for l in lines if l.strip()])
            file_path = args.get('file_path', '') if args else ''
            self.console.print(f"Read {num_lines} lines from {file_path}")

        elif tool_name in ["Bash", "bash"] and not is_error:
            lines = result_text.split('\n')
            # Show command result
            if "Exit code:" in result_text or "Command:" in result_text:
                # Parse bash tool output
                self.console.print("Command completed")
                # Show output lines (skip metadata)
                output_started = False
                shown_lines = 0
                for line in lines:
                    if "Stdout:" in line or "Stderr:" in line:
                        output_started = True
                        continue
                    if output_started and line.strip() and shown_lines < 5:
                        escaped_line = line.replace('[', '\\[').replace(']', '\\]')
                        self.console.print(f"     {escaped_line[:77]}")
                        shown_lines += 1
            else:
                # Generic output
                self.console.print("Command completed")
                for line in lines[:5]:
                    if line.strip():
                        escaped_line = line.replace('[', '\\[').replace(']', '\\]')
                        self.console.print(f"     {escaped_line[:77]}")
                if len(lines) > 5:
                    self.console.print(f"     … +{len(lines)-5} lines")

        else:
            # Generic result display
            lines = result_text.split('\n')
            summary_line = lines[0][:80] if lines else ""
            self.console.print(summary_line)
            if len(lines) > 1:
                for line in lines[1:4]:
                    if line.strip():
                        escaped_line = line.replace('[', '\\[').replace(']', '\\]')
                        self.console.print(f"     {escaped_line[:77]}")
                if len(lines) > 4:
                    self.console.print(f"     … +{len(lines)-4} lines")

    def render_welcome(self, model: str = None, tools=None, skills=None) -> None:
        """Render welcome banner with ASCII art."""
        from .. import __version__

        # ASCII art for Agenix
        ascii_art = Text.from_markup("""[cyan]   _                    _
  / \\   __ _  ___ _ __ (_)_  __
 / _ \\ / _` |/ _ \\ '_ \\| \\ \\/ /
/ ___ \\ (_| |  __/ | | | |>  <
/_/   \\_\\__, |\\___|_| |_|_/_/\\_\\
        |___/[/cyan]""")

        # Get working directory (shortened if too long)
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]

        # Build right side info
        info_text = Text()
        info_text.append(f"Version {__version__}", style="dim")
        info_text.append("\n\n")
        info_text.append("Model: ", style="cyan")
        info_text.append(model or 'gpt-4o')
        info_text.append("\n")
        info_text.append("Working Directory: ", style="cyan")
        info_text.append(cwd)
        info_text.append("\n\n")
        info_text.append("Commands: ", style="yellow")
        info_text.append("/help /clear /sessions /quit")

        # Skills (if any)
        if skills and len(skills) > 0:
            info_text.append("\n")
            info_text.append("Skills: ", style="green")
            skill_names = [s.name for s in skills[:10]]
            skills_str = ", ".join(skill_names)
            if len(skills) > 10:
                skills_str += f" ... ({len(skills) - 10} more)"
            info_text.append(skills_str)

        # Create two-column layout
        layout = Table.grid(expand=True, padding=(0, 3))
        layout.add_column(justify="left", no_wrap=True)
        layout.add_column(justify="left")

        layout.add_row(ascii_art, info_text)

        # Create panel
        panel = Panel(
            layout,
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        )

        self.console.print(panel)

    def prompt_config_input(self, field_name: str, description: str, is_secret: bool = False) -> str:
        """Prompt user for configuration input.

        Args:
            field_name: Name of the configuration field
            description: Description of what this field is for
            is_secret: If True, input will be hidden

        Returns:
            The user input
        """
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.validation import Validator, ValidationError

        class NonEmptyValidator(Validator):
            def validate(self, document):
                if not document.text.strip():
                    raise ValidationError(
                        message='This field is required',
                        cursor_position=len(document.text)
                    )

        self.console.print(
            f"[bold yellow]{description}[/bold yellow]"
        )

        try:
            value = pt_prompt(
                f"{field_name}: ",
                validator=NonEmptyValidator(),
                is_password=is_secret
            )
            return value.strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("[red]Configuration cancelled[/red]")
            sys.exit(0)

    def prompt(self, text: str = ">") -> str:
        """Show input prompt with better unicode support."""
        try:
            # Use prompt_toolkit for better unicode handling (especially Chinese)
            return self.prompt_session.prompt(f"{text} ")
        except EOFError:
            return "/quit"
        except KeyboardInterrupt:
            return "/quit"

    def clear(self) -> None:
        """Clear the screen."""
        self.console.clear()


class CLI:
    """Main CLI interface."""

    def __init__(self, renderer: Optional[CLIRenderer] = None):
        self.renderer = renderer or CLIRenderer()
        self.tools = None  # Store tools for /help command
        self.model = None  # Store model name
        self.skills = None  # Store skills list

    def run_interactive(self, agent, tools=None, model=None, skills=None, show_welcome=True) -> None:
        """Run interactive chat loop."""
        import asyncio

        self.tools = tools  # Store for /help command
        self.model = model  # Store model name
        self.skills = skills  # Store skills

        # Show welcome only if requested (main() may have already shown it)
        if show_welcome:
            self.renderer.render_welcome(model=model, tools=tools, skills=skills)

        while True:
            try:
                # Get user input
                user_input = self.renderer.prompt()

                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    if not self.handle_command(user_input, agent):
                        break
                    continue

                # Process message
                asyncio.run(self.process_message(agent, user_input))

            except KeyboardInterrupt:
                self.renderer.render_message("system", "\nUse /quit to exit")
                continue
            except Exception as e:
                self.renderer.render_error(str(e))

    async def process_message(self, agent, user_input: str) -> None:
        """Process a user message."""
        try:
            # Stream agent response
            async for event in agent.prompt(user_input):
                self.renderer.render_event(event)

        except KeyboardInterrupt:
            self.renderer.render_message("system", "\nInterrupted by user")
        except Exception as e:
            import traceback
            # Show error to user - this is an LLM/API error, not a tool error
            error_msg = f"{type(e).__name__}: {str(e)}"
            if "--debug" in sys.argv:
                error_msg += f"\n\nTraceback:\n{traceback.format_exc()}"
            self.renderer.render_error(error_msg)

    def handle_command(self, command: str, agent) -> bool:
        """Handle CLI commands.

        Returns:
            True to continue, False to exit
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ["/quit", "/exit"]:
            self.renderer.render_message("system", "Goodbye!")
            return False

        elif cmd == "/help":
            self.renderer.render_welcome(model=self.model, tools=self.tools, skills=self.skills)

        elif cmd == "/clear":
            agent.clear_messages()
            self.renderer.clear()
            self.renderer.render_message("system", "Conversation cleared")

        elif cmd == "/sessions":
            self.list_sessions()

        elif cmd == "/load":
            if args:
                self.load_session(agent, args)
            else:
                self.renderer.render_message(
                    "system", "Usage: /load <session_id>", is_error=True)

        else:
            self.renderer.render_message(
                "system", f"Unknown command: {cmd}", is_error=True)

        return True

    def list_sessions(self) -> None:
        """List saved sessions."""
        from ..core.session import SessionManager

        manager = SessionManager()
        sessions = manager.list_sessions()

        if not sessions:
            self.renderer.render_message("system", "No saved sessions")
            return

        self.renderer.console.print("\n[bold]Saved Sessions:[/bold]")
        for session in sessions:
            self.renderer.console.print(
                f"  • {session['session_id']} - {session['created_at']}"
            )

    def load_session(self, agent, session_id: str) -> None:
        """Load a session."""
        from ..core.session import SessionManager

        try:
            manager = SessionManager()
            messages = manager.load_session(session_id)

            agent.messages = messages
            self.renderer.render_message(
                "system",
                f"Loaded session: {session_id} ({len(messages)} messages)"
            )
        except FileNotFoundError:
            self.renderer.render_error(f"Session not found: {session_id}")
        except Exception as e:
            self.renderer.render_error(f"Error loading session: {str(e)}")
