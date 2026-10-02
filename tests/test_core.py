from datetime import datetime, timedelta, timezone

from leadradar.db import Store
from leadradar.models import Item, Lead
from leadradar.pipeline import fair_share
from leadradar.report import write
from leadradar.sources import apify, reddit
from leadradar.notify import telegram, texts

NOW = datetime.now(timezone.utc)


def item(source="web:x.com", n=0, **kw):
    return Item(source=source, native_id=f"id{n}", url=f"https://example.com/{n}", text="hello " * 10, created_at=NOW - timedelta(minutes=n), **kw)


def test_item_id_uses_source_family():
    assert item("web:linkedin.com").id == "web:id0"


def test_reddit_queries_are_folded_with_or():
    groups = reddit._query_groups([f"q{i}" for i in range(8)], size=6)
    assert len(groups) == 2
    assert groups[0].startswith('"q0" OR "q1"')


def test_reddit_targets_use_one_multireddit():
    assert reddit._targets({"subreddits": ["a", "r/b"], "global_search": False}) == ["r/a+b"]
    assert reddit._targets({"subreddits": []}) == [""]


def test_apify_pick_and_fill():
    row = {"author": {"name": "Ana"}, "items": [{"u": "x"}]}
    assert apify._pick(row, "author.name") == "Ana"
    assert apify._pick(row, "items.0.u") == "x"
    assert apify._pick(row, "missing.path") == ""
    assert apify._fill({"q": "{queries}", "n": 5}, ["a", "b"], None) == {"q": ["a", "b"], "n": 5}
    assert apify._fill({"q": "{query}"}, ["a"], "a") == {"q": "a"}


def test_apify_parse_date_handles_ms_and_iso():
    assert apify._parse_date(1790910562692).year == 2026
    assert apify._parse_date("2026-10-02T03:09:22.692Z").tzinfo is not None
    assert apify._parse_date("") is None


def test_fair_share_round_robins_sources():
    items = [item("workana", i) for i in range(10)] + [item("hackernews", 100 + i) for i in range(2)]
    picked = fair_share(items, 4)
    assert [p.source for p in picked].count("hackernews") == 2


def test_store_dedupes_and_report_renders(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    it = item()
    assert store.unseen([it]) == [it]
    store.mark_seen([it])
    assert store.unseen([it]) == []
    lead = Lead(item=it, score=90, intent="seeking_provider", lang="en", summary="s", why="w", draft="</script><!--<script>")
    store.save_leads([lead])
    page = write(store, str(tmp_path / "out"), 70).read_text(encoding="utf-8")
    assert "</script><!--" not in page  # data can't open/close tags inside the script
    assert page.count("</script>") == 1
    assert (tmp_path / "out" / "leads.csv").exists()


def test_telegram_card_escapes_html():
    lead = Lead(item=item(title="<b>x</b>"), score=80, intent="asking_how", lang="es", summary="a & b", why="w", draft="d")
    card = telegram.card(lead, texts("es"))
    assert "&lt;b&gt;x&lt;/b&gt;" in card and "a &amp; b" in card
    assert "Pregunta cómo" in card


def test_agentreach_parsers():
    from leadradar.sources import agentreach

    listing = {"data": {"children": [{"data": {"permalink": "/r/a/1", "name": "t3_1"}}]}}
    assert agentreach._reddit_posts(listing)[0]["name"] == "t3_1"
    assert agentreach._reddit_posts(None) == []
    assert agentreach._tweet_time("Wed Oct 01 12:00:00 +0000 2026").tzinfo is not None
    assert agentreach._tweet_time("") is None


def test_canonical_url_merges_variants():
    from leadradar.pipeline import canonical_url

    assert canonical_url("https://www.linkedin.com/posts/x?utm=1") == canonical_url("https://linkedin.com/posts/x/")
    assert canonical_url("https://twitter.com/a/status/1") == canonical_url("https://x.com/a/status/1")


def test_generator_maps_every_field_into_example_config():
    from pathlib import Path

    import yaml

    from leadradar import generator

    example = yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))
    fake = generator.Generated(
        offer="SEO", ideal_client="shops", not_a_fit="students", tone="warm", report_language="es",
        queries=["busco seo"], keywords=["seo"], job_board_queries=["seo audit"], linkedin_queries=["busco seo"],
        subreddits=["SEO"], exclude=["curso"], extra_sites=["community.shopify.com"], bluesky_langs=["es"], workana=True,
    )

    from leadradar import llm

    class FakeLLM:
        def __init__(self, scoring):
            pass

        def parse(self, *a, **kw):
            return llm.Result(fake, "ok")

    orig = llm.LLM
    llm.LLM = FakeLLM
    try:
        cfg = generator.generate("SEO freelancer", example, provider="gemini")
    finally:
        llm.LLM = orig
    assert cfg["scoring"]["provider"] == "gemini" and cfg["scoring"]["model"] == "gemini-3.8-flash"
    assert cfg["queries"] == ["busco seo"]
    assert cfg["sources"]["workana"]["enabled"] is True
    assert "community.shopify.com" in cfg["sources"]["web"]["sites"]
    assert yaml.safe_load(generator.dump(cfg, "SEO"))["profile"]["offer"].startswith("SEO")


