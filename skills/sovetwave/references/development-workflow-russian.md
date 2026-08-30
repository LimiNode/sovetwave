# Russian language for development work

Read this reference for Russian reports and discussions about Git, pull requests, CI, builds, tests, code review, plans, releases, and completed work. Apply the classification rule from [russian-technical-language.md](russian-technical-language.md): preserve names and tools; translate ordinary roles, states, actions, and descriptions.

## Pull requests and Git

Keep `PR`, `Git`, commit hashes, branch names, commands, paths, and file names unchanged. Describe their ordinary roles in Russian: «коммит» names the Git object, while its hash remains exact.

| English wording | Role in the sentence | Prefer when the meaning fits |
|---|---|---|
| draft PR | PR state | черновой PR |
| commit / commit hash | Git object / identifier | коммит / хэш коммита |
| base branch | target role | целевая ветка |
| head branch | source role | ветка изменений / исходная ветка |
| untracked files | Git state | неотслеживаемые файлы |
| staged changes | Git state | изменения, подготовленные к коммиту |
| working tree | Git concept | рабочее дерево |
| mergeable | PR state | конфликтов слияния нет / может быть слит без конфликтов |

`main` is usually a branch identifier, not «главная». `origin` is a remote name, not «источник».

## Build, tests, and CI

Keep tool and target names such as `CMake`, `CTest`, `CI`, `ASan`, `test_sync_capture`, and `C++17` unchanged. Translate what they did or what state they are in.

| English wording | Role in the sentence | Prefer when the meaning fits |
|---|---|---|
| focused tests | test-set scope | целевые тесты |
| smoke test | quick confidence check | быстрая проверка; retain `smoke test` only when it is the established project term |
| CI job | CI unit of work | задание CI |
| check | validation result | проверка |
| run | CI or test execution | запуск |
| passed / failed | outcome | пройден / не пройден; завершился успешно / завершился ошибкой — согласовать форму и число с подлежащим |
| build failure | outcome | ошибка сборки |

## Review, planning, and delivery

Translate generic work-management language, while preserving formal names of issues, labels, milestones, and APIs.

| English wording | Prefer when the meaning fits |
|---|---|
| implementation | реализация |
| behaviour | поведение |
| fallback | резервный вариант / запасной путь |
| finding | замечание / вывод |
| follow-up | следующий шаг / последующая проверка |
| pending | ожидает выполнения / находится в ожидании |
| ready | готов |
| blocked | заблокирован |

Do not translate by a global one-to-one table. For example, `base` in a pull request is «целевая ветка», in arithmetic it is «основание», and in addressing it can be «базовый адрес».
