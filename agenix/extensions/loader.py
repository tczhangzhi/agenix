"""Extension loader - discovers and loads Python extension modules."""

import importlib.util
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import (CommandDefinition, EventHandler, EventType, ExtensionAPI,
                    ExtensionSetup, LoadedExtension, ToolDefinition)


class ExtensionLoaderAPI:
    """Implementation of ExtensionAPI for use during extension loading."""

    def __init__(self, extension: LoadedExtension):
        self.extension = extension

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a custom tool."""
        self.extension.tools[tool.name] = tool

    def register_command(self, command: CommandDefinition) -> None:
        """Register a custom command."""
        self.extension.commands[command.name] = command

    def on(self, event_type: EventType, handler: Optional[EventHandler] = None):
        """Subscribe to an event.

        Can be used as a decorator or direct call:

        # As decorator:
        @agenix.on(EventType.SESSION_START)
        async def handler(event, ctx):
            pass

        # Direct call:
        agenix.on(EventType.SESSION_START, handler)
        """
        def decorator(func: EventHandler) -> EventHandler:
            if event_type not in self.extension.handlers:
                self.extension.handlers[event_type] = []
            self.extension.handlers[event_type].append(func)
            return func

        # If handler provided, register it directly
        if handler is not None:
            return decorator(handler)

        # Otherwise, return decorator
        return decorator

    def notify(self, message: str, type: str = "info") -> None:
        """Show a notification."""
        prefix = {
            "info": "ℹ️ ",
            "warning": "⚠️ ",
            "error": "❌ "
        }.get(type, "")
        print(f"{prefix}{message}")


def discover_extensions(directory: str) -> List[str]:
    """Discover extension files in a directory.

    Returns list of absolute paths to .py files.
    """
    if not os.path.exists(directory):
        return []

    extensions = []
    try:
        for entry in os.listdir(directory):
            entry_path = os.path.join(directory, entry)

            # Direct .py files
            if os.path.isfile(entry_path) and entry.endswith('.py'):
                extensions.append(entry_path)

            # Directories with __init__.py
            elif os.path.isdir(entry_path):
                init_file = os.path.join(entry_path, '__init__.py')
                if os.path.exists(init_file):
                    extensions.append(init_file)

    except Exception as e:
        print(f"Warning: Failed to discover extensions in {directory}: {e}")

    return extensions


def load_extension_module(file_path: str) -> Optional[ExtensionSetup]:
    """Load a Python extension module and return its setup function.

    Returns:
        The setup() function from the module, or None if not found.
    """
    try:
        # Get module name from file path
        module_name = Path(file_path).stem
        if module_name == "__init__":
            module_name = Path(file_path).parent.name

        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Look for setup() function
        if hasattr(module, 'setup'):
            setup_fn = getattr(module, 'setup')
            if callable(setup_fn):
                return setup_fn

        return None

    except Exception as e:
        print(f"Error loading extension from {file_path}: {e}")
        traceback.print_exc()
        return None


async def load_extension(file_path: str) -> Optional[LoadedExtension]:
    """Load an extension from a file path.

    Returns:
        LoadedExtension instance, or None if loading failed.
    """
    # Create extension object
    extension_name = Path(file_path).stem
    if extension_name == "__init__":
        extension_name = Path(file_path).parent.name

    extension = LoadedExtension(
        path=file_path,
        name=extension_name,
        tools={},
        commands={},
        handlers={}
    )

    # Load the module
    setup_fn = load_extension_module(file_path)
    if not setup_fn:
        print(
            f"Warning: Extension {file_path} does not export a setup() function")
        return None

    # Call setup with our API
    api = ExtensionLoaderAPI(extension)
    try:
        # Support both sync and async setup functions
        import asyncio
        import inspect
        if inspect.iscoroutinefunction(setup_fn):
            await setup_fn(api)
        else:
            setup_fn(api)
    except Exception as e:
        print(f"Error calling setup() in {file_path}: {e}")
        traceback.print_exc()
        return None

    return extension


async def load_builtin_extension(module_path: str) -> Optional[LoadedExtension]:
    """Load a built-in extension from a module path.

    Args:
        module_path: Python module path (e.g., 'agenix.extensions.builtin.cli_channel')

    Returns:
        LoadedExtension instance, or None if loading failed.
    """
    try:
        # Import the module
        import importlib
        module = importlib.import_module(module_path)

        # Get extension name from module path
        extension_name = module_path.split('.')[-1]

        # Create extension object
        extension = LoadedExtension(
            path=f"<builtin:{module_path}>",
            name=extension_name,
            tools={},
            commands={},
            handlers={}
        )

        # Look for setup() function
        if not hasattr(module, 'setup'):
            print(f"Warning: Built-in extension {module_path} does not export a setup() function")
            return None

        setup_fn = getattr(module, 'setup')
        if not callable(setup_fn):
            print(f"Warning: Built-in extension {module_path} setup is not callable")
            return None

        # Call setup with our API
        api = ExtensionLoaderAPI(extension)
        try:
            import asyncio
            import inspect
            if inspect.iscoroutinefunction(setup_fn):
                await setup_fn(api)
            else:
                setup_fn(api)
        except Exception as e:
            print(f"Error calling setup() in built-in extension {module_path}: {e}")
            traceback.print_exc()
            return None

        return extension

    except ImportError as e:
        print(f"Error importing built-in extension {module_path}: {e}")
        return None
    except Exception as e:
        print(f"Error loading built-in extension {module_path}: {e}")
        traceback.print_exc()
        return None


async def discover_and_load_extensions(
    cwd: str,
    agenix_dir: Optional[str] = None,
    builtin_extensions: Optional[List[str]] = None
) -> List[LoadedExtension]:
    """Discover and load extensions from standard locations.

    Loads from (in order):
    1. Built-in: agenix.extensions.builtin.*
    2. Global: ~/.agenix/extensions/
    3. Project: .agenix/extensions/

    Args:
        cwd: Current working directory (for project-local extensions)
        agenix_dir: Global agenix directory (default: ~/.agenix)
        builtin_extensions: List of built-in extension module paths to load

    Returns:
        List of successfully loaded extensions.
    """
    if agenix_dir is None:
        agenix_dir = os.path.expanduser("~/.agenix")

    extensions: List[LoadedExtension] = []

    # 1. Load built-in extensions
    if builtin_extensions:
        for module_path in builtin_extensions:
            ext = await load_builtin_extension(module_path)
            if ext:
                extensions.append(ext)

    all_paths: List[str] = []
    seen = set()

    # 2. Global extensions: ~/.agenix/extensions/
    global_ext_dir = os.path.join(agenix_dir, "extensions")
    for path in discover_extensions(global_ext_dir):
        if path not in seen:
            seen.add(path)
            all_paths.append(path)

    # 3. Project-local extensions: .agenix/extensions/
    local_ext_dir = os.path.join(cwd, ".agenix", "extensions")
    for path in discover_extensions(local_ext_dir):
        if path not in seen:
            seen.add(path)
            all_paths.append(path)

    # Load all discovered extensions
    for path in all_paths:
        extension = await load_extension(path)
        if extension:
            extensions.append(extension)

    return extensions