def test_same_post_from_another_source_is_not_new_next_run(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    via_web = Item(source="web:linkedin.com", native_id="a", url="https://www.linkedin.com/posts/abc?utm=x")
    via_apify = Item(source="apify:linkedin.com", native_id="b", url="https://linkedin.com/posts/abc")
    store.mark_seen([via_web])
    assert store.unseen([via_apify]) == []


def test_bump_tries_gives_up_after_limit(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    it = item()
    assert store.bump_tries([it], limit=2) == []
    assert store.bump_tries([it], limit=2) == [it]


def test_naive_datetimes_become_utc():
    it = Item(source="x", native_id="1", url="https://x.com/1", created_at=datetime(2026, 1, 1))
    assert it.created_at.tzinfo is not None
    assert it.created_at < NOW  # comparison with aware datetimes no longer crashes


def test_empty_yaml_blocks_keep_defaults():
    from leadradar.config import DEFAULTS, _merge

    cfg = _merge(DEFAULTS, {"notify": {"discord": None}, "sources": {"rss": {"enabled": True, "feeds": None}}})
    assert cfg["notify"]["discord"] == {"enabled": False}
    assert cfg["sources"]["rss"]["feeds"] == []


def test_report_drops_non_http_links(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    bad = Item(source="scrape:x", native_id="1", url="javascript:alert(1)", text="t" * 30)
    store.save_leads([Lead(item=bad, score=90, intent="job_post", lang="en", summary="s", why="w", draft="")])
    page = write(store, str(tmp_path / "out"), 70).read_text(encoding="utf-8")
    assert "javascript:alert" not in page


def test_telegram_card_fits_even_with_heavy_escaping():
    lead = Lead(item=item(title="&" * 500), score=80, intent="asking_how", lang="en",
                summary="<" * 400, why=">" * 400, draft="&" * 5000)
    card = telegram.card(lead, texts("en"))
    assert len(card) <= 4000
    assert card.endswith("</blockquote>")


def test_workana_relative_dates():
    from leadradar.sources.workana import parse_relative

    assert (NOW - parse_relative("Hace 16 horas", NOW)).total_seconds() == 16 * 3600
    assert (NOW - parse_relative("Ayer", NOW)).days == 1
    assert (NOW - parse_relative("Publicado: Hace 2 semanas", NOW)).days == 14
    assert (NOW - parse_relative("Hace 4 d�as", NOW)).days == 4  # mis-decoded accent still works
    assert parse_relative("???", NOW) is None


def test_dates_decoded_from_linkedin_and_x_ids():
    from leadradar.sources.web import date_from_url

    li = date_from_url("https://www.linkedin.com/posts/someone_activity-7511623336741855232-gzwf")
    assert li.isoformat().startswith("2026-10-02T03:09:22")
    assert date_from_url("https://x.com/a/status/1975000000000000000").year == 2025
    assert date_from_url("https://example.com/post/1") is None


def test_vendor_and_non_request_scores_are_capped():
    from leadradar import scorer

    items = [item(n=i) for i in range(3)]
    verdicts = scorer.Verdicts(results=[
        scorer.Verdict(index=0, author_role="vendor", explicit_request=True, fits_offer=True, is_lead=True, score=90, intent="seeking_provider", lang="en", summary="", why="", draft="hi"),
        scorer.Verdict(index=1, author_role="buyer", explicit_request=False, fits_offer=True, is_lead=True, score=90, intent="asking_how", lang="en", summary="", why="", draft="hi"),
        scorer.Verdict(index=2, author_role="buyer", explicit_request=True, fits_offer=True, is_lead=True, score=90, intent="seeking_provider", lang="en", summary="", why="", draft="hi"),
    ])

    from leadradar.llm import Result

    class FakeLLM:
        def parse(self, *a, **kw):
            return Result(verdicts, "ok", usage={"input": 1, "output": 1, "cache_read": 0, "cache_write": 0})

    s = scorer.Scorer.__new__(scorer.Scorer)
    s.llm, s.system, s.rejected = FakeLLM(), "", []
    s.usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    scores = [l.score for l in s._score_batch(items)]
    assert scores == [30, 55, 90]


def _fake_openai_completion(parsed=None, refusal=None):
    from types import SimpleNamespace as NS

    msg = NS(parsed=parsed, refusal=refusal)
    usage = NS(prompt_tokens=100, completion_tokens=20, prompt_tokens_details=NS(cached_tokens=40))
    return NS(choices=[NS(message=msg, finish_reason="stop")], usage=usage)


def test_openai_and_gemini_providers(monkeypatch):
    from leadradar import llm, scorer

    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    gem = llm.LLM({"provider": "gemini"})
    assert gem.model == "gemini-3.8-flash"
    assert "generativelanguage.googleapis.com" in str(gem.client.base_url)

    oai = llm.LLM({"provider": "openai"})
    calls = []
    verdicts = scorer.Verdicts(results=[])

    class Completions:
        @staticmethod
        def parse(**kw):
            calls.append(kw)
            return _fake_openai_completion(parsed=verdicts)

    oai.client = type("C", (), {"chat": type("Ch", (), {"completions": Completions})})()
    r = oai.parse("sys", "user", scorer.Verdicts)
    assert r.stop == "ok" and r.parsed is verdicts
    assert r.usage == {"input": 100, "output": 20, "cache_read": 40, "cache_write": 0}
    assert calls[0]["max_completion_tokens"] == 16000 and calls[0]["reasoning_effort"] == "low"
    assert calls[0]["messages"][0] == {"role": "system", "content": "sys"}
    assert abs(oai.cost(r.usage) - (60 * 0.25 + 20 * 2.0 + 40 * 0.025) / 1e6) < 1e-12

    Completions.parse = staticmethod(lambda **kw: _fake_openai_completion(refusal="no"))
    assert oai.parse("s", "u", scorer.Verdicts).stop == "refusal"


def test_missing_key_and_bad_provider_are_clear(monkeypatch):
    import pytest

    from leadradar import llm

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        llm.LLM({"provider": "gemini"})
    with pytest.raises(SystemExit, match="provider must be one of"):
        llm.LLM({"provider": "bard"})
