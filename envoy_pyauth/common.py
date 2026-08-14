import os

# Kept as a compatibility export for consumers which import it. Authorization
# decisions must never depend on Django's debug mode: a test/development setting
# is not an authentication mechanism and has historically leaked into deployed
# environments.
DJANGO_DEBUG = os.environ.get("DJANGO_DEBUG", "FALSE").upper() == "TRUE"
