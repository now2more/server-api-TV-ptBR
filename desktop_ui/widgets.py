import math
import time

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, QSettings, QTimer, Signal, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QMouseEvent, QPainter, QPalette, QPen, QPixmap, QPolygonF, QRadialGradient
from PySide6.QtWidgets import QDialogButtonBox, QGraphicsDropShadowEffect, QHeaderView, QHBoxLayout, QLabel, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, EditableComboBox, IconWidget, LineEdit, MessageBox, PlainTextEdit, PrimaryPushButton, PushButton, SearchLineEdit, StrongBodyLabel, TableItemDelegate, isDarkTheme, qconfig, setCustomStyleSheet
from utils.i18n import t


def apply_dialog_theme(dialog):
"""
[PT-BR]     dark = isDarkTheme()

[PT-BR]     background = "#202020" if dark else "#FFFFFF"

[PT-BR]     surface = "#27272A" if dark else "#F8FAFC"

[PT-BR]     foreground = "#E2E8F0" if dark else "#1F2937"

[PT-BR]     muted = "#CBD5E1" if dark else "#475569"

[PT-BR]     border = "#3F3F46" if dark else "#E2E8F0"

[PT-BR]     hover = "#323232" if dark else "#E2E8F0"

[PT-BR]     dialog.setStyleSheet(
"""
        QDialog {{ background-color: {background}; color: {foreground}; }}
        QLabel {{ color: {foreground}; }}
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
            background-color: {surface}; color: {foreground}; border: 1px solid {border};
            border-radius: 5px; padding: 4px 6px;
        }}
        QDialogButtonBox QPushButton {{
            background-color: {surface}; color: {muted}; border: 1px solid {border};
            border-radius: 5px; padding: 5px 14px; min-width: 72px;
        }}
        QDialogButtonBox QPushButton:hover {{ background-color: {hover}; color: {foreground}; }}
        """
    )


def localize_dialog_buttons(buttons):
"""
[PT-BR]     labels = {

[PT-BR]         QDialogButtonBox.StandardButton.Save: "desktop.save",

[PT-BR]         QDialogButtonBox.StandardButton.Cancel: "desktop.cancel",

[PT-BR]         QDialogButtonBox.StandardButton.Close: "desktop.close",

[PT-BR]         QDialogButtonBox.StandardButton.Ok: "desktop.confirm",

[PT-BR]         QDialogButtonBox.StandardButton.Yes: "desktop.yes",

[PT-BR]         QDialogButtonBox.StandardButton.No: "desktop.no",

[PT-BR]     }

[PT-BR]     for standard, key in labels.items():

[PT-BR]         try:

[PT-BR]             button = buttons.button(standard)

[PT-BR]         except TypeError:

[PT-BR]             button = buttons.button(type(buttons).StandardButton(standard.value))

[PT-BR]         if button:

[PT-BR]             button.setText(t(key))





[PT-BR] def apply_input_border_style(widget, selector):

[PT-BR]     states = ",\n".join([

[PT-BR]         selector,

[PT-BR]         f"{selector}:hover",

[PT-BR]         f"{selector}:focus",

[PT-BR]         f"{selector}[transparent=true]:focus",

[PT-BR]         f"{selector}[transparent=false]:focus",

[PT-BR]         f"{selector}:disabled",

[PT-BR]     ])

[PT-BR]     light = f"{states} {{ border-bottom-color: rgba(0, 0, 0, 13); }}"

[PT-BR]     dark = f"{states} {{ border-bottom-color: rgba(255, 255, 255, 0.08); }}"

[PT-BR]     setCustomStyleSheet(widget, light, dark)





[PT-BR] def _table_check_state(state):

[PT-BR]     if isinstance(state, Qt.CheckState):

[PT-BR]         return state

[PT-BR]     if isinstance(state, bool):

[PT-BR]         return Qt.CheckState.Checked if state else Qt.CheckState.Unchecked

[PT-BR]     try:

[PT-BR]         return Qt.CheckState(int(state))

[PT-BR]     except (TypeError, ValueError):

[PT-BR]         return Qt.CheckState.Unchecked





[PT-BR] def paint_table_checkbox(painter, rect, state):

[PT-BR]     state = _table_check_state(state)

[PT-BR]     size = min(16, rect.width(), rect.height())

