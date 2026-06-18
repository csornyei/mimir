import os

# Must be set before any mimir module is imported, because MimirConfig()
# is constructed at import time and these fields have no default.
os.environ.setdefault("OPENAI_API_KEY", "dummy-key-for-tests")
