# local-dev-agent

Локальная multi-agent система, где задача описывается один раз в `config/intake.json`, а дальше команда агентов сама декомпозирует работу, делает инкременты, проверяет результат и доводит задачу до terminal state.

## Ментальная модель

Почти всё сводится к трём сущностям:

- `config/intake.json` — что строим, где строим и как проверяем
- `data/agent.db` — текущее состояние задач и запусков
- `sandboxes/...` — сам проект, который агенты меняют

Остальное в основном обслуживает этот цикл.

## Текущее состояние

Сейчас каноничная схема такая:

- `config/intake.json` — единственная ручная точка входа для новой или обновлённой задачи
- `data/project.runtime.json` — generated runtime-конфиг активного проекта; руками не редактируется
- `data/agent.db` — основной state store для задач, запусков и событий
- `runs/<run_id>/` — артефакты конкретного запуска
- `tasks/inbox`, `tasks/blocked`, `tasks/needs-human`, `tasks/done` — файловые зеркала для удобства и recovery, но не основной источник истины

Runtime уже `DB-first`, а `tasks/*` остаются как человекочитаемое зеркало и запасной механизм восстановления через `./agent.sh recover`.

Важно:

- runtime-конфиг не подставляется молча по умолчанию
- перед `run`, `auto`, `status`, `diff` и остальными рабочими командами сначала нужен `./agent.sh kickoff`

## Что делает система

Агентный цикл сейчас умеет:

- читать задачу из `config/intake.json`
- готовить или подхватывать проект в `sandboxes/...`
- строить план и подзадачи
- передавать инкременты developer-агенту
- запускать verification plan
- делать review
- повторять итерации до успеха, блокировки или необходимости человека

## Требования

- Python 3.12+
- Docker, если стек использует docker-runner
- локально доступный model API, совместимый с текущим клиентом

По умолчанию ожидается Ollama-совместимый endpoint:

- `http://127.0.0.1:11434/api/chat`

## Быстрый старт

### 1. Подготовь `.env`

```bash
cp .env.example .env
```

Минимально проверь значения:

- `MODEL_API_URL`
- `MODEL_DEFAULT_NAME`

Шаблон лежит в `./.env.example`.

### 2. При необходимости собери docker-runner

Если в `config/intake.json` у стека указан runner типа `docker`, нужен соответствующий образ.

Текущий базовый runner собирается так:

```bash
docker build -t local-dev-agent-python:3.12 -f tooling/docker/python-runner.Dockerfile .
```

`tooling/docker/python-runner.Dockerfile` всё ещё нужен, потому что это не часть конкретного sandbox-проекта, а reusable execution environment для стеков, которые проверяются через Docker.

### 3. Заполни `config/intake.json`

Можно начать с шаблона:

```bash
cp config/intake.example.json config/intake.json
```

В нормальном сценарии пользователь меняет только `config/intake.json`.

### 4. Запусти задачу

```bash
./agent.sh kickoff
./agent.sh auto
```

Это основной happy path.

## Что редактировать, а что нет

Редактировать руками:

- `config/intake.json`
- `config/roles.json`
- prompts в `config/roles/*` и `config/prompts/*`

Не редактировать руками:

- `data/project.runtime.json`
- `data/agent.db`
- `runs/*`

Если нужно поменять проект, стек или verification, это делается через `config/intake.json`, а не через runtime-файлы.

## Как оформлять задачу

`config/intake.json` описывает всё, что нужно для запуска:

- `run` — режим запуска и политика сброса
- `project` — имя и путь проекта
- `stack` — технический контекст выполнения
- `task` — сама задача
- `verification` — как проверять результат

### `project`

Тут задаются:

- `name` — имя проекта
- `path` — путь проекта внутри `sandboxes/`
- `existing` — это доработка существующего проекта или старт с нуля

### `stack`

Это не project-specific if/else в коде, а runtime-описание среды:

- допустимые пути записи
- runner
- bootstrap-файлы

Именно здесь задаётся, как агенту можно работать с проектом.

Сейчас поддерживаются:

- `runner.type = "docker"`
- `runner.type = "local"`

Для `bootstrap_files` можно использовать два режима:

- `source` + `target` — скопировать подготовленный файл
- `content` + `target` — создать bootstrap-файл прямо из `config/intake.json`

### `task`

Минимум, который надо хорошо заполнить:

- `id`
- `title`
- `description`
- `constraints`
- `done_when`

Практически:

- `description` описывает цель и текущее состояние
- `constraints` задаёт границы
- `done_when` задаёт критерии завершения

### `verification`

Здесь описывается способ проверки:

- `trusted_paths`
- `must_not_modify`
- `allow_generated_tests`
- `allow_visual_checks`
- `visual_review`

Система строит verification plan на основе intake/runtime-контекста, а не только из заранее подготовленного шаблона.

Для `visual_review` контекст можно задавать двумя способами:

- `prompt` — путь к тексту внутри `config/`
- `prompt_text` — встроенный текст прямо в `config/intake.json`

## Основные команды

Все команды запускаются через:

```bash
./agent.sh <command>
```

### `kickoff`

```bash
./agent.sh kickoff
```

Что делает:

- читает `config/intake.json`
- сбрасывает runtime-состояние в соответствии с `run.*`
- подготавливает sandbox-проект
- пишет generated-файл `data/project.runtime.json`
- создаёт запись задачи в SQLite
- синхронизирует файловое зеркало в `tasks/inbox/`

Если хочешь изменить проект, стек, verification или reset policy, меняй `config/intake.json`, а не `data/project.runtime.json`.

### `run`

```bash
./agent.sh run
```

