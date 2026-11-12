# Phase 2 — остаточне прийняття власником

**ACCEPTED — 12.11.2026.** Власник явно прийняв Users & Groups і дозволив
merge [PR #3](https://github.com/the1llus1on/cyberforge/pull/3) після успішного
CI фінального коміту. Цей запис замінює попередній checklist зі статусом REVIEW.
Прийнята реалізація: `50d89e970559d725ca0f603e3db220b130d55847`;
фіналізація змінює лише документацію.

## Докази та їх джерело

| Перевірка | Джерело й підтверджений результат |
|---|---|
| Основні user/group functions | Власник: вручну перевірено у WSLg |
| Guest, Administrator, Instructor, Learner | Власник: navigation і permissions перевірено |
| User/group operations, radio roles, membership controls | Власник: перевірено, включно з indicator-only interaction |
| Persistence та logout | Власник: перевірено у WSLg |
| Standard Ukrainian input і shortcuts | Власник: працюють у WSLg; попередньо також підтверджено English і Shift+Insert |
| Ukrainian Enhanced input і shortcuts | Власник: працюють у native Windows 11 |
| Мінімальний розмір native Windows вікна | Власник: фізичне enforcement підтверджено |
| Автоматизовані Linux/Windows checks | Прийнята ревізія: Linux121 passed, Windows119 passed/2 POSIX skips; Ruff, install, migrations/import/startup, CI — success |
| Додаткові GUI/ACL checks | Попередня автоматизація: native Windows47 GUI passed; WSLg75 GUI passed; ACL нового native demo-каталогу/БД/credentials перевірено |

Власник повідомив результати фізичних перевірок; агент не представляє їх
як власне фізичне тестування. CI/offscreen/widget captures не підміняють
фізичну перевірку. Докази автоматизації й незмінений native snapshot:
[Windows guide](diagnostics/native-windows.md),
[CI прийнятої ревізії](https://github.com/the1llus1on/cyberforge/actions/runs/43131852256),
[технічний аудит](audits/phase-2-pre-acceptance.md).
Фінальний документаційний HEAD перевіряється окремо в PR перед merge.

## Задокументовані межі

- WSLg Ukrainian Enhanced (Windows layout0x20422) лишається upstream
  Weston mapping limitation; успіх native Windows не виправляє WSLg.
- Фізичний WSLg resize може порушувати Qt minimum hints. Native Windows
  enforcement підтверджено власником; точний WSLg compositor/RDP компонент
  не встановлено. Безпечні варіанти — native launch або ручне maximize WSLg.
- Повна фізична DPI100/125/150/200% і multi-monitor матриця не перелічена
  в остаточному повідомленні власника й не позначається як пройдена.
  Права інших Windows БД/профілів окремими ACL checks не перевірялися.

## Межа наступних фаз

Історія власних learner attempts та подання їх результатів віднесені до
існуючих Phase9–10 у [плані](IMPLEMENTATION_PLAN.md). Зараз це лише план;
сценарних сутностей, scoring або результатів у Phase2 не додано.

**Phase 3 — NOT STARTED.** Прийняття Phase2 і дозвіл merge не є дозволом
розпочати наступну фазу. SRS v3.0, demo databases/credentials, native Windows
workspace та інші локальні дані зберігаються без змін.
