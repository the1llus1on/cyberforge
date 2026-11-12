"""Desired email cues from NIST TN 2276 (2023), Table 1 / Appendix B.

IDs are the publication's Appendix B section references, scoped by CATALOG_ID.
Ukrainian labels are CyberForge translations, not official NIST translations.
No cue presence, cue count, premise alignment, or detection score is inferred.
"""

from dataclasses import dataclass
from enum import StrEnum

CATALOG_ID = "nist-tn-2276:2023"
SOURCE_URL = "https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2276.pdf"


class NistCueId(StrEnum):
    SPELLING_GRAMMAR = "B.1.1"
    INCONSISTENCY = "B.1.2"
    ATTACHMENT_TYPE = "B.2.1"
    SENDER_IDENTITY = "B.2.2"
    URL_HYPERLINKING = "B.2.3"
    DOMAIN_SPOOFING = "B.2.4"
    MINIMAL_BRANDING = "B.3.1"
    IMITATED_BRANDING = "B.3.2"
    UNPROFESSIONAL_DESIGN = "B.3.3"
    SECURITY_ICONS = "B.3.4"
    LEGAL_LANGUAGE = "B.4.1"
    DISTRACTING_DETAIL = "B.4.2"
    SENSITIVE_INFORMATION = "B.4.3"
    URGENCY = "B.4.4"
    THREATENING_LANGUAGE = "B.4.5"
    GENERIC_GREETING = "B.4.6"
    MISSING_SIGNER_DETAILS = "B.4.7"
    HUMANITARIAN_APPEAL = "B.5.1"
    TOO_GOOD_OFFER = "B.5.2"
    SPECIAL_RECIPIENT = "B.5.3"
    LIMITED_TIME = "B.5.4"
    BUSINESS_PROCESS = "B.5.5"
    IMPERSONATION = "B.5.6"


@dataclass(frozen=True)
class CueType:
    source_name: str
    label: str


@dataclass(frozen=True)
class NistCue:
    id: NistCueId
    cue_type: CueType
    source_name: str
    label: str


ERROR = CueType("Error", "Помилки")
TECHNICAL = CueType("Technical indicator", "Технічні індикатори")
VISUAL = CueType("Visual presentation indicator", "Візуальні індикатори")
LANGUAGE = CueType("Language and content", "Мова та зміст")
TACTIC = CueType("Common tactic", "Поширені тактики")

CUES = (
    NistCue(
        NistCueId.SPELLING_GRAMMAR,
        ERROR,
        "Spelling and grammar irregularities",
        "Орфографічні та граматичні помилки",
    ),
    NistCue(NistCueId.INCONSISTENCY, ERROR, "Inconsistency", "Неузгодженості"),
    NistCue(NistCueId.ATTACHMENT_TYPE, TECHNICAL, "Attachment type", "Тип вкладення"),
    NistCue(
        NistCueId.SENDER_IDENTITY,
        TECHNICAL,
        "Sender display name and email address",
        "Відображуване ім’я та адреса відправника",
    ),
    NistCue(
        NistCueId.URL_HYPERLINKING, TECHNICAL, "URL hyperlinking", "Гіперпосилання URL"
    ),
    NistCue(NistCueId.DOMAIN_SPOOFING, TECHNICAL, "Domain spoofing", "Підміна домену"),
    NistCue(
        NistCueId.MINIMAL_BRANDING,
        VISUAL,
        "No/minimal branding and logos",
        "Відсутній або мінімальний брендинг і логотипи",
    ),
    NistCue(
        NistCueId.IMITATED_BRANDING,
        VISUAL,
        "Logo imitation or out-of-date branding/logos",
        "Імітація або застарілі брендинг і логотипи",
    ),
    NistCue(
        NistCueId.UNPROFESSIONAL_DESIGN,
        VISUAL,
        "Unprofessional looking design or formatting",
        "Непрофесійний дизайн або форматування",
    ),
    NistCue(
        NistCueId.SECURITY_ICONS,
        VISUAL,
        "Security indicators and icons",
        "Індикатори та значки безпеки",
    ),
    NistCue(
        NistCueId.LEGAL_LANGUAGE,
        LANGUAGE,
        "Legal language/copyright info/disclaimers",
        "Юридичні формулювання, авторське право, застереження",
    ),
    NistCue(
        NistCueId.DISTRACTING_DETAIL,
        LANGUAGE,
        "Distracting detail",
        "Деталі, що відволікають",
    ),
    NistCue(
        NistCueId.SENSITIVE_INFORMATION,
        LANGUAGE,
        "Requests for sensitive information",
        "Запити конфіденційної інформації",
    ),
    NistCue(NistCueId.URGENCY, LANGUAGE, "Sense of urgency", "Відчуття терміновості"),
    NistCue(
        NistCueId.THREATENING_LANGUAGE,
        LANGUAGE,
        "Threatening language",
        "Погрозливі формулювання",
    ),
    NistCue(
        NistCueId.GENERIC_GREETING, LANGUAGE, "Generic greeting", "Загальне привітання"
    ),
    NistCue(
        NistCueId.MISSING_SIGNER_DETAILS,
        LANGUAGE,
        "Lack of signer details",
        "Відсутність даних підписанта",
    ),
    NistCue(
        NistCueId.HUMANITARIAN_APPEAL,
        TACTIC,
        "Humanitarian appeals",
        "Гуманітарні заклики",
    ),
    NistCue(
        NistCueId.TOO_GOOD_OFFER,
        TACTIC,
        "Too good to be true offers",
        "Надто вигідні пропозиції",
    ),
    NistCue(
        NistCueId.SPECIAL_RECIPIENT,
        TACTIC,
        "You’re special",
        "Особливий статус адресата",
    ),
    NistCue(
        NistCueId.LIMITED_TIME,
        TACTIC,
        "Limited time offer",
        "Обмежена в часі пропозиція",
    ),
    NistCue(
        NistCueId.BUSINESS_PROCESS,
        TACTIC,
        "Mimics a work or business process",
        "Імітація робочого або бізнес-процесу",
    ),
    NistCue(
        NistCueId.IMPERSONATION,
        TACTIC,
        "Poses as friend, colleague, supervisor, authority figure",
        "Видавання себе за друга, колегу, керівника чи авторитетну особу",
    ),
)
CUES_BY_ID = {cue.id: cue for cue in CUES}