Запускает один workflow для следующей inbox-задачи. Удобно для ручного контроля.

### `auto`

```bash
./agent.sh auto
```

Крутит очередь автономно: берёт задачи одну за другой и доводит каждую до terminal state. Это основной autonomous режим.

### `once`

```bash
./agent.sh once
```

Упрощённый однопроходный запуск. Полезен как smoke/debug режим, но не основной loop.

### `status`

```bash
./agent.sh status
./agent.sh run-status <run_id|latest>
```

Показывает состояние последнего или конкретного run.

### `backlog`

```bash
./agent.sh backlog
```

Показывает текущие задачи по группам и список запусков.

### `diff`

```bash
./agent.sh diff
```

Показывает текущие изменения проекта.

### `approve`

```bash
./agent.sh approve
```

Показывает изменения и коммитит их, если есть что подтверждать.

### `reject`

```bash
./agent.sh reject
```

Отклоняет текущие изменения и восстанавливает рабочее дерево проекта.

### `recover`

```bash
./agent.sh recover
```

Восстанавливает записи задач из файлового зеркала `tasks/*` обратно в SQLite. Это recovery-механизм, а не часть обычного happy-path runtime.

### `test`

```bash
./agent.sh test
```

Проверяет текущий test runner отдельно от полного агентного цикла.

## Настройка модели

Env-конфиг читается из `app/env.py`.

Основные переменные:

- `MODEL_API_URL`
- `MODEL_DEFAULT_NAME`
- `AGENT_MAX_ATTEMPTS`
- `AGENT_HTTP_TIMEOUT`
- `NARRATOR_USE_MODEL`

Пример:

```env
MODEL_API_URL=http://127.0.0.1:11434/api/chat
MODEL_DEFAULT_NAME=qwen2.5-coder:7b
AGENT_MAX_ATTEMPTS=5
AGENT_HTTP_TIMEOUT=180
NARRATOR_USE_MODEL=0
```

По умолчанию `NARRATOR_USE_MODEL=0`, то есть командные сообщения строятся через deterministic fallback и не блокируют pipeline отдельным LLM-вызовом. Если нужен “живой” chat-style narration, можно включить `NARRATOR_USE_MODEL=1`.

## Настройка ролей

Главный конфиг ролей: `config/roles.json`.

Роль сейчас описывает:

- `actor`
- `model`
- `persona_prompt`
- `allowed_actions`
- `capabilities`

Что можно менять без правок Python-кода:

- модель у конкретной роли
- persona роли
- capability prompts
- права роли

Полезные каталоги:

- `config/roles/developer/`
- `config/roles/project_lead/`
- `config/roles/reviewer/`
- `config/prompts/`
- `config/actors/`

## Runtime-артефакты

Во время работы создаются:

- `data/project.runtime.json`
- `data/agent.db`
- `runs/<run_id>/state.json`
- `runs/<run_id>/events.jsonl`
- `runs/<run_id>/verification_plan.json`

Обычно не коммитятся:

- `.env`
- `data/agent.db`
- содержимое `runs/*`
- живое состояние sandbox-проектов

Обычно коммитятся:

- `.env.example`
- `config/*`
- `app/*`
- `agent.sh`
- `.gitkeep` для пустых runtime-директорий, если они реально нужны

## Что ещё важно понимать

### Зачем ещё нужны `tasks/*`

Они нужны не как главный storage, а как:

- наглядная очередь для человека
- зеркало текущего состояния задач
- источник для `recover`, если локальная DB потеряна

### Зачем ещё нужен `tooling/docker`

Он нужен как слой инфраструктуры исполнения:

- хранит reusable runner images
- не относится к конкретному sandbox-проекту
- позволяет разным задачам использовать одинаковую проверочную среду

Если когда-нибудь все стеки уйдут на локальные команды без Docker, этот слой можно будет упростить или удалить. Сейчас он ещё рабочий и полезный.

## Типовой сценарий

### Новый проект

1. Заполнить `config/intake.json`.
2. Выполнить `./agent.sh kickoff`.
3. Выполнить `./agent.sh auto`.
4. Смотреть `./agent.sh backlog` и `./agent.sh status`.
5. Если результат устраивает, выполнить `./agent.sh approve`.

### Доработка существующего проекта

1. Указать существующий `project.path` в `config/intake.json`.
2. Выбрать подходящий `run.project_reset`, обычно `preserve` или `git_restore`.
3. Ограничить `stack.workspace.allowed_write_paths`.
4. При необходимости заполнить `verification.must_not_modify`.
5. Выполнить `./agent.sh kickoff`.
6. Запустить `./agent.sh auto` или `./agent.sh run`.

## Ограничения текущей версии

- verification всё ещё сильно зависит от качества описания в `config/intake.json`
- visual QA пока не полноценный browser/screenshot evaluation слой
- docker runner остаётся основным универсальным способом прогонов
- часть агентного поведения всё ещё определяется prompt-дисциплиной, а не полноценным tool-using ReAct runtime

## Канонические файлы

Если нужно быстро понять проект, начни отсюда:

- `agent.sh`
- `config/intake.example.json`
- `config/intake.json`
- `config/roles.json`
- `app/commands/kickoff.py`
- `app/commands/auto.py`
- `app/core/state_machine.py`
- `app/core/verification_plan.py`
- `app/core/db.py`

## Коротко

Если задача новая, в нормальном случае нужно сделать только это:

1. Заполнить `config/intake.json`.
2. Выполнить `./agent.sh kickoff`.
3. Выполнить `./agent.sh auto`.

Остальное уже относится к отладке, recovery или донастройке ролей и среды.
