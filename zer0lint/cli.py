"""CLI for zer0lint."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from zer0lint import __version__
from zer0lint.orchestrator import run_generate

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(help="zer0lint — mem0 extraction optimizer")


@app.command()
def generate(
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        help="Path to mem0 config.json (e.g., ~/.mem0/config.json)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    apply: bool = typer.Option(
        True, "--apply/--no-apply", help="Apply the generated prompt to config"
    ),
) -> None:
    """
    Generate a custom extraction prompt optimized for your mem0 system.

    This command:
    1. Samples your existing memories
    2. Analyzes what categories of information you're storing
    3. Generates a domain-specific extraction prompt
    4. Tests it against synthetic facts
    5. Applies it to your mem0 config (if score >= 4/5)

    Example:
        zer0lint generate --config ~/.mem0/config.json --verbose
    """

    if not config_path:
        # Try common locations
        candidates = [
            Path.home() / ".mem0" / "config.json",
            Path.home() / ".mem0_config.json",
            Path("config.json"),
        ]
        config_path = next((str(c) for c in candidates if c.exists()), None)

        if not config_path:
            err_console.print(
                "[red]Error:[/red] No config found. Provide with --config "
                "(e.g., --config ~/.mem0/config.json)"
            )
            raise typer.Exit(1)

    config_path = Path(config_path)
    if not config_path.exists():
        err_console.print(f"[red]Error:[/red] Config not found: {config_path}")
        raise typer.Exit(1)

    # Load config and initialize mem0
    try:
        with open(config_path) as f:
            config_dict = json.load(f)
    except Exception as e:
        err_console.print(f"[red]Error reading config:[/red] {e}")
        raise typer.Exit(1)

    # Initialize mem0 with the config
    try:
        from mem0 import Memory

        memory = Memory.from_config(config_dict)
    except Exception as e:
        err_console.print(f"[red]Error initializing mem0:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"\n[bold]zer0lint v{__version__} — mem0 extraction optimizer[/bold]\n")
    console.print(f"Config: {config_path}")
    console.print("Running optimization flow...\n")

    # Run the generate flow
    result = run_generate(memory, config_path=config_path if apply else None, verbose=verbose)

    # Display results
    if result["success"]:
        console.print("\n[bold green]✓ Optimization successful[/bold green]\n")

        if result["final_score"] is not None:
            score_color = "green" if result["final_score"] >= 4 else "yellow"
            console.print(
                f"Extraction quality: [bold {score_color}]{result['final_score']}/5[/bold {score_color}]"
            )

        if result["generated_prompt"]:
            console.print("\n[bold]Generated prompt:[/bold]\n")
            prompt_syntax = Syntax(
                result["generated_prompt"][:500] + ("..." if len(result["generated_prompt"]) > 500 else ""),
                "text",
                theme="monokai",
                line_numbers=False,
            )
            console.print(prompt_syntax)

        if result["applied"]:
            console.print(f"\n[green]✓ Prompt applied to config[/green]")
            if result["backup_path"]:
                console.print(f"  Backup saved: {result['backup_path']}")

        console.print("\nLog:")
        for log_entry in result["iteration_log"]:
            console.print(f"  • {log_entry}")
    else:
        console.print(f"[red]✗ Optimization failed[/red]\n")
        for log_entry in result["iteration_log"]:
            console.print(f"  • {log_entry}")
        raise typer.Exit(1)


@app.command()
def check(
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        help="Path to mem0 config.json",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """
    Check your current mem0 extraction pipeline health.

    Runs 5 synthetic facts through your current extraction and scores the result.
    """
    console.print("[bold]zer0lint check — extraction health assessment[/bold]\n")
    console.print("[yellow]Note: check command not yet implemented in v0.1[/yellow]")
    console.print("Use 'zer0lint generate' to diagnose and fix extraction issues.")


@app.command()
def prompts() -> None:
    """Show information about available domain prompts."""
    console.print("[bold]zer0lint domain prompts[/bold]\n")
    console.print("[yellow]Prompt management features coming in v0.2[/yellow]")


@app.callback(invoke_without_command=True)
def version(
    show_version: bool = typer.Option(
        None, "--version", help="Show version and exit"
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """zer0lint — mem0 extraction optimizer."""
    if show_version or (ctx.invoked_subcommand is None and show_version is not False):
        console.print(f"zer0lint v{__version__}")
        raise typer.Exit(0)


if __name__ == "__main__":
    app()
