import json
import os
import subprocess
import sys

import pytest
import yaml
from jsonschema import ValidationError
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton, QTabWidget
from shiboken6 import delete
from test_marketplace import make_skill

from marketmaker.app import MainWindow
from marketmaker.catalog import index_skills
from marketmaker.export import export_marketplace, publish_marketplace

APP = QApplication.instance() or QApplication([])


@pytest.fixture
def window(tmp_path):
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    settings.setValue("roots", [])
    instance = MainWindow(settings)
    instance.show()
    APP.processEvents()
    yield instance
    instance.close()
    delete(instance)


def button(window, title):
    return next(
        button for button in window.findChildren(QPushButton) if button.text() == title
    )


def test_locations_add_cancel_remove_and_reload(window, tmp_path, monkeypatch):
    source = make_skill(tmp_path / "source")
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: str(source.parent)
    )
    button(window, "&Add folder…").click()
    assert window.roots.count() == 1
    restored = MainWindow(window.settings)
    assert restored.roots.item(0).text() == str(source.parent)
    delete(restored)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: "")
    button(window, "&Add folder…").click()
    assert window.roots.count() == 1
    button(window, "&Index locations").click()
    assert window.model.rowCount() == 1
    window.roots.setCurrentRow(0)
    button(window, "&Remove").click()
    assert window.settings.value("roots", type=list) == []
    button(window, "&Index locations").click()
    assert window.model.rowCount() == 0
    assert not window.export_button.isEnabled()


def test_docks_restore_and_export_tab(window):
    expected = [
        (
            window.skill_locations_dock,
            "Skill locations",
            Qt.DockWidgetArea.LeftDockWidgetArea,
        ),
        (
            window.skill_details_dock,
            "Skill Details",
            Qt.DockWidgetArea.RightDockWidgetArea,
        ),
        (window.share_git_dock, "Share via Git", Qt.DockWidgetArea.RightDockWidgetArea),
    ]
    tabs = window.findChild(QTabWidget)
    assert [tabs.tabText(i) for i in range(tabs.count())] == ["Export"]
    for dock, title, area in expected:
        assert dock.windowTitle() == title
        assert window.dockWidgetArea(dock) == area
        dock.setFloating(True)
        APP.processEvents()
        assert dock.isFloating()
        dock.setFloating(False)
        dock.close()
    actions = [
        action
        for menu in window.menuBar().actions()
        for action in menu.menu().actions()
    ]
    for dock, title, area in expected:
        action = next(action for action in actions if action.text() == title)
        action.trigger()
        assert dock.isVisible()


def test_sort_filter_keyboard_selection_and_details(window, tmp_path):
    make_skill(tmp_path, "alpha")
    make_skill(tmp_path, "beta")
    window.roots.addItem(str(tmp_path))
    window.scan()
    window.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    window.table.setFocus()
    QTest.keyClick(window.table, Qt.Key.Key_Space)
    assert [skill.name for skill in window.selected_skills()] == ["beta"]
    assert window.skill_details.property_values["name"] == "beta"
    window.search.setText("alpha")
    button(window, "Select visible").click()
    assert len(window.selected_skills()) == 2
    button(window, "Clear visible").click()
    assert [skill.name for skill in window.selected_skills()] == ["beta"]
    window.search.setText("no matches")
    assert window.skill_details.property_values == {}
    assert window.export_button.isEnabled()


