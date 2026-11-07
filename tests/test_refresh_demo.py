"""
tests/test_refresh_demo.py

Unit tests for the demo-refresh tooling in scripts/refresh_demo.py —
the stamping/provenance helpers only. The pipeline invocation in
generate_report() is the real CLI path and is exercised end-to-end
by running the script from the repository root, not here.
"""

import pytest

import scripts.refresh_demo as rd

# ── stamp_html: idempotent, renders identical HTML ─────────────────


class TestStampHtml:
    """Exactly one current stamp, anchored after the charset meta."""

    def test_inserts_exactly_one_stamp(self):
        html = "<!DOCTYPE html><html><head>" \
               '<meta charset="UTF-8"></head><body></body></html>'
        stamped = rd.stamp_html(html, generated_on="2026-11-03", sha="a" * 40)

        assert stamped.count("demo-sha: " + "a" * 40) == 1

    def test_stamped_body_content_unchanged(self):
        """The stamp is an invisible HTML comment; rendering is untouched."""
        html = '<!DOCTYPE html><meta charset="UTF-8"><body><h1>x</h1></body>'
        stamped = rd.stamp_html(html, generated_on="2026-11-03", sha="b" * 40)

        assert "<body><h1>x</h1></body>" in stamped
        assert rd.ANCHOR + "\n<!-- Generated on 2026-11-03" in stamped

    def test_restamp_replaces_old_stamp(self):
        """Re-running the script must not stack stamps."""
        html = '<!DOCTYPE html><meta charset="UTF-8">'
        first = rd.stamp_html(html, generated_on="2026-11-01", sha="a" * 40)
        second = rd.stamp_html(first, generated_on="2026-11-03", sha="b" * 40)

        assert second.count("demo-sha:") == 1
        assert "demo-sha: " + "b" * 40 in second
        assert "demo-sha: " + "a" * 40 not in second

    def test_stamp_is_two_well_formed_comments(self):
        """The provenance block must not nest one comment in another:
        the parser closes at the inner '-->' and leaks the remainder
        as visible text above the report."""
        html = '<!DOCTYPE html><meta charset="UTF-8"><body></body>'
        stamped = rd.stamp_html(
            html, generated_on="2026-11-03", sha="d" * 40
        )

        lines = stamped.split(rd.ANCHOR, 1)[1].lstrip("\n").splitlines()
        assert lines[0].startswith("<!-- Generated on 2026-11-03")
        assert lines[0].endswith("-->") and "demo-sha" not in lines[0]
        assert lines[1] == "<!-- demo-sha: " + "d" * 40 + " -->"

    def test_missing_anchor_fails_loudly(self):
        with pytest.raises(SystemExit):
            rd.stamp_html("<p>no anchor</p>",
                          generated_on="2026-11-03", sha="c" * 40)
