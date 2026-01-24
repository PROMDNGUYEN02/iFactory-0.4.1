"""
Component QSS - Component-specific stylesheets.

All component styles use CSS variables from base_qss.py.
No hardcoded values - maintain design system consistency.
"""

BUTTONS_QSS = """
/* ============================================
   Button Component
   ============================================ */

QPushButton {
    background-color: var(--color-primary);
    color: var(--color-background);
    border: none;
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    font-size: var(--font-body-size);
    font-weight: var(--font-body-weight);
    min-height: 32px;
}

QPushButton:hover {
    background-color: var(--color-primary-hover);
}

QPushButton:pressed {
    background-color: var(--color-primary-active);
}

QPushButton:disabled {
    background-color: var(--color-surface);
    color: var(--color-text-disabled);
}

QPushButton:default {
    background-color: var(--color-primary);
}

QPushButton[buttonType="secondary"] {
    background-color: transparent;
    border: 1px solid var(--color-border);
    color: var(--color-text-primary);
}

QPushButton[buttonType="secondary"]:hover {
    background-color: var(--color-surface-hover);
    border-color: var(--color-primary);
}

QPushButton[buttonType="danger"] {
    background-color: var(--color-error);
}

QPushButton[buttonType="danger"]:hover {
    background-color: #b91c1c;
}

QPushButton[buttonType="success"] {
    background-color: var(--color-success);
}

QPushButton[buttonType="success"]:hover {
    background-color: #15803d;
}

QPushButton[buttonType="ghost"] {
    background-color: transparent;
    color: var(--color-primary);
}

QPushButton[buttonType="ghost"]:hover {
    background-color: var(--color-surface-hover);
}

QPushButton[buttonType="icon"] {
    background-color: transparent;
    border: none;
    padding: var(--spacing-sm);
    border-radius: var(--radius-md);
}

QPushButton[buttonType="icon"]:hover {
    background-color: var(--color-surface-hover);
}
"""

CARDS_QSS = """
/* ============================================
   Card Component
   ============================================ */

QFrame[frameType="card"] {
    background-color: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
}

QFrame[frameType="card"]:hover {
    border-color: var(--color-primary);
    box-shadow: var(--shadow-md);
}

QFrame[frameType="card"][selected="true"] {
    border: 2px solid var(--color-primary);
    background-color: var(--color-surface-active);
}
"""

INPUTS_QSS = """
/* ============================================
   Input Components
   ============================================ */

QLineEdit,
QTextEdit,
QPlainTextEdit {
    background-color: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    font-size: var(--font-body-size);
    color: var(--color-text-primary);
    selection-background-color: var(--color-primary);
    selection-color: var(--color-background);
}

QLineEdit:hover,
QTextEdit:hover,
QPlainTextEdit:hover {
    border-color: var(--color-primary);
}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus {
    border: 2px solid var(--color-primary);
}

QLineEdit:disabled,
QTextEdit:disabled,
QPlainTextEdit:disabled {
    background-color: var(--color-surface);
    color: var(--color-text-disabled);
    border-color: var(--color-border-light);
}

/* ComboBox */
QComboBox {
    background-color: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    font-size: var(--font-body-size);
    color: var(--color-text-primary);
    min-height: 32px;
}

QComboBox:hover {
    border-color: var(--color-primary);
}

QComboBox:focus {
    border: 2px solid var(--color-primary);
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: url(:/icon/arrow-down.svg);
}

QComboBox QAbstractItemView {
    background-color: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    selection-background-color: var(--color-primary);
    selection-color: var(--color-background);
}

/* SpinBox */
QSpinBox,
QDoubleSpinBox {
    background-color: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    font-size: var(--font-body-size);
    color: var(--color-text-primary);
}

QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 2px solid var(--color-primary);
}

QSpinBox::up-button,
QDoubleSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::down-button {
    background-color: var(--color-surface);
    border: none;
    width: 16px;
}

QSpinBox::up-button:hover,
QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {
    background-color: var(--color-surface-hover);
}
"""

LISTS_QSS = """
/* ============================================
   List Components
   ============================================ */

QListWidget,
QListView,
QTreeWidget,
QTableView {
    background-color: var(--color-background);
    border: none;
    outline: none;
    selection-background-color: var(--color-primary);
    selection-color: var(--color-background);
    alternate-background-color: var(--color-surface);
}

QListWidget::item,
QListView::item {
    padding: var(--spacing-sm) var(--spacing-md);
    border-radius: var(--radius-sm);
    margin: 1px;
}

QListWidget::item:hover,
QListView::item:hover {
    background-color: var(--color-surface-hover);
}

QListWidget::item:selected,
QListView::item:selected {
    background-color: var(--color-primary);
    color: var(--color-background);
}

QTreeWidget::item {
    padding: var(--spacing-sm);
    border-radius: var(--radius-sm);
}

QTreeWidget::item:hover {
    background-color: var(--color-surface-hover);
}

QTreeWidget::item:selected {
    background-color: var(--color-primary);
    color: var(--color-background);
}
"""

