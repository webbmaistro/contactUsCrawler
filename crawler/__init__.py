"""
Restaurant Contact Form Crawler package.
Automatically finds and submits contact forms on restaurant websites.
"""

from crawler.logger import Logger
from crawler.llm import OllamaLLM
from crawler.contact_finder import ContactPageFinder
from crawler.form_detector import FormFieldDetector
from crawler.runner import ContactFormCrawler, main

__all__ = [
    "Logger",
    "OllamaLLM",
    "ContactPageFinder",
    "FormFieldDetector",
    "ContactFormCrawler",
    "main",
]
