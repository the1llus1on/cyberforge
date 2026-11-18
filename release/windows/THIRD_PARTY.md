# Сторонні компоненти CyberForge для Windows

Каталог `licenses` містить доступні в інстальованих wheel копії LICENSE,
COPYING, COPYRIGHT і NOTICE, ліцензію CPython та інвентар середовища
збирання. Python, SQLite, Qt, PySide6/Shiboken, Chromium (Qt WebEngine),
PyInstaller bootloader та залежності Python мають власні ліцензії.
Інвентар середовища може включати інструменти, що використовувалися
лише під час збирання. Вміст конкретного ZIP указує фактичні бінарні файли.

- [CPython license](https://docs.python.org/3.12/license.html),
  [SQLite copyright](https://sqlite.org/copyright.html).
- [Qt licensing](https://www.qt.io/licensing/open-source-lgpl-obligations),
  [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).
- [Qt WebEngine and Chromium license notices](https://doc.qt.io/qt-6.10/qtwebengine-licensing.html),
  [Qt 6.10 third-party code](https://doc.qt.io/qt-6.10/licenses-used-in-qt.html),
  [Qt 6.10.3 source archives](https://download.qt.io/archive/qt/6.10/6.10.3/submodules/).
- [PyInstaller license and bootloader terms](https://pyinstaller.org/en/stable/license.html).
- [Inno Setup license](https://jrsoftware.org/inno-setup/license).

Qt DLL залишаються окремими файлами. Перед зовнішнім поширенням
матеріалів відповідальний за випуск перевіряє комплект ліцензій і
відповідного коду для точних версій із manifest, зокрема сповіщення
Chromium та вимоги обраного режиму ліцензування Qt. Збирання кандидата
саме собою не є дозволом на поширення.
