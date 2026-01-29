# Restaurant Contact Form Crawler 🍽️

A Python-based web crawler that automatically finds and submits contact forms on restaurant websites at scale. Built with Playwright for reliable browser automation and optional AI-powered form detection using Ollama (100% free, runs locally).

## 🎯 What It Does

This crawler helps you reach out to hundreds or thousands of restaurants by:

1. **Finding Contact Pages** - Automatically discovers contact pages using common URL patterns and link text
2. **Detecting Form Fields** - Intelligently identifies name, email, message, and other form fields
3. **Filling Forms** - Populates forms with your custom message
4. **Submitting** - Submits the forms and verifies success
5. **Tracking Results** - Logs everything to CSV with status for each restaurant

### Expected Success Rates
- **60-70%** with CSS selectors only (no LLM)
- **85-95%** with Ollama LLM fallback enabled
- **60-90 websites per hour** with default delays (20-40 seconds between submissions)

## ✨ Features

- ✅ **Automated Contact Page Discovery** - Tries common patterns like `/contact`, `/contact-us`, etc.
- ✅ **Smart Form Field Detection** - Uses CSS selectors to find form fields by name, ID, placeholder, etc.
- ✅ **AI-Powered Fallback** - Optional Ollama integration for when selectors fail (100% free, local LLM)
- ✅ **Resume Capability** - Saves progress every N websites so you can stop and resume anytime
- ✅ **Detailed Logging** - Color-coded console output + detailed log files
- ✅ **Rate Limiting** - Random delays between submissions to avoid detection
- ✅ **Error Handling** - Gracefully handles failures and continues with next website
- ✅ **Debug Features** - Optional screenshot and HTML saving for failed submissions
- ✅ **Configurable** - Easy-to-edit config file for all settings

## 📋 Prerequisites

- **Python 3.8+** (Python 3.10+ recommended)
- **Ollama** (optional, for AI-powered form detection - see [LLM_SETUP.md](LLM_SETUP.md))

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd contactUsCrawler
```

### 2. Run the Setup Script (recommended)

```bash
python setup.py
```

This installs Python dependencies and the Playwright Chromium browser. To also pull the Ollama model (requires [Ollama](https://ollama.com) installed):

```bash
python setup.py --ollama
```

### Alternative: Manual Installation

<details>
<summary>Click to expand manual steps</summary>

**Install Python dependencies:**
```bash
pip install -r requirements.txt
```

**Install Playwright browsers:**
```bash
playwright install chromium
```

**Optional – Ollama for AI form detection:**  
Install from [ollama.com](https://ollama.com), then:
```bash
ollama pull llama3.2
```

</details>

## 📝 Usage

### 1. Prepare Your Restaurant List

Create a CSV file named `restaurants.csv` with two columns:

```csv
website_url,restaurant_name
https://example-restaurant.com,Example Restaurant
https://another-restaurant.com,Another Restaurant
```

See `sample_restaurants.csv` for a template.

### 2. Configure Your Settings

Edit `config.py` to customize:
- Your name and email
- Your message template
- Delay timings
- LLM settings
- And more...

### 3. Run the Crawler

```bash
python crawler.py
```

**First run**: Set `HEADLESS_MODE = False` in `config.py` to watch the browser and verify it's working correctly.

**Production runs**: Set `HEADLESS_MODE = True` for faster, background execution.

### 4. Monitor Progress

The crawler will:
- Display color-coded progress in the terminal
- Save progress to `restaurants_results.csv` every 5 websites (configurable)
- Write detailed logs to `crawler.log`

### 5. Resume If Interrupted

If the crawler stops or crashes, just run it again:

```bash
python crawler.py
```

It will automatically skip already-processed websites and continue where it left off.

## 📊 Output

The crawler creates/updates `restaurants_results.csv` with these columns:

| Column | Description |
|--------|-------------|
| `website_url` | Original website URL |
| `restaurant_name` | Restaurant name |
| `contact_page_url` | URL of the contact page (if found) |
| `status` | Result status (see below) |

### Status Values

- `sent` - Form successfully submitted
- `no contact page found` - Couldn't find a contact page
- `failed: required fields not found` - Contact page found but couldn't detect email/message fields
- `failed: submission error` - Form detected but submission failed
- `failed: [error message]` - Other error occurred

## ⚙️ Configuration

All settings are in `config.py`. Key configurations:

### Sender Information
```python
SENDER_NAME = "Webb Hammond"
SENDER_EMAIL = "webb@flowdrop.ai"
MESSAGE_TEMPLATE = "Your message here with {restaurant_name} placeholder"
```

### Delays
```python
MIN_DELAY = 20  # Minimum seconds between submissions
MAX_DELAY = 40  # Maximum seconds between submissions
```

### LLM Settings
```python
USE_LLM_FALLBACK = True  # Enable/disable AI fallback
OLLAMA_MODEL = "llama3.2"  # Which model to use
LLM_FALLBACK_ONLY = True  # Only use LLM when selectors fail
```

### Browser Settings
```python
HEADLESS_MODE = True  # Run without visible browser
BROWSER_TIMEOUT = 30000  # Page load timeout (ms)
```

See `config.py` for all available options.

## 🔍 How It Works

### 1. Contact Page Detection

The crawler tries multiple strategies:

1. **Common URL Patterns** - Tests `/contact`, `/contact-us`, `/get-in-touch`, etc.
2. **Link Text Search** - Looks for links with text like "Contact", "Contact Us", etc.
3. **Content Verification** - Confirms the page has a contact form

### 2. Form Field Detection

**CSS Selector Method** (primary):
- Searches for fields using name, ID, placeholder, and aria-label attributes
- Matches against common patterns like "email", "your-email", "e-mail", etc.
- Works for ~60-70% of websites

**LLM Fallback Method** (when selectors fail):
- Extracts form HTML from the page
- Sends it to local Ollama LLM
- LLM analyzes the HTML and returns CSS selectors for each field
- Increases success rate to 85-95%

### 3. Form Submission

1. Fills detected fields with your information
2. Clicks the submit button
3. Waits for submission to complete
4. Checks for success indicators (thank you messages, URL changes, etc.)

## 🐛 Troubleshooting

### Playwright Installation Issues

```bash
# If playwright install fails, try:
python -m playwright install chromium

