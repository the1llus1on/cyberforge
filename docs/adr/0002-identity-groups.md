# ADR-0002 — Облікові записи, сесії та навчальні групи

**Статус:** реалізовано для рев’ю Phase 2, 11.11.2026.
**Джерело:** SRS v3.0 §§2, 3, 14–16, 21–23; ADR-0001.

## Межі

Phase 2 явно погоджена власником. Додаються лише користувачі, групи та
авторизація. Сценарії, результати, LLM, резервне копіювання/відновлення
всього продукту і Windows-пакування залишаються відповідним наступним фазам.
Схема SRS та затверджені ролі не змінюються.

## Рішення

- `domain/accounts.py`: Role, Workspace, незмінні Account/LearningGroup без хешів.
  `application/accounts.py`: автентифікація, політика робочих розділів,
  управління користувачами. `groups/service.py`: окремі групові операції.
  UI отримує DTO та викликає сервіси; composition root — `main.py`.
- SQLite/SQLAlchemy 2.x, одна спільна БД. За замовчуванням —
  `QStandardPaths.AppLocalDataLocation/cyberforge.sqlite3`; явний `--database`
  обирає інший файл. Міграції Alembic пакуються всередині Python-пакета й
  застосовуються перед запуском UI або setup. `create_all()` не використовується.
- Чотири таблиці: users, learning_groups, group_instructors, group_learners.
  Складені PK запобігають повторному членству, FK з CASCADE підтримують
  цілісність. Ролі й довжини перевіряються constraints; SQLite-тригери
  забороняють невідповідні ролі у таблицях членства. `foreign_keys=ON`
  установлюється для кожного з’єднання.
- Записи виконуються у транзакціях `BEGIN IMMEDIATE`: перевірка прав,
  перевірка останнього адміністратора та зміни серіалізовані між процесами.
  SQLAlchemy приховує параметри помилок. Журналювання облікових даних відсутнє.
- Логіни: ASCII, 1–80 символів `[A-Za-z0-9_.-]`, без зовнішніх пробілів;
  пошук і унікальність нечутливі до регістру через username_key.
  Відображуване ім’я підтримує українську. Паролі: 12–1024 символи,
  без обрізання пробілів; Argon2id зі стандартними параметрами argon2-cffi,
  випадковою сіллю та rehash після успішного входу за потреби.
  Невідомий логін теж проходить dummy Argon2 verification; помилка входу однакова.
- Сесія — випадковий 256-бітний токен лише у пам’яті процесу. Роль не береться
  з UI або токена: кожна захищена операція повторно читає активний обліковий
  запис і auth_version з БД. Пароль, роль або стан змінюють auth_version і
  відкликають усі старі сесії, зокрема в іншому процесі. Звичайний logout
  відкликає поточний токен. Сесії не переживають перезапуск; автоматичного
  входу та запису токенів на диск немає.
- Власна зміна пароля потребує поточного пароля й завершує сесії.
  Адміністративне скидання задає новий пароль через масковане поле; прихованих
  тимчасових або спільних паролів немає. Передачу нового пароля синтетичному
  користувачу виконує адміністратор поза журналом застосунку.
- Видалення користувачів замінене деактивацією, щоб не руйнувати майбутні
  зв’язки. Зміна ролі атомарно прибирає попереднє членство. Деактивація
  зберігає зв’язки, але забороняє вхід. Останнього активного адміністратора
  не можна деактивувати або перевести в іншу роль.
- Тільки Administrator змінює користувачів і групи. Instructor читає лише
  закріплені групи, Learner — власні групи; читання невідомого/чужого ID
  відхиляється. Administrator має глобальні права і не потребує членства
  у group_instructors. Тести перевіряють UI й прямі service-виклики.
- Guest зберігає погоджені порожні перегляди оболонки; доступ до даних закритий.
  Форма входу займає область усього вікна, має маскований пароль і «Закрити».
  Після входу/виходу історія починається з Home. Logout очищає форми,
  адміністративні списки й пошук. UI перевіряє актуальність сесії щосекунди;
  сервіс відхиляє відкликану сесію одразу при зверненні.
- Нормальний startup створює лише схему. Перший Administrator додається явно
  через інтерактивний `--init-admin` у порожній БД. Demo — окрема команда
  з обов’язковими шляхами БД та нового файлу паролів. Усі сім паролів
  незалежні, генеруються secrets, файл створюється ексклюзивно (POSIX 0600).
  Колізія файлу відкочує seed; повторна команда з повним набором demo-логінів
  нічого не змінює, зберігаючи паролі й правки власника. Непорожня стороння
  або частково ініціалізована база відхиляється.

