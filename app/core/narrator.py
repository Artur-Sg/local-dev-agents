import json

from adapters.ollama import request_model
from core.capabilities import FIX_REVIEW, FIX_TESTS, GENERATE_SOLUTION
from core.events import AgentEvent, TeamMessage
from core.roles import (
    get_actor_config,
    get_default_language,
    get_default_model,
    get_role_config,
    read_config_prompt,
)
from prompts import render_prompt


class TeamNarrator:
    def narrate(self, event: AgentEvent) -> TeamMessage | None:
        role_config = get_role_config(event.role)
        actor_config = get_actor_config(role_config["actor"])

        fact = self._describe_event(event)
        if fact is None:
            return None

        text = self._generate_actor_message(event, role_config, actor_config, fact)
        author = self._build_author(actor_config)

        return TeamMessage(
            role=event.role,
            author=author,
            text=text,
            task_id=event.task_id,
            status=event.status,
            created_at=event.created_at,
        )

    def _build_author(self, actor_config: dict) -> str:
        emoji = actor_config["emoji"]
        display_name = actor_config["display_name"]
        return f"{emoji} {display_name}".strip()

    def _generate_actor_message(
        self,
        event: AgentEvent,
        role_config: dict,
        actor_config: dict,
        fact: str,
    ) -> str:
        prompt_path = actor_config.get("communication_prompt", "")
        if not prompt_path:
            return fact

        model = role_config["model"] or get_default_model()
        system_prompt = read_config_prompt(prompt_path)
        language = get_default_language()
        user_prompt = render_prompt(
            "narrate_event",
            event_type=event.type,
            role=event.role,
            status=event.status or "",
            language_name=self._language_name(language),
            capability=str(event.payload.get("capability", "")),
            fact=fact,
            payload=json.dumps(self._public_payload(event), ensure_ascii=False, indent=2),
        )

        try:
            return request_model(model, system_prompt, user_prompt).strip()
        except Exception:
            return fact

    def _language_name(self, code: str) -> str:
        mapping = {
            "ru": "Russian",
            "en": "English",
            "uk": "Ukrainian",
        }
        return mapping.get(code, code)

    def _describe_event(self, event: AgentEvent) -> str | None:
        if event.message.strip():
            return event.message.strip()

        if event.type in {"step_started", "step_succeeded"}:
            return None

        if event.type == "step_failed":
            step_name = event.payload.get("step_name", "unknown_step")
            action = event.payload.get("action", "unknown_action")
            error = event.payload.get("error", "unknown error")
            return f"Шаг {step_name} ({action}) завершился ошибкой: {error}"

        if event.type == "run_blocked_dirty":
            return "Sandbox не чистый. Сначала нужно `./agent.sh approve` или `./agent.sh reject`."

        if event.type == "task_started":
            return "Проверяю sandbox и подготавливаю задачу к выполнению."

        if event.type == "task_loaded":
            return "Задача прочитана и готова к передаче в работу."

        if event.type == "generation_started":
            capability = event.payload.get("capability")
            if capability == GENERATE_SOLUTION:
                return "Начинаю реализацию задачи."
            if capability == FIX_TESTS:
                return "Начинаю исправлять падение тестов."
            if capability == FIX_REVIEW:
                return "Начинаю правки по замечаниям ревью."
            return "Начинаю новый шаг генерации."

        if event.type == "bad_format":
            error = event.payload.get("error", "unknown error")
            return f"Ответ модели нельзя применить: {error}"

        if event.type == "files_written":
            files = event.payload.get("files", [])
            if not files:
                return "Изменения записаны."
            joined = ", ".join(files)
            return f"Изменения записаны в {joined}."

        if event.type == "tests_started":
            return "Запускаю тесты."

        if event.type == "tests_passed":
            output = event.payload.get("output", "")
            return f"PASS — {self._summarize_test_output(output)}"

        if event.type == "tests_failed":
            output = event.payload.get("output", "")
            return f"FAIL — {self._summarize_test_output(output)}"

        if event.type == "review_started":
            return "Начинаю проверку изменений."

        if event.type == "review_approved":
            review = event.payload.get("review", "").strip()
            first_line = review.splitlines()[0] if review else "APPROVE"
            return first_line

        if event.type == "review_requested_changes":
            review = event.payload.get("review", "").strip()
            first_line = review.splitlines()[0] if review else "REQUEST_CHANGES"
            return first_line

        if event.type == "workflow_pass":
            return "Задача прошла тесты и ревью."

        if event.type == "workflow_fail":
            return "Тесты упали, нужна следующая итерация."

        if event.type == "workflow_final_fail":
            return "Не удалось довести задачу до успешного результата."

        if event.type == "approval_diff":
            diff = event.payload.get("diff", "")
            if not diff.strip():
                return "Показываю diff для подтверждения.\n\nNo changes"
            return f"Показываю diff для подтверждения.\n\n{diff}"

        if event.type == "changes_committed":
            output = event.payload.get("output", "").strip()
            if not output:
                return "Commit создан."
            return f"Commit создан.\n\n{output}"

        if event.type == "changes_rejected":
            return "Изменения отклонены и рабочее дерево восстановлено."

        if event.type == "git_status_dirty":
            return "Рабочее дерево грязное."

        if event.type == "git_status_clean":
            return "Рабочее дерево чистое."

        if event.type == "git_diff":
            diff = event.payload.get("diff", "")
            return diff if diff.strip() else "No changes"

        if event.type == "git_changes":
            changes = event.payload.get("changes", "")
            return changes if changes.strip() else "No changes"

        if event.type == "raw_output":
            return event.payload.get("output", "")

        return None

    def _summarize_test_output(self, output: str) -> str:
        lines = [line.strip() for line in output.splitlines() if line.strip()]

        for line in reversed(lines):
            if " passed" in line or " failed" in line or " error" in line:
                return line

        return "тесты завершены"

    def _public_payload(self, event: AgentEvent) -> dict:
        hidden_keys = {
            "attempt",
            "max_attempts",
        }

        return {
            key: value
            for key, value in event.payload.items()
            if key not in hidden_keys
        }
