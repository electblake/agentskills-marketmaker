import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtWidgets import QApplication, QTabWidget
from test_marketplace import make_skill

from marketmaker.app import MainWindow

APP = QApplication.instance() or QApplication([])


def test_index_filter_selection_and_settings(tmp_path):
    make_skill(tmp_path / "source", "first")
    make_skill(tmp_path / "source", "second")
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("roots", [str(tmp_path / "source")])
    window = MainWindow(settings)
    window.show()
    window.scan()
    window.search.setText("first")
    window.check_visible(Qt.CheckState.Checked)
    assert [skill.name for skill in window.selected_skills()] == ["first"]
    window.search.setText("second")
    assert [skill.name for skill in window.selected_skills()] == ["first"]
    window.check_visible(Qt.CheckState.Checked)
    assert len(window.selected_skills()) == 2
    assert "plugins/first/plugin.json" in window.preview.toPlainText()
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    assert window.skill_details.property_values["name"] == "second"
    assert "Follow the instructions." in window.skill_details.instructions.toPlainText()
    window.roots.addItem(str(tmp_path / "another-source"))
    window.save_roots()
    assert settings.value("roots", type=list)[1] == str(tmp_path / "another-source")
    assert window.export_button.isEnabled()
    assert not window.publish_button.isEnabled()
    APP.processEvents()
    window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_skill_details_metadata_rendering_and_selection_reset(tmp_path):
    source = make_skill(tmp_path / "source", "detailed")
    (source / "SKILL.md").write_text(
        "---\nname: detailed\ndescription: A detailed skill\nlicense: MIT\n"
        "metadata:\n  author: Team\n  tags: [desktop, qt]\n"
        "---\n# Instructions\n\nUse **Qt**.\n",
        encoding="utf-8",
    )
    settings = QSettings(str(tmp_path / "details.ini"), QSettings.Format.IniFormat)
    settings.setValue("roots", [str(source.parent)])
    window = MainWindow(settings)
    window.show()
    window.scan()
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    details = window.skill_details
    assert details.property_values["license"] == "MIT"
    assert details.property_values["metadata.author"] == "Team"
    assert details.property_values["metadata.tags[1]"] == "qt"
    assert details.property_values["File count"] == "3"
    assert details.property_values["assets/data.bin"].endswith(" bytes")
    assert "Use Qt." in details.instructions.toPlainText()
    assert "metadata:" not in details.instructions.toPlainText()
    assert (
        window.dockWidgetArea(window.skill_details_dock)
        == Qt.DockWidgetArea.RightDockWidgetArea
    )
    assert all(
        tab.tabText(i) != "Skill instructions"
        for tab in window.findChildren(QTabWidget)
        for i in range(tab.count())
    )
    window.skill_details_dock.setFloating(True)
    APP.processEvents()
    assert window.skill_details_dock.isFloating()
    window.skill_details_dock.setFloating(False)
    window.scan()
    assert details.property_values == {}
    assert details.instructions.toPlainText() == ""
    window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
