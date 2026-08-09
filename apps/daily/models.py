# apps.daily — read-only reports for the Daily Log system.
# No Django models here: selectors.py queries daily_events directly via
# connections["default"].cursor() against the unmanaged legacy schema.
