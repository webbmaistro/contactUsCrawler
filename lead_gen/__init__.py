"""
Compliant Restaurant Lead-Gen Bot package.
Collects: Restaurant Name → Website → Public Email (from their own website).
Uses Google Places and Geoapify Places in parallel; restaurant website; public business emails only.
"""

# Ensure config (and logging) is loaded when package is used
from lead_gen import config  # noqa: F401

from lead_gen.pipeline import run_pipeline, main

__all__ = ["run_pipeline", "main", "config"]
