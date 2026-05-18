"""
SYSTEM LOCK — PRODUCTION BASELINE

This file defines whether the system is in:
- LOCKED (production-safe mode)
- UNLOCKED (development mode)

DO NOT MODIFY WITHOUT AUTHORIZATION
"""

SYSTEM_LOCKED = True

# Safety switches
ALLOW_SCHEMA_CHANGES = False
ALLOW_PIPELINE_RESTRUCTURE = False
ALLOW_EXPERIMENTAL_FEATURES = False

# Runtime protections
STRICT_RFQ_LOCK = True
STRICT_EMAIL_LOCK = True
STRICT_QUOTE_NUMBER_LOCK = True

# Logging
ENABLE_AUDIT_LOGGING = True