## Межі гарантій

Сервіси захищають операції застосунку; користувач ОС із можливістю змінювати
файл SQLite або Python-код перебуває поза цією межею. Власник має зберігати БД
та demo-файл у приватному каталозі ОС. POSIX 0600 не є доказом Windows ACL:
Windows 11 перевіряється окремо. Python/Qt не гарантують фізичного затирання
всіх копій рядків у пам’яті; поля очищаються, секрети не зберігаються у DTO,
налаштуваннях або логах. Cloud LLM та keyring тут не потрібні: API-секретів немає.

## Уточнення POSIX permissions перед прийняттям Phase 2

Нові відсутні каталоги шляху БД створюються з mode 0700, сам файл —
ексклюзивним os.open(O_CREAT|O_EXCL) з mode 0600 перед з’єднанням SQLite.
Глобальний umask не змінюється. SQLite успадковує права БД для journal/WAL/SHM;
це перевіряється живими SQLite-транзакціями у POSIX-тестах з umask 000.
Наявні каталоги й файли не chmod-яться: їхні попередні права зберігаються,
тому автоматичного виправлення старих відкритих БД немає. Адміністратор ОС
має перевірити їх окремо. Довільний наявний каталог не вважається власністю
застосунку. Захист від зловмисника з правом змінювати батьківський каталог
не гарантується. POSIX mode не встановлює Windows DACL; Windows ACL та
успадкування прав sidecar-файлів на Windows 11 не перевірено.

## Погоджені зміни за owner review PR #3

