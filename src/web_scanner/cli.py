"""Command-line interface for the web scanner."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .orchestrator import ScanOrchestrator
from .utils import setup_logging

app = typer.Typer(
    name="web-scanner",
    help="Scan websites, extract content, and analyze for issues.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def scan(
    url: str = typer.Argument(..., help="The URL to scan"),
    max_depth: int = typer.Option(3, "--depth", "-d", help="Maximum crawl depth"),
    max_pages: int = typer.Option(100, "--max-pages", "-m", help="Maximum pages to crawl"),
    output_dir: Path = typer.Option(None, "--output", "-o", help="Output directory"),
    skip_screenshots: bool = typer.Option(False, "--no-screenshots", help="Skip screenshot capture"),
    skip_grammar: bool = typer.Option(False, "--no-grammar", help="Skip grammar analysis"),
    skip_links: bool = typer.Option(False, "--no-links", help="Skip broken link analysis"),
    skip_ocr: bool = typer.Option(False, "--no-ocr", help="Skip OCR analysis"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Scan a website and analyze its content."""
    setup_logging(verbose)

    console.print(Panel.fit(
        f"[bold blue]Web Scanner[/bold blue]\n"
        f"Scanning: [green]{url}[/green]\n"
        f"Max Depth: {max_depth} | Max Pages: {max_pages}",
        title="Starting Scan",
    ))

    try:
        orchestrator = ScanOrchestrator(
            url=url,
            max_depth=max_depth,
            max_pages=max_pages,
            skip_screenshots=skip_screenshots,
            skip_grammar=skip_grammar,
            skip_links=skip_links,
            skip_ocr=skip_ocr,
            output_dir=output_dir,
        )

        # Run the scan
        report = asyncio.run(orchestrator.run())

        # Display results
        _display_results(report, orchestrator.storage)

    except KeyboardInterrupt:
        console.print("\n[yellow]Scan cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


def _display_results(report, storage) -> None:
    """Display scan results in a formatted table."""
    console.print()

    # Summary table
    table = Table(title="Scan Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Pages Crawled", str(report.pages_crawled))
    table.add_row("Pages Analyzed", str(report.pages_analyzed))
    table.add_row("Grammar Issues", str(len(report.grammar_issues)))
    table.add_row("Broken Links", str(len(report.link_issues)))
    table.add_row("OCR Issues", str(len(report.ocr_issues)))

    if report.errors:
        table.add_row("Errors", str(len(report.errors)))

    console.print(table)

    # Issues summary
    if report.grammar_issues:
        console.print(f"\n[yellow]Top Grammar Issues:[/yellow]")
        for issue in report.grammar_issues[:5]:
            console.print(f"  • {issue.message}")
            if issue.suggestions:
                console.print(f"    Suggestion: {issue.suggestions[0]}")

    if report.link_issues:
        console.print(f"\n[yellow]Broken Links:[/yellow]")
        for issue in report.link_issues[:5]:
            console.print(f"  • {issue.target_url}")
            console.print(f"    Error: {issue.error_message}")

    # Output paths
    console.print(Panel.fit(
        f"Data: [cyan]{storage.get_output_dir()}[/cyan]\n"
        f"Reports: [cyan]{storage.get_reports_dir()}[/cyan]",
        title="Output Locations",
    ))


@app.command()
def version() -> None:
    """Show version information."""
    from . import __version__
    console.print(f"Web Scanner version {__version__}")


if __name__ == "__main__":
    app()
