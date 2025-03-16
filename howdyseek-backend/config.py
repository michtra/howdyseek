"""
Environment configuration file
"""

# Chrome profile configuration
USER_DATA_DIR_ARG = r'user-data-dir=/home/michael/.config/chromium/'
PROFILE_DIR_ARG = '--profile-directory=Default'

# TAMU URLs
TAMU_SCHEDULER_BASE_URL = "https://tamu.collegescheduler.com"
FALL_2025_URL = f"{TAMU_SCHEDULER_BASE_URL}/terms/Fall%202025%20-%20College%20Station/options"
TERM_STRING = '//*[@id="Fall 2025 - College Station"]'

# API and other constants
API_BASE_URL = "http://localhost:8000"
INVALID_PAGE_STRING = "invalid.aspx?aspxerrorpath=/"
DEFAULT_REFRESH_INTERVAL_RANGE = (30, 40)  # Default seconds range if API fails
