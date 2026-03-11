from backend.infra.db import create_engine_and_session, init_db
from backend.policies.event_log import build_policy_summary, record_policy_hit_events, record_policy_update_events


def test_policy_event_log_tracks_hits_and_latest_changes(tmp_path):
    engine, session_factory = create_engine_and_session(tmp_path / "policy.db")
    init_db(engine)

    with session_factory() as db:
        record_policy_update_events(
            db,
            policy_key="sender_whitelist",
            previous_values=[],
            next_values=["alerts@example.com"],
            actor="admin",
        )
        record_policy_hit_events(
            db,
            analysis_id="analysis-1",
            policy_evaluation={
                "sender_whitelist": "alerts@example.com",
                "sender_blacklist": "",
                "domain_blacklist": "",
            },
        )
        db.commit()

        summary = build_policy_summary(
            db,
            current_policies={
                "sender_whitelist": ["alerts@example.com"],
                "sender_blacklist": [],
                "domain_blacklist": [],
            },
        )

    item = summary["sender_whitelist"][0]
    assert item["value"] == "alerts@example.com"
    assert item["hit_count"] == 1
    assert item["last_hit_at"] is not None
    assert item["last_changed_by"] == "admin"
    assert item["last_change_action"] == "added"