[PT-BR]     box = QRect(rect.center().x() - size // 2, rect.center().y() - size // 2, size, size)

[PT-BR]     checked = state in (Qt.CheckState.Checked, Qt.CheckState.PartiallyChecked)

[PT-BR]     border = QColor("#60A5FA" if isDarkTheme() else "#2563EB") if checked else QColor(

[PT-BR]         "#94A3B8" if isDarkTheme() else "#64748B"

[PT-BR]     )

[PT-BR]     painter.save()

[PT-BR]     painter.setRenderHint(QPainter.RenderHint.Antialiasing)

[PT-BR]     painter.setPen(QPen(border, 1.6))

[PT-BR]     painter.setBrush(QBrush(border if checked else Qt.BrushStyle.NoBrush))

[PT-BR]     painter.drawRoundedRect(box.adjusted(1, 1, -1, -1), 3, 3)

[PT-BR]     painter.setPen(QPen(

[PT-BR]         QColor("#FFFFFF"),

[PT-BR]         1.8,

[PT-BR]         Qt.PenStyle.SolidLine,

[PT-BR]         Qt.PenCapStyle.RoundCap,

[PT-BR]         Qt.PenJoinStyle.RoundJoin,

[PT-BR]     ))

[PT-BR]     if state == Qt.CheckState.Checked:

[PT-BR]         painter.drawLine(box.left() + 4, box.center().y(), box.left() + 7, box.bottom() - 4)

[PT-BR]         painter.drawLine(box.left() + 7, box.bottom() - 4, box.right() - 3, box.top() + 4)

[PT-BR]     elif state == Qt.CheckState.PartiallyChecked:

[PT-BR]         painter.drawLine(box.left() + 4, box.center().y(), box.right() - 4, box.center().y())

[PT-BR]     painter.restore()





[PT-BR] class ContinuousTreeItemDelegate(QStyledItemDelegate):
"""

    def paint(self, painter, option, index):
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            if selected:
                if isDarkTheme():
                    color = QColor("#1D4ED8")
                    color.setAlpha(175)
                else:
                    color = QColor("#BFDBFE")
                    color.setAlpha(230)
            else:
                color = QColor(255, 255, 255, 12) if isDarkTheme() else QColor(15, 23, 42, 10)
            painter.setBrush(color)
            self._draw_row_segment(painter, option, index)
            painter.restore()

        clean_option = QStyleOptionViewItem(option)
        clean_option.state &= ~(QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver)
        if selected:
            text_color = QColor("#F8FAFC" if isDarkTheme() else "#1E3A8A")
        else:
            text_color = QColor("#E2E8F0" if isDarkTheme() else "#1F2937")
        clean_option.palette.setColor(QPalette.ColorRole.Text, text_color)
        super().paint(painter, clean_option, index)

    def _draw_row_segment(self, painter, option, index):
        view = self.parent()
        if index.column() != 0:
            return
        rect = view.viewport().rect()
        rect.setTop(option.rect.top() + 2)
        rect.setBottom(option.rect.bottom() - 2)
        rect.adjust(2, 0, -2, 0)
        painter.drawRoundedRect(rect, 4.0, 4.0)


class TableCheckBoxHeader(QHeaderView):
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._state = Qt.CheckState.Unchecked
        self._resizing = False
        self.setSectionsClickable(True)
        self.setSortIndicatorShown(True)

    def set_check_state(self, state):
        if state != self._state:
            self._state = state
            self.viewport().update()

    def paintSection(self, painter, rect, logical_index):
        super().paintSection(painter, rect, logical_index)
        if logical_index == 0:
            paint_table_checkbox(painter, rect, self._state)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._resizing:
            self._resizing = False
            super().mouseReleaseEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton and self.logicalIndexAt(event.position().toPoint()) == 0:
            self.toggled.emit(self._state != Qt.CheckState.Checked)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.logicalIndexAt(event.position().toPoint()) == 0:
            boundary = self.sectionViewportPosition(0) + self.sectionSize(0)
            if abs(event.position().x() - boundary) <= 6:
                self._resizing = True
                super().mousePressEvent(event)
                return
            event.accept()
            return
        super().mousePressEvent(event)


def warning_message_box(title: str, content: str, parent=None):
    box = MessageBox(title, content, parent)
    warning_icon = box.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
    box.setWindowIcon(warning_icon)
    title_label = box.findChild(QLabel, "titleLabel")
    if title_label and title_label.parentWidget() and title_label.parentWidget().layout():
        title_layout = title_label.parentWidget().layout()
        title_layout.removeWidget(title_label)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        icon_label = QLabel(title_label.parentWidget())
        icon_label.setObjectName("warningIcon")
        icon_label.setFixedSize(22, 22)
        icon_label.setPixmap(warning_icon.pixmap(20, 20))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setToolTip(title)
        title_row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(title_label, 1, Qt.AlignmentFlag.AlignVCenter)
        title_layout.insertLayout(0, title_row)
    return box


class TableCheckBoxDelegate(TableItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.text = ""
        option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator

    def paint(self, painter, option, index):
        primary_delegate = getattr(self.parent(), "delegate", None)
        if primary_delegate is None:
            QStyledItemDelegate.paint(self, painter, option, index)
            paint_table_checkbox(
                painter,
                option.rect,
                index.data(Qt.ItemDataRole.CheckStateRole),
            )
            return
        self.hoverRow = primary_delegate.hoverRow
        self.pressedRow = primary_delegate.pressedRow
        self.selectedRows = primary_delegate.selectedRows
        super().paint(painter, option, index)

    def _drawCheckBox(self, painter, option, index):
        paint_table_checkbox(
            painter,
            option.rect,
            index.data(Qt.ItemDataRole.CheckStateRole),
        )

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if option.rect.contains(event.position().toPoint()):
                checked = (
                    _table_check_state(index.data(Qt.ItemDataRole.CheckStateRole))
                    == Qt.CheckState.Checked
                )
                return model.setData(
                    index,
                    Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked,
                    Qt.ItemDataRole.CheckStateRole,
                )
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Select):
            checked = (
                _table_check_state(index.data(Qt.ItemDataRole.CheckStateRole))
                == Qt.CheckState.Checked
            )
            return model.setData(
                index,
                Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked,
                Qt.ItemDataRole.CheckStateRole,
            )
        return False


class _AdaptiveTableColumns(QObject):
"""


[PT-BR]     layout_fitted = Signal()



[PT-BR]     def __init__(self, table, widths: list[int], state_key: str, fixed_widths=None, minimum_widths=None):

[PT-BR]         super().__init__(table)

[PT-BR]         self.table = table

[PT-BR]         self.viewport = table.viewport()

[PT-BR]         self.header = table.horizontalHeader()

[PT-BR]         self.state_key = state_key

[PT-BR]         self.fixed_widths = dict(fixed_widths or {})

[PT-BR]         self.minimum_widths = {

[PT-BR]             column: max(1, int(width))

[PT-BR]             for column, width in (minimum_widths or {}).items()

[PT-BR]         }

[PT-BR]         self._applying = False

[PT-BR]         self._weights = self._load_weights(widths)

[PT-BR]         self._save_timer = QTimer(self)

[PT-BR]         self._save_timer.setSingleShot(True)

[PT-BR]         self._save_timer.setInterval(250)

[PT-BR]         self._save_timer.timeout.connect(self._save)

[PT-BR]         self._fit_timer = QTimer(self)

[PT-BR]         self._fit_timer.setSingleShot(True)

[PT-BR]         self._fit_timer.timeout.connect(self.fit)



[PT-BR]         self.viewport.installEventFilter(self)

[PT-BR]         self.header.sectionMoved.connect(self._schedule_save)

[PT-BR]         self.header.sectionResized.connect(self._section_resized)

[PT-BR]         QTimer.singleShot(0, self.fit)



[PT-BR]     def _load_weights(self, widths: list[int]) -> list[float]:

[PT-BR]         count = self.header.count()

[PT-BR]         defaults = [float(width) for width in widths[:count]]

[PT-BR]         if len(defaults) < count:

[PT-BR]             defaults.extend([100.0] * (count - len(defaults)))



[PT-BR]         settings = QSettings()

[PT-BR]         saved_state = settings.value(f"appearance/table_headers/{self.state_key}")

[PT-BR]         if saved_state is not None:

[PT-BR]             self.header.restoreState(saved_state)

[PT-BR]         else:

[PT-BR]             for column, width in enumerate(defaults):

[PT-BR]                 self.header.resizeSection(column, int(width))



[PT-BR]         saved_weights = settings.value(f"appearance/table_column_weights/{self.state_key}")

[PT-BR]         if isinstance(saved_weights, (list, tuple)) and len(saved_weights) == count:

[PT-BR]             try:

[PT-BR]                 parsed = [max(1.0, float(value)) for value in saved_weights]

[PT-BR]                 if all(value > 0 for value in parsed):

[PT-BR]                     return parsed

[PT-BR]             except (TypeError, ValueError):

[PT-BR]                 pass

[PT-BR]         if saved_state is not None:

[PT-BR]             return [float(max(1, self.header.sectionSize(column))) for column in range(count)]

[PT-BR]         return defaults



[PT-BR]     def eventFilter(self, watched, event):

[PT-BR]         if watched is self.viewport and event.type() in {

[PT-BR]             QEvent.Type.Resize,

[PT-BR]             QEvent.Type.Show,

[PT-BR]         }:

[PT-BR]             self._fit_timer.start(0)

[PT-BR]         return super().eventFilter(watched, event)



[PT-BR]     def fit(self):

[PT-BR]         visible = [

[PT-BR]             column

[PT-BR]             for column in range(self.header.count())

[PT-BR]             if not self.header.isSectionHidden(column)

[PT-BR]         ]

[PT-BR]         available = self.viewport.width()

[PT-BR]         if not visible or available <= 0:

[PT-BR]             return



[PT-BR]         minimum = self.header.minimumSectionSize()

[PT-BR]         minimums = {

[PT-BR]             column: max(minimum, self.minimum_widths.get(column, minimum))

[PT-BR]             for column in visible

[PT-BR]         }

[PT-BR]         fixed = {

[PT-BR]             column: width

[PT-BR]             for column, width in self.fixed_widths.items()

[PT-BR]             if column in visible

[PT-BR]         }

[PT-BR]         sizes = dict(fixed)

[PT-BR]         pending = [column for column in visible if column not in fixed]

[PT-BR]         remaining = available - sum(fixed.values())

[PT-BR]         minimum_total = sum(minimums[column] for column in pending)

[PT-BR]         for column in pending:

[PT-BR]             sizes[column] = minimums[column]



[PT-BR]         # Keep important columns readable even when the viewport is too narrow.

[PT-BR]         # The table can then scroll horizontally instead of eliding their data.

[PT-BR]         if remaining > minimum_total and pending:

[PT-BR]             extra = remaining - minimum_total

[PT-BR]             weight_total = sum(self._weights[column] for column in pending)

[PT-BR]             for position, column in enumerate(pending):

[PT-BR]                 if position == len(pending) - 1:

[PT-BR]                     sizes[column] += extra

[PT-BR]                 else:

[PT-BR]                     share = round(extra * self._weights[column] / weight_total)

[PT-BR]                     sizes[column] += share

[PT-BR]                     extra -= share

[PT-BR]                     weight_total -= self._weights[column]



[PT-BR]         self._applying = True

[PT-BR]         self.header.blockSignals(True)

[PT-BR]         try:

[PT-BR]             for column in visible:

[PT-BR]                 self.header.resizeSection(column, sizes[column])

[PT-BR]         finally:

[PT-BR]             self.header.blockSignals(False)

[PT-BR]             self._applying = False

[PT-BR]         # Blocking section signals keeps an adaptive resize from being treated

[PT-BR]         # as a user resize, but it also prevents persistent cell editors from

[PT-BR]         # receiving updated geometry. Re-layout the view after the final column

[PT-BR]         # sizes are applied so hidden pages restore with correctly placed

[PT-BR]         # editors.

[PT-BR]         self.table.doItemsLayout()

[PT-BR]         self.layout_fitted.emit()



[PT-BR]     def _section_resized(self, *_):

[PT-BR]         if self._applying:

[PT-BR]             return

[PT-BR]         self._weights = [

[PT-BR]             float(max(1, self.header.sectionSize(column)))

[PT-BR]             for column in range(self.header.count())

[PT-BR]         ]

[PT-BR]         self._fit_timer.start(150)

[PT-BR]         self._schedule_save()



[PT-BR]     def _schedule_save(self, *_):

[PT-BR]         self._save_timer.start()



[PT-BR]     def _save(self):

[PT-BR]         settings = QSettings()

[PT-BR]         settings.setValue(

[PT-BR]             f"appearance/table_headers/{self.state_key}",

[PT-BR]             self.header.saveState(),

[PT-BR]         )

[PT-BR]         settings.setValue(

[PT-BR]             f"appearance/table_column_weights/{self.state_key}",

[PT-BR]             self._weights,

[PT-BR]         )





[PT-BR] def configure_table_columns(table, widths: list[int], state_key: str, fixed_widths=None, minimum_widths=None):

[PT-BR]     header = table.horizontalHeader()

[PT-BR]     header.setCascadingSectionResizes(False)

[PT-BR]     header.setMinimumSectionSize(40)

[PT-BR]     header.setStretchLastSection(False)

[PT-BR]     header.setSectionsMovable(True)

[PT-BR]     header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

[PT-BR]     for column, width in (fixed_widths or {}).items():

[PT-BR]         header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)

