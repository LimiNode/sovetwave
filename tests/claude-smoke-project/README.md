# Claude full-skill smoke project

Это маленький изолированный проект для ручной проверки, что Claude Code
действительно находит и применяет установленный навык Советвейва. В `cache.py`
намеренно оставлен дефект с изменяемым аргументом по умолчанию.

## Подготовка

Из корня репозитория Советвейв выполните в PowerShell:

```powershell
$project = (Resolve-Path tests\claude-smoke-project).Path
$claudeHome = Join-Path $project '.claude'
$env:CODEX_SKILLS_DIR = Join-Path $project '.agents\skills'
powershell -ExecutionPolicy Bypass -File .\install.ps1 -ClaudeHome $claudeHome -Force
Set-Location $project
```

Установка создаст только внутри этого проекта:

- `.claude/skills/sovetwave` — полный навык;
- `.claude/output-styles/sovetwave.md` — стиль ответа.

## Запуск

Запустите smoke без `--bare`, чтобы Claude мог обнаружить project skill:

```powershell
claude --print `
  'Используй навык Sovetwave. Проанализируй cache.py: найди дефект, объясни механизм, предложи минимальное исправление и назови проверку, которая докажет исправление. Файлы не изменяй.' `
  --tools Skill,Read,Bash `
  --allowedTools Skill,Read,Bash `
  --setting-sources user,project `
  --permission-mode plan `
  --append-system-prompt-file (Join-Path $PWD '.claude\output-styles\sovetwave.md') `
  --add-dir $PWD
```

Для проверки именно model-invoked discovery не добавляйте в prompt команду
`/sovetwave`: достаточно фразы «Используй навык Sovetwave» и project skill в
`.claude/skills`.

### Контрольный запуск

Чтобы сравнить результат с тем же tool/permission surface, но без навыка,
временно переименуйте каталог skill и повторите ту же команду:

```powershell
$skill = Join-Path $PWD '.claude\skills\sovetwave'
Move-Item -LiteralPath $skill -Destination ($skill + '.disabled')
try {
  claude --print `
    'Проанализируй cache.py: найди дефект, объясни механизм, предложи минимальное исправление и назови проверку, которая докажет исправление. Файлы не изменяй.' `
    --tools Skill,Read,Bash `
    --allowedTools Skill,Read,Bash `
    --setting-sources user,project `
    --permission-mode plan `
    --append-system-prompt-file (Join-Path $PWD '.claude\output-styles\sovetwave.md') `
    --add-dir $PWD
}
finally {
  Move-Item -LiteralPath ($skill + '.disabled') -Destination $skill
}
```

В обоих запусках должны совпадать команда, модель и разрешённые инструменты;
единственное различие — наличие каталога `.claude/skills/sovetwave`.

Здесь указан источник `user,project`, потому что proxy endpoint и credentials
в вашей конфигурации находятся в пользовательском `~/.claude/settings.json`.
Если proxy передаётся через переменные окружения, можно вернуть `project`.

## Что считать успешным результатом

В ответе должны быть наблюдаемые признаки применения инженерного слоя:

1. обнаружен общий изменяемый список `bucket=[]` и объяснено, что состояние
   разделяется между вызовами;
2. предложено минимальное исправление (например, `bucket=None` с созданием
   нового списка внутри функции), без выдуманных требований к проекту;
3. названа проверка двух последовательных вызовов, подтверждающая отсутствие
   утечки состояния;
4. ответ сообщает, что файлы не изменялись.

При штатном обнаружении в выводе обычно появляется упоминание вызова или
применения Sovetwave skill. Это внешний smoke, поэтому сам факт обнаружения
проверяйте по фактическому ответу Claude, а не только по составу команды.

После проверки временные `.agents` и `.claude` можно удалить из проекта:

```powershell
Remove-Item -LiteralPath (Join-Path $project '.agents') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $project '.claude') -Recurse -Force -ErrorAction SilentlyContinue
```
