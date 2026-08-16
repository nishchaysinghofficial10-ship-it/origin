"""Security-gated web boundary for the ORIGIN interactive beta.

This package is intentionally separate from the verified research core. The
HTTP process validates and queues requests.  A network-disabled worker invokes
the existing computational CLI, while a separately secret-bearing researcher
performs bounded, citation-preserving public-web synthesis.
"""

__version__ = "0.2.0-beta"