PANELS_QSS = """
/* ============================================
   Panel Components
   ============================================ */

QFrame[frameType="panel"] {
    background-color: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
}

QFrame[frameType="panel"][floating="true"] {
    background-color: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
}

/* Left Menu */
QFrame[frameType="left-menu"] {
    background-color: var(--color-surface);
    border-right: 1px solid var(--color-border);
}

QFrame[frameType="left-menu"][collapsed="true"] {
    background-color: var(--color-background);
}

/* Right Panel */
QFrame[frameType="right-panel"] {
    background-color: var(--color-background);
    border-left: 1px solid var(--color-border);
    box-shadow: var(--shadow-xl);
}

QFrame[frameType="right-panel"][expanded="true"] {
    background-color: var(--color-surface);
}

/* Settings Panel */
QFrame[frameType="settings-panel"] {
    background-color: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
}

/* Theme Panel */
QFrame[frameType="theme-panel"] {
    background-color: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
}
"""

MENUS_QSS = """
/* ============================================
   Menu Components
   ============================================ */

QMenu {
    background-color: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--spacing-xs);
}

QMenu::item {
    padding: var(--spacing-sm) var(--spacing-md);
    border-radius: var(--radius-sm);
    min-width: 150px;
}

QMenu::item:selected {
    background-color: var(--color-primary);
    color: var(--color-background);
}

QMenu::item:disabled {
    color: var(--color-text-disabled);
}

QMenu::separator {
    height: 1px;
    background-color: var(--color-divider);
    margin: var(--spacing-xs) var(--spacing-sm);
}
"""

STATUS_INDICATORS_QSS = """
/* ============================================
   Status Indicator Component
   ============================================ */

QLabel[statusType="running"] {
    color: var(--color-status-running);
}

QLabel[statusType="shutdown"] {
    color: var(--color-status-shutdown);
}

QLabel[statusType="stop"] {
    color: var(--color-status-stop);
}

QLabel[statusType="maintenance"] {
    color: var(--color-status-maintenance);
}

QLabel[statusType="alarm"] {
    color: var(--color-status-alarm);
}

QLabel[statusType="unknown"] {
    color: var(--color-status-unknown);
}

QFrame[statusType="running"] {
    background-color: var(--color-status-running);
}

QFrame[statusType="shutdown"] {
    background-color: var(--color-status-shutdown);
}

QFrame[statusType="stop"] {
    background-color: var(--color-status-stop);
}

QFrame[statusType="maintenance"] {
    background-color: var(--color-status-maintenance);
}

QFrame[statusType="alarm"] {
    background-color: var(--color-status-alarm);
}

QFrame[statusType="unknown"] {
    background-color: var(--color-status-unknown);
}
"""

TOOLBARS_QSS = """
/* ============================================
   Toolbar Component
   ============================================ */

QToolBar {
    background-color: var(--color-surface);
    border: none;
    border-bottom: 1px solid var(--color-border);
    spacing: var(--spacing-sm);
}

QToolBar::separator {
    background-color: var(--color-divider);
    width: 1px;
    margin: var(--spacing-sm) var(--spacing-xs);
}

QToolButton {
    background-color: transparent;
    border: none;
    border-radius: var(--radius-sm);
    padding: var(--spacing-sm);
    min-width: 32px;
    min-height: 32px;
}

QToolButton:hover {
    background-color: var(--color-surface-hover);
}

QToolButton:pressed {
    background-color: var(--color-surface-active);
}

QToolButton:checked {
    background-color: var(--color-primary);
    color: var(--color-background);
}
"""

PROGRESS_BARS_QSS = """
/* ============================================
   Progress Bar Component
   ============================================ */

QProgressBar {
    background-color: var(--color-surface);
    border: none;
    border-radius: var(--radius-sm);
    height: 4px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: var(--color-primary);
    border-radius: var(--radius-sm);
}

QProgressBar[status="success"]::chunk {
    background-color: var(--color-success);
}

QProgressBar[status="warning"]::chunk {
    background-color: var(--color-warning);
}

QProgressBar[status="error"]::chunk {
    background-color: var(--color-error);
}
"""

DIALOGS_QSS = """
/* ============================================
   Dialog Component
   ============================================ */

QDialog {
    background-color: var(--color-background);
}

QDialog > QWidget {
    background-color: var(--color-background);
}

QMessageBox {
    background-color: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
}

QMessageBox QPushButton {
    min-width: 80px;
    min-height: 32px;
}
"""

ALL_COMPONENTS_QSS = f"""
{BUTTONS_QSS}

{CARDS_QSS}

{INPUTS_QSS}

{LISTS_QSS}

{PANELS_QSS}

{MENUS_QSS}

{STATUS_INDICATORS_QSS}

{TOOLBARS_QSS}

{PROGRESS_BARS_QSS}

{DIALOGS_QSS}
"""

__all__ = [
    "ALL_COMPONENTS_QSS",
    "BUTTONS_QSS",
    "CARDS_QSS",
    "INPUTS_QSS",
    "LISTS_QSS",
    "PANELS_QSS",
    "MENUS_QSS",
    "STATUS_INDICATORS_QSS",
    "TOOLBARS_QSS",
    "PROGRESS_BARS_QSS",
    "DIALOGS_QSS",
]
