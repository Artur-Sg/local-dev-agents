from core.events import AgentEvent, TeamMessage
from core.capabilities import FIX_REVIEW, FIX_TESTS, GENERATE_SOLUTION
from core.roles import get_actor_config, get_role_config

class TeamNarrator:
    def narrate(self, event: AgentEvent) -> TeamMessage | None:
        role_config = get_role_config(event.role)
        actor_config = get_actor_config(role_config["actor"])
        emoji = actor_config["emoji"]
        author = f"{emoji} {actor_config['display_name']}".strip()
        text = self._build_text(event)
        if text is None:
            return None

        return TeamMessage(
            role=event.role,
            author=author,
            text=text,
            task_id=event.task_id,
            status=event.status,
            created_at=event.created_at,
        )

    def _build_text(self, event: AgentEvent) -> str | None:
        if event.type == "step_started":
            return None

        if event.type == "step_succeeded":
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
            return "Задача прочитана. Передаю её в разработку."

        if event.type == "generation_started":
            capability = event.payload.get("capability")
            if capability == GENERATE_SOLUTION:
                return "Генерирую решение."
            if capability == FIX_TESTS:
                return "Готовлю исправление после падения тестов."
            if capability == FIX_REVIEW:
                return "Готовлю исправление по замечаниям ревью."
            return "Запускаю генерацию."

        if event.type == "bad_format":
            return f"Ответ модели в неверном формате: {event.payload.get('error', 'unknown error')}"

        if event.type == "files_written":
            files = event.payload.get("files", [])
            if not files:
                return "Изменения записаны. Передаю дальше по пайплайну."
            joined = ", ".join(files)
            return f"Готово, внёс изменения в {joined}. Передаю в тестирование."

        if event.type == "tests_started":
            return "Запускаю тесты."

        if event.type == "tests_passed":
            output = event.payload.get("output", "")
            summary = self._summarize_test_output(output)
            return f"PASS — {summary}"

        if event.type == "tests_failed":
            output = event.payload.get("output", "")
            summary = self._summarize_test_output(output)
            return f"FAIL — {summary}"

        if event.type == "review_started":
            return "Проверяю diff."

        if event.type == "review_approved":
            review = event.payload.get("review", "").strip()
            first_line = review.splitlines()[0] if review else "Нет результата ревью."
            return first_line

        if event.type == "review_requested_changes":
            review = event.payload.get("review", "").strip()
            first_line = review.splitlines()[0] if review else "Нужны правки по результатам ревью."
            return first_line

        if event.type == "workflow_pass":
            return "Задача прошла тесты и ревью."

        if event.type == "workflow_fail":
            return "Тесты упали. Возвращаю задачу на исправление."

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

        return event.message or None

    def _summarize_test_output(self, output: str) -> str:
        lines = [line.strip() for line in output.splitlines() if line.strip()]

        for line in reversed(lines):
            if " passed" in line or " failed" in line or " error" in line:
                return line

        return "тесты завершены"
