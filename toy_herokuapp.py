import asyncio
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai.mcp import MCPServerStdio

from bdi import BDI
from bdi.schemas import DesireStatus
from codex import CodexModel, CodexProvider


load_dotenv()


# Hardcoded toy demo configuration (edit these constants to change behavior).
MODEL_NAME = "gpt-5.3-codex"
MAX_CYCLES = 20
VERBOSE = True
TASKS_TO_RUN = ["01", "02", "03", "04", "05", "06", "07"]
OUTPUT_DIR = "/Users/douglas/code/masters/pydantic-ai-bdi/output/playwright"

TARGET_URL = "https://the-internet.herokuapp.com/"
CYCLE_SLEEP_SECONDS = 1.0


@dataclass(frozen=True)
class HerokuappTask:
    number: str
    title: str
    desire_prompt: str
    summary_prompt: str


def build_playwright_server() -> MCPServerStdio:
    return MCPServerStdio(
        "npx",
        args=["-y", "@playwright/mcp@latest"],
        tool_prefix="playwright",
        timeout=300,
    )


def build_tasks() -> list[HerokuappTask]:
    return [
        HerokuappTask(
            number="01",
            title="Open home page and report title and current URL",
            desire_prompt=(
                "Use the available Playwright browser tools to open "
                f"{TARGET_URL}. Confirm the page has loaded. Gather the page title and "
                "current URL. Perform only this task. Stop once the page is open and "
                "you have collected the title and current URL."
            ),
            summary_prompt=(
                "You just completed Task 01 against the-internet.herokuapp.com. "
                "Use Playwright tools if needed to inspect the current page and return "
                "a plain-text summary using exactly this template:\n"
                "Task: 01\n"
                "Current URL: <value>\n"
                "Page Title: <value>\n"
                "Notes: <value>"
            ),
        ),
        HerokuappTask(
            number="02",
            title="Click first link and report destination URL and content",
            desire_prompt=(
                "Use Playwright tools to open "
                f"{TARGET_URL}. Click the first available link on the page. After "
                "navigation, gather the destination URL and the visible page content. "
                "Perform only this task. Stop once you have the destination URL and "
                "content."
            ),
            summary_prompt=(
                "You just completed Task 02. Use Playwright tools if needed and return "
                "a plain-text summary using exactly this template:\n"
                "Task: 02\n"
                "Clicked Link (best effort): <value>\n"
                "Destination URL: <value>\n"
                "Page Title: <value>\n"
                "Visible Content: <value>\n"
                "Notes: <value>"
            ),
        ),
        HerokuappTask(
            number="03",
            title="Form Authentication login and report destination URL and content",
            desire_prompt=(
                "Use Playwright tools to open "
                f"{TARGET_URL}, find the 'Form Authentication' page, and access it. "
                "Find the username and password shown on that page, fill the login "
                "inputs, and click the login button. Then gather the destination URL "
                "after login and the visible page content. Perform only this task. Stop "
                "after login and data collection are complete."
            ),
            summary_prompt=(
                "You just completed Task 03. Use Playwright tools if needed and return "
                "a plain-text summary using exactly this template:\n"
                "Task: 03\n"
                "Form Authentication Page URL: <value>\n"
                "Username Used: <value>\n"
                "Password Used: <value>\n"
                "Destination URL After Login: <value>\n"
                "Page Title: <value>\n"
                "Visible Content: <value>\n"
                "Notes: <value>"
            ),
        ),
        HerokuappTask(
            number="04",
            title="Hovers page and user names",
            desire_prompt=(
                "Use Playwright tools to open "
                f"{TARGET_URL}, find the 'Hovers' page, and access it. Find the names "
                "of the users shown on that page. Perform only this task. Stop once you "
                "have collected the user names."
            ),
            summary_prompt=(
                "You just completed Task 04. Use Playwright tools if needed and return "
                "a plain-text summary using exactly this template:\n"
                "Task: 04\n"
                "Page URL: <value>\n"
                "Users Found:\n"
                "- <user 1>\n"
                "- <user 2>\n"
                "- <user 3>\n"
                "Notes: <value>"
            ),
        ),
        HerokuappTask(
            number="05",
            title="Checkboxes page click all checkboxes",
            desire_prompt=(
                "Use Playwright tools to open "
                f"{TARGET_URL}, find the 'Checkboxes' page, and access it. Click all "
                "checkboxes so they end in the checked state. Perform only this task. "
                "Stop once all checkboxes are checked."
            ),
            summary_prompt=(
                "You just completed Task 05. Use Playwright tools if needed and return "
                "a plain-text summary using exactly this template:\n"
                "Task: 05\n"
                "Page URL: <value>\n"
                "Checkbox Count: <value>\n"
                "Checked States After Clicking All: <value>\n"
                "Notes: <value>"
            ),
        ),
        HerokuappTask(
            number="06",
            title="Context Menu page right-click and report alert text",
            desire_prompt=(
                "Use Playwright tools to open "
                f"{TARGET_URL}, find the 'Context Menu' page, and access it. Right-click "
                "inside the box with id or label 'hot-spot'. Capture the alert text. "
                "Perform only this task. Stop once you have captured the alert text."
            ),
            summary_prompt=(
                "You just completed Task 06. Use Playwright tools if needed and return "
                "a plain-text summary using exactly this template:\n"
                "Task: 06\n"
                "Page URL: <value>\n"
                "Alert Text: <value>\n"
                "Notes: <value>"
            ),
        ),
        HerokuappTask(
            number="07",
            title="Data Tables sort and return current table data order",
            desire_prompt=(
                "Use Playwright tools to open "
                f"{TARGET_URL}, find the 'Data Tables' page, and access it. In Example "
                "1 table, left click on 'First Name'. In Example 2 table, left click on "
                "'Last Name'. Then gather the rows from both tables in their current "
                "order. Perform only this task. Stop once both tables have been sorted "
                "and the current row order is collected."
            ),
            summary_prompt=(
                "You just completed Task 07. Use Playwright tools if needed and return "
                "a plain-text summary using exactly this template:\n"
                "Task: 07\n"
                "Page URL: <value>\n"
                "Example 1 Current Order:\n"
                "- <Last Name | First Name | Email | Due | Web Site>\n"
                "- <row 2>\n"
                "- <row 3>\n"
                "- <row 4>\n"
                "Example 2 Current Order:\n"
                "- <Last Name | First Name | Email | Due | Web Site>\n"
                "- <row 2>\n"
                "- <row 3>\n"
                "- <row 4>\n"
                "Notes: <value>"
            ),
        ),
    ]


