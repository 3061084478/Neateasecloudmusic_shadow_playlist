from __future__ import annotations

from typing import Iterable, List

from PySide6 import QtCore, QtGui, QtWidgets


class ActiveDateCalendar(QtWidgets.QCalendarWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._active_dates: set[str] = set()
        self._last_valid_date = self.selectedDate()
        self._default_min_date = self.minimumDate()
        self._default_max_date = QtCore.QDate.currentDate()
        self._nav_filter_installed = False
        self._header: QtWidgets.QFrame | None = None
        self._header_prev: QtWidgets.QToolButton | None = None
        self._header_next: QtWidgets.QToolButton | None = None
        self._header_title: QtWidgets.QLabel | None = None
        self._calendar_view: QtWidgets.QAbstractItemView | None = None
        self._calendar_viewport: QtWidgets.QWidget | None = None
        self.setMaximumDate(self._default_max_date)
        self.setDateEditEnabled(False)
        self.setNavigationBarVisible(False)
        self.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.NoVerticalHeader)
        self.setGridVisible(False)
        weekend_format = QtGui.QTextCharFormat()
        weekend_format.setForeground(QtGui.QBrush(QtGui.QColor(245, 247, 252, 228)))
        self.setWeekdayTextFormat(QtCore.Qt.Saturday, weekend_format)
        self.setWeekdayTextFormat(QtCore.Qt.Sunday, weekend_format)
        self._build_header()
        self.clicked.connect(self._on_clicked)
        self.activated.connect(self._on_clicked)
        self.selectionChanged.connect(self._on_selection_changed)
        self.currentPageChanged.connect(self._on_current_page_changed)
        QtCore.QTimer.singleShot(0, self._sync_navigation_controls)

    def _build_header(self) -> None:
        header = QtWidgets.QFrame(self)
        header.setObjectName("activeCalendarHeader")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        prev_button = QtWidgets.QToolButton(header)
        prev_button.setObjectName("activeCalendarPrevButton")
        prev_button.setText("◀")
        prev_button.clicked.connect(lambda: self._step_month(-1))

        next_button = QtWidgets.QToolButton(header)
        next_button.setObjectName("activeCalendarNextButton")
        next_button.setText("▶")
        next_button.clicked.connect(lambda: self._step_month(1))

        title_label = QtWidgets.QLabel(header)
        title_label.setObjectName("activeCalendarTitle")
        title_label.setAlignment(QtCore.Qt.AlignCenter)

        header_layout.addWidget(prev_button, 0, QtCore.Qt.AlignVCenter)
        header_layout.addWidget(title_label, 1, QtCore.Qt.AlignCenter)
        header_layout.addWidget(next_button, 0, QtCore.Qt.AlignVCenter)

        layout = self.layout()
        if isinstance(layout, QtWidgets.QVBoxLayout):
            layout.insertWidget(0, header)
        else:
            header.setParent(self)

        self._header = header
        self._header_prev = prev_button
        self._header_next = next_button
        self._header_title = title_label

    @staticmethod
    def _to_key(date: QtCore.QDate) -> str:
        return date.toString("yyyy-MM-dd")

    @staticmethod
    def _parse_date_key(text: str) -> QtCore.QDate:
        return QtCore.QDate.fromString(text, "yyyy-MM-dd")

    def set_active_dates(self, date_keys: Iterable[str], preferred_date: QtCore.QDate | None = None) -> None:
        today = QtCore.QDate.currentDate()
        parsed_dates = []
        for text in date_keys:
            if not text:
                continue
            date = self._parse_date_key(str(text))
            if date.isValid() and date <= today:
                parsed_dates.append(date)
        parsed_dates.sort(key=lambda item: item.toJulianDay())
        self._active_dates = {self._to_key(item) for item in parsed_dates}
        if parsed_dates:
            min_date = parsed_dates[0]
            max_date = parsed_dates[-1]
        else:
            fallback = preferred_date if preferred_date and preferred_date.isValid() else QtCore.QDate.currentDate()
            if fallback > today:
                fallback = today
            min_date = fallback
            max_date = fallback
        with QtCore.QSignalBlocker(self):
            self.setMinimumDate(min_date)
            self.setMaximumDate(max_date)
        target = self._resolve_target_date(preferred_date or self.selectedDate())
        with QtCore.QSignalBlocker(self):
            self.setSelectedDate(target)
            self.setCurrentPage(target.year(), target.month())
        self._clamp_current_page()
        self._sync_navigation_controls()
        self._last_valid_date = target
        self.updateCells()

    def is_date_active(self, date: QtCore.QDate) -> bool:
        return self._to_key(date) in self._active_dates

    def has_active_dates(self) -> bool:
        return bool(self._active_dates)

    @staticmethod
    def _month_key(year: int, month: int) -> int:
        return year * 12 + month

    def _current_page_key(self) -> int:
        return self._month_key(self.yearShown(), self.monthShown())

    def _bound_page(self, year: int, month: int) -> tuple[int, int]:
        key = self._month_key(year, month)
        min_key = self._month_key(self.minimumDate().year(), self.minimumDate().month())
        max_key = self._month_key(self.maximumDate().year(), self.maximumDate().month())
        if key < min_key:
            return (self.minimumDate().year(), self.minimumDate().month())
        if key > max_key:
            return (self.maximumDate().year(), self.maximumDate().month())
        return (year, month)

    def setCurrentPage(self, year: int, month: int) -> None:  # type: ignore[override]
        bounded_year, bounded_month = self._bound_page(year, month)
        super().setCurrentPage(bounded_year, bounded_month)

    def _can_show_previous_month(self) -> bool:
        min_key = self._month_key(self.minimumDate().year(), self.minimumDate().month())
        return self._current_page_key() > min_key

    def _can_show_next_month(self) -> bool:
        max_key = self._month_key(self.maximumDate().year(), self.maximumDate().month())
        return self._current_page_key() < max_key

    def _sync_navigation_controls(self) -> None:
        prev_button = self._header_prev
        next_button = self._header_next
        title_label = self._header_title
        calendar_view = self.findChild(QtWidgets.QAbstractItemView, "qt_calendar_calendarview")
        view_port = calendar_view.viewport() if calendar_view is not None else None
        self._calendar_view = calendar_view
        self._calendar_viewport = view_port
        installed_any = False
        for widget in (calendar_view, view_port):
            if widget is None:
                continue
            if not widget.property("_v5_nav_filter_installed"):
                widget.installEventFilter(self)
                widget.setProperty("_v5_nav_filter_installed", True)
            installed_any = True
        self._nav_filter_installed = installed_any
        if prev_button is not None:
            prev_button.setEnabled(self._can_show_previous_month())
        if next_button is not None:
            next_button.setEnabled(self._can_show_next_month())
        if title_label is not None:
            month_date = QtCore.QDate(self.yearShown(), self.monthShown(), 1)
            title_label.setText(month_date.toString("yyyy 年 M 月"))

    def _step_month(self, delta: int) -> None:
        base = QtCore.QDate(self.yearShown(), self.monthShown(), 1)
        target = base.addMonths(delta)
        bounded_year, bounded_month = self._bound_page(target.year(), target.month())
        with QtCore.QSignalBlocker(self):
            self.setCurrentPage(bounded_year, bounded_month)
        self._clamp_current_page()

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        name = watched.objectName() if isinstance(watched, QtCore.QObject) else ""
        event_type = event.type()
        if name in {"qt_calendar_monthbutton", "qt_calendar_yearbutton", "qt_calendar_yearedit"}:
            if event_type in (
                QtCore.QEvent.MouseButtonPress,
                QtCore.QEvent.MouseButtonRelease,
                QtCore.QEvent.MouseButtonDblClick,
                QtCore.QEvent.Wheel,
                QtCore.QEvent.KeyPress,
                QtCore.QEvent.FocusIn,
            ):
                return True
        if name == "qt_calendar_prevmonth":
            if event_type in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
                if event_type == QtCore.QEvent.MouseButtonRelease and self._can_show_previous_month():
                    self._step_month(-1)
                return True
        if name == "qt_calendar_nextmonth":
            if event_type in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
                if event_type == QtCore.QEvent.MouseButtonRelease and self._can_show_next_month():
                    self._step_month(1)
                return True
        if watched in {self._calendar_view, self._calendar_viewport} or name in {"qt_calendar_calendarview", "qt_scrollarea_viewport"}:
            if event_type == QtCore.QEvent.Wheel:
                wheel = event  # type: ignore[assignment]
                if isinstance(wheel, QtGui.QWheelEvent):
                    delta = wheel.angleDelta().y()
                    if delta > 0 and self._can_show_previous_month():
                        self._step_month(-1)
                    if delta < 0 and self._can_show_next_month():
                        self._step_month(1)
                    return True
            if event_type == QtCore.QEvent.KeyPress:
                key_event = event  # type: ignore[assignment]
                if isinstance(key_event, QtGui.QKeyEvent):
                    key = key_event.key()
                    if key == QtCore.Qt.Key_PageUp:
                        if self._can_show_previous_month():
                            self._step_month(-1)
                        return True
                    if key == QtCore.Qt.Key_PageDown:
                        if self._can_show_next_month():
                            self._step_month(1)
                        return True
        return super().eventFilter(watched, event)

    def _clamp_current_page(self) -> None:
        min_date = self.minimumDate()
        max_date = self.maximumDate()
        shown_key = self._month_key(self.yearShown(), self.monthShown())
        min_key = self._month_key(min_date.year(), min_date.month())
        max_key = self._month_key(max_date.year(), max_date.month())
        if shown_key < min_key:
            with QtCore.QSignalBlocker(self):
                self.setCurrentPage(min_date.year(), min_date.month())
            return
        if shown_key > max_key:
            with QtCore.QSignalBlocker(self):
                self.setCurrentPage(max_date.year(), max_date.month())
        self._sync_navigation_controls()

    def _on_current_page_changed(self, _year: int, _month: int) -> None:
        self._clamp_current_page()

    def showPreviousMonth(self) -> None:
        if self._can_show_previous_month():
            self._step_month(-1)

    def showNextMonth(self) -> None:
        if self._can_show_next_month():
            self._step_month(1)

    def showPreviousYear(self) -> None:
        target_year = self.yearShown() - 1
        target_month = self.monthShown()
        bounded_year, bounded_month = self._bound_page(target_year, target_month)
        with QtCore.QSignalBlocker(self):
            self.setCurrentPage(bounded_year, bounded_month)
        self._sync_navigation_controls()

    def showNextYear(self) -> None:
        target_year = self.yearShown() + 1
        target_month = self.monthShown()
        bounded_year, bounded_month = self._bound_page(target_year, target_month)
        with QtCore.QSignalBlocker(self):
            self.setCurrentPage(bounded_year, bounded_month)
        self._sync_navigation_controls()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            if self._can_show_previous_month():
                self.showPreviousMonth()
            event.accept()
            return
        if delta < 0:
            if self._can_show_next_month():
                self.showNextMonth()
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        key = event.key()
        if key == QtCore.Qt.Key_PageUp:
            if self._can_show_previous_month():
                self.showPreviousMonth()
            event.accept()
            return
        if key == QtCore.Qt.Key_PageDown:
            if self._can_show_next_month():
                self.showNextMonth()
            event.accept()
            return
        if key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            event.accept()
            return
        super().keyPressEvent(event)

    def event(self, event: QtCore.QEvent) -> bool:
        if event.type() in (QtCore.QEvent.Show, QtCore.QEvent.ShowToParent, QtCore.QEvent.Polish):
            QtCore.QTimer.singleShot(0, self._sync_navigation_controls)
            QtCore.QTimer.singleShot(0, self._clamp_current_page)
        return super().event(event)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._clamp_current_page()
        self._sync_navigation_controls()

    def _resolve_target_date(self, preferred_date: QtCore.QDate) -> QtCore.QDate:
        if self._active_dates:
            if preferred_date.isValid() and self.is_date_active(preferred_date):
                return preferred_date
            if self._last_valid_date.isValid() and self.is_date_active(self._last_valid_date):
                return self._last_valid_date
            dates = sorted(self._active_dates)
            today = QtCore.QDate.currentDate().toString("yyyy-MM-dd")
            candidate = next((item for item in reversed(dates) if item <= today), dates[-1])
            return self._parse_date_key(candidate)
        if preferred_date.isValid():
            return preferred_date
        return QtCore.QDate.currentDate()

    def _coerce_to_valid(self, selected: QtCore.QDate) -> QtCore.QDate:
        if not self._active_dates:
            return self._last_valid_date if self._last_valid_date.isValid() else selected
        if selected.isValid() and self.is_date_active(selected):
            self._last_valid_date = selected
            return selected
        return self._resolve_target_date(self._last_valid_date)

    def _on_clicked(self, selected: QtCore.QDate) -> None:
        target = self._coerce_to_valid(selected)
        if target != selected:
            with QtCore.QSignalBlocker(self):
                self.setSelectedDate(target)
            self.showSelectedDate()

    def _on_selection_changed(self) -> None:
        selected = self.selectedDate()
        target = self._coerce_to_valid(selected)
        if target != selected:
            with QtCore.QSignalBlocker(self):
                self.setSelectedDate(target)
            self.showSelectedDate()

    def paintCell(self, painter: QtGui.QPainter, rect: QtCore.QRect, date: QtCore.QDate) -> None:
        in_current_month = date.month() == self.monthShown() and date.year() == self.yearShown()
        if not in_current_month:
            painter.save()
            painter.fillRect(rect, QtCore.Qt.transparent)
            painter.restore()
            return

        if self.is_date_active(date):
            super().paintCell(painter, rect, date)
            if date != self.selectedDate():
                painter.save()
                painter.setPen(QtGui.QColor(245, 247, 252, 228))
                painter.drawText(rect, QtCore.Qt.AlignCenter, str(date.day()))
                painter.restore()
            return

        painter.save()
        painter.fillRect(rect.adjusted(1, 1, -1, -1), QtGui.QColor(255, 255, 255, 8))
        painter.setPen(QtGui.QColor(134, 145, 160, 148))
        painter.drawText(rect, QtCore.Qt.AlignCenter, str(date.day()))
        painter.restore()


