"""Constants for the Label Printer integration."""

DOMAIN = "label_printer"

# Config entry data
CONF_HOST = "host"
CONF_PORT = "port"

# Options (entry.options)
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60  # seconds

# Per-job print settings, adjustable via entities and merged into every
# /print request. font_size 0 means "use the add-on's configured default".
OPT_FONT_SIZE = "font_size"
OPT_AUTOCUT = "autocut"
OPT_MIRROR = "mirror"
OPT_HALF_CUT = "half_cut"
OPT_HIGH_DPI = "high_dpi"
OPT_CHAIN_PRINT = "chain_print"
OPT_FEED_AMOUNT = "feed_amount"

PRINT_SETTING_DEFAULTS = {
    OPT_FONT_SIZE: 0,
    OPT_AUTOCUT: True,
    OPT_MIRROR: False,
    OPT_HALF_CUT: False,
    OPT_HIGH_DPI: False,
    OPT_CHAIN_PRINT: False,
    OPT_FEED_AMOUNT: 10,
}
