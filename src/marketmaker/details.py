import re
from datetime import datetime

import yaml
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from marketmaker.catalog import Skill


class SkillDetails(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.summary = QLabel("Select a skill to view its details.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.properties = QScrollArea()
        self.properties.setWidgetResizable(True)
        self.properties.setAccessibleName("Skill properties")
        splitter.addWidget(self.properties)
        instructions = QWidget()
        instructions_layout = QVBoxLayout(instructions)
        instructions_layout.setContentsMargins(0, 0, 0, 0)
        instructions_layout.addWidget(QLabel("Instructions"))
        self.instructions = QTextBrowser()
        self.instructions.setAccessibleName("Rendered skill instructions")
        self.instructions.setOpenLinks(False)
        instructions_layout.addWidget(self.instructions)
        splitter.addWidget(instructions)
        layout.addWidget(splitter)
        self.clear()

    def clear(self):
        self.summary.setText("Select a skill to view its details.")
        content = QWidget()
        self.form = QFormLayout(content)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(0)
        self.form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.properties.setWidget(content)
        self.instructions.clear()
        self.property_values = {}
        self.row_count = 0

    def add_property(self, name, value):
        if isinstance(value, dict) and value:
            for key, child in value.items():
                self.add_property(f"{name}.{key}", child)
            return
        if isinstance(value, list) and value:
            for index, child in enumerate(value):
                self.add_property(f"{name}[{index}]", child)
            return
        row = QWidget()
        row.setAutoFillBackground(True)
        row.setBackgroundRole(
            QPalette.ColorRole.AlternateBase
            if self.row_count % 2
            else QPalette.ColorRole.Base
        )
        row_layout = QFormLayout(row)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        row_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        label = QLabel(name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setMinimumWidth(100)
        text = QLabel(str(value))
        text.setTextFormat(Qt.TextFormat.PlainText)
        text.setWordWrap(True)
        text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        text.setAccessibleName(name)
        row_layout.addRow(label, text)
        self.form.addRow(row)
        self.property_values[name] = str(value)
        self.row_count += 1

    def add_section(self, title):
        label = QLabel(title)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        label.setMargin(8)
        self.form.addRow(label)
        self.row_count = 0

    def load_skill(self, skill: Skill):
        path = skill.path / "SKILL.md"
        text = path.read_text(encoding="utf-8-sig")
        _, frontmatter, body = re.split(r"(?m)^---\s*$", text, maxsplit=2)
        metadata = yaml.safe_load(frontmatter)
        files = sorted(file for file in skill.path.rglob("*") if file.is_file())
        sizes = {file: file.stat().st_size for file in files}
        self.clear()
        self.summary.setText(metadata["name"])
        self.add_section("Frontmatter")
        for name, value in metadata.items():
            self.add_property(name, value)
        self.add_section("File details")
        self.add_property("Source folder", skill.path)
        self.add_property("Instructions file", path)
        self.add_property(
            "Modified",
            datetime.fromtimestamp(path.stat().st_mtime)
            .astimezone()
            .isoformat(timespec="seconds"),
        )
        self.add_property("File count", len(files))
        self.add_property("Total bytes", sum(sizes.values()))
        self.add_section("Files")
        for file, size in sizes.items():
            self.add_property(
                file.relative_to(skill.path).as_posix(), f"{size:,} bytes"
            )
        self.instructions.document().setBaseUrl(
            QUrl.fromLocalFile(str(skill.path) + "/")
        )
        self.instructions.setMarkdown(body.strip())
