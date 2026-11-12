"""Catalog ID validation and lossless handling of baseline free-text snapshots."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from cyberforge.application.accounts import AccountService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.domain.nist_cues import CATALOG_ID, CUES, NistCueId
from cyberforge.domain.scenarios import ScenarioParameters, stored_parameters
from cyberforge.persistence.database import Database


@pytest.mark.parametrize(
    "extra",
    [
        {"nist_cues": ["unknown"]},
        {"nist_cues": ["Sense of urgency"]},
        {"nist_cues": ["B.4.4", "B.4.4"]},
        {"nist_cue_catalog": "unverified"},
    ],
)
def test_unknown_duplicate_or_unverified_cues_rejected(extra):
    with pytest.raises(ValidationError):
        ScenarioParameters(topic="Синтетична тема", difficulty="beginner", **extra)


def test_catalog_selects_all_and_keeps_custom_tactics_separate(scenario_env):
    env = scenario_env
    source = dict(
        topic="Синтетична тема",
        difficulty="beginner",
        nist_cues=tuple(NistCueId),
        tactics=("Власна тактика",),
    )
    scenario = env.service.create(env.tokens["teacher"], source)
    assert scenario.parameters.nist_cue_catalog == CATALOG_ID
    assert len(scenario.parameters.nist_cues) == 23
    assert len({cue.cue_type for cue in CUES}) == 5
    assert scenario.parameters.tactics == ("Власна тактика",)
    restored = env.service.get(env.tokens["teacher"], scenario.id)
    assert restored.parameters.nist_cues == tuple(NistCueId)
    with pytest.raises(ApplicationError):
        env.service.create(
            env.tokens["teacher"], source | {"nist_cues": ("Власна тактика",)}
        )


@pytest.mark.parametrize("status", ["draft", "published"])
def test_legacy_names_remain_unmapped_and_raw_snapshots_unchanged(scenario_env, status):
    env = scenario_env
    token = env.tokens["teacher"]
    original = env.service.create(
        token, dict(topic="Синтетична тема", difficulty="beginner")
    )
    legacy = dict(
        topic="Синтетична тема",
        difficulty="beginner",
        nist_cues=["Spelling and grammar irregularities", "B.4.4", "Власний опис"],
    )
    raw = json.dumps(legacy, ensure_ascii=False)
    with env.database.engine.begin() as db:
        db.execute(
            text(
                "UPDATE scenario_versions SET parameters=:p, status=:s "
                "WHERE scenario_id=:id"
            ),
            dict(p=raw, s=status, id=original.id),
        )
    read = env.service.get(token, original.id)
    assert read.parameters.nist_cues == ()
    assert read.parameters.legacy_nist_cues == tuple(legacy["nist_cues"])
    # No display-text matching, even if a label or an ID appears to be exact.
    assert stored_parameters(legacy) == read.parameters
    same = env.service.update(
        token, original.id, read.parameters, expected_version=1, expected_revision=1
    )
    assert same == read
    new = env.service.update(
        token,
        original.id,
        read.parameters.model_dump()
        | {"topic": "Оновлена тема", "nist_cues": ("B.4.4",)},
        expected_version=1,
        expected_revision=1,
    )
    assert new.parameters.nist_cues == (NistCueId.URGENCY,)
    assert new.parameters.legacy_nist_cues == read.parameters.legacy_nist_cues
    with pytest.raises(ApplicationError, match="некласифіковані"):
        env.service.update(
            token,
            original.id,
            new.parameters.model_dump() | {"legacy_nist_cues": ()},
            expected_version=new.version,
            expected_revision=new.revision,
        )
    if status == "published":
        assert new.version == 2
        with env.database.engine.connect() as db:
            assert (
                db.execute(
                    text(
                        "SELECT parameters FROM scenario_versions "
                        "WHERE scenario_id=:id AND number=1"
                    ),
                    {"id": original.id},
                ).scalar()
                == raw
            )
    reopened = Database(Path(env.database.engine.url.database))
    reopened.upgrade()
    try:
        accounts = AccountService(reopened)
        assert (
            ScenarioService(accounts)
            .get(accounts.login("teacher", env.password), new.id)
            .parameters
            == new.parameters
        )
    finally:
        reopened.close()


def test_unknown_stored_catalog_fails_safely_without_mutation(scenario_env):
    env = scenario_env
    token = env.tokens["teacher"]
    original = env.service.create(
        token, dict(topic="Синтетична тема", difficulty="beginner")
    )
    raw = json.dumps(
        dict(
            topic="Синтетична тема",
            difficulty="beginner",
            nist_cue_catalog=CATALOG_ID,
            nist_cues=["unverified-id"],
        )
    )
    with env.database.engine.begin() as db:
        db.execute(text("UPDATE scenario_versions SET parameters=:p"), {"p": raw})
    with pytest.raises(ApplicationError, match="не підтримуються"):
        env.service.get(token, original.id)
    with pytest.raises(ApplicationError, match="не підтримуються"):
        env.service.update(
            token,
            original.id,
            original.parameters,
            expected_version=1,
            expected_revision=1,
        )
    with env.database.engine.connect() as db:
        assert (
            db.execute(text("SELECT parameters FROM scenario_versions")).scalar() == raw
        )
