"""AlphaKit option-chain feeds and pricing helpers.

Importing this package triggers the module-level
``FeedRegistry.register`` calls inside every option-feed adapter, so
strategies can resolve them by name from a single entry point.
"""

from __future__ import annotations

from alphakit.data.options import polygon_adapter, synthetic  # registers at import
