import time

from services.orchestrator.app.main import CENTERS, rank, select_centers
from services.shared.schemas import Specialty


def test_every_case_has_centers_and_one_live_agent():
    for s in Specialty:
        hs = select_centers(s)
        assert hs, s
        assert [h.live for h in hs].count(True) == 1 and hs[0].live


def test_capabilities_match_the_case():
    for h in select_centers(Specialty.stroke_thrombectomy):
        assert CENTERS[h.hospital_id]["capabilities"]["thrombectomy"]["value"] is True
    for h in select_centers(Specialty.cardiac_icu):
        assert CENTERS[h.hospital_id]["capabilities"]["cardiac_icu"]["value"] is True
    assert "delta_health" not in {h.hospital_id for h in select_centers(Specialty.stroke_thrombectomy)}


def test_nothing_outside_the_window_by_default():
    for s in Specialty:
        assert all(h.transport.tier != "outside" for h in select_centers(s))


def test_bed_memory_skips_recent_declines():
    mem = {"ummc": {"status": "declined", "ts": time.time()}}
    ids = {h.hospital_id for h in select_centers(Specialty.cardiac_icu, mem)}
    assert "ummc" not in ids and "delta_health" in ids


def test_rank_orders_by_treatment_start():
    t = {"est_ground_min": 10, "est_air_min": 10}
    r = rank([{"status": "available", "treatment_start_min": 90, "transport": t},
              {"status": "declined", "treatment_start_min": None, "transport": t},
              {"status": "available", "treatment_start_min": 52, "transport": t}])
    assert [x["treatment_start_min"] for x in r] == [52, 90]
