import os

# Keep the compatibility setting deterministic; authorization never consults it.
os.environ.setdefault("DJANGO_DEBUG", "FALSE")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "envoy_pyauth.mypy_settings")