[PT-BR]         header.resizeSection(column, width)

[PT-BR]     existing = getattr(header, "_adaptive_columns", None)

[PT-BR]     if (

[PT-BR]         existing is not None

[PT-BR]         and existing.state_key == state_key

[PT-BR]         and existing.fixed_widths == dict(fixed_widths or {})

[PT-BR]         and existing.minimum_widths == {

[PT-BR]             column: max(1, int(width))

[PT-BR]             for column, width in (minimum_widths or {}).items()

[PT-BR]         }

[PT-BR]     ):

[PT-BR]         header.setSectionsClickable(True)

[PT-BR]         header.setSortIndicatorShown(True)

[PT-BR]         return

[PT-BR]     header._adaptive_columns = _AdaptiveTableColumns(

[PT-BR]         table,

[PT-BR]         widths,

[PT-BR]         state_key,

[PT-BR]         fixed_widths=fixed_widths,

[PT-BR]         minimum_widths=minimum_widths,

[PT-BR]     )

[PT-BR]     header.setSectionsClickable(True)

[PT-BR]     header.setSortIndicatorShown(True)





[PT-BR] class AppLineEdit(LineEdit):

[PT-BR]     def __init__(self, parent=None):

[PT-BR]         super().__init__(parent)

[PT-BR]         apply_input_border_style(self, "LineEdit")





