"""Command-line interface for the web scanner."""

import asyncio
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
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
    # AI Analysis options
    enable_ai: bool = typer.Option(False, "--ai", help="Enable AI-powered analysis (requires API key)"),
    ai_api_key: str = typer.Option(
        None, "--ai-key", envvar="SCANNER_OPENROUTER_API_KEY",
        help="OpenRouter API key (or set SCANNER_OPENROUTER_API_KEY env var)"
    ),
    no_ai_text: bool = typer.Option(False, "--no-ai-text", help="Skip AI text analysis"),
    no_ai_html: bool = typer.Option(False, "--no-ai-html", help="Skip AI HTML analysis"),
    no_ai_visual: bool = typer.Option(False, "--no-ai-visual", help="Skip AI visual/screenshot analysis"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Scan a website and analyze its content."""
    setup_logging(verbose)

    # Check for API key if AI is enabled
    if enable_ai and not ai_api_key:
        ai_api_key = os.environ.get("SCANNER_OPENROUTER_API_KEY")
        if not ai_api_key:
            console.print("[red]Error: AI analysis requires an API key.[/red]")
            console.print("Provide it via --ai-key or set SCANNER_OPENROUTER_API_KEY environment variable.")
            raise typer.Exit(1)

    # Build feature list
    features = []
    if not skip_screenshots:
        features.append("Screenshots")
    if not skip_grammar:
        features.append("Grammar")
    if not skip_links:
        features.append("Links")
    if not skip_ocr and not skip_screenshots:
        features.append("OCR")
    if enable_ai:
        ai_features = []
        if not no_ai_text:
            ai_features.append("Text")
        if not no_ai_html:
            ai_features.append("HTML")
        if not no_ai_visual and not skip_screenshots:
            ai_features.append("Visual")
        if ai_features:
            features.append(f"AI ({', '.join(ai_features)})")

    console.print(Panel.fit(
        f"[bold blue]Web Scanner[/bold blue]\n"
        f"Scanning: [green]{url}[/green]\n"
        f"Max Depth: {max_depth} | Max Pages: {max_pages}\n"
        f"Features: {', '.join(features) if features else 'None'}",
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
            enable_ai=enable_ai,
            ai_api_key=ai_api_key,
            ai_analyze_text=not no_ai_text,
            ai_analyze_html=not no_ai_html,
            ai_analyze_screenshots=not no_ai_visual,
            output_dir=output_dir,
        )

        # Run the scan
        report = asyncio.run(orchestrator.run())

        # Display results
        _display_results(report, orchestrator.storage, enable_ai)

    except KeyboardInterrupt:
        console.print("\n[yellow]Scan cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


def _display_results(report, storage, enable_ai: bool = False) -> None:
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

    # AI Analysis results
    if enable_ai and report.ai_analyses:
        total_text_issues = sum(len(a.text_issues) for a in report.ai_analyses)
        total_html_issues = sum(len(a.html_issues) for a in report.ai_analyses)
        total_visual_issues = sum(len(a.visual_issues) for a in report.ai_analyses)

        table.add_row("AI Text Issues", str(total_text_issues))
        table.add_row("AI HTML Issues", str(total_html_issues))
        table.add_row("AI Visual Issues", str(total_visual_issues))

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

    # AI Analysis summary
    if enable_ai and report.ai_analyses:
        console.print(f"\n[bold magenta]AI Analysis Summary:[/bold magenta]")

        for analysis in report.ai_analyses[:3]:  # Show first 3 pages
            console.print(f"\n  [cyan]{analysis.url}[/cyan]")

            if analysis.visual_score is not None:
                score_color = "green" if analysis.visual_score >= 7 else "yellow" if analysis.visual_score >= 5 else "red"
                console.print(f"    Visual Score: [{score_color}]{analysis.visual_score:.1f}/10[/{score_color}]")

            # Show critical issues
            all_issues = analysis.text_issues + analysis.html_issues + analysis.visual_issues
            critical_issues = [i for i in all_issues if i.severity == "critical"]

            if critical_issues:
                console.print(f"    [red]Critical Issues ({len(critical_issues)}):[/red]")
                for issue in critical_issues[:3]:
                    desc = issue.description[:80] + "..." if len(issue.description) > 80 else issue.description
                    console.print(f"      • [{issue.category}] {desc}")

            # Show warning count
            warnings = [i for i in all_issues if i.severity == "warning"]
            if warnings:
                console.print(f"    [yellow]Warnings: {len(warnings)}[/yellow]")

    # Errors
    if report.errors:
        console.print(f"\n[red]Errors:[/red]")
        for error in report.errors[:5]:
            console.print(f"  • {error}")

    # Output paths
    html_report_path = storage.get_reports_dir() / "report.html"
    console.print(Panel.fit(
        f"Data: [cyan]{storage.get_output_dir()}[/cyan]\n"
        f"Reports: [cyan]{storage.get_reports_dir()}[/cyan]\n"
        f"HTML Report: [bold green]{html_report_path}[/bold green]",
        title="Output Locations",
    ))


@app.command()
def version() -> None:
    """Show version information."""
    from . import __version__
    console.print(f"Web Scanner version {__version__}")


if __name__ == "__main__":
    app()
