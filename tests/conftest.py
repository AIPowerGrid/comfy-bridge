# Test-environment defaults. APIClient() requires GRID_API_KEY at construction;
# CI has no .env, so provide a dummy before any test instantiates it. setdefault
# keeps a real local value if one is exported.
import os

os.environ.setdefault("GRID_API_KEY", "test-key")
