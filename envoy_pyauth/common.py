import os

# Compatibility export; authorization must never depend on debug mode.
DJANGO_DEBUG = os.environ.get("DJANGO_DEBUG", "FALSE").upper() == "TRUE"
