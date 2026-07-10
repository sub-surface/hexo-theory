from __future__ import annotations

from connectn_lab.theory_book import build_markdown, inline_markdown, markdown_to_html, summarize_corpus


def test_inline_markdown_code_spans():
    assert inline_markdown("count `tau` first") == "count <code>tau</code> first"


def test_markdown_to_html_rewrites_report_image_paths():
    html = markdown_to_html("![cap](../reports/connect6_theory_book_evidence/figures/a.png)\n\n*caption*")
    assert 'src="connect6_theory_book_evidence/figures/a.png"' in html
    assert "<figcaption>caption</figcaption>" in html


def test_summarize_corpus_degrades_without_results(tmp_path):
    summary = summarize_corpus(tmp_path)
    assert summary.opening_rows == 0
    assert summary.self_play_games == 0
    assert summary.atom_count == 0
    markdown = build_markdown(summary)
    assert "The Little Book of Seeded Connect6" in markdown
    assert "one-cap cooling" in markdown
