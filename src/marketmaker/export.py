import json
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

from marketmaker.catalog import Skill

PLUGIN_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_SCHEMA = json.loads(
    files("marketmaker").joinpath("schemas/plugin.schema.json").read_text()
)
NAME_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "maxLength": 64,
    "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$",
}


def manifests(
    skills: list[Skill], name: str, display_name: str, version: str, author: str
):
    catalog = {"name": name, "interface": {"displayName": display_name}, "plugins": []}
    plugins = []
    for skill in skills:
        plugin = {
            "$schema": PLUGIN_SCHEMA_URL,
            "name": skill.name,
            "version": version,
            "description": skill.description,
            "author": {"name": author},
            "extensions": {
                "com.openai": {
                    "interface": {
                        "displayName": skill.name,
                        "developerName": author,
                        "category": "Productivity",
                    }
                }
            },
        }
        plugins.append(plugin)
        catalog["plugins"].append(
            {
                "name": skill.name,
                "source": {"source": "local", "path": f"./plugins/{skill.name}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Productivity",
            }
        )
    return catalog, plugins


def export_marketplace(
    skills: list[Skill],
    destination: Path,
    name: str,
    display_name: str,
    version: str,
    author: str,
) -> Path:
    catalog, plugins = manifests(skills, name, display_name, version, author)
    Draft202012Validator(NAME_SCHEMA).validate(name)
    Draft202012Validator(
        {"type": "array", "minItems": 1, "uniqueItems": True, "items": NAME_SCHEMA}
    ).validate([skill.name for skill in skills])
    for skill, plugin in zip(skills, plugins):
        Draft202012Validator(
            {"type": "string", "minLength": 1, "maxLength": 1024}
        ).validate(skill.description)
        Draft202012Validator(PLUGIN_SCHEMA).validate(plugin)
    destination.mkdir()
    catalog_path = destination / ".agents" / "plugins" / "marketplace.json"
    catalog_path.parent.mkdir(parents=True)
    for skill, plugin in zip(skills, plugins):
        plugin_root = destination / "plugins" / skill.name
        # Materialize linked source folders so the export is self-contained.
        shutil.copytree(skill.path, plugin_root / "skills" / skill.name)
        (plugin_root / "plugin.json").write_text(
            json.dumps(plugin, indent=2) + "\n", encoding="utf-8"
        )
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    (destination / "README.md").write_text(
        f"# {display_name}\n\n"
        "This repository contains a skill-only marketplace, with one plugin per skill.\n\n"
        "After publishing this repository, team members can add it with:\n\n"
        "```sh\ncodex plugin marketplace add OWNER/REPOSITORY\n```\n\n"
        "For a local checkout, run `codex plugin marketplace add .` from this folder.\n"
        "Open the ChatGPT desktop Plugins Directory, choose the marketplace, and install a plugin.\n\n"
        "Skills retain their original files and license terms. External tools, credentials, "
        "and dependencies referenced by a skill must be supplied on the destination host.\n",
        encoding="utf-8",
    )
    return destination


def publish_marketplace(directory: Path, remote: str):
    """Publish a fresh export to an existing empty Git remote using host credentials."""
    commands = [
        ["git", "init", "--initial-branch=main"],
        ["git", "add", "--all", "--force"],
        ["git", "commit", "-m", "Export skill marketplace"],
        ["git", "remote", "add", "origin", remote],
        ["git", "push", "--set-upstream", "origin", "main"],
    ]
    for command in commands:
        subprocess.run(command, cwd=directory, check=True)
