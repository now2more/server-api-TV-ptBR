import re

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QTextBrowser
from qfluentwidgets import isDarkTheme, qconfig

from utils.config import resource_path
from utils.i18n import get_language, t


def extract_release_notes(markdown: str, version: str, language: str | None = None) -> str:
"""
[PT-BR]     version = str(version or "").lstrip("vV")

[PT-BR]     if not version:

[PT-BR]         return ""

[PT-BR]     heading = re.escape(version)

[PT-BR]     match = re.search(

[PT-BR]         rf"^##\s+v?{heading}\s*$([\s\S]*?)(?=^##\s+v|\Z)",

[PT-BR]         markdown,

[PT-BR]         re.MULTILINE,

[PT-BR]     )

[PT-BR]     if not match:

[PT-BR]         return ""



[PT-BR]     section = match.group(0).strip()

[PT-BR]     language = language or get_language()

[PT-BR]     english = re.search(r"<details>\s*<summary>English</summary>([\s\S]*?)</details>", section, re.IGNORECASE)

[PT-BR]     if language.startswith("en"):

[PT-BR]         english_content = english.group(1).strip() if english else section

[PT-BR]         content = f"## v{version}\n\n{english_content}" if english else english_content

[PT-BR]     else:

[PT-BR]         content = re.sub(r"<details>[\s\S]*?</details>", "", section, flags=re.IGNORECASE).strip()

[PT-BR]     return content





[PT-BR] class ChangelogDialog(QDialog):

[PT-BR]     def __init__(self, version: str, parent=None):

[PT-BR]         super().__init__(parent)

[PT-BR]         self.version = str(version or "")

[PT-BR]         self.setObjectName("changelogDialog")

[PT-BR]         self.setWindowTitle(t("desktop.changelog_title").format(version=self.version))

[PT-BR]         self.resize(760, 620)



[PT-BR]         self.viewer = QTextBrowser(self)

[PT-BR]         self.viewer.setOpenExternalLinks(True)

[PT-BR]         self.viewer.setMarkdown(self._read_changelog(self.version))



[PT-BR]         self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)

[PT-BR]         self.close_button = self.buttons.button(QDialogButtonBox.StandardButton.Close)

[PT-BR]         self.close_button.setText(t("desktop.close"))

[PT-BR]         self.buttons.rejected.connect(self.reject)



[PT-BR]         layout = QVBoxLayout(self)

[PT-BR]         layout.addWidget(self.viewer)

[PT-BR]         layout.addWidget(self.buttons)

[PT-BR]         qconfig.themeChangedFinished.connect(self._schedule_theme_refresh)

[PT-BR]         self._apply_theme()



[PT-BR]     def _schedule_theme_refresh(self, *_):

[PT-BR]         QTimer.singleShot(0, self._apply_theme)



[PT-BR]     def _apply_theme(self):

[PT-BR]         dark = isDarkTheme()

[PT-BR]         background = "#202020" if dark else "#FFFFFF"

[PT-BR]         surface = "#27272A" if dark else "#F8FAFC"

[PT-BR]         foreground = "#E2E8F0" if dark else "#1F2937"

[PT-BR]         muted = "#CBD5E1" if dark else "#475569"

[PT-BR]         border = "#3F3F46" if dark else "#E2E8F0"

[PT-BR]         hover = "#323232" if dark else "#E2E8F0"



[PT-BR]         palette = self.viewer.palette()

[PT-BR]         palette.setColor(QPalette.ColorRole.Base, QColor(surface))

[PT-BR]         palette.setColor(QPalette.ColorRole.Text, QColor(foreground))

[PT-BR]         palette.setColor(QPalette.ColorRole.Link, QColor("#60A5FA" if dark else "#2563EB"))

[PT-BR]         self.viewer.setPalette(palette)

[PT-BR]         self.setStyleSheet(
"""
            QDialog#changelogDialog {{ background-color: {background}; }}
            QTextBrowser {{
                background-color: {surface}; color: {foreground};
                border: 1px solid {border}; border-radius: 6px; padding: 10px;
            }}
            QDialogButtonBox QPushButton {{
                background-color: {surface}; color: {muted}; border: 1px solid {border};
                border-radius: 5px; padding: 5px 14px; min-width: 72px;
            }}
            QDialogButtonBox QPushButton:hover {{ background-color: {hover}; color: {foreground}; }}
            """
        )

    def retranslate(self):
        self.setWindowTitle(t("desktop.changelog_title").format(version=self.version))
        self.viewer.setMarkdown(self._read_changelog(self.version))
        self.close_button.setText(t("desktop.close"))

    @staticmethod
    def _read_changelog(version):
        path = resource_path("CHANGELOG.md")
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = extract_release_notes(file.read(), version)
                return content or t("desktop.changelog_version_unavailable").format(version=version)
        except OSError:
            return t("desktop.changelog_unavailable")
