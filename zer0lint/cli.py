"""CLI for zer0lint v0.2."""

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
from zer0lint.fixer import detect_extraction_model
from zer0lint.orchestrator import run_check, run_generate

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(help="zer0lint — AI memory extraction diagnostics")

DEFAULT_CONFIG_CANDIDATES = [
    Path.home() / ".mem0" / "config.json",
    Path.home() / ".mem0_config.json",
    Path("config.json"),
]


def _load_config(config_path: Optional[str]) -> tuple[dict, Optional[Path]]:
    """Load mem0 config from path or auto-detect. Returns (config_dict, resolved_path)."""
    if config_path:
        p = Path(config_path)
        if not p.exists():
            err_console.print(f"[red]Config not found:[/red] {p}")
            raise typer.Exit(1)
    else:
        p = next((c for c in DEFAULT_CONFIG_CANDIDATES if c.exists()), None)
        if not p:
            err_console.print(
                "[red]No config found.[/red] Provide with --config (e.g., --config ~/.mem0/config.json)"
            )
            raise typer.Exit(1)

    try:
        with open(p) as f:
            return json.load(f), p
    except Exception as e:
        err_console.print(f"[red]Error reading config:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def check(
    config_path: Optional[str] = typer.Option(None, "--config", help="Path to mem0 config.json"),
    add_url: Optional[str] = typer.Option(None, "--add-url", help="HTTP endpoint for storing facts (e.g. http://localhost:19420/add)"),
    search_url: Optional[str] = typer.Option(None, "--search-url", help="HTTP endpoint for searching memories (e.g. http://localhost:19420/recall_b)"),
    http_wait: float = typer.Option(1.5, "--http-wait", help="Seconds to wait after add() before searching (increase for slow backends)"),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="Override test user_id for isolation (HTTP mode)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    n: int = typer.Option(5, "--facts", "-n", help="Number of test facts"),
) -> None:
    """
    Check extraction pipeline health — works with mem0 config or any HTTP memory endpoint.

    mem0 mode:  zer0lint check --config ~/.mem0/config.json
    HTTP mode:  zer0lint check --add-url http://localhost:19420/add --search-url http://localhost:19420/recall_b
    """
    # --- Validate flags ---
    if config_path and (add_url or search_url):
        err_console.print("[red]Cannot use both --config and --add-url/--search-url. Pick one mode.[/red]")
        raise typer.Exit(1)
    if bool(add_url) != bool(search_url):
        err_console.print("[red]--add-url and --search-url must be provided together.[/red]")
        raise typer.Exit(1)

    is_http = bool(add_url and search_url)

    console.print(f"\n[bold]zer0lint v{__version__} — extraction health check[/bold]")

    if is_http:
        console.print(f"Mode   : HTTP")
        console.print(f"Add    : {add_url}")
        console.print(f"Search : {search_url}\n")
        result = run_check(
            verbose=verbose, n_facts=n,
            add_url=add_url, search_url=search_url,
            http_timeout=30.0, http_user_id=user_id,
            wait_seconds=http_wait,
        )
    else:
        config_dict, resolved = _load_config(config_path)
        model = detect_extraction_model(config_dict)
        has_custom = bool(config_dict.get("custom_fact_extraction_prompt"))
        console.print(f"Config : {resolved}")
        console.print(f"Model  : {model}")
        console.print(f"Prompt : {'custom' if has_custom else 'default (mem0 built-in)'}\n")
        result = run_check(config_dict, verbose=verbose, n_facts=n)

    color = {"HEALTHY": "green", "ACCEPTABLE": "cyan", "DEGRADED": "yellow", "CRITICAL": "red"}.get(
        result["status"], "white"
    )
    console.print(
        f"Score  : [bold {color}]{result['score']}/{result['total']} ({result['pct']:.0f}%) — {result['status']}[/bold {color}]\n"
    )

    if not verbose:
        for d in result["details"]:
            icon = "✅" if d["found"] else ("⚠ " if d.get("stored") else "❌")
            console.print(f"  {icon} {d['label']}")

    if result["status"] in ("DEGRADED", "CRITICAL"):
        console.print(
            "\n[yellow]Run [bold]zer0lint generate[/bold] to diagnose and fix.[/yellow]"
        )
    elif result["status"] == "ACCEPTABLE":
        console.print("\n[cyan]Run [bold]zer0lint generate[/bold] to try improving to 5/5.[/cyan]")


