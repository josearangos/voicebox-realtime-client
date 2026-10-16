from app.chunking import make_chunks
from app.teleprompter import render_html

TEXT = "<b>x</b> is bold. <script>alert(1)</script> runs. &amp; stays literal."


def test_user_text_rendered_literally():
    out = render_html(TEXT, make_chunks(TEXT))
    assert "<script" not in out and "<b>" not in out and "</b>" not in out
    assert "&lt;b&gt;x&lt;/b&gt;" in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert "&amp;amp;" in out                      # the literal "&amp;" typed by the user
