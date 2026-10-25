import json
import subprocess

import pytest
from jsonschema import ValidationError

from marketmaker.catalog import index_skills
from marketmaker.export import export_marketplace, publish_marketplace


def make_skill(root, name="example", content=b"supporting bytes\x00\xff"):
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Example workflow\n---\n\nFollow the instructions.\n",
        encoding="utf-8",
    )
    (directory / "assets").mkdir()
    (directory / "assets" / "data.bin").write_bytes(content)
    (directory / "LICENSE").write_text("Original license", encoding="utf-8")
    return directory


def test_complete_export_and_paths(tmp_path):
    source = make_skill(tmp_path / "source")
    skills = index_skills([source.parent, source])
    assert len(skills) == 1
    output = export_marketplace(
        skills, tmp_path / "out", "team", "Team", "1.0.0", "Authors"
    )
    catalog = json.loads((output / ".agents/plugins/marketplace.json").read_text())
    entry = catalog["plugins"][0]
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert entry["category"] == "Productivity"
    plugin_root = output / entry["source"]["path"]
    manifest = json.loads((plugin_root / "plugin.json").read_text())
    assert manifest["name"] == "example"
    assert manifest["author"] == {"name": "Authors"}
    copied = plugin_root / "skills/example"
    assert {p.relative_to(source) for p in source.rglob("*")} == {
        p.relative_to(copied) for p in copied.rglob("*")
    }
    for path in source.rglob("*"):
        if path.is_file():
            assert path.read_bytes() == (copied / path.relative_to(source)).read_bytes()


def test_duplicate_names_fail_before_writing(tmp_path):
    make_skill(tmp_path / "one")
    make_skill(tmp_path / "two")
    skills = index_skills([tmp_path / "one", tmp_path / "two"])
    with pytest.raises(ValidationError):
        export_marketplace(skills, tmp_path / "out", "team", "Team", "1.0.0", "Authors")
    assert not (tmp_path / "out").exists()


def test_existing_destination_preserved(tmp_path):
    make_skill(tmp_path / "source")
    output = tmp_path / "out"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        export_marketplace(
            index_skills([tmp_path / "source"]),
            output,
            "team",
            "Team",
            "1.0.0",
            "Authors",
        )
    assert sentinel.read_text() == "keep"


def test_missing_location_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        index_skills([tmp_path / "missing"])


def test_publish_to_git_remote(tmp_path, monkeypatch):
    for key, value in {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    make_skill(tmp_path / "source")
    output = export_marketplace(
        index_skills([tmp_path / "source"]),
        tmp_path / "out",
        "team",
        "Team",
        "1.0.0",
        "Authors",
    )
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    publish_marketplace(output, str(remote))
    result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(remote),
            "show",
            "main:.agents/plugins/marketplace.json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["name"] == "team"