# On Linux, you may need system dependencies:
sudo playwright install-deps
```

### Ollama Not Working

```bash
# Check if Ollama is running:
curl http://localhost:11434/api/tags

# Start Ollama (if not running):
ollama serve

# Verify model is installed:
ollama list
```

See [LLM_SETUP.md](LLM_SETUP.md) for detailed troubleshooting.

### Low Success Rate

1. **Enable LLM fallback** in `config.py`:
   ```python
   USE_LLM_FALLBACK = True
   ```

2. **Check logs** in `crawler.log` to see why sites are failing

3. **Enable debug features**:
   ```python
   SCREENSHOT_ON_FAILURE = True
   SAVE_HTML_ON_FAILURE = True
   ```

4. **Run in non-headless mode** to watch what's happening:
   ```python
   HEADLESS_MODE = False
   ```

### "No contact page found" for Sites You Know Have One

The contact page might be:
- Behind a menu or hamburger icon
- Using an unusual URL pattern
- Loaded dynamically with JavaScript

Try:
1. Manually finding the contact page URL
2. Adding that pattern to `CONTACT_URL_PATTERNS` in `config.py`

### Rate Limiting / IP Blocking

If you're getting blocked:
1. Increase delays in `config.py`:
   ```python
   MIN_DELAY = 40
   MAX_DELAY = 60
   ```

2. Process fewer sites per session

3. Consider using residential proxies (requires code modification)

## 📈 Performance Expectations

Based on default settings (20-40 second delays):

| Metric | Value |
|--------|-------|
| Processing Speed | 60-90 websites/hour |
| Success Rate (selectors only) | 60-70% |
| Success Rate (with LLM) | 85-95% |
| CPU Usage | Low-Moderate |
| Memory Usage | ~200-500 MB |

### Performance Tips

1. **Faster Processing** - Reduce delays (but increases blocking risk):
   ```python
   MIN_DELAY = 10
   MAX_DELAY = 20
   ```

2. **Higher Success Rate** - Enable LLM and use a better model:
   ```python
   USE_LLM_FALLBACK = True
   OLLAMA_MODEL = "llama3.2"  # or "mistral" for better accuracy
   ```

3. **Lower Resource Usage** - Use a smaller LLM model:
   ```python
   OLLAMA_MODEL = "phi3"  # or "qwen2.5:3b"
   ```

## 🚨 Limitations

1. **JavaScript-Heavy Sites** - Sites that heavily rely on JavaScript frameworks may be harder to parse
2. **CAPTCHAs** - Cannot bypass CAPTCHAs (sites with CAPTCHAs will fail)
3. **Login-Required Forms** - Cannot access forms behind authentication
4. **Dynamic Content** - Forms loaded via AJAX after page load may not be detected
5. **Custom Form Implementations** - Highly custom/unique forms may require manual selector configuration

## ⚖️ Legal & Ethical Considerations

**IMPORTANT**: This tool is for legitimate business outreach only.

✅ **Appropriate Uses**:
- Reaching out to potential business customers
- Partnership inquiries
- Legitimate sales outreach
- Market research (non-intrusive)

❌ **Inappropriate Uses**:
- Spam
- Phishing
- Harassment
- Unauthorized marketing
- Violating website terms of service

**Best Practices**:
1. Only contact businesses relevant to your service
2. Include clear opt-out instructions in your message
3. Respect "Do Not Contact" requests immediately
4. Don't send follow-ups unless there's engagement
5. Ensure your message provides genuine value
6. Comply with CAN-SPAM Act and similar regulations
7. Respect website terms of service
8. Use reasonable delays to avoid overloading servers

**Disclaimer**: You are responsible for how you use this tool. The authors assume no liability for misuse.

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Playwright](https://playwright.dev/) for reliable browser automation
- Uses [Ollama](https://ollama.com/) for free, local AI capabilities
- Inspired by the need for scalable, cost-effective business outreach

## 📞 Support

For issues or questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Review [LLM_SETUP.md](LLM_SETUP.md) for Ollama issues
3. Open an issue on GitHub

## 🗺️ Roadmap

Future enhancements:
- [ ] Proxy support for rotating IPs
- [ ] Multi-threaded processing for faster execution
- [ ] Support for more LLM providers
- [ ] Advanced CAPTCHA detection
- [ ] Dashboard for monitoring progress
- [ ] Email verification before submission
- [ ] A/B testing different message templates

---

**Happy Crawling! 🚀**

Remember: Use responsibly and ethically. Quality outreach beats quantity every time.
