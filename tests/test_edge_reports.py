"""The Edge-vetting panel on the three assess report templates - same pattern
as the micro-synthesis panel: presentation only, badged articulation-only, and
absent when no Edge data rode along."""
import json
from pathlib import Path

from engine.assess import assess_player
from reports.render import render_html
from schemas import ForwardMicroCard, GoalieCard, SkaterCard, GoalieEdgeCard, SkaterEdgeCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _wedgewood_card() -> GoalieCard:
    return GoalieCard(
        name="Scott Wedgewood", age=33, role="Starter", proj_war_pct=85,
        even_strength=80, penalty_kill=60, high_danger=82, med_danger=70,
        low_danger=65, quality_starts=88, excellent_starts=70, bad_starts=75,
        rebound_control=60, consistency=55,
    )


def test_skater_report_gains_the_edge_panel():
    a = assess_player(
        SkaterCard(**_load("hughes.json")),
        edge_card=SkaterEdgeCard(**_load("hughes_edge.json")),
    )
    html = render_html("assess_skater", a.model_dump())
    assert "NHL Edge" in html
    assert "Articulation only" in html
    assert "45.1" in html          # the corroboration's receipt renders


def test_skater_report_without_edge_has_no_panel():
    a = assess_player(SkaterCard(**_load("hughes.json")))
    html = render_html("assess_skater", a.model_dump())
    assert "NHL Edge" not in html


def test_goalie_report_gains_the_edge_panel():
    a = assess_player(
        _wedgewood_card(), edge_card=GoalieEdgeCard(**_load("wedgewood_edge.json"))
    )
    html = render_html("assess_goalie", a.model_dump())
    assert "NHL Edge" in html
    assert ".837" in html


def test_goalie_report_without_edge_has_no_panel():
    html = render_html("assess_goalie", assess_player(_wedgewood_card()).model_dump())
    assert "NHL Edge" not in html


def test_micro_report_gains_the_edge_panel():
    m = lambda v, avg=None, pct=None: {"value": v, "avg": avg, "percentile": pct}
    edge = SkaterEdgeCard(
        card_kind="edge", name="Macklin Celebrini", season="2025-26",
        position="F", gp=70,
        hardest_shot=m(88.0), max_skating_speed=m(22.8, None, 80),
        most_miles_per_game=m(4.1, None, 90),
        sog_all=m(200, 86, 95), sog_high_danger=m(60, 32, 90),
        sog_mid_range=m(80, 27, 92), sog_long_range=m(12, 8, 70),
        zone_time_defensive=m(37.0, 40.1, 90), zone_time_neutral=m(17.0, 16.8),
        zone_time_offensive=m(46.0, 43.1, 90),
    )
    a = assess_player(ForwardMicroCard(**_load("celebrini_micro.json")), edge_card=edge)
    html = render_html("assess_micro", a.model_dump())
    assert "NHL Edge" in html
    assert "46.0" in html


def test_edge_caveats_render_in_the_panel():
    a = assess_player(
        SkaterCard(**_load("hughes.json")),
        edge_card=SkaterEdgeCard(**_load("hughes_edge.json")),
    )
    html = render_html("assess_skater", a.model_dump())
    from markupsafe import escape

    for caveat in a.edge_vetting.caveats:
        assert str(escape(caveat))[:40] in html
