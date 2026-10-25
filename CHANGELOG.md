# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-25

### Added

- Added the PySide6 desktop app with persistent skill locations, recursive indexing, search, and skill selection.
- Added marketplace export with portable plugin manifests and complete skill folders.
- Added Git publishing and the `uv run agentskills-marketmaker` launcher.
- Added a Windows installer with pinned, SHA-256-verified downloads of Python, Qt, and Git dependencies.
- Added dockable Skill locations, Skill Details, and Share via Git panels.
- Added parsed frontmatter, file properties, and rendered instructions to Skill Details.
- Added a View menu for reopening closed docks and 27 regression tests.

### Changed

- Renamed the Export preview tab to Export.

### Fixed

- Fixed intermittent native Qt crashes during application shutdown.
- Fixed Git publishing omitting exported assets matched by copied `.gitignore` rules.