def select_tasks(all_tasks: list[HerokuappTask]) -> list[HerokuappTask]:
    task_by_number = {task.number: task for task in all_tasks}
    selected: list[HerokuappTask] = []

    for task_number in TASKS_TO_RUN:
        task = task_by_number.get(task_number)
        if not task:
            print(f"[WARN] Unknown task number in TASKS_TO_RUN: {task_number}")
            continue
        selected.append(task)

    return selected


def get_primary_desire_status(agent: BDI) -> DesireStatus | None:
    if not agent.desires:
        return None
    return agent.desires[0].status


def create_agent(model: CodexModel, task: HerokuappTask, log_path: Path) -> BDI:
    return BDI(
        model,
        desires=[task.desire_prompt],
        intentions=[task.title],
        verbose=VERBOSE,
        enable_human_in_the_loop=False,
        log_file_path=str(log_path),
        mcp_servers=[build_playwright_server()],
    )


async def run_task(model: CodexModel, task: HerokuappTask, output_path: Path) -> None:
    log_path = output_path / f"herokuapp-task-{task.number}.log"

    print(f"\n=== Task {task.number}: {task.title} ===")
    print(f"Target: {TARGET_URL}")

    cycles_run = 0
    outcome = "unknown"
    error_message: str | None = None
    summary_text: str | None = None

    try:
        agent = create_agent(model, task, log_path)

        async with agent.run_mcp_servers():
            for cycle in range(1, MAX_CYCLES + 1):
                cycles_run = cycle
                print(f"\n----- Task {task.number} | Cycle {cycle}/{MAX_CYCLES} -----")

                cycle_status = await agent.bdi_cycle()
                desire_status = get_primary_desire_status(agent)

                if desire_status in (DesireStatus.ACHIEVED, DesireStatus.FAILED):
                    outcome = desire_status.value
                    break

                if cycle_status in {"stopped", "interrupted"}:
                    outcome = cycle_status
                    break

                await asyncio.sleep(CYCLE_SLEEP_SECONDS)
            else:
                outcome = "timed_out"

            print(f"\n----- Task {task.number} | Summary Extraction -----")
            try:
                summary_result = await agent.run(task.summary_prompt)
                summary_text = str(summary_result.output).strip()
            except Exception as exc:
                error_message = (
                    f"{error_message}; summary extraction failed: {exc}"
                    if error_message
                    else f"summary extraction failed: {exc}"
                )
                print(f"[ERROR] Summary extraction failed: {exc}")

    except Exception as exc:
        outcome = "error"
        error_message = str(exc)
        print(
            f"[ERROR] Task {task.number} failed before completion "
            f"(including MCP startup): {exc}"
        )
        print("[INFO] Continuing to the next task.")

    print(f"\n=== Task {task.number} Result ===")
    print(f"Status: {outcome}")
    print(f"Cycles Run: {cycles_run}/{MAX_CYCLES}")
    if error_message:
        print(f"Error: {error_message}")
    if summary_text:
        print(summary_text)
    else:
        print("Summary: (unavailable)")
    print(f"Log File: {log_path}")


async def main() -> None:
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    tasks = select_tasks(build_tasks())
    if not tasks:
        print("No valid tasks selected. Edit TASKS_TO_RUN in toy_herokuapp.py.")
        return

    print("=== Herokuapp BDI + Playwright Toy Run ===")
    print(f"Model: {MODEL_NAME}")
    print(f"Max Cycles Per Task: {MAX_CYCLES}")
    print(f"Verbose: {VERBOSE}")
    print(f"Tasks: {', '.join(task.number for task in tasks)}")
    print(f"Raw Logs Directory: {output_path}")

    provider = CodexProvider()
    model = CodexModel(MODEL_NAME, provider=provider)

    for task in tasks:
        await run_task(model, task, output_path)

    print("\n=== Toy Run Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
