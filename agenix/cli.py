"""Main entry point for agenix."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from .core.agent import Agent, AgentConfig
from .core.llm import get_provider
from .core.session import SessionManager
from .core.settings import Settings, get_default_model
from .tools.bash import BashTool
from .tools.edit import EditTool
from .tools.grep import GrepTool
from .tools.read import ReadTool
from .tools.write import WriteTool
from .tools.glob import GlobTool
from .tools.skill import SkillTool
from .tools.task import TaskTool
from .channel.tui import CLI, CLIRenderer
from .extensions import discover_and_load_extensions, ExtensionRunner, ExtensionContext


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Agenix - Lightweight AI coding agent with multi-model support"
    )

    # Model configuration
    parser.add_argument(
        "--model",
        type=str,
        help="Model to use (e.g., gpt-4o, claude-sonnet-4-5, gemini/gemini-pro)"
    )

    parser.add_argument(
        "--api-key",
        type=str,
        help="API key (or set AGENIX_API_KEY env var)"
    )

    parser.add_argument(
        "--base-url",
        type=str,
        help="API base URL (optional, for custom endpoints)"
    )

    parser.add_argument(
        "--reasoning-effort",
        type=str,
        choices=["low", "medium", "high"],
        help="Reasoning effort for thinking models (low/medium/high)"
    )

    # Agent configuration
    parser.add_argument(
        "--working-dir",
        type=str,
        default=".",
        help="Working directory for file operations (default: current directory)"
    )

    parser.add_argument(
        "--system-prompt",
        type=str,
        help="Custom system prompt"
    )

    parser.add_argument(
        "--session",
        type=str,
        help="Session ID to load"
    )

    parser.add_argument(
        "--max-turns",
        type=int,
        help="Maximum conversation turns per prompt (default: 100)"
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        help="Maximum tokens for LLM output (default: 16384)"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        help="Sampling temperature (default: 0.7)"
    )

    # Commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Auth command (placeholder for future implementation)
    auth_parser = subparsers.add_parser("auth", help="Manage OAuth authentication")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command")

    # auth login
    login_parser = auth_subparsers.add_parser("login", help="Login to a provider")
    login_parser.add_argument("provider", choices=["google", "claude", "chatgpt", "antigravity"])

    # auth list
    auth_subparsers.add_parser("list", help="List configured providers")

    # auth status
    status_parser = auth_subparsers.add_parser("status", help="Show token status")
    status_parser.add_argument("provider", nargs="?")

    # auth revoke
    revoke_parser = auth_subparsers.add_parser("revoke", help="Revoke tokens")
    revoke_parser.add_argument("provider")

    # Main message argument
    parser.add_argument(
        "message",
        nargs="*",
        help="Direct message to process (non-interactive mode)"
    )

    return parser.parse_args()


def get_default_system_prompt(tools: list) -> str:
    """Get default system prompt with dynamic guidelines based on available tools.

    Args:
        tools: List of available tool instances
    """
    import datetime

    # Get tool names
    tool_names = {tool.name for tool in tools}

    # Tool descriptions (keep it short - one line per tool)
    tool_descriptions = {
        "read": "Read file contents",
        "write": "Create or overwrite files",
        "edit": "Make surgical edits to files (find exact text and replace)",
        "bash": "Execute bash commands (ls, grep, find, etc.)",
        "grep": "Search file contents for patterns",
        "glob": "Find files matching glob patterns",
        "skill": "Load specialized instructions from SKILL.md files",
        "task": "Delegate tasks to specialized subagents",
        "MemoryRead": "Read from memory store (daily notes or long-term memory)",
        "MemoryWrite": "Write to memory store (daily notes or long-term memory)",
        "CronList": "List scheduled cron jobs",
        "CronAdd": "Add a new scheduled cron job",
        "CronRemove": "Remove a scheduled cron job",
    }

    # Build tools list
    tools_list = "\n".join([
        f"- {name}: {tool_descriptions.get(name, 'Tool')}"
        for name in sorted(tool_names)
        if name in tool_descriptions
    ])

    # Build guidelines dynamically based on available tools
    guidelines = []

    has_read = "read" in tool_names
    has_edit = "edit" in tool_names
    has_write = "write" in tool_names

    # Read before edit guideline
    if has_read and has_edit:
        guidelines.append("Use read to examine files before editing")

    # Edit guideline
    if has_edit:
        guidelines.append("Use edit for precise changes (old text must match exactly)")

    # Write guideline
    if has_write:
        guidelines.append("Use write only for new files or complete rewrites")

    # Output guideline
    if has_edit or has_write:
        guidelines.append("When summarizing your actions, output plain text directly - do NOT use cat or bash to display what you did")

    # Always include these
    guidelines.append("Be concise in your responses")
    guidelines.append("Show file paths clearly when working with files")

    guidelines_text = "\n".join([f"- {g}" for g in guidelines])

    # Get current date/time
    now = datetime.datetime.now()
    date_time = now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")

    # Get working directory
    cwd = os.getcwd()

    return f"""You are an expert coding assistant operating inside Agenix, a coding agent harness. You help users by reading files, executing commands, editing code, and writing new files.