def test_export_cancel_preview_and_publish_workflow(window, tmp_path, monkeypatch):
    make_skill(tmp_path / "source", "selected")
    make_skill(tmp_path / "source", "unselected")
    window.roots.addItem(str(tmp_path / "source"))
    window.scan()
    window.search.setText("^not-regex$")
    assert window.proxy.rowCount() == 0
    window.search.setText(str(tmp_path / "source" / "selected"))
    button(window, "Select visible").click()
    window.name.setText("team-export")
    window.display_name.setText("Team Export")
    window.version.setText("2.1.0")
    window.author.setText("Authors")
    assert '"version": "2.1.0"' in window.preview.toPlainText()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: "")
    window.export_button.click()
    assert window.exported is None
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path)
    )
    window.export_button.click()
    output = tmp_path / "team-export"
    assert window.exported == output
    assert window.export_path.text() == str(output)
    catalog = json.loads((output / ".agents/plugins/marketplace.json").read_text())
    assert [plugin["name"] for plugin in catalog["plugins"]] == ["selected"]
    manifest = json.loads((output / "plugins/selected/plugin.json").read_text())
    assert manifest["version"] == "2.1.0"
    assert manifest["author"]["name"] == "Authors"
    assert not window.publish_button.isEnabled()
    for key, value in {
        "GIT_AUTHOR_NAME": "Tests",
        "GIT_COMMITTER_NAME": "Tests",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    window.remote.setText(str(remote))
    assert window.publish_button.isEnabled()
    window.publish_button.click()
    assert window.exported is None
    assert not window.publish_button.isEnabled()
    window.remote.setText("another-remote")
    assert not window.publish_button.isEnabled()
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
    assert json.loads(result.stdout) == catalog


def test_publishing_keeps_ignored_skill_assets(tmp_path, monkeypatch):
    source = make_skill(tmp_path / "source")
    (source / ".gitignore").write_text("*.bin\n")
    output = export_marketplace(
        index_skills([source]), tmp_path / "out", "team", "Team", "1.0.0", "Tests"
    )
    for key, value in {
        "GIT_AUTHOR_NAME": "Tests",
        "GIT_COMMITTER_NAME": "Tests",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    publish_marketplace(output, str(remote))
    result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(remote),
            "show",
            "main:plugins/example/skills/example/assets/data.bin",
        ],
        check=False,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == (source / "assets/data.bin").read_bytes()


@pytest.mark.parametrize("platform", ["offscreen", "windows"])
@pytest.mark.parametrize("floating", [False, True])
@pytest.mark.parametrize("shutdown", ["close", "quit"])
def test_real_entry_point_exits_cleanly(platform, floating, shutdown, tmp_path):
    source = make_skill(tmp_path / "source")
    code = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import marketmaker.app as module
original_show = module.MainWindow.show
def show_and_close(self):
    original_show(self)
    self.roots.clear()
    self.roots.addItem(sys.argv[1])
    self.scan()
    self.table.setCurrentIndex(self.proxy.index(0, 0))
    if sys.argv[2] == 'True':
        self.skill_details_dock.setFloating(True)
        self.share_git_dock.setFloating(True)
    action = self.close if sys.argv[3] == 'close' else QApplication.instance().quit
    QTimer.singleShot(50, action)
module.MainWindow.show = show_and_close
module.main()
"""
    for iteration in range(3):
        result = subprocess.run(
            [sys.executable, "-c", code, str(source.parent), str(floating), shutdown],
            check=False,
            env={**os.environ, "QT_QPA_PLATFORM": platform},
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, (
            platform,
            iteration,
            result.returncode,
            result.stderr,
        )


@pytest.mark.parametrize("name", ["../escape", "invalid/name", "", "bad--name"])
def test_invalid_marketplace_identity_fails_before_writing(tmp_path, name):
    source = make_skill(tmp_path / "source")
    with pytest.raises(ValidationError):
        export_marketplace(
            index_skills([source]), tmp_path / "out", name, "Team", "1.0.0", "Tests"
        )
    assert not (tmp_path / "out").exists()


def test_empty_export_fails_before_writing(tmp_path):
    with pytest.raises(ValidationError):
        export_marketplace([], tmp_path / "out", "team", "Team", "1.0.0", "Tests")
    assert not (tmp_path / "out").exists()


def test_malformed_frontmatter_surfaces_yaml_failure(tmp_path):
    source = make_skill(tmp_path)
    (source / "SKILL.md").write_text("---\nname: [broken\n---\nBody")
    with pytest.raises(yaml.YAMLError):
        index_skills([source])


def test_invalid_git_remote_surfaces_native_failure(tmp_path, monkeypatch):
    source = make_skill(tmp_path / "source")
    output = export_marketplace(
        index_skills([source]), tmp_path / "out", "team", "Team", "1.0.0", "Tests"
    )
    for key, value in {
        "GIT_AUTHOR_NAME": "Tests",
        "GIT_COMMITTER_NAME": "Tests",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(subprocess.CalledProcessError) as failure:
        publish_marketplace(output, str(tmp_path / "missing-remote"))
    assert failure.value.cmd[:2] == ["git", "push"]
    assert (output / ".agents/plugins/marketplace.json").is_file()
