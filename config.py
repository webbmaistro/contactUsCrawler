"""
Configuration file for the Contact Form Crawler
Customize these settings to match your needs
"""

# ========== SENDER INFORMATION ==========
SENDER_NAME = "Webb Hammond"
SENDER_EMAIL = "webb@flowdrop.ai"
MESSAGE_TEMPLATE = """Hi {restaurant_name}, I'm Webb from Flowdrop. We've built an AI agent for restaurant back office that's cheaper than MarginEdge and handles scheduling too. We're filling a small pilot group to test it. Would love to show you a quick demo: https://calendly.com/webb-flowdrop/new-meeting"""

# ========== CSV FILE SETTINGS ==========
INPUT_CSV = "restaurants.csv"  # Path to your input CSV file
OUTPUT_CSV = "restaurants_results.csv"  # Where to save results

# ========== BROWSER SETTINGS ==========
HEADLESS_MODE = True  # Set to False to see the browser in action
BROWSER_TIMEOUT = 30000  # 30 seconds timeout for page loads (in milliseconds)
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720

# ========== CRAWLER BEHAVIOR ==========
# Delay between submissions (in seconds) - random value between min and max
MIN_DELAY = 20
MAX_DELAY = 40

# Maximum number of contact page links to check per website
MAX_CONTACT_LINKS_TO_CHECK = 5

# ========== CONTACT PAGE DETECTION ==========
# Common URL patterns for contact pages
CONTACT_URL_PATTERNS = [
    "/contact",
    "/contact-us",
    "/contactus",
    "/get-in-touch",
    "/getintouch",
    "/reach-us",
    "/contact-form",
    "/inquiry",
    "/reach-out",
    "/support",
    "/help",
    "/feedback",
]

# Link text patterns to identify contact links
CONTACT_LINK_TEXT = [
    "contact",
    "contact us",
    "get in touch",
    "reach us",
    "reach out",
    "send message",
    "email us",
    "touch",
    "inquiry",
    "feedback",
]

# ========== FORM FIELD DETECTION ==========
# Common field name/id/label patterns for form fields
NAME_FIELD_PATTERNS = [
    "name", "your-name", "fullname", "full-name", "contact-name",
    "customer-name", "sender-name", "fname", "firstname", "first-name"
]

EMAIL_FIELD_PATTERNS = [
    "email", "e-mail", "your-email", "contact-email", "sender-email",
    "customer-email", "mail", "email-address", "emailaddress"
]

MESSAGE_FIELD_PATTERNS = [
    "message", "your-message", "comments", "comment", "inquiry",
    "question", "details", "description", "body", "text", "content",
    "msg", "note", "notes", "feedback"
]

PHONE_FIELD_PATTERNS = [
    "phone", "telephone", "tel", "mobile", "contact-number",
    "phone-number", "phonenumber", "cell"
]

SUBMIT_BUTTON_PATTERNS = [
    "submit", "send", "send message", "send inquiry", "contact us",
    "get in touch", "submit form", "submit inquiry", "submit message"
]

# ========== LLM SETTINGS (OLLAMA) ==========
# Enable/disable LLM fallback for form field detection
USE_LLM_FALLBACK = True

# Ollama API endpoint (default local installation)
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Model to use (llama3.2, phi3, mistral, qwen2.5:3b)
# Smaller models are faster but less accurate
OLLAMA_MODEL = "llama3.2"

# Temperature for LLM responses (0.0 = deterministic, 1.0 = creative)
LLM_TEMPERATURE = 0.1

# Maximum tokens for LLM response
LLM_MAX_TOKENS = 500

# Only use LLM if selector-based detection fails
# If True, LLM is used as fallback only
# If False, LLM is used for all form detections
LLM_FALLBACK_ONLY = True

# ========== LOGGING SETTINGS ==========
LOG_FILE = "crawler.log"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# ========== RETRY SETTINGS ==========
MAX_RETRIES_PER_SITE = 2  # Number of retries if a site fails
RETRY_DELAY = 5  # Seconds to wait before retrying

# ========== PROGRESS SAVING ==========
# Save progress every N websites
SAVE_PROGRESS_INTERVAL = 5

# ========== ADVANCED SETTINGS ==========
# User agent string for the browser
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Whether to screenshot failed submissions for debugging
SCREENSHOT_ON_FAILURE = False
SCREENSHOT_DIR = "screenshots"

# Whether to save HTML of contact pages for debugging
SAVE_HTML_ON_FAILURE = False
HTML_DIR = "html_dumps"