[PT-BR] class AppSearchLineEdit(SearchLineEdit):

[PT-BR]     def __init__(self, parent=None):

[PT-BR]         super().__init__(parent)

[PT-BR]         apply_input_border_style(self, "LineEdit")





[PT-BR] class AppEditableComboBox(EditableComboBox):

[PT-BR]     def __init__(self, parent=None):

[PT-BR]         super().__init__(parent)

[PT-BR]         apply_input_border_style(self, "LineEdit")





[PT-BR] class AppPlainTextEdit(PlainTextEdit):

[PT-BR]     def __init__(self, parent=None):

[PT-BR]         super().__init__(parent)

[PT-BR]         apply_input_border_style(self, "PlainTextEdit")





[PT-BR] class AccentPushButton(PrimaryPushButton):

[PT-BR]     def _postInit(self):

[PT-BR]         super()._postInit()

[PT-BR]         qconfig.themeChangedFinished.connect(self._apply_semantic_style)

[PT-BR]         self._apply_semantic_style()



[PT-BR]     def _apply_semantic_style(self, *_):

[PT-BR]         self.setStyleSheet(

[PT-BR]             "QPushButton { color: #FFFFFF; background-color: #2563EB; border: none; border-radius: 6px; padding: 6px 13px; }"

[PT-BR]             "QPushButton[hasIcon=true] { padding-left: 31px; }"

[PT-BR]             "QPushButton:hover { background-color: #1D4ED8; }"

[PT-BR]             "QPushButton:pressed { background-color: #1E40AF; }"

[PT-BR]             "QPushButton:disabled { color: #CBD5E1; background-color: #64748B; }"

[PT-BR]         )



