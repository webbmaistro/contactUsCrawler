"""Ollama chain/franchise filter (optional)."""

import os
from typing import Optional

import requests

from lead_gen import config


def use_ollama_chain_filter() -> bool:
    """Whether to use Ollama for chain detection. Env LEAD_GEN_USE_OLLAMA_CHAIN=0 disables."""
    env = os.environ.get("LEAD_GEN_USE_OLLAMA_CHAIN", "").strip().lower()
    if env in ("0", "false", "no", "off"):
        return False
    if env in ("1", "true", "yes", "on"):
        return True
    return config.USE_OLLAMA_CHAIN_FILTER


def ollama_available() -> bool:
    """Check if Ollama is running and the model is installed."""
    if not use_ollama_chain_filter():
        return False
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code != 200:
            return False
        models = r.json().get("models", [])
        names = [m.get("name", "") for m in models]
        return any(config.OLLAMA_MODEL in n for n in names)
    except requests.RequestException:
        return False


def is_chain_restaurant_ollama(name: str, domain: str) -> bool:
    """
    Ask Ollama if this restaurant is likely a chain/franchise.
    Returns True if chain (skip), False if independent or on error (proceed).
    """
    if not use_ollama_chain_filter():
        return False
    prompt = (
        f"Is this restaurant a chain or franchise (e.g. McDonald's, Chipotle, Starbucks)? "
        f"Consider the name and website domain.\n"
        f"Restaurant name: {name}\n"
        f"Website domain: {domain}\n"
        f"Answer with exactly one word: yes or no."
    )
    try:
        r = requests.post(
            config.OLLAMA_API_URL,
            json={
                "model": config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 10},
            },
            timeout=config.OLLAMA_CHAIN_TIMEOUT,
        )
        if r.status_code != 200:
            return False
        text = (r.json().get("response") or "").strip().lower()
        return "yes" in text.split() or text.startswith("yes")
    except requests.RequestException:
        return False
