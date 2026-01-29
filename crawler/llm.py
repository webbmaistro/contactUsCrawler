"""Interface to Ollama for AI-powered form field detection."""

import json
import re
from typing import Dict, Optional

import requests

import config

from crawler.logger import Logger


class OllamaLLM:
    """Interface to Ollama for AI-powered form field detection."""

    def __init__(self, logger: Logger):
        self.logger = logger
        self.api_url = config.OLLAMA_API_URL
        self.model = config.OLLAMA_MODEL
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if Ollama is available and the model is installed."""
        if not config.USE_LLM_FALLBACK:
            return False

        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]

                if any(self.model in name for name in model_names):
                    self.logger.info(f"Ollama is available with model: {self.model}")
                    return True
                else:
                    self.logger.warning(
                        f"Ollama is running but model '{self.model}' not found. "
                        f"Available models: {', '.join(model_names)}"
                    )
                    return False
            return False
        except requests.RequestException:
            self.logger.warning("Ollama is not available. LLM fallback disabled.")
            return False

    def detect_form_fields(self, html: str) -> Optional[Dict[str, str]]:
        """Use LLM to detect form field selectors from HTML."""
        if not self.available:
            return None

        prompt = f"""Analyze this HTML form and identify CSS selectors for the contact form fields.
Return ONLY a valid JSON object with these keys: "name", "email", "message", "phone", "submit".
For each key, provide the best CSS selector (id, name, or other attribute) to find that field.
If a field doesn't exist, use an empty string "".

HTML:
{html[:3000]}

Respond with ONLY the JSON object, no explanation:"""

        try:
            self.logger.debug("Calling Ollama LLM for form field detection...")

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.LLM_TEMPERATURE,
                    "num_predict": config.LLM_MAX_TOKENS
                }
            }

            response = requests.post(self.api_url, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                llm_response = result.get("response", "")

                # Try to extract JSON from response
                json_match = re.search(r'\{[^{}]*\}', llm_response)
                if json_match:
                    selectors = json.loads(json_match.group())
                    self.logger.debug(f"LLM detected selectors: {selectors}")
                    return selectors
                else:
                    self.logger.warning("LLM response did not contain valid JSON")
                    return None
            else:
                self.logger.error(f"Ollama API error: {response.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Error calling Ollama: {str(e)}")
            return None