[PT-BR]     def setIcon(self, icon):

[PT-BR]         super().setIcon(icon.icon(color=QColor("#FFFFFF")) if hasattr(icon, "icon") else icon)





[PT-BR] class DangerPushButton(PushButton):

[PT-BR]     def _postInit(self):

[PT-BR]         super()._postInit()

[PT-BR]         qconfig.themeChangedFinished.connect(self._apply_semantic_style)

[PT-BR]         self._apply_semantic_style()



[PT-BR]     def _apply_semantic_style(self, *_):

[PT-BR]         color = "#F87171" if isDarkTheme() else "#DC2626"

[PT-BR]         border = "#EF4444" if isDarkTheme() else "#FCA5A5"

[PT-BR]         hover = "rgba(248, 113, 113, 28)" if isDarkTheme() else "rgba(220, 38, 38, 18)"

[PT-BR]         pressed = "rgba(248, 113, 113, 48)" if isDarkTheme() else "rgba(220, 38, 38, 34)"

[PT-BR]         self.setStyleSheet(

[PT-BR]             f"QPushButton {{ color: {color}; background-color: transparent; border: 1px solid {border}; border-radius: 6px; padding: 5px 12px; }}"

[PT-BR]             "QPushButton[hasIcon=true] { padding-left: 31px; }"

[PT-BR]             f"QPushButton:hover {{ background-color: {hover}; }}"

[PT-BR]             f"QPushButton:pressed {{ background-color: {pressed}; }}"

[PT-BR]             "QPushButton:disabled { color: #94A3B8; border-color: #64748B; background-color: transparent; }"

[PT-BR]         )

[PT-BR]         if hasattr(self, "_semantic_icon"):

[PT-BR]             icon = self._semantic_icon

[PT-BR]             PushButton.setIcon(self, icon.icon(color=QColor(color)) if hasattr(icon, "icon") else icon)



[PT-BR]     def setIcon(self, icon):

[PT-BR]         self._semantic_icon = icon

[PT-BR]         color = QColor("#F87171" if isDarkTheme() else "#DC2626")

[PT-BR]         super().setIcon(icon.icon(color=color) if hasattr(icon, "icon") else icon)





[PT-BR] def play_circle_icon(color="#FFFFFF"):

[PT-BR]     pixmap = QPixmap(32, 32)

[PT-BR]     pixmap.fill(Qt.GlobalColor.transparent)

[PT-BR]     painter = QPainter(pixmap)

[PT-BR]     painter.setRenderHint(QPainter.RenderHint.Antialiasing)

[PT-BR]     painter.setPen(QPen(QColor(color), 2.1))

[PT-BR]     painter.drawEllipse(3.5, 3.5, 25, 25)

[PT-BR]     painter.setPen(Qt.PenStyle.NoPen)

[PT-BR]     painter.setBrush(QColor(color))

[PT-BR]     painter.drawPolygon(QPolygonF([QPointF(13, 10), QPointF(13, 22), QPointF(23, 16)]))

[PT-BR]     painter.end()

[PT-BR]     return QIcon(pixmap)





[PT-BR] class MetricIconWidget(QWidget):
"""

    def __init__(self, icon=None, parent=None):
        super().__init__(parent)
        self._icon = icon or QIcon()
        self._angle = 0.0

    def setIcon(self, icon):
        self._icon = icon or QIcon()
        self.update()

    def set_angle(self, angle: float):
        self._angle = angle
        self.update()

    def paintEvent(self, _event):
        if self._icon.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        size = min(self.width(), self.height())
        self._icon.paint(painter, QRect(-size // 2, -size // 2, size, size))


class GlassCard(CardWidget):
"""


[PT-BR]     def __init__(self, parent=None, accent="#2563EB"):

[PT-BR]         super().__init__(parent)

[PT-BR]         self._accent = QColor(accent)

[PT-BR]         self._pulse_until = 0.0

[PT-BR]         self._pulse_timer = QTimer(self)

[PT-BR]         self._pulse_timer.setInterval(33)

[PT-BR]         self._pulse_timer.timeout.connect(self._advance_pulse)

[PT-BR]         self.setBorderRadius(12)

[PT-BR]         self._shadow = QGraphicsDropShadowEffect(self)

[PT-BR]         self._shadow.setBlurRadius(18)

[PT-BR]         self._shadow.setOffset(0, 3)

[PT-BR]         self.setGraphicsEffect(self._shadow)

[PT-BR]         qconfig.themeChangedFinished.connect(self._apply_surface_style)

[PT-BR]         self._apply_surface_style()



[PT-BR]     def set_accent(self, accent: str):

[PT-BR]         self._accent = QColor(accent)

[PT-BR]         self.update()



[PT-BR]     def pulse(self, duration_ms: int = 360):

[PT-BR]         self._pulse_until = max(self._pulse_until, time.monotonic() + duration_ms / 1000)

[PT-BR]         if not self._pulse_timer.isActive():

[PT-BR]             self._pulse_timer.start()

