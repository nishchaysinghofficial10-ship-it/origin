"""Security-gated web boundary for the ORIGIN interactive beta.

This package is intentionally separate from the verified research core. The
HTTP process validates and queues requests; a distinct worker process invokes
the existing CLI with fixed budgets and no provider or retrieval authority.
"""

__version__ = "0.1.0-beta"
