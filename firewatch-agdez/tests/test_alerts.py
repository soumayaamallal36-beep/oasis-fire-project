import pytest
from src.alerts.email_alert import EmailAlert
from src.alerts.slack_alert import SlackAlert

def test_email_alert_initialization():
    alert = EmailAlert()
    assert alert.smtp_port == 587
    assert alert.cooldown_hours == 4

def test_slack_alert_initialization():
    alert = SlackAlert()
    assert alert.cooldown_hours == 4

def test_slack_blocks_generation():
    alert = SlackAlert()
    blocks = alert._build_blocks("Élevé", 0.9, ["Vent fort"])
    assert len(blocks) == 4
    assert blocks[0]["type"] == "header"
