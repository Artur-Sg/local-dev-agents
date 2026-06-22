from dataclasses import dataclass
from pathlib import Path
import re

from core.actions import RUN_VISUAL_CHECK
from core.roles import require_action
from core.settings import get_project_dir, get_visual_review_config


@dataclass(frozen=True)
class VisualCheckResult:
    skipped: bool
    passed: bool
    summary: str
    details: list[str]
    metrics: dict[str, object]


def run_visual_check() -> VisualCheckResult:
    require_action(RUN_VISUAL_CHECK)

    project_dir = get_project_dir()
    config = get_visual_review_config()
    enabled = config["enabled"]
    checker = config["checker"]
    html_path = project_dir / "index.html"
    css_path = project_dir / "styles.css"

    details: list[str] = []
    metrics: dict[str, object] = {
        "enabled": enabled,
        "checker": checker,
        "files": config["files"],
        "project_dir": str(project_dir),
    }

    if not enabled:
        return VisualCheckResult(
            skipped=True,
            passed=True,
            summary="Visual QA отключён для текущего профиля.",
            details=[],
            metrics=metrics,
        )

    if checker != "static-html":
        return VisualCheckResult(
            skipped=True,
            passed=True,
            summary=f"Для профиля не настроен поддерживаемый visual checker: {checker or 'none'}.",
            details=[],
            metrics=metrics,
        )

    if not html_path.exists():
        return VisualCheckResult(
            skipped=False,
            passed=False,
            summary="Не найден index.html, визуальную проверку выполнить нельзя.",
            details=["Missing index.html"],
            metrics=metrics,
        )

    if not css_path.exists():
        return VisualCheckResult(
            skipped=False,
            passed=False,
            summary="Не найден styles.css, визуальную проверку выполнить нельзя.",
            details=["Missing styles.css"],
            metrics=metrics,
        )

    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")

    hero_present = bool(re.search(r'class="[^"]*hero[^"]*"', html))
    cta_menu_link = '#menu' in html
    fixed_position = "position: fixed" in css
    sticky_position = "position: sticky" in css
    has_media = "@media" in css
    has_max_width = "max-width" in css
    has_grid = "display: grid" in css
    has_hover = ":hover" in css
    section_count = len(re.findall(r"<section\b", html))
    cta_count = len(re.findall(r'href="#menu"', html))

    metrics.update(
        {
            "hero_present": hero_present,
            "cta_menu_link": cta_menu_link,
            "cta_count": cta_count,
            "fixed_position": fixed_position,
            "sticky_position": sticky_position,
            "has_media": has_media,
            "has_max_width": has_max_width,
            "has_grid": has_grid,
            "has_hover": has_hover,
            "section_count": section_count,
            "html_length": len(html),
            "css_length": len(css),
        }
    )

    if not hero_present:
        details.append("Не найден явный hero-блок.")
    if not cta_menu_link or cta_count == 0:
        details.append("Не найден CTA со ссылкой на #menu.")
    if fixed_position:
        details.append("В styles.css найден position: fixed.")
    if sticky_position:
        details.append("В styles.css найден position: sticky.")
    if not has_max_width:
        details.append("Не найден max-width, контент может быть слишком растянут.")
    if not has_grid:
        details.append("Не найден display: grid, карточная сетка выглядит сомнительно.")
    if not has_hover:
        details.append("Не найдено hover-состояний.")
    if not has_media:
        details.append("Не найден адаптивный @media-блок.")
    if section_count < 2:
        details.append("Слишком мало section-блоков для полноценной страницы.")

    passed = not details
    summary = (
        "Визуальная проверка пройдена: базовые признаки полноценной веб-страницы на месте."
        if passed
        else "Визуальная проверка не пройдена: найдены признаки сломанного или сырого интерфейса."
    )

    return VisualCheckResult(
        skipped=False,
        passed=passed,
        summary=summary,
        details=details,
        metrics=metrics,
    )