[PT-BR]         self.update()



[PT-BR]     def _advance_pulse(self):

[PT-BR]         if time.monotonic() >= self._pulse_until:

[PT-BR]             self._pulse_timer.stop()

[PT-BR]         self.update()



[PT-BR]     def _apply_surface_style(self, *_):

[PT-BR]         shadow = QColor("#000000")

[PT-BR]         shadow.setAlpha(70 if isDarkTheme() else 24)

[PT-BR]         self._shadow.setColor(shadow)



[PT-BR]     def paintEvent(self, _event):

[PT-BR]         now = time.monotonic()

[PT-BR]         pulse = 0.0

[PT-BR]         if now < self._pulse_until:

[PT-BR]             remaining = (self._pulse_until - now) / 0.36

[PT-BR]             pulse = math.sin(max(0.0, min(1.0, remaining)) * math.pi)

[PT-BR]         painter = QPainter(self)

[PT-BR]         painter.setRenderHint(QPainter.RenderHint.Antialiasing)

[PT-BR]         rect = self.rect().adjusted(1, 1, -1, -1)

[PT-BR]         radius = 12.0

[PT-BR]         accent = QColor(self._accent)

[PT-BR]         glass = QLinearGradient(0, rect.top(), 0, rect.bottom())

[PT-BR]         if isDarkTheme():

[PT-BR]             glass.setColorAt(0, QColor(39, 51, 70, 198 if self.isHover else 186))

[PT-BR]             glass.setColorAt(1, QColor(22, 30, 45, 178 if self.isHover else 164))

[PT-BR]             highlight = QColor(255, 255, 255, 42)

[PT-BR]             border = QColor(255, 255, 255, 38)

[PT-BR]         else:

[PT-BR]             glass.setColorAt(0, QColor(255, 255, 255, 222 if self.isHover else 208))

[PT-BR]             glass.setColorAt(1, QColor(241, 245, 249, 200 if self.isHover else 184))

[PT-BR]             highlight = QColor(255, 255, 255, 178)

[PT-BR]             border = QColor(148, 163, 184, 48)

[PT-BR]         painter.setPen(Qt.PenStyle.NoPen)

[PT-BR]         painter.setBrush(glass)

[PT-BR]         painter.drawRoundedRect(rect, radius, radius)

[PT-BR]         radial = QRadialGradient(rect.right() - 12, rect.top() + 10, max(48, rect.width() * 0.36))

[PT-BR]         tint = QColor(accent)

[PT-BR]         tint.setAlpha(int((24 if isDarkTheme() else 14) + pulse * 24))

[PT-BR]         radial.setColorAt(0, tint)

[PT-BR]         radial.setColorAt(1, QColor(accent.red(), accent.green(), accent.blue(), 0))

[PT-BR]         painter.setBrush(radial)

[PT-BR]         painter.drawRoundedRect(rect, radius, radius)

[PT-BR]         painter.setBrush(Qt.BrushStyle.NoBrush)

[PT-BR]         painter.setPen(QPen(highlight, 1.0))

[PT-BR]         painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)

[PT-BR]         if pulse:

[PT-BR]             border = QColor(accent)

[PT-BR]             border.setAlpha(int(42 + pulse * 126))

[PT-BR]         painter.setPen(QPen(border, 1.0))

[PT-BR]         painter.drawRoundedRect(rect, radius, radius)





[PT-BR] class MetricCard(CardWidget):

[PT-BR]     def __init__(

[PT-BR]         self,

[PT-BR]         title: str,

[PT-BR]         value: str = "--",

[PT-BR]         detail: str = "",

[PT-BR]         icon=None,

[PT-BR]         parent=None,

[PT-BR]         accent="#0E5CAD",

[PT-BR]         animate_value_updates: bool = False,

[PT-BR]     ):

[PT-BR]         super().__init__(parent)

[PT-BR]         self._accent = QColor(accent)

[PT-BR]         self._animate_value_updates = animate_value_updates

[PT-BR]         self._activity = False

[PT-BR]         self._rotate_icon = False

[PT-BR]         self._activity_delay = 0.0

[PT-BR]         self._activity_started_at = 0.0

[PT-BR]         self._pulse_until = 0.0

[PT-BR]         self._animation_timer = QTimer(self)

[PT-BR]         self._animation_timer.setInterval(33)  # 30 fps is ample for small dashboard accents.

[PT-BR]         self._animation_timer.timeout.connect(self._advance_animation)

[PT-BR]         self.setMinimumHeight(104)

[PT-BR]         self.setBorderRadius(12)

[PT-BR]         self._shadow = QGraphicsDropShadowEffect(self)

[PT-BR]         self._shadow.setBlurRadius(18)

[PT-BR]         self._shadow.setOffset(0, 3)

[PT-BR]         self.setGraphicsEffect(self._shadow)

[PT-BR]         root = QHBoxLayout(self)

[PT-BR]         root.setContentsMargins(18, 14, 18, 14)

[PT-BR]         root.setSpacing(14)

[PT-BR]         self.icon_container = QWidget(self) if icon else None

[PT-BR]         self.icon_widget = MetricIconWidget(icon.icon(color=QColor(accent)) if hasattr(icon, "icon") else icon, self.icon_container) if icon else None

