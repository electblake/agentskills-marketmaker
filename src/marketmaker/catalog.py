import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Skill:
    path: Path
    name: str
    description: str


def index_skills(roots: list[Path]) -> list[Skill]:
    skills = []
    visited = set()

    def visit(directory: Path):
        resolved = directory.expanduser().resolve(strict=True)
        if resolved in visited:
            return
        visited.add(resolved)
        children = sorted(resolved.iterdir(), key=lambda path: path.name.casefold())
        if resolved / "SKILL.md" in children:
            text = (resolved / "SKILL.md").read_text(encoding="utf-8-sig")
            _, frontmatter, _ = re.split(r"(?m)^---\s*$", text, maxsplit=2)
            metadata = yaml.safe_load(frontmatter)
            skills.append(Skill(resolved, metadata["name"], metadata["description"]))
            return
        for child in children:
            if child.is_dir():
                visit(child)

    for root in roots:
        visit(root)
    return sorted(skills, key=lambda skill: (skill.name.casefold(), str(skill.path)))