Available tools:
{tools_list}

Guidelines:
{guidelines_text}

Current date and time: {date_time}
Current working directory: {cwd}"""


def main():
    """Main entry point."""
    args = parse_args()

    # Handle auth commands
    if args.command == "auth":
        console = CLIRenderer()
        console.render_error(
            "Auth system not yet implemented.\n"
            "For now, please use environment variables or settings.json:\n"
            "  - AGENIX_API_KEY\n"
            "  - AGENIX_MODEL\n"
            "  - AGENIX_BASE_URL\n"
            "Or create ~/.agenix/settings.json or .agenix/settings.json"
        )
        sys.exit(1)

    # Setup working directory
    working_dir = os.path.abspath(args.working_dir)
    if not os.path.exists(working_dir):
        print(f"Error: Working directory does not exist: {working_dir}")
        sys.exit(1)

    # Load settings from all sources
    cli_args_dict = {
        "model": args.model,
        "api_key": args.api_key,
        "base_url": args.base_url,
        "reasoning_effort": getattr(args, "reasoning_effort", None),
        "max_turns": args.max_turns,
        "max_tokens": args.max_tokens,
        "temperature": getattr(args, "temperature", None),
        "system_prompt": args.system_prompt,
        "session": args.session,
        "working_dir": working_dir,
    }
    # Remove None values
    cli_args_dict = {k: v for k, v in cli_args_dict.items() if v is not None}

    settings = Settings.load(working_dir=working_dir, cli_args=cli_args_dict)

    # Check if we have a direct message (non-interactive)
    is_interactive = not args.message

    # Initialize CLI renderer for interactive mode (will set session_id later)
    cli = CLI() if is_interactive else None

    # Setup workspace
    workspace = Path(working_dir) / ".agenix"
    workspace.mkdir(exist_ok=True)

    # Setup core tools (read, write, edit, bash, grep, glob, skill)
    # Extension tools (memory, cron) will be added by extensions
    tools = [
        ReadTool(working_dir=working_dir),
        WriteTool(working_dir=working_dir),
        EditTool(working_dir=working_dir),
        BashTool(working_dir=working_dir),
        GrepTool(working_dir=working_dir),
        GlobTool(working_dir=working_dir),
        SkillTool(working_dir=working_dir),
    ]

    # Validate settings and prompt for missing values
    if not settings.api_key:
        if is_interactive and cli:
            settings.api_key = cli.renderer.prompt_config_input(
                "API Key",
                "API key required (set AGENIX_API_KEY or use --api-key)",
                is_secret=True
            )
        else:
            print(
                "Error: API key not found. Please set AGENIX_API_KEY environment variable,\n"
                "create ~/.agenix/settings.json, or use --api-key parameter.\n\n"
                "Example:\n"
                "  export AGENIX_API_KEY='your-key'\n"
                "  agenix\n\n"
                "Or:\n"
                "  agenix --api-key 'your-key'"
            )
            sys.exit(1)

    if not settings.model:
        settings.model = get_default_model()

    # Show banner in interactive mode
    if is_interactive and cli:
        # Get skills from SkillTool for banner
        try:
            skill_tool = next(t for t in tools if t.name == "skill")
            skills = [{"name": name, "description": info.get("description", "")}
                      for name, info in skill_tool._available_skills.items()]
        except (StopIteration, AttributeError):
            skills = []

        cli.renderer.render_welcome(model=settings.model, tools=tools, skills=skills)

    # Setup agent
    try:
        config = AgentConfig(
            model=settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url,
            system_prompt=settings.system_prompt or get_default_system_prompt(tools),
            max_turns=settings.max_turns,
            max_tokens=settings.max_tokens,
            reasoning_effort=settings.reasoning_effort,
            auto_compact=settings.auto_compact,
        )
        agent = Agent(config=config, tools=tools)

        # Add TaskTool after agent creation (needs agent_id)
        task_tool = TaskTool(
            working_dir=working_dir,
            agent_id=agent.agent_id,
            parent_chain=[],
            model=settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url,
        )
        agent.tools.append(task_tool)
        agent.tool_map[task_tool.name] = task_tool

    except Exception as e:
        if is_interactive and cli:
            cli.renderer.render_error(f"Error initializing agent: {e}")
        else:
            print(f"Error initializing agent: {e}")
        sys.exit(1)

    # Setup session management
    session_manager = SessionManager()

    # Load session if specified
    if settings.session:
        try:
            messages = session_manager.load_session(settings.session)
            agent.messages = messages
            print(f"Loaded session: {settings.session} ({len(messages)} messages)")
        except Exception as e:
            print(f"Error loading session: {e}")
            sys.exit(1)

    # Subscribe to agent events for session persistence
    current_session_id = settings.session or session_manager.create_session()

    # Pass session ID to CLI for resume hint
    if cli:
        cli.session_id = current_session_id

    def on_message_end(event):
        """Save messages to session."""
        from agenix.core.messages import MessageEndEvent
        if isinstance(event, MessageEndEvent) and event.message:
            session_manager.save_message(current_session_id, event.message)

    agent.subscribe(on_message_end)

    # Get skills for interactive mode
    skills = []
    if is_interactive:
        try:
            skill_tool = next(t for t in tools if t.name == "skill")
            skills = [{"name": name, "description": info.get("description", "")}
                      for name, info in skill_tool._available_skills.items()]
        except (StopIteration, AttributeError):
            pass

    # Run CLI
    if is_interactive:
        # Run async main loop
        async def run_async():
            """Run interactive CLI with background services."""
            try:
                # Load extensions (built-in + user)
                extensions = await discover_and_load_extensions(
                    cwd=working_dir,
                    builtin_extensions=[
                        'agenix.extensions.builtin.memory',
                        'agenix.extensions.builtin.cron',
                        'agenix.extensions.builtin.heartbeat',
                    ]
                )

                # Create extension context
                ctx = ExtensionContext(agent=agent, cwd=working_dir, tools=agent.tools)
                runner = ExtensionRunner(extensions=extensions, context=ctx)

                # Add extension tools to agent
                from .tools.builtin.base import Tool
                from .extensions.types import ToolDefinition

                for tool_name, tool_def in runner.get_tools().items():
                    # Wrap extension ToolDefinition as agent Tool
                    class ExtensionTool(Tool):
                        def __init__(self, definition: ToolDefinition):
                            self.definition = definition

                        @property
                        def name(self) -> str:
                            return self.definition.name

                        @property
                        def description(self) -> str:
                            return self.definition.description

                        def to_dict(self):
                            return {
                                "name": self.definition.name,
                                "description": self.definition.description,
                                "input_schema": self.definition.parameters
                            }

                        async def execute(self, tool_call_id: str, arguments: dict, on_update=None):
                            from .tools.builtin.base import ToolResult
                            try:
                                result = await self.definition.execute(arguments, ctx)
                                return ToolResult(content=str(result), is_error=False)
                            except Exception as e:
                                return ToolResult(content=f"Error: {str(e)}", is_error=True)

                    ext_tool = ExtensionTool(tool_def)
                    agent.tools.append(ext_tool)
                    agent.tool_map[ext_tool.name] = ext_tool

                # Emit SESSION_START
                from .extensions.types import SessionStartEvent
                await runner.emit(SessionStartEvent())

                # Run interactive CLI
                await cli.run_interactive_async(
                    agent,
                    tools=agent.tools,
                    model=settings.model,
                    skills=skills,
                    show_welcome=False
                )

            except KeyboardInterrupt:
                print("\nShutting down...")
            finally:
                # Emit SESSION_END
                from .extensions.types import SessionEndEvent
                await runner.emit(SessionEndEvent())

                # Cleanup agent
                await agent.cleanup()

        asyncio.run(run_async())
    else:
        # Non-interactive mode
        message = " ".join(args.message)
        renderer = CLIRenderer()
        asyncio.run(process_single_message(agent, message, renderer))


async def process_single_message(agent, message: str, renderer: CLIRenderer):
    """Process a single message in non-interactive mode."""
    try:
        renderer.render_message("user", message)

        async for event in agent.prompt(message):
            renderer.render_event(event)

    except Exception as e:
        renderer.render_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