[PT-BR]         if self.icon_widget:

[PT-BR]             self.icon_container.setFixedSize(42, 42)

[PT-BR]             color = QColor(accent)

[PT-BR]             self.icon_container.setStyleSheet(

[PT-BR]                 f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 38); border-radius: 10px;"

[PT-BR]             )

[PT-BR]             icon_layout = QHBoxLayout(self.icon_container)

[PT-BR]             icon_layout.setContentsMargins(9, 9, 9, 9)

[PT-BR]             self.icon_widget.setFixedSize(24, 24)

[PT-BR]             icon_layout.addWidget(self.icon_widget)

[PT-BR]             root.addWidget(self.icon_container, 0, Qt.AlignmentFlag.AlignTop)

[PT-BR]         layout = QVBoxLayout()

[PT-BR]         layout.setContentsMargins(0, 0, 0, 0)

[PT-BR]         layout.setSpacing(4)

[PT-BR]         self.title_label = BodyLabel(title, self)

[PT-BR]         self.value_label = StrongBodyLabel(value, self)

[PT-BR]         font = self.value_label.font()

[PT-BR]         font.setPointSize(20)

[PT-BR]         font.setBold(True)

[PT-BR]         self.value_label.setFont(font)

[PT-BR]         self.detail_label = BodyLabel(detail, self)

[PT-BR]         layout.addWidget(self.title_label)

[PT-BR]         layout.addWidget(self.value_label)

[PT-BR]         layout.addWidget(self.detail_label)

[PT-BR]         root.addLayout(layout, 1)

[PT-BR]         qconfig.themeChangedFinished.connect(self._apply_text_colors)

[PT-BR]         qconfig.themeChangedFinished.connect(self._apply_surface_style)

[PT-BR]         self._apply_text_colors()

[PT-BR]         self._apply_surface_style()



[PT-BR]     def _apply_text_colors(self, *_):

[PT-BR]         dark = isDarkTheme()

[PT-BR]         title = "#CBD5E1" if dark else "#475569"

[PT-BR]         detail = "#94A3B8" if dark else "#64748B"

[PT-BR]         value = self._accent.lighter(135).name() if dark else self._accent.name()

[PT-BR]         self.title_label.setStyleSheet(f"color: {title};")

[PT-BR]         self.value_label.setStyleSheet(f"color: {value};")

[PT-BR]         self.detail_label.setStyleSheet(f"color: {detail};")



[PT-BR]     def _apply_surface_style(self, *_):

[PT-BR]         shadow = QColor("#000000")

[PT-BR]         shadow.setAlpha(70 if isDarkTheme() else 24)

[PT-BR]         self._shadow.setColor(shadow)



[PT-BR]     def set_clickable(self, clickable: bool = True):

[PT-BR]         self.setClickEnabled(clickable)

[PT-BR]         self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)



[PT-BR]     def set_value(self, value, detail: str | None = None):

[PT-BR]         changed = self.value_label.text() != str(value)

[PT-BR]         self.value_label.setText(str(value))

[PT-BR]         if detail is not None:

[PT-BR]             self.detail_label.setText(detail)

[PT-BR]         if changed and self._activity and self._animate_value_updates:

[PT-BR]             self.pulse()



[PT-BR]     def set_activity(self, active: bool, *, delay_ms: int = 0, rotate_icon: bool = False):
"""
        self._activity = active
        self._rotate_icon = active and rotate_icon
        self._activity_delay = delay_ms / 1000
        if active:
            self._activity_started_at = time.monotonic()
            if not self._animation_timer.isActive():
                self._animation_timer.start()
        elif time.monotonic() >= self._pulse_until:
            self._animation_timer.stop()
        self.update()

    def pulse(self, duration_ms: int = 360):
"""
[PT-BR]         self._pulse_until = max(self._pulse_until, time.monotonic() + duration_ms / 1000)

[PT-BR]         if not self._animation_timer.isActive():

[PT-BR]             self._animation_timer.start()



[PT-BR]     def _advance_animation(self):

[PT-BR]         now = time.monotonic()

[PT-BR]         self._advance_icon_rotation()

[PT-BR]         if not self._activity and now >= self._pulse_until:

[PT-BR]             self._animation_timer.stop()

[PT-BR]         self.update()



[PT-BR]     def paintEvent(self, event):

[PT-BR]         now = time.monotonic()

[PT-BR]         elapsed = now - self._activity_started_at - self._activity_delay

[PT-BR]         phase = max(0.0, elapsed) / 2.8

[PT-BR]         pulse = 0.0

[PT-BR]         if now < self._pulse_until:

[PT-BR]             remaining = (self._pulse_until - now) / 0.36

[PT-BR]             pulse = math.sin(max(0.0, min(1.0, remaining)) * math.pi)

[PT-BR]         painter = QPainter(self)

[PT-BR]         painter.setRenderHint(QPainter.RenderHint.Antialiasing)

[PT-BR]         radius = 12.0

[PT-BR]         rect = self.rect().adjusted(1, 1, -1, -1)

[PT-BR]         accent = QColor(self._accent)



[PT-BR]         # A translucent two-layer surface reads as glass while keeping the

