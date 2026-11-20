"""Create the versioned Windows demo in a separate, atomically published profile."""

import shutil
from uuid import uuid4

from cyberforge.application.accounts import AccountService
from cyberforge.application.demo import initialize_demo
from cyberforge.application.learner_demo import prepare_publication
from cyberforge.domain.accounts import ApplicationError
from cyberforge.persistence.profile import PrivateProfile
from cyberforge.persistence.recovery import ProfileRecovery

DEMO_DIRECTORY = "CyberForge-demo-v1"
CREDENTIALS_NAME = "demo-credentials.json"
LESSON = "lesson-v1"


def prepare_demo_profile(
    container: PrivateProfile, *, initialize: bool
) -> PrivateProfile:
    """Perform explicit setup while the caller holds the container process lock."""
    active = container.root / LESSON
    container.validate(active, directory=True, missing=True)
    if active.exists():
        return PrivateProfile(active)
    if not initialize:
        raise ApplicationError(
            "Демонстрацію ще не підготовлено. Запустіть з --demo-profile --init-demo."
        )
    draft = container.directory("seed-" + uuid4().hex)
    try:
        profile = PrivateProfile(draft)
        with profile.acquire():
            database = ProfileRecovery(profile).startup()
            try:
                credentials = profile.root / CREDENTIALS_NAME
                accounts = AccountService(database)
                initialize_demo(accounts, credentials)
                profile.validate(credentials)
                prepare_publication(accounts, credentials)
            finally:
                database.close()
        if active.exists():
            raise ApplicationError("Демонстраційний профіль уже існує.")
        draft.rename(active)
        return PrivateProfile(active)
    finally:
        if draft.exists():
            shutil.rmtree(draft, ignore_errors=True)
