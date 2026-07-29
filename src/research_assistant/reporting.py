from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.research_assistant.models import ResearchReport


def write_research_report(report: ResearchReport, output_directory: str | Path) -> dict[str, Path]:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "research_report.json"
    markdown_path = directory / "research_report.md"
    json_path.write_text(json.dumps(asdict(report), indent=2, default=str), encoding="utf-8")

    lines = [
        "# Atlas Research Recommendation",
        "",
        f"**Objective:** {report.request.objective}",
        f"**Summary:** {report.summary}",
        "",
        "## Candidate ranking",
        "",
        "| Rank | Candidate | Strategy | Decision | Score | Reasons |",
        "|---:|---|---|---|---:|---|",
    ]
    for rank, assessment in enumerate(report.assessments, start=1):
        evidence = assessment.evidence
        reasons = ", ".join(assessment.reasons) or "none"
        lines.append(
            f"| {rank} | {evidence.candidate_id} | {evidence.strategy} | "
            f"{assessment.decision.value} | {assessment.score:.4f} | {reasons} |"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This report is research evidence only. Manual approval remains required, and no live "
            "orders are submitted by the research assistant.",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}