[PT-BR]         # rendering path cheap and identical on every supported platform.

[PT-BR]         glass = QLinearGradient(0, rect.top(), 0, rect.bottom())

[PT-BR]         if isDarkTheme():

[PT-BR]             glass.setColorAt(0, QColor(39, 51, 70, 204 if self.isHover else 190))

[PT-BR]             glass.setColorAt(1, QColor(22, 30, 45, 184 if self.isHover else 170))

[PT-BR]             highlight = QColor(255, 255, 255, 42)

[PT-BR]             border_base = QColor(255, 255, 255, 38)

[PT-BR]         else:

[PT-BR]             glass.setColorAt(0, QColor(255, 255, 255, 224 if self.isHover else 210))

[PT-BR]             glass.setColorAt(1, QColor(241, 245, 249, 202 if self.isHover else 186))

[PT-BR]             highlight = QColor(255, 255, 255, 178)

[PT-BR]             border_base = QColor(148, 163, 184, 48)

[PT-BR]         painter.setPen(Qt.PenStyle.NoPen)

[PT-BR]         painter.setBrush(glass)

[PT-BR]         painter.drawRoundedRect(rect, radius, radius)



[PT-BR]         radial = QRadialGradient(rect.right() - 12, rect.top() + 10, max(48, rect.width() * 0.36))

[PT-BR]         tint = QColor(accent)

[PT-BR]         tint.setAlpha(24 if isDarkTheme() else 14)

[PT-BR]         tint.setAlpha(int(tint.alpha() + pulse * 20))

[PT-BR]         radial.setColorAt(0, tint)

[PT-BR]         radial.setColorAt(1, QColor(accent.red(), accent.green(), accent.blue(), 0))

[PT-BR]         painter.setBrush(radial)

[PT-BR]         painter.drawRoundedRect(rect, radius, radius)



[PT-BR]         # An inner top highlight makes the material feel layered rather than flat.

[PT-BR]         painter.setBrush(Qt.BrushStyle.NoBrush)

[PT-BR]         painter.setPen(QPen(highlight, 1.0))

[PT-BR]         painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)

[PT-BR]         if self._activity:

[PT-BR]             # A very low-opacity travelling wash gives activity context without obscuring text.

[PT-BR]             width = max(1, rect.width())

[PT-BR]             offset = (phase % 1.0) * width * 1.8 - width * 0.8

[PT-BR]             glow = QLinearGradient(offset, 0, offset + width * 0.7, 0)

[PT-BR]             transparent = QColor(accent)

[PT-BR]             transparent.setAlpha(0)

[PT-BR]             highlight = QColor(accent)

[PT-BR]             highlight.setAlpha(16 if not isDarkTheme() else 24)

[PT-BR]             glow.setColorAt(0, transparent)

[PT-BR]             glow.setColorAt(0.5, highlight)

[PT-BR]             glow.setColorAt(1, transparent)

[PT-BR]             painter.setPen(Qt.PenStyle.NoPen)

[PT-BR]             painter.setBrush(glow)

[PT-BR]             painter.drawRoundedRect(rect, radius, radius)

[PT-BR]         border = QColor(accent)

[PT-BR]         border.setAlpha(int(28 + pulse * 105 + (math.sin(phase * math.tau) + 1) * 8 if self._activity else 32 + pulse * 120))

[PT-BR]         if not self._activity and pulse == 0:

[PT-BR]             border = border_base

[PT-BR]         painter.setBrush(Qt.BrushStyle.NoBrush)

[PT-BR]         painter.setPen(QPen(border, 1.0))

[PT-BR]         painter.drawRoundedRect(rect, radius, radius)



[PT-BR]     def set_visual(self, icon=None, accent=None):
"""
        if accent is not None:
            self._accent = QColor(accent)
        if self.icon_widget and icon is not None:
            rendered_icon = icon.icon(color=self._accent) if hasattr(icon, "icon") else icon
            self.icon_widget.setIcon(rendered_icon)
        if self.icon_container:
            color = self._accent
            self.icon_container.setStyleSheet(
                f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 38); border-radius: 10px;"
            )
        self._apply_text_colors()

    def _advance_icon_rotation(self):
        if self.icon_widget:
            elapsed = max(0.0, time.monotonic() - self._activity_started_at - self._activity_delay)
            self.icon_widget.set_angle((elapsed * 90) % 360 if self._rotate_icon else 0)


class NavigationStatusIndicator(QWidget):
    """Small status glyph overlaid on a navigation icon without affecting layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.icon_widget = IconWidget(self)
        self.icon_widget.setFixedSize(8, 8)
        self.icon_widget.move(3, 3)
        self.hide()

    def set_status(self, icon, color: str, icon_color: str = "#FFFFFF"):
        accent = QColor(color)
        rendered_icon = icon.icon(color=QColor(icon_color)) if hasattr(icon, "icon") else icon
        self.icon_widget.setIcon(rendered_icon)
        self.setStyleSheet(
            f"background-color: {accent.name()}; border: 1px solid rgba(255, 255, 255, 190); border-radius: 7px;"
        )
        self.show()
        self.raise_()


def metric_row(cards: list[MetricCard]) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    for card in cards:
        layout.addWidget(card, 1)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    return widget