@app.command()
def generate(
    config_path: Optional[str] = typer.Option(None, "--config", help="Path to mem0 config.json"),
    add_url: Optional[str] = typer.Option(None, "--add-url", help="HTTP endpoint for storing facts"),
    search_url: Optional[str] = typer.Option(None, "--search-url", help="HTTP endpoint for searching memories"),
    http_wait: float = typer.Option(1.5, "--http-wait", help="Seconds to wait after add() before searching"),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="Override test user_id for isolation (HTTP mode)"),
    verbose: bool = typer.Option(True, "--verbose/--quiet", "-v/-q"),
    apply: bool = typer.Option(True, "--apply/--dry-run", help="Apply fix to config (mem0 mode) or save prompt (HTTP mode)"),
    save_prompt: Optional[str] = typer.Option(None, "--save-prompt", help="Save generated prompt to file (HTTP mode)"),
    n: int = typer.Option(5, "--facts", "-n", help="Number of test facts"),
) -> None:
    """
    Diagnose and fix extraction — works with mem0 config or any HTTP memory endpoint.

    mem0 mode:  zer0lint generate --config ~/.mem0/config.json
    HTTP mode:  zer0lint generate --add-url http://localhost:19420/add --search-url http://localhost:19420/recall_b --save-prompt prompt.txt

    Runs three phases:
    1. Baseline recall test
    2. Re-test with zer0lint technical extraction prompt
    3. Apply fix — writes to config (mem0 mode) or saves to file (HTTP mode)
    """
    # --- Validate flags ---
    if config_path and (add_url or search_url):
        err_console.print("[red]Cannot use both --config and --add-url/--search-url. Pick one mode.[/red]")
        raise typer.Exit(1)
    if bool(add_url) != bool(search_url):
        err_console.print("[red]--add-url and --search-url must be provided together.[/red]")
        raise typer.Exit(1)

    is_http = bool(add_url and search_url)

    console.print(f"\n[bold]zer0lint v{__version__} — extraction optimizer[/bold]")

    if is_http:
        console.print(f"Mode   : HTTP")
        console.print(f"Add    : {add_url}")
        console.print(f"Search : {search_url}")
        if not apply:
            console.print("[yellow]Mode   : dry-run[/yellow]")
        console.print()
        result = run_generate(
            verbose=verbose,
            n_facts=n,
            add_url=add_url,
            search_url=search_url,
            http_timeout=30.0,
            http_user_id=user_id,
            save_prompt_path=save_prompt if apply else None,
            wait_seconds=http_wait,
        )
    else:
        config_dict, resolved = _load_config(config_path)
        model = detect_extraction_model(config_dict)
        has_custom = bool(config_dict.get("custom_fact_extraction_prompt"))
        console.print(f"Config : {resolved}")
        console.print(f"Model  : {model}")
        console.print(f"Prompt : {'custom' if has_custom else 'default (mem0 built-in)'}")
        if not apply:
            console.print("[yellow]Mode   : dry-run (will not write to config)[/yellow]")
        console.print()
        result = run_generate(
            base_config=config_dict,
            config_path=resolved if apply else None,
            verbose=verbose,
            n_facts=n,
            wait_seconds=http_wait,
        )

    if not result["success"]:
        err_console.print("[red]✗ Generate failed.[/red]")
        raise typer.Exit(1)

    if result.get("verdict") == "already_healthy":
        console.print("\n[green]✅ Your extraction is already at 100%. No changes needed.[/green]")
        raise typer.Exit(0)

    # Show before/after
    init_pct = result.get("initial_pct", 0)
    impr_pct = result.get("improved_pct", 0)
    imp_pp = result.get("improvement_pp", 0)

    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  Before : {result['initial_score']}/{result.get('total', 5) if 'total' in result else 5} ({init_pct:.0f}%)")
    console.print(f"  After  : {result['improved_score']}/{result.get('total', 5) if 'total' in result else 5} ({impr_pct:.0f}%)")
    imp_color = "green" if imp_pp > 0 else "red"
    console.print(f"  Δ      : [{imp_color}]{imp_pp:+.0f}pp[/{imp_color}]")

    verdict = result.get("verdict")
    if verdict == "improved" and result.get("applied"):
        console.print(f"\n[green]✅ Fix applied to config.[/green]")
        if result.get("backup_path"):
            console.print(f"   Backup: {result['backup_path']}")
        console.print("\n[dim]Restart your agent to pick up the new extraction prompt.[/dim]")
    elif verdict == "improved" and result.get("saved_prompt_path"):
        console.print(f"\n[green]✅ Prompt saved to {result['saved_prompt_path']}[/green]")
        console.print("[dim]Add this as the extraction prompt in your memory system's config.[/dim]")
    elif verdict == "improved" and is_http and not result.get("saved_prompt_path"):
        console.print(f"\n[cyan]Would improve by {imp_pp:+.0f}pp.[/cyan]")
        console.print("[dim]Use --save-prompt <file> to save the prompt, then add it to your memory system's extraction config.[/dim]")
    elif verdict == "improved" and not result.get("applied"):
        console.print(f"\n[cyan]Would improve by {imp_pp:+.0f}pp — run without --dry-run to apply.[/cyan]")
    elif verdict == "no_improvement":
        console.print(f"\n[yellow]⚠ zer0lint prompt did not improve recall on this config.[/yellow]")
        console.print("[dim]Your current setup may already be optimized, or a different domain prompt is needed.[/dim]")
    elif verdict == "below_threshold":
        console.print(f"\n[yellow]⚠ Improvement detected but below threshold — not applying automatically.[/yellow]")


@app.callback(invoke_without_command=True)
def version_cb(
    show_version: bool = typer.Option(None, "--version", is_eager=True, help="Show version"),
    ctx: typer.Context = typer.Context,
) -> None:
    """zer0lint — AI memory extraction diagnostics."""
    if show_version:
        console.print(f"zer0lint v{__version__}")
        raise typer.Exit(0)


if __name__ == "__main__":
    app()
