"""Settings and configuration management for agenix.

Supports multiple configuration sources with priority:
1. Command-line arguments (highest)
2. .agenix/settings.json (project-local)
3. ~/.agenix/settings.json (user-global)
4. Environment variables
5. Defaults (lowest)
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class Settings:
    """Agenix settings with multiple sources."""

    # Model configuration
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    reasoning_effort: Optional[str] = None  # "low", "medium", "high"

    # Agent configuration
    max_turns: int = 100
    max_tokens: int = 16384
    temperature: float = 0.7

    # Context compaction
    auto_compact: bool = True  # Automatically compact context when overflow detected

    # Working directory
    working_dir: str = "."

    # System prompt
    system_prompt: Optional[str] = None

    # Session
    session: Optional[str] = None

    # OAuth tokens path
    oauth_tokens_file: Optional[str] = None

    # Extra settings
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        working_dir: Optional[str] = None,
        cli_args: Optional[Dict[str, Any]] = None
    ) -> "Settings":
        """Load settings from all sources with proper priority.

        Priority (highest to lowest):
        1. CLI arguments
        2. .agenix/settings.json (project-local)
        3. ~/.agenix/settings.json (user-global)
        4. Environment variables
        5. Defaults

        Args:
            working_dir: Working directory for project-local settings
            cli_args: Command-line arguments dict

        Returns:
            Settings instance with merged configuration
        """
        settings = cls()

        if working_dir:
            settings.working_dir = working_dir

        # Layer 1: Defaults (already set in dataclass)

        # Layer 2: Environment variables
        settings._load_from_env()

        # Layer 3: Global settings (~/.agenix/settings.json)
        global_settings_path = Path.home() / ".agenix" / "settings.json"
        settings._load_from_file(global_settings_path)

        # Layer 4: Project-local settings (.agenix/settings.json)
        if working_dir:
            project_settings_path = Path(working_dir) / ".agenix" / "settings.json"
            settings._load_from_file(project_settings_path)

        # Layer 5: CLI arguments (highest priority)
        if cli_args:
            settings._load_from_dict(cli_args)

        return settings

    def _load_from_env(self):
        """Load settings from environment variables."""
        if os.getenv("AGENIX_MODEL"):
            self.model = os.getenv("AGENIX_MODEL")
        if os.getenv("AGENIX_API_KEY"):
            self.api_key = os.getenv("AGENIX_API_KEY")
        if os.getenv("AGENIX_BASE_URL"):
            self.base_url = os.getenv("AGENIX_BASE_URL")
        if os.getenv("AGENIX_REASONING_EFFORT"):
            self.reasoning_effort = os.getenv("AGENIX_REASONING_EFFORT")
        if os.getenv("AGENIX_MAX_TURNS"):
            self.max_turns = int(os.getenv("AGENIX_MAX_TURNS"))
        if os.getenv("AGENIX_MAX_TOKENS"):
            self.max_tokens = int(os.getenv("AGENIX_MAX_TOKENS"))
        if os.getenv("AGENIX_TEMPERATURE"):
            self.temperature = float(os.getenv("AGENIX_TEMPERATURE"))
        if os.getenv("AGENIX_AUTO_COMPACT"):
            self.auto_compact = os.getenv("AGENIX_AUTO_COMPACT").lower() in ("true", "1", "yes")

    def _load_from_file(self, file_path: Path):
        """Load settings from a JSON file."""
        if not file_path.exists():
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                self._load_from_dict(data)
        except (json.JSONDecodeError, IOError):
            # Ignore invalid files
            pass

    def _load_from_dict(self, data: Dict[str, Any]):
        """Load settings from a dictionary."""
        if "model" in data and data["model"]:
            self.model = data["model"]
        if "api_key" in data and data["api_key"]:
            self.api_key = data["api_key"]
        if "base_url" in data and data["base_url"]:
            self.base_url = data["base_url"]
        if "reasoning_effort" in data and data["reasoning_effort"]:
            self.reasoning_effort = data["reasoning_effort"]
        if "max_turns" in data:
            self.max_turns = int(data["max_turns"])
        if "max_tokens" in data:
            self.max_tokens = int(data["max_tokens"])
        if "temperature" in data:
            self.temperature = float(data["temperature"])
        if "auto_compact" in data:
            self.auto_compact = bool(data["auto_compact"])
        if "working_dir" in data and data["working_dir"]:
            self.working_dir = data["working_dir"]
        if "system_prompt" in data and data["system_prompt"]:
            self.system_prompt = data["system_prompt"]
        if "session" in data and data["session"]:
            self.session = data["session"]
        if "oauth_tokens_file" in data and data["oauth_tokens_file"]:
            self.oauth_tokens_file = data["oauth_tokens_file"]

        # Store any extra settings
        known_keys = {
            "model", "api_key", "base_url", "reasoning_effort",
            "max_turns", "max_tokens", "temperature", "auto_compact",
            "working_dir", "system_prompt", "session", "oauth_tokens_file"
        }
        for key, value in data.items():
            if key not in known_keys:
                self.extra[key] = value

    def save(self, file_path: Path):
        """Save settings to a JSON file.

        Args:
            file_path: Path to save settings to
        """
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "reasoning_effort": self.reasoning_effort,
            "max_turns": self.max_turns,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "auto_compact": self.auto_compact,
            "working_dir": self.working_dir,
            "system_prompt": self.system_prompt,
            "session": self.session,
            "oauth_tokens_file": self.oauth_tokens_file,
        }

        # Add extra settings
        data.update(self.extra)

        # Remove None values for cleaner JSON
        data = {k: v for k, v in data.items() if v is not None}

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        data = {
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "reasoning_effort": self.reasoning_effort,
            "max_turns": self.max_turns,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "auto_compact": self.auto_compact,
            "working_dir": self.working_dir,
            "system_prompt": self.system_prompt,
            "session": self.session,
            "oauth_tokens_file": self.oauth_tokens_file,
        }
        data.update(self.extra)
        return {k: v for k, v in data.items() if v is not None}


def get_default_model() -> str:
    """Get default model."""
    return "gpt-4o"


def ensure_config_dir():
    """Ensure ~/.agenix directory exists."""
    config_dir = Path.home() / ".agenix"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
