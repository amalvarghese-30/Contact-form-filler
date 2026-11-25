"""Unit tests for URL/SSRF security validation and field clustering/mapping."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import escape_html, extract_domain, validate_target_url
from app.core.config import get_settings
from form_filler import FieldMeta, build_mapping, interpret_submission_response


def test_validate_target_url_public_https():
    ok, url, err = validate_target_url("example.com/contact")
    assert ok is True
    assert url == "https://example.com/contact"
    assert err == ""


def test_validate_target_url_blocks_private_ip_and_file_scheme():
    for bad in ("file:///etc/passwd", "http://10.0.0.1/admin", "http://169.254.169.254/latest", "http://192.168.1.1"):
        ok, _, err = validate_target_url(bad)
        assert ok is False
        assert err != ""


def test_validate_target_url_localhost_controlled_by_setting():
    settings = get_settings()
    orig = settings.allow_localhost_testing
    try:
        settings.allow_localhost_testing = False
        ok, _, _ = validate_target_url("http://127.0.0.1:8080/test")
        assert ok is False

        settings.allow_localhost_testing = True
        ok, norm, _ = validate_target_url("http://127.0.0.1:8080/test")
        assert ok is True
        assert norm == "http://127.0.0.1:8080/test"
    finally:
        settings.allow_localhost_testing = orig


def test_extract_domain_and_escape_html():
    assert extract_domain("https://Sub.Example.COM/contact") == "sub.example.com"
    assert escape_html('<script>alert("x")</script>') == "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"


def test_build_mapping_classifies_standard_contact_fields():
    fields = [
        FieldMeta(tag="input", type="text", name="fullname", id="fullname", placeholder="Full Name", aria_label="", label_text="Full Name", selector="input#fullname", visible=True),
        FieldMeta(tag="input", type="email", name="email", id="email", placeholder="Email", aria_label="", label_text="Email", selector="input#email", visible=True),
        FieldMeta(tag="input", type="tel", name="phone", id="phone", placeholder="Phone", aria_label="", label_text="Phone", selector="input#phone", visible=True),
        FieldMeta(tag="textarea", type="textarea", name="message", id="message", placeholder="Message", aria_label="", label_text="Message", selector="textarea#message", visible=True),
    ]
    mapping = build_mapping(fields)
    assert mapping.get("fullname") == "input#fullname"
    assert mapping.get("email") == "input#email"
    assert mapping.get("phone") == "input#phone"
    assert mapping.get("message") == "textarea#message"


def test_interpret_submission_response():
    assert interpret_submission_response({"success": True, "message": "Sent"})[0] == "success"
    assert interpret_submission_response({"success": False, "message": "Invalid email"})[0] == "failed"
    assert interpret_submission_response({"foo": "bar"})[0] == "unknown"
