"""
Prompt builder — composes the layered system prompt from versioned files.

The prompt has 5 layers:
1. Identity (static)
2. Rules (rarely changed)
3. Tool guide (sometimes changed)
4. Lessons learned (primary improvement target)
5. Few-shot examples (secondary improvement target)
"""

import yaml
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def get_latest_version() -> str:
    """Find the latest prompt version directory."""
    versions = sorted(
        [d.name for d in PROMPTS_DIR.iterdir() if d.is_dir() and d.name.startswith("v")],
        key=lambda v: int(v[1:])
    )
    return versions[-1] if versions else "v0"


def build_system_prompt(version: str | None = None) -> str:
    """
    Compose the full system prompt from layered files.

    Args:
        version: Prompt version to use (e.g., 'v0', 'v1'). 
                 If None, uses latest version.

    Returns:
        Complete system prompt string.
    """
    if version is None:
        version = get_latest_version()

    version_dir = PROMPTS_DIR / version

    if not version_dir.exists():
        raise FileNotFoundError(f"Prompt version {version} not found at {version_dir}")

    # Layer 1: Identity
    identity = _load_text(version_dir / "identity.md")

    # Layer 2: Rules
    rules = _load_text(version_dir / "rules.md")

    # Layer 3: Tool guide
    tool_guide = _load_text(version_dir / "tool_guide.md")

    # Layer 4: Lessons learned
    lessons = _load_lessons(version_dir / "lessons_learned.yaml")

    # Layer 5: Few-shot examples
    examples = _load_examples(version_dir / "few_shot.yaml")

    # Compose
    parts = [identity]

    if rules:
        parts.append(rules)

    if tool_guide:
        parts.append(tool_guide)

    if lessons:
        parts.append(lessons)

    if examples:
        parts.append(examples)

    return "\n\n---\n\n".join(parts)


def _load_text(path: Path) -> str:
    """Load a text file, return empty string if not found."""
    if path.exists():
        return path.read_text().strip()
    return ""


def _load_lessons(path: Path) -> str:
    """Load lessons_learned.yaml and format as prompt text."""
    if not path.exists():
        return ""

    data = yaml.safe_load(path.read_text())
    if not data or not data.get("lessons"):
        return ""

    lines = ["## Lessons Learned (from previous evaluations)\n"]
    for i, lesson in enumerate(data["lessons"], 1):
        trigger = lesson.get("trigger", "")
        action = lesson.get("action", "")
        priority = lesson.get("priority", "normal").upper()

        lines.append(f"### Lesson {i} [{priority}]")
        lines.append(f"**When:** {trigger}")
        lines.append(f"**Do:** {action}")
        lines.append("")

    return "\n".join(lines)


def _load_examples(path: Path) -> str:
    """Load few_shot.yaml and format as prompt text."""
    if not path.exists():
        return ""

    data = yaml.safe_load(path.read_text())
    if not data or not data.get("examples"):
        return ""

    lines = ["## Reference Examples\n"]
    lines.append("Follow these patterns when handling similar situations:\n")
    for i, example in enumerate(data["examples"], 1):
        situation = example.get("situation", "")
        correct_response = example.get("correct_response", "")
        lines.append(f"**Example {i}: {situation}**")
        lines.append(f"Correct approach: {correct_response}")
        lines.append("")

    return "\n".join(lines)


def copy_version(source_version: str, target_version: str) -> Path:
    """
    Copy a prompt version to create a new one.

    Returns:
        Path to the new version directory.
    """
    import shutil

    source_dir = PROMPTS_DIR / source_version
    target_dir = PROMPTS_DIR / target_version

    if target_dir.exists():
        shutil.rmtree(target_dir)

    shutil.copytree(source_dir, target_dir)
    return target_dir


def update_lessons(version: str, new_lessons: list[dict]) -> None:
    """Add new lessons to a prompt version's lessons_learned.yaml."""
    path = PROMPTS_DIR / version / "lessons_learned.yaml"

    data = {"lessons": []}
    if path.exists():
        loaded = yaml.safe_load(path.read_text())
        if loaded and loaded.get("lessons"):
            data["lessons"] = loaded["lessons"]

    data["lessons"].extend(new_lessons)

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def update_examples(version: str, new_examples: list[dict]) -> None:
    """Add new examples to a prompt version's few_shot.yaml."""
    path = PROMPTS_DIR / version / "few_shot.yaml"

    data = {"examples": []}
    if path.exists():
        loaded = yaml.safe_load(path.read_text())
        if loaded and loaded.get("examples"):
            data["examples"] = loaded["examples"]

    data["examples"].extend(new_examples)

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def update_metadata(version: str, metadata_updates: dict) -> None:
    """Update metadata for a prompt version."""
    path = PROMPTS_DIR / version / "metadata.yaml"

    data = {}
    if path.exists():
        data = yaml.safe_load(path.read_text()) or {}

    data.update(metadata_updates)

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
