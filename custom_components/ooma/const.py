"""Constants for the Ooma Home Assistant integration."""

DOMAIN = "ooma"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # seconds

# Event names emitted on Home Assistant bus
EVENT_OOMA_INCOMING_CALL = "ooma_incoming_call"
EVENT_OOMA_MISSED_CALL = "ooma_missed_call"
EVENT_OOMA_VOICEMAIL_RECEIVED = "ooma_voicemail_received"

# Attribute keys
ATTR_CALLER_NAME = "caller_name"
ATTR_CALLER_NUMBER = "caller_number"
ATTR_CALL_TYPE = "call_type"
ATTR_CALL_DURATION = "call_duration"
ATTR_TIMESTAMP = "timestamp"
ATTR_UNREAD_COUNT = "unread_count"
ATTR_TOTAL_COUNT = "total_count"
