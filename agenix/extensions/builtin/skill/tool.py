"""Skill Tool - Dynamically load skill instructions from SKILL.md files.

This tool implements the "Skills as Tools" design pattern, allowing agents to
load specialized instructions on-demand.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from ....tools.builtin.base import Tool, ToolResult


class SkillTool(Tool):
    """Skill Tool - Load specialized instructions from SKILL.md files.

    Skills are markdown files with YAML frontmatter that provide specialized
    instructions for specific tasks (e.g., git commits, PR reviews, testing).

    Skills are loaded from multiple directories with priority:
    1. Project local: {project}/.agenix/skills/
    2. User global: ~/.config/agenix/skills/
    3. Built-in: {agenix}/skills/

    Example:
        >>> skill_tool = SkillTool(working_dir=".")
        >>> result = await skill_tool.execute(
        ...     tool_call_id="123",
        ...     arguments={"skill_name": "commit"}
        ... )
    """

    def __init__(self, working_dir: str = "."):
        """Initialize Skill Tool.

        Args:
            working_dir: Working directory (for .agenix/skills/)
        """
        # Build search paths (lowest to highest priority)
        self.skill_dirs = []

        # 1. Built-in skills
        builtin_dir = Path(__file__).parent.parent / "skills"
        if builtin_dir.exists():
            self.skill_dirs.append(builtin_dir)

        # 2. User global skills
        global_dir = Path.home() / ".config" / "agenix" / "skills"
        if global_dir.exists():
            self.skill_dirs.append(global_dir)

        # 3. Project local skills
        local_dir = Path(working_dir) / ".agenix" / "skills"
        if local_dir.exists():
            self.skill_dirs.append(local_dir)

        # Scan available skills
        self._available_skills = self._scan_skills()

        # Build tool description
        skill_list = ", ".join(sorted(self._available_skills.keys()))
        if not skill_list:
            skill_list = "No skills available"

        super().__init__(
            name="skill",
            description=f"""Load a skill to get specialized instructions for specific tasks.

Skills provide detailed, step-by-step instructions for common workflows like
creating git commits, reviewing PRs, writing tests, etc.

Available skills: {skill_list}

Use this tool when you need detailed instructions for a specialized task.""",
            parameters={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill to load",
                        "enum": list(self._available_skills.keys()) if self._available_skills else ["no-skills"]
                    }
                },
                "required": ["skill_name"]
            }
        )

    def _scan_skills(self) -> Dict[str, Path]:
        """Scan all directories for available skills.

        Returns:
            Dict mapping skill name to SKILL.md path
        """
        skills = {}

        # Scan from lowest to highest priority (later overrides earlier)
        for skill_dir in self.skill_dirs:
            if not skill_dir.exists():
                continue

            for item in skill_dir.iterdir():
                if not item.is_dir():
                    continue

                skill_file = item / "SKILL.md"
                if skill_file.exists():
                    # Parse skill name from frontmatter
                    name = self._parse_skill_name(skill_file)
                    skills[name] = skill_file

        return skills

    def _parse_skill_name(self, skill_file: Path) -> str:
        """Parse skill name from SKILL.md frontmatter.

        Args:
            skill_file: Path to SKILL.md

        Returns:
            Skill name (fallback to directory name)
        """
        try:
            content = skill_file.read_text()

            # Parse YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1])
                    if metadata and "name" in metadata:
                        return metadata["name"]
        except Exception:
            pass

        # Fallback to directory name
        return skill_file.parent.name

    async def execute(
        self,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_update: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """Execute the skill tool - load and return skill instructions.

        Args:
            tool_call_id: Unique ID for this tool call
            arguments: {"skill_name": "skill-name"}
            on_update: Optional progress callback

        Returns:
            ToolResult with skill instructions
        """
        skill_name = arguments.get("skill_name", "")

        if not skill_name:
            return ToolResult(
                content="Error: skill_name parameter is required",
                is_error=True
            )

        # Find skill file
        skill_file = self._available_skills.get(skill_name)
        if not skill_file:
            available = ", ".join(sorted(self._available_skills.keys()))
            return ToolResult(
                content=f"Error: Skill '{skill_name}' not found.\n\nAvailable skills: {available}",
                is_error=True
            )

        # Load skill content
        try:
            if on_update:
                on_update(f"Loading skill '{skill_name}'...")

            content = skill_file.read_text()

            # Remove YAML frontmatter (agent doesn't need to see it)
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()

            # Format result
            result = f"""**Skill '{skill_name}' loaded successfully**

{content}

---
*Follow these instructions carefully. Use the guidelines and examples provided.*
*Skill source: {skill_file.parent.name}/SKILL.md*
"""

            return ToolResult(
                content=result,
                details={
                    "skill_name": skill_name,
                    "skill_file": str(skill_file),
                    "source": "builtin" if "agenix/skills" in str(skill_file) else "custom"
                }
            )

        except Exception as e:
            return ToolResult(
                content=f"Error loading skill '{skill_name}': {str(e)}",
                is_error=True
            )
