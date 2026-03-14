"""SDD command-line interface."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sdd_server.core.enforcement import EnforcementEngine

import typer
from rich.console import Console
from rich.table import Table

from sdd_server.core.enforcement import BYPASS_GRACE_SECONDS, EnforcementReport

app = typer.Typer(name="sdd", help="Specs-Driven Development CLI", add_completion=False)
console = Console()


def _project_root() -> Path:
    return Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()


def _build_engine(root: Path) -> EnforcementEngine:
    """Construct an EnforcementEngine from services rooted at *root*."""
    from sdd_server.core.enforcement import EnforcementEngine
    from sdd_server.core.metadata import MetadataManager
    from sdd_server.core.spec_manager import SpecManager
    from sdd_server.core.spec_validator import SpecValidator
    from sdd_server.infrastructure.git import GitClient

    return EnforcementEngine(
        project_root=root,
        spec_manager=SpecManager(root),
        spec_validator=SpecValidator(root),
        git_client=GitClient(root),
        metadata_manager=MetadataManager(root),
    )


# ---------------------------------------------------------------------------
# Preflight output helpers
# ---------------------------------------------------------------------------


def _print_preflight_interactive(report: EnforcementReport) -> None:
    """Rich-formatted preflight output for interactive use."""
    if report.bypass_active:
        console.print(f"[yellow]⚠ Active bypass:[/yellow] {report.bypass_reason}")

    if report.violations:
        console.print("[red]✗ Preflight BLOCKED — violations:[/red]")
        for v in report.violations:
            console.print(f"  [red]•[/red] [{v.rule}] {v.message}")
            if v.suggestion:
                console.print(f"    [dim]→ {v.suggestion}[/dim]")
    else:
        console.print("[green]✓ No blocking violations[/green]")

    if report.warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for w in report.warnings:
            console.print(f"  [yellow]•[/yellow] [{w.rule}] {w.message}")
            if w.suggestion:
                console.print(f"    [dim]→ {w.suggestion}[/dim]")

    summary = f"Checks: {report.checks_passed}/{report.checks_run} passed"
    if report.blocked:
        console.print(f"\n[red]{summary}[/red]")
        console.print('[dim]To bypass: sdd bypass --reason "<your reason>"[/dim]')
    else:
        console.print(f"\n[green]{summary}[/green]")


def _print_preflight_hook(report: EnforcementReport) -> None:
    """Plain-text preflight output for git hook context (no Rich markup)."""
    if report.bypass_active:
        print(f"SDD: Active bypass — {report.bypass_reason}")

    for v in report.violations:
        print(f"  BLOCKED [{v.rule}]: {v.message}")
        if v.suggestion:
            print(f"  → {v.suggestion}")

    for w in report.warnings:
        print(f"  WARN [{w.rule}]: {w.message}")

    if not report.blocked:
        print(f"SDD: OK ({report.checks_passed}/{report.checks_run} checks passed)")


def _print_preflight_json(report: EnforcementReport) -> None:
    """JSON output for CI/CD pipelines."""
    print(json.dumps(report.as_dict(), indent=2))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def init(
    project_name: str = typer.Argument(..., help="Name of the project"),
    description: str = typer.Option("", "--description", "-d", help="Short project description"),
    project_root: str = typer.Option("", "--root", "-r", help="Project root (default: cwd)"),
) -> None:
    """Initialize a new SDD project."""
    from sdd_server.core.initializer import ProjectInitializer
    from sdd_server.core.spec_manager import SpecManager
    from sdd_server.core.startup import StartupValidator
    from sdd_server.infrastructure.git import GitClient

    root = Path(project_root).resolve() if project_root else _project_root()
    git_client = GitClient(root)
    spec_manager = SpecManager(root)
    initializer = ProjectInitializer(root, spec_manager, git_client)

    try:
        initializer.init_new_project(project_name, description)
        console.print(
            f"[green]✓[/green] Project '[bold]{project_name}[/bold]' initialized at {root}"
        )
    except Exception as exc:
        console.print(f"[red]✗ Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    validator = StartupValidator(root)
    report = validator.run()
    for check in report.warnings:
        console.print(f"[yellow]⚠[/yellow] {check.message}")


@app.command()
def preflight(
    ci: bool = typer.Option(False, "--ci", help="CI/CD mode: JSON output, strict exit codes"),
    hook_mode: bool = typer.Option(
        False, "--hook-mode", help="Minimal output for git hook context", hidden=True
    ),
) -> None:
    """Run enforcement checks. Exits with code 1 if blocked."""
    root = _project_root()
    engine = _build_engine(root)
    report = engine.run(action="commit")

    if ci:
        _print_preflight_json(report)
    elif hook_mode:
        _print_preflight_hook(report)
    else:
        _print_preflight_interactive(report)

    if report.blocked:
        raise typer.Exit(1)


@app.command()
def bypass(
    reason: str = typer.Option(
        ..., "--reason", "-r", help="Justification for bypassing enforcement"
    ),
    action: str = typer.Option("commit", "--action", "-a", help="Action being bypassed"),
) -> None:
    """Record an enforcement bypass with an explicit reason (24 h grace period)."""
    from sdd_server.core.metadata import MetadataManager
    from sdd_server.infrastructure.git import GitClient
    from sdd_server.models.state import BypassRecord

    root = _project_root()
    git_client = GitClient(root)
    metadata = MetadataManager(root)

    actor = git_client.get_user_name()
    now = datetime.now(UTC)
    record = BypassRecord(timestamp=now, actor=actor, reason=reason, action=action)

    try:
        metadata.append_bypass(record)
    except Exception as exc:
        console.print(f"[red]✗ Could not record bypass:[/red] {exc}")
        raise typer.Exit(1) from exc

    grace_hours = BYPASS_GRACE_SECONDS // 3600
    console.print("[yellow]⚠ Bypass recorded[/yellow]")
    console.print(f"  Actor:   {actor}")
    console.print(f"  Action:  {action}")
    console.print(f"  Reason:  {reason}")
    console.print(f"  Expires: {grace_hours} h from now")
    console.print("[dim]This bypass will appear in 'sdd status' output.[/dim]")


@app.command()
def status() -> None:
    """Show project workflow state and status."""
    from sdd_server.core.metadata import MetadataManager
    from sdd_server.core.spec_manager import SpecManager

    root = _project_root()
    metadata = MetadataManager(root)
    spec_manager = SpecManager(root)
    state = metadata.load()
    issues = spec_manager.validate_structure()

    console.print(f"\n[bold]Project:[/bold] {root.name}")
    console.print(f"[bold]Workflow State:[/bold] {state.workflow_state.value}\n")

    if state.features:
        table = Table(title="Features")
        table.add_column("Feature", style="cyan")
        table.add_column("State", style="magenta")
        table.add_column("History")
        for fid, fs in state.features.items():
            table.add_row(fid, fs.state.value, str(len(fs.history)))
        console.print(table)

    if state.bypasses:
        now = datetime.now(UTC)
        active = []
        expired = []
        for bp in state.bypasses:
            ts = bp.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            elapsed = (now - ts).total_seconds()
            if elapsed < BYPASS_GRACE_SECONDS:
                active.append((bp, BYPASS_GRACE_SECONDS - elapsed))
            else:
                expired.append(bp)

        if active:
            console.print(f"\n[yellow]⚠ Active bypasses: {len(active)}[/yellow]")
            for bp, remaining in active:
                hrs = int(remaining // 3600)
                mins = int((remaining % 3600) // 60)
                console.print(
                    f"  [yellow]•[/yellow] [{bp.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                    f"{bp.actor}: {bp.reason}  [dim](expires in {hrs}h {mins}m)[/dim]"
                )

        if expired:
            console.print(f"\n[dim]Expired bypasses: {len(expired)}[/dim]")
            for bp in expired:
                console.print(
                    f"  [dim]• [{bp.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                    f"{bp.actor}: {bp.reason}[/dim]"
                )

    if issues:
        console.print("\n[red]Spec issues:[/red]")
        for issue in issues:
            console.print(f"  • {issue}")
    else:
        console.print("\n[green]✓ Spec structure OK[/green]")


@app.callback(invoke_without_command=True)
def version_callback(
    version: bool = typer.Option(False, "--version", "-v", is_eager=True, help="Show version"),
) -> None:
    """Show version or help when called without subcommand."""
    if version:
        console.print("sdd-server 0.1.0")
        raise typer.Exit()
