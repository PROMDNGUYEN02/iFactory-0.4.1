"""
Entry point for `python -m iFactory`

This module serves as the application launcher. It handles the initial
environment setup and delegates the actual bootstrap process to the
`bootstrap` module.

Key Design Decisions:
    - Lazy Imports: Imports are performed inside the `main()` function.
      This speeds up shell completion and allows for graceful handling
      of missing dependencies before the logging system is initialized.
    - Global Error Handling: Catches critical startup errors to provide
      user-friendly feedback via stderr.
"""

import sys


def main() -> int:
    """
    Application entry point.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    try:
        from iFactory.bootstrap import run_application

        return run_application()
    except ImportError as e:
        # Handle missing modules or path issues before logging is available
        print(
            f"[CRITICAL] Failed to start: Missing dependencies or import error.\n"
            f"Details: {e}",
            file=sys.stderr,
        )
        return 1
    except Exception as e:
        # Catch-all for unexpected errors during bootstrap
        print(
            f"[CRITICAL] Unhandled exception during startup.\n" f"Details: {e}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
