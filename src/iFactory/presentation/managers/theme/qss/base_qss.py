"""
Base QSS - CSS Variables and Global Styles.

This file defines all CSS variables using design tokens.
All other QSS files reference these variables.
No hardcoded values in component stylesheets.
"""

BASE_QSS = """
/* ============================================
   CSS Variables - Design Tokens
   ============================================ */

/* Color Variables */
:root {
    /* Brand Colors */
    ${color-primary};
    ${color-primary-hover};
    ${color-primary-active};
    ${color-secondary};
    
    /* Semantic Colors */
    ${color-success};
    ${color-warning};
    ${color-error};
    ${color-info};
    
    /* Background Colors */
    ${color-background};
    ${color-surface};
    ${color-surface-hover};
    ${color-surface-active};
    
    /* Text Colors */
    ${color-text-primary};
    ${color-text-secondary};
    ${color-text-tertiary};
    ${color-text-disabled};
    
    /* Border Colors */
    ${color-border};
    ${color-border-light};
    ${color-border-focus};
    ${color-divider};
    
    /* Overlay */
    ${color-overlay};
    
    /* Status Colors */
    ${color-status-running};
    ${color-status-shutdown};
    ${color-status-stop};
    ${color-status-maintenance};
    ${color-status-alarm};
    ${color-status-unknown};
    
    /* Spacing Variables */
    ${spacing-xs};
    ${spacing-sm};
    ${spacing-md};
    ${spacing-lg};
    ${spacing-xl};
    ${spacing-xxl};
    
    /* Typography Variables */
    ${font-caption-family};
    ${font-caption-size};
    ${font-caption-weight};
    ${font-caption-line-height};
    ${font-caption-letter-spacing};
    
    ${font-body-small-family};
    ${font-body-small-size};
    ${font-body-small-weight};
    ${font-body-small-line-height};
    ${font-body-small-letter-spacing};
    
    ${font-body-family};
    ${font-body-size};
    ${font-body-weight};
    ${font-body-line-height};
    ${font-body-letter-spacing};
    
    ${font-body-large-family};
    ${font-body-large-size};
    ${font-body-large-weight};
    ${font-body-large-line-height};
    ${font-body-large-letter-spacing};
    
    ${font-heading-small-family};
    ${font-heading-small-size};
    ${font-heading-small-weight};
    ${font-heading-small-line-height};
    ${font-heading-small-letter-spacing};
    
    ${font-heading-family};
    ${font-heading-size};
    ${font-heading-weight};
    ${font-heading-line-height};
    ${font-heading-letter-spacing};
    
    ${font-heading-large-family};
    ${font-heading-large-size};
    ${font-heading-large-weight};
    ${font-heading-large-line-height};
    ${font-heading-large-letter-spacing};
    
    ${font-display-small-family};
    ${font-display-small-size};
    ${font-display-small-weight};
    ${font-display-small-line-height};
    ${font-display-small-letter-spacing};
    
    ${font-display-family};
    ${font-display-size};
    ${font-display-weight};
    ${font-display-line-height};
    ${font-display-letter-spacing};
    
    ${font-display-large-family};
    ${font-display-large-size};
    ${font-display-large-weight};
    ${font-display-large-line-height};
    ${font-display-large-letter-spacing};
    
    /* Shadow Variables */
    ${shadow-sm};
    ${shadow-md};
    ${shadow-lg};
    ${shadow-xl};
    ${shadow-inner};
    ${shadow-focus-ring};
    
    /* Radius Variables */
    ${radius-none};
    ${radius-sm};
    ${radius-md};
    ${radius-lg};
    ${radius-xl};
    ${radius-full};
}

/* ============================================
   Global Styles
   ============================================ */

* {
    font-family: var(--font-body-family);
    font-size: var(--font-body-size);
    color: var(--color-text-primary);
    background-color: var(--color-background);
    border: none;
    outline: none;
    selection-background-color: var(--color-primary);
    selection-color: var(--color-background);
}

QWidget {
    background-color: var(--color-background);
    color: var(--color-text-primary);
    border: none;
    outline: none;
}

QMainWindow {
    background-color: var(--color-background);
}

QWidget:focus {
    outline: none;
}

QWidget:focus-visible {
    outline: var(--shadow-focus-ring);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
}

/* ============================================
   Scrollbar Styles
   ============================================ */

QScrollBar:vertical,
QScrollBar:horizontal {
    background-color: transparent;
    border: none;
    margin: 0px;
}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {
    background-color: var(--color-text-tertiary);
    border-radius: var(--radius-md);
    min-height: var(--spacing-lg);
    min-width: var(--spacing-lg);
}

QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {
    background-color: var(--color-text-secondary);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    background: none;
    border: none;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
}

/* ============================================
   Tooltip Styles
   ============================================ */

QToolTip {
    background-color: var(--color-text-primary);
    color: var(--color-background);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    font-size: var(--font-body-small-size);
    font-weight: var(--font-body-small-weight);
}
"""

__all__ = ["BASE_QSS"]
