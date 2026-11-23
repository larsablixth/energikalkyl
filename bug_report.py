"""Bug reports from the app: a pre-filled GitHub issue (pure, no Streamlit).

The repository is public, so a report is public: only non-personal context is
added (app version, language, grid operator, fuse, phases, price period, which
kind of consumption data). Never the address, the Tibber token, the meter ID or
the consumption itself.
"""

import subprocess
from pathlib import Path
from urllib.parse import urlencode

ISSUES_URL = "https://github.com/larsablixth/energikalkyl/issues/new"
MAX_URL_LEN = 7000  # GitHub refuses very long URLs; the description is shortened to fit

# sim_inputs keys that are safe to show publicly (see app.py "sim_inputs")
_SAFE_CONTEXT = ("grid_operator", "fuse_amps", "phases", "current_tariff", "price_range",
                 "price_days", "use_solar", "solar_kwp", "solar_source", "use_heating_model",
                 "own_consumption", "pricing_mode")


def app_version() -> str:
    """Short git commit of the running code, or '' when unknown."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             timeout=5, cwd=Path(__file__).resolve().parent)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def context_lines(sim_inputs: dict | None, language: str, version: str, has_results: bool) -> list[str]:
    """Non-personal facts about the session, one 'key: value' line each."""
    lines = [f"version: {version or 'okänd'}", f"språk: {language}",
             f"resultat beräknat: {'ja' if has_results else 'nej'}"]
    for k in _SAFE_CONTEXT:
        if sim_inputs and k in sim_inputs and sim_inputs[k] not in (None, ""):
            lines.append(f"{k}: {sim_inputs[k]}")
    return lines


def issue_url(title: str, what: str, expected: str, steps: str, context: list[str]) -> str:
    """URL that opens a new GitHub issue with title and body filled in."""
    def body(desc):
        parts = [
            "### Vad hände?", desc.strip() or "_(ej ifyllt)_", "",
            "### Vad förväntade du dig?", expected.strip() or "_(ej ifyllt)_", "",
            "### Vad gjorde du (steg)?", steps.strip() or "_(ej ifyllt)_", "",
            "### Appens läge (automatiskt, inga personuppgifter)", "```", *context, "```", "",
            "_Skickat från Energikalkyl. Bifoga inte förbrukningsfiler här — de innehåller ditt mätar-id "
            "och rapporten är offentlig._",
        ]
        return "\n".join(parts)

    t = (title.strip() or "Felrapport")[:120]
    desc = what
    url = f"{ISSUES_URL}?{urlencode({'title': t, 'labels': 'bug', 'body': body(desc)})}"
    while len(url) > MAX_URL_LEN and len(desc) > 200:
        desc = desc[: int(len(desc) * 0.8)] + " …(förkortad)"
        url = f"{ISSUES_URL}?{urlencode({'title': t, 'labels': 'bug', 'body': body(desc)})}"
    return url