Джерело: [коментар власника](https://github.com/the1llus1on/cyberforge/pull/3#issuecomment-6804044603).
Цей запис замінює попередні рішення про Guest preview та лише деактивацію;
SRS v3.0 залишається незмінним. Phase 2 — REVIEW.

- Guest більше не бачить і не відкриває Constructor/Analytics, включно з
  прямим navigate. Home/Profile/Settings збережені. Це погоджене уточнення ADR-0001.
- Administrator може видалити іншого користувача після підтвердження. Сервіс
  забороняє видалення поточного й останнього активного адміністратора;
  членство видаляється транзакційно. Будь-які інші FK до users перевіряються
  до delete: за наявності даних потрібна деактивація, навіть якщо FK має CASCADE.
  Після видалення сесії відхиляються. Credential fingerprint у сесії запобігає
  відновленню доступу при повторному використанні SQLite ID в іншому процесі;
  rehash також консервативно відкликає старі сесії.
- Єдина кнопка зберігає metadata та обидва набори членства однією транзакцією,
  включно з новою групою. Невалідне членство відкочує всі зміни.
- Фільтри приховують наявні items без реконструкції або повторного select:
  edit identity і checked draft membership зберігаються навіть у прихованих items.
- Learner — роль нового запису. Combo використовує widget popup і негайне
  прийняття clicked index; зміна ролі у формі не зберігає БД автоматично.
- Активне й неактивне виділення стилізуються окремо; порожня область списку
  скидає вибір. Палітра й архітектура оболонки збережені.
- Причина WSLg keyboard та межі фізичної перевірки —
  [діагностика](../diagnostics/wslg-keyboard.md).

## Наступне owner review: popup, обидва списки, display names

Попередній RoleCombo та clicked→setCurrentIndex→hidePopup видалено разом
із stylesheet override combobox-popup. Використовується стандартний
QComboBox і його життєвий цикл; Save залишається єдиним записом БД.
Початковий тест showPopup не покривав відкриття мишею й відкладене повторне
відображення. Нові тести перевіряють усі ролі, наступні event-loop turn,
F4/Enter/Escape. Для WSLg synthetic mouse grab існує явно задокументований skip.
Офіційний контракт Qt: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QComboBox.html

Причина асиметрії: instructors був EditableList, learners — QListWidget.
Обидва тепер EditableList. focusOutEvent знімає selection, але не current
identity і не check states; empty click скидає current/selection. Фільтри
не перебудовують items. Кожен список має окремий regression test.

Users entry містить display_name, username, role, active status; пошук
використовує повний текст. Довгі назви elide-right, повний текст у tooltip,
горизонтальне прокручування вимкнено. Зміна імені оновлює entry після Save.
Фізичне українське введення лишається невирішеним environment issue до
порівняння probe/native Windows; не змінювати налаштування автоматично.

## Owner-directed заміна popup і membership selection

RoleChoice тепер містить три стандартні QRadioButton у exclusive QButtonGroup:
Учень, Викладач, Адміністратор. Popup та його тести/обробники прибрані;
Learner default і explicit Save не змінюються. Це замінює попереднє рішення
про QComboBox, з огляду на повторний фізичний збій і upstream WSLg #1522.

MembershipPicker — QListWidget NoSelection, items без ItemIsSelectable.
Постійні check indicators не перекриваються row-selection. Delegate змінює
CheckStateRole один раз при лівому mouse release у рядку; Space обробляється
стандартним Qt delegate. Current index підтримує клавіатурну навігацію, але
не виділення. Фільтри й атомарний save працюють із незмінними draft items.

Корекцію clipboard shortcuts дозволено додавати лише після фізичних
key/modifier/scan доказів; наразі є safe observer тільки в окремому probe.
Застосунок не отримав глобальних keyboard filters. Standard Ukrainian typing
підтверджено власником, Enhanced і Ctrl+V під Standard — відкриті дефекти
оточення/shortcut path; подробиці та upstream статус — у diagnostics.

## Indicator-only membership та підтверджена shortcut-корекція

Після нового owner review broad MembershipDelegate видалено. Qt default
QStyledItemDelegate виконує indicator hit-testing за стилем; negative GUI
тести використовують SE_ItemViewItemText, empty space і позитивний
SE_ItemViewItemCheckIndicator. NoSelection та keyboard Space збережені.
Atomic save без змін. Це замінює попереднє рішення про row-release toggle.

Власник надав фізичні English/Standard Ukrainian події з однаковими scans:
C: 43/421 scan36, V: 56/41C scan37, X: 58/427 scan35, A: 41/424 scan26
(усі значення hex), модифікатор тільки Control 0x04000000. Qt StandardKey
не збігається з українськими logical keys; це підтверджує причину shortcuts.
ClipboardShortcuts у межах MainWindow обробляє тільки чотири точні пари
Ukr logical key + scan під backend=wayland та наявним WSLg versions marker,
з точним Ctrl. Уже впізнані StandardKey, інші modifiers/keys/scans/platforms,
Unicode та input-method events пропускаються. ShortcutOverride резервує
редагувальну дію; тільки KeyPress викликає native copy/paste/cut/selectAll
і споживається один раз, без synthetic events. Password/NoEcho забороняють
copy/cut, readonly не змінюється. Немає логування чи транслітерації тексту.
Standalone probe навмисно лишається baseline observer без виправлення.
Enhanced mapping перебуває нижче Qt і цим рішенням не виправляється.

Геометрія обчислюється у logical pixels з availableGeometry: preferred
1400×900, minimum 1100×720, обидва bounded екраном із запасом 48 px.
Root scroll містить usable content minimum 860×620, незалежний від WM hints;
при примусовому меншому frame з’являється прокручування. Адміністративні
форми прокручуються окремо у вкладках, дії збереження/видалення розміщено
поза ними у двоколонковій панелі. Це замінює full-page-scroll-only layout.

## Вузькі виправлення pre-acceptance audit

CreateUser враховує обраний active; неповний membership payload відхиляється,
щоб None не означав мовчазне очищення іншої ролі. Existing inactive memberships
зберігаються при Save й видимі у picker; нові inactive assignments заборонені.
Logout очищає також filters, а refresh не втрачає їх. Cancel/New не імітують Save.
DBAPI failures мають safe errors, UI повертається до Guest, startup не друкує
traceback/SQL. Delete guard використовує фактичні FK columns, а не припущення
про id. Windows hosted offscreen CI додано окремо від manual Windows11 gate.
Докази й межі — audits/phase-2-pre-acceptance.md. SRS/Phase scope незмінні.

Historical FK guard дотримується SQLite parent collation/affinity і
case-insensitive table identifiers, у тому числі для alternate unique key.
Windows CI відтворив окремий дефект redirected CP1252: CLI задає UTF-8
тільки для перенаправлених stdout/stderr. Interactive console, stdin,
системна locale та Windows host settings не змінюються.

## Native Windows acceptance workspace

Окремий tracked-source snapshot, portable uv/Python3.12 (no-bin/no-registry),
locked venv і cache/temp ізольовано в дозволеному test root. Demo — в новому
profile-каталозі з protected ACL user/SYSTEM/Administrators до створення БД.
Launcher не seed-ить дані; наявні owner DB/credentials не копіюються.
Native geometry probe використовує empty temporary DB та WM_GETMINMAXINFO,
не записує account/clipboard/text. Initial client bounds не враховували
Windows decorations: showEvent clamp коригує тільки початкову позицію рамки.
Physical WSLg resize violation не приховується fixed size або force-resize loop.
Повні межі automated/physical acceptance — diagnostics/native-windows.md.
