import json
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QSortFilterProxyModel, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from marketmaker.catalog import index_skills
from marketmaker.details import SkillDetails
from marketmaker.export import export_marketplace, manifests, publish_marketplace


class MainWindow(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.settings = (
            settings
            if settings is not None
            else QSettings("MarketMaker", "MarketMaker")
        )
        self.skills = []
        self.exported = None
        self.setWindowTitle("MarketMaker — Skill marketplaces")
        self.resize(1200, 820)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)
        heading = QLabel("Build a skill marketplace")
        font = heading.font()
        font.setPointSize(font.pointSize() + 8)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                "Index local folders, choose skills, then export and share with your team."
            )
        )

        sources = QWidget()
        source_layout = QVBoxLayout(sources)
        source_layout.setContentsMargins(12, 12, 12, 12)
        self.roots = QListWidget()
        self.roots.setAccessibleName("Skill locations")
        defaults = [
            str(Path.home() / ".agents/skills"),
            str(Path.home() / ".codex/skills"),
        ]
        self.roots.addItems(self.settings.value("roots", defaults, type=list))
        source_layout.addWidget(self.roots)
        root_actions = QHBoxLayout()
        add = QPushButton("&Add folder…")
        add.clicked.connect(self.add_root)
        remove = QPushButton("&Remove")
        remove.clicked.connect(self.remove_root)
        root_actions.addWidget(add)
        root_actions.addWidget(remove)
        source_layout.addLayout(root_actions)
        scan = QPushButton("&Index locations")
        scan.clicked.connect(self.scan)
        source_layout.addWidget(scan)
        self.skill_locations_dock = QDockWidget("Skill locations", self)
        self.skill_locations_dock.setObjectName("skillLocationsDock")
        self.skill_locations_dock.setWidget(sources)
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.skill_locations_dock
        )

        catalog = QWidget()
        catalog_layout = QVBoxLayout(catalog)
        catalog_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search skills, descriptions, and paths")
        self.search.setAccessibleName("Search skills")
        catalog_layout.addWidget(self.search)
        self.model = QStandardItemModel(0, 3, self)
        self.model.setHorizontalHeaderLabels(["Skill", "Description", "Source folder"])
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.table = QTableView()
        self.table.setAccessibleName("Indexed skills; check to include in export")
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().hide()
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 330)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().currentChanged.connect(self.show_skill)
        catalog_layout.addWidget(self.table)
        actions = QHBoxLayout()
        for label, state in [
            ("Select visible", Qt.CheckState.Checked),
            ("Clear visible", Qt.CheckState.Unchecked),
        ]:
            button = QPushButton(label)
            button.clicked.connect(
                lambda checked=False, state=state: self.check_visible(state)
            )
            actions.addWidget(button)
        self.count = QLabel("No skills indexed")
        actions.addWidget(self.count, 1)
        catalog_layout.addLayout(actions)
        layout.addWidget(catalog, 3)

        tabs = QTabWidget()
        export_tab = QWidget()
        export_layout = QHBoxLayout(export_tab)
        form = QFormLayout()
        self.name = QLineEdit("team-skills")
        self.display_name = QLineEdit("Team Skills")
        self.version = QLineEdit("1.0.0")
        self.author = QLineEdit()
        self.author.setPlaceholderText("Publisher or team name")
        for label, field in [
            ("Marketplace &ID", self.name),
            ("&Display name", self.display_name),
            ("&Version", self.version),
            ("&Publisher", self.author),
        ]:
            form.addRow(label, field)
            field.textChanged.connect(self.refresh_preview)
        self.export_button = QPushButton("&Export marketplace…")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export)
        form.addRow(self.export_button)
        export_layout.addLayout(form, 1)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Generated marketplace and plugin manifests")
        export_layout.addWidget(self.preview, 2)
        tabs.addTab(export_tab, "Export")

        self.skill_details = SkillDetails()
        self.skill_details_dock = QDockWidget("Skill Details", self)
        self.skill_details_dock.setObjectName("skillDetailsDock")
        self.skill_details_dock.setWidget(self.skill_details)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.skill_details_dock
        )

        publish_tab = QWidget()
        publish_layout = QFormLayout(publish_tab)
        description = QLabel(
            "Publish the most recent export to an existing empty GitHub or other Git repository.\n"
            "Uses this host’s Git identity and credentials. All exported files will be pushed."
        )
        description.setWordWrap(True)
        publish_layout.addRow(description)
        self.export_path = QLineEdit()
        self.export_path.setReadOnly(True)
        publish_layout.addRow("Exported folder", self.export_path)
        self.remote = QLineEdit()
        self.remote.setPlaceholderText(
            "https://github.com/your-team/your-marketplace.git"
        )
        publish_layout.addRow("Git &remote", self.remote)
        self.publish_button = QPushButton("Commit and &push export")
        self.publish_button.setEnabled(False)
        self.publish_button.clicked.connect(self.publish)
        self.remote.textChanged.connect(self.refresh_publish)
        publish_layout.addRow(self.publish_button)
        self.share_git_dock = QDockWidget("Share via Git", self)
        self.share_git_dock.setObjectName("shareGitDock")
        self.share_git_dock.setWidget(publish_tab)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.share_git_dock)
        view_menu = self.menuBar().addMenu("&View")
        for dock in (
            self.skill_locations_dock,
            self.skill_details_dock,
            self.share_git_dock,
        ):
            view_menu.addAction(dock.toggleViewAction())
        layout.addWidget(tabs, 2)
        self.setCentralWidget(body)
        self.resizeDocks([self.skill_details_dock], [320], Qt.Orientation.Horizontal)
        self.statusBar().showMessage("Add skill locations, then index them to begin.")
        self.model.itemChanged.connect(self.refresh_preview)
        self.refresh_preview()

    def save_roots(self):
        self.settings.setValue(
            "roots", [self.roots.item(i).text() for i in range(self.roots.count())]
        )

    def add_root(self):
        directory = QFileDialog.getExistingDirectory(self, "Add skill location")
        if directory:
            self.roots.addItem(directory)
            self.save_roots()

    def remove_root(self):
        self.roots.takeItem(self.roots.currentRow())
        self.save_roots()

    def scan(self):
        self.skills = index_skills(
            [Path(self.roots.item(i).text()) for i in range(self.roots.count())]
        )
        self.model.removeRows(0, self.model.rowCount())
        self.skill_details.clear()
        for skill in self.skills:
            item = QStandardItem(skill.name)
            item.setCheckable(True)
            item.setData(skill, Qt.ItemDataRole.UserRole)
            row = [
                item,
                QStandardItem(skill.description),
                QStandardItem(str(skill.path)),
            ]
            for cell in row:
                cell.setToolTip(cell.text())
            self.model.appendRow(row)
        self.refresh_preview()
        self.statusBar().showMessage(f"Indexed {len(self.skills)} skills.")

    def selected_skills(self):
        return [
            self.model.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.model.rowCount())
            if self.model.item(row).checkState() == Qt.CheckState.Checked
        ]

    def check_visible(self, state):
        for row in range(self.proxy.rowCount()):
            index = self.proxy.mapToSource(self.proxy.index(row, 0))
            self.model.itemFromIndex(index).setCheckState(state)

    def show_skill(self, current, previous):
        if current.isValid():
            index = self.proxy.mapToSource(current.siblingAtColumn(0))
            skill = self.model.itemFromIndex(index).data(Qt.ItemDataRole.UserRole)
            self.skill_details.load_skill(skill)
        else:
            self.skill_details.clear()

    def refresh_preview(self):
        selected = self.selected_skills()
        self.count.setText(f"{len(selected)} selected / {len(self.skills)} indexed")
        self.export_button.setEnabled(bool(selected))
        catalog, plugins = manifests(
            selected,
            self.name.text(),
            self.display_name.text(),
            self.version.text(),
            self.author.text(),
        )
        sections = [
            ".agents/plugins/marketplace.json\n" + json.dumps(catalog, indent=2)
        ]
        sections.extend(
            f"plugins/{plugin['name']}/plugin.json\n" + json.dumps(plugin, indent=2)
            for plugin in plugins
        )
        self.preview.setPlainText("\n\n".join(sections))

    def export(self):
        parent = QFileDialog.getExistingDirectory(
            self, "Choose parent folder for a NEW marketplace folder"
        )
        if parent:
            self.exported = export_marketplace(
                self.selected_skills(),
                Path(parent) / self.name.text(),
                self.name.text(),
                self.display_name.text(),
                self.version.text(),
                self.author.text(),
            )
            self.export_path.setText(str(self.exported))
            self.refresh_publish()
            self.statusBar().showMessage(f"Exported marketplace to {self.exported}")

    def refresh_publish(self):
        self.publish_button.setEnabled(
            self.exported is not None and bool(self.remote.text())
        )

    def publish(self):
        publish_marketplace(self.exported, self.remote.text())
        self.publish_button.setEnabled(False)
        self.exported = None
        self.statusBar().showMessage(
            "Marketplace pushed. Team members can add the repository in Codex."
        )


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
