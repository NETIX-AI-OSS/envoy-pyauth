import os

# common.py reads DJANGO_DEBUG at import time; default it for the test process so importing
# envoy_pyauth doesn't KeyError. Individual tests exercising the debug bypass set it explicitly.
os.environ.setdefault("DJANGO_DEBUG", "FALSE")
