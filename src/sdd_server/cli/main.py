"""SDD command-line interface."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="sdd", help="Specs-Driven Development CLI", add_completion=False)
console = Console()


def _project_root() -> Path:
    return Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()


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
def preflight() -> None:
    """Run preflight checks on the project spec structure."""
    from sdd_server.core.spec_manager import SpecManager

    root = _project_root()
    mgr = SpecManager(root)
    issues = mgr.validate_structure()

    if issues:
        console.print("[red]✗ Preflight failed:[/red]")
        for issue in issues:
            console.print(f"  • {issue}")
        raise typer.Exit(1)
    else:
        console.print("[green]✓ All spec checks passed[/green]")


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
        console.print(f"\n[yellow]⚠ Active bypasses: {len(state.bypasses)}[/yellow]")
        for bypass in state.bypasses:
            console.print(
                f"  [{bypass.timestamp.strftime('%Y-%m-%d %H:%M')}] {bypass.actor}: {bypass.reason}"
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
