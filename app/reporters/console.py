from core.events import TeamMessage, get_reporters, register_reporter


class ConsoleReporter:
    def publish(self, message: TeamMessage) -> None:
        task = f" [{message.task_id}]" if message.task_id else ""
        status = f" ({message.status})" if message.status else ""
        print(f"{message.author}{task}{status}: {message.text}", flush=True)


def setup_console_reporting() -> None:
    if not any(isinstance(reporter, ConsoleReporter) for reporter in get_reporters()):
        register_reporter(ConsoleReporter())