def attach_active_calendar(date_edit: QtWidgets.QDateEdit) -> ActiveDateCalendar:
    calendar = ActiveDateCalendar(date_edit)
    date_edit.setCalendarWidget(calendar)
    date_edit.setCalendarPopup(True)

    def _on_date_changed(date: QtCore.QDate) -> None:
        current_calendar = date_edit.calendarWidget()
        if not isinstance(current_calendar, ActiveDateCalendar):
            return
        if not current_calendar.has_active_dates():
            return
        if current_calendar.is_date_active(date):
            return
        with QtCore.QSignalBlocker(date_edit):
            date_edit.setDate(current_calendar.selectedDate())

    date_edit.dateChanged.connect(_on_date_changed)
    return calendar


def apply_active_dates(date_edits: List[QtWidgets.QDateEdit], date_keys: Iterable[str]) -> None:
    keys = list(date_keys)
    for edit in date_edits:
        calendar = edit.calendarWidget()
        if isinstance(calendar, ActiveDateCalendar):
            calendar.set_active_dates(keys, preferred_date=edit.date())
            with QtCore.QSignalBlocker(edit):
                edit.setMinimumDate(calendar.minimumDate())
                edit.setMaximumDate(calendar.maximumDate())
                edit.setDate(calendar.selectedDate())
