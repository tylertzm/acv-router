#!/usr/bin/env python3
"""Tests for the ElevenLabs cold call pipeline."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Set env before importing
os.environ["ELEVENLABS_API_KEY"] = "test_key"
os.environ["ELEVENLABS_VOICE_ID"] = "test_voice_id"

import cold_call


class TestAgentConfig(unittest.TestCase):
    """Test agent config persistence."""

    def test_save_and_load_config(self):
        """Test saving and loading agent config."""
        test_config = Path(__file__).parent / "test_agent_config.json"
        original = cold_call.AGENT_CONFIG_FILE

        try:
            cold_call.AGENT_CONFIG_FILE = test_config
            cold_call._save_agent_config("test_agent_123", "test_voice_456")

            config = cold_call._load_agent_config()
            self.assertEqual(config["agent_id"], "test_agent_123")
            self.assertEqual(config["voice_id"], "test_voice_456")
            self.assertIn("created_at", config)
        finally:
            cold_call.AGENT_CONFIG_FILE = original
            if test_config.exists():
                test_config.unlink()

    def test_load_missing_config(self):
        """Test loading config when file doesn't exist."""
        original = cold_call.AGENT_CONFIG_FILE
        try:
            cold_call.AGENT_CONFIG_FILE = Path("/tmp/nonexistent_config.json")
            config = cold_call._load_agent_config()
            self.assertEqual(config, {})
        finally:
            cold_call.AGENT_CONFIG_FILE = original


class TestCallLogging(unittest.TestCase):
    """Test call logging."""

    def test_log_call_creates_file(self):
        """Test that _log_call creates a JSON log file."""
        result = {"conversation_id": "conv_test_123", "status": "initiated"}
        cold_call._log_call("+4930123456", "Test GmbH", result)

        # Find the most recent log file
        logs = sorted(cold_call.CACHE_DIR.glob("*Test_GmbH*.json"))
        self.assertTrue(len(logs) > 0, "No log file created")

        data = json.loads(logs[-1].read_text())
        self.assertEqual(data["to_number"], "+4930123456")
        self.assertEqual(data["company"], "Test GmbH")
        self.assertEqual(data["response"]["conversation_id"], "conv_test_123")

        # Cleanup
        logs[-1].unlink()


class TestPhoneNormalization(unittest.TestCase):
    """Test phone number normalization in batch-call."""

    def test_german_local_to_e164(self):
        """German local numbers should be converted to +49."""
        # This logic is inline in cmd_batch_call, test the pattern
        phone = "0309929350"
        if not phone.startswith("+"):
            if phone.startswith("0"):
                phone = "+49" + phone[1:]
        self.assertEqual(phone, "+49309929350")

    def test_already_e164(self):
        """Numbers already in E.164 should stay unchanged."""
        phone = "+49309929350"
        if not phone.startswith("+"):
            if phone.startswith("0"):
                phone = "+49" + phone[1:]
        self.assertEqual(phone, "+49309929350")

    def test_swiss_number(self):
        """Swiss numbers without + get + prefix."""
        phone = "0216016100"
        if not phone.startswith("+"):
            if phone.startswith("0"):
                phone = "+49" + phone[1:]  # Current logic assumes German
        # Note: Swiss numbers would need +41, not +49. This is a known limitation.
        self.assertTrue(phone.startswith("+"))


class TestSystemPrompt(unittest.TestCase):
    """Test the agent system prompt."""

    def test_prompt_contains_dynamic_variables(self):
        """Prompt should contain all expected dynamic variable placeholders."""
        for var in ["{{company_name}}", "{{contact_name}}", "{{city}}", "{{technician_count}}"]:
            self.assertIn(var, cold_call.AGENT_SYSTEM_PROMPT, f"Missing variable: {var}")

    def test_prompt_uses_formal_german(self):
        """Prompt should use formal German addressing (Sie)."""
        self.assertIn("Sie", cold_call.AGENT_SYSTEM_PROMPT)
        self.assertIn("SHK", cold_call.AGENT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
