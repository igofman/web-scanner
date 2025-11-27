"""HTML report generator for beautiful, modern static reports."""

import html
from datetime import datetime
from pathlib import Path

from ..models import AnalysisReport


def generate_html_report(report: AnalysisReport, output_path: Path) -> Path:
    """Generate a beautiful static HTML report."""

    # Calculate stats
    total_issues = (
        len(report.grammar_issues) +
        len(report.link_issues) +
        len(report.ocr_issues)
    )

    ai_stats = {}
    if report.ai_analyses:
        ai_stats = {
            "pages": len(report.ai_analyses),
            "text_issues": sum(len(a.text_issues) for a in report.ai_analyses),
            "html_issues": sum(len(a.html_issues) for a in report.ai_analyses),
            "visual_issues": sum(len(a.visual_issues) for a in report.ai_analyses),
        }
        ai_stats["total"] = ai_stats["text_issues"] + ai_stats["html_issues"] + ai_stats["visual_issues"]

        # Count by severity
        all_issues = []
        for a in report.ai_analyses:
            all_issues.extend(a.text_issues + a.html_issues + a.visual_issues)
        ai_stats["critical"] = sum(1 for i in all_issues if i.severity == "critical")
        ai_stats["warning"] = sum(1 for i in all_issues if i.severity == "warning")
        ai_stats["info"] = sum(1 for i in all_issues if i.severity == "info")

        # Average visual score
        scores = [a.visual_score for a in report.ai_analyses if a.visual_score is not None]
        ai_stats["avg_score"] = sum(scores) / len(scores) if scores else None

    # Calculate duration
    duration = ""
    if report.scan_completed:
        delta = report.scan_completed - report.scan_started
        minutes, seconds = divmod(int(delta.total_seconds()), 60)
        duration = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web Scanner Report - {html.escape(report.base_url)}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --info: #3b82f6;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-400: #9ca3af;
            --gray-500: #6b7280;
            --gray-600: #4b5563;
            --gray-700: #374151;
            --gray-800: #1f2937;
            --gray-900: #111827;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: var(--gray-800);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        /* Header */
        .header {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 1.5rem;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        }}

        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .logo {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .logo-icon {{
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.5rem;
        }}

        .logo-text {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--gray-900);
        }}

        .scan-meta {{
            text-align: right;
            color: var(--gray-500);
            font-size: 0.875rem;
        }}

        .url-display {{
            background: var(--gray-100);
            padding: 1rem 1.5rem;
            border-radius: 0.75rem;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 1rem;
            color: var(--primary-dark);
            word-break: break-all;
        }}

        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.2);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.3);
        }}

        .stat-icon {{
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            margin-bottom: 1rem;
        }}

        .stat-icon.primary {{ background: rgba(99, 102, 241, 0.1); color: var(--primary); }}
        .stat-icon.success {{ background: rgba(16, 185, 129, 0.1); color: var(--success); }}
        .stat-icon.warning {{ background: rgba(245, 158, 11, 0.1); color: var(--warning); }}
        .stat-icon.danger {{ background: rgba(239, 68, 68, 0.1); color: var(--danger); }}
        .stat-icon.info {{ background: rgba(59, 130, 246, 0.1); color: var(--info); }}

        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--gray-900);
            margin-bottom: 0.25rem;
        }}

        .stat-label {{
            color: var(--gray-500);
            font-size: 0.875rem;
            font-weight: 500;
        }}

        /* Score Card */
        .score-card {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
        }}

        .score-card .stat-icon {{
            background: rgba(255, 255, 255, 0.2);
            color: white;
        }}

        .score-card .stat-value {{
            color: white;
        }}

        .score-card .stat-label {{
            color: rgba(255, 255, 255, 0.8);
        }}

        /* Section */
        .section {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.2);
        }}

        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--gray-200);
        }}

        .section-title {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--gray-900);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .badge-danger {{ background: rgba(239, 68, 68, 0.1); color: var(--danger); }}
        .badge-warning {{ background: rgba(245, 158, 11, 0.1); color: var(--warning); }}
        .badge-success {{ background: rgba(16, 185, 129, 0.1); color: var(--success); }}
        .badge-info {{ background: rgba(59, 130, 246, 0.1); color: var(--info); }}

        /* Issue List */
        .issue-list {{
            list-style: none;
        }}

        .issue-item {{
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 0.75rem;
            border-left: 4px solid;
            background: var(--gray-50);
        }}

        .issue-item.critical {{
            border-color: var(--danger);
            background: rgba(239, 68, 68, 0.05);
        }}

        .issue-item.warning {{
            border-color: var(--warning);
            background: rgba(245, 158, 11, 0.05);
        }}

        .issue-item.info {{
            border-color: var(--info);
            background: rgba(59, 130, 246, 0.05);
        }}

        .issue-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.5rem;
        }}

        .issue-title {{
            font-weight: 600;
            color: var(--gray-800);
        }}

        .issue-category {{
            font-size: 0.75rem;
            padding: 0.125rem 0.5rem;
            border-radius: 4px;
            background: var(--gray-200);
            color: var(--gray-600);
        }}

        .issue-description {{
            color: var(--gray-600);
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }}

        .issue-suggestion {{
            color: var(--success);
            font-size: 0.875rem;
            display: flex;
            align-items: flex-start;
            gap: 0.5rem;
        }}

        .issue-context {{
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.8rem;
            background: var(--gray-100);
            padding: 0.5rem;
            border-radius: 4px;
            color: var(--gray-700);
            margin-top: 0.5rem;
        }}

        /* AI Analysis */
        .ai-page {{
            border: 1px solid var(--gray-200);
            border-radius: 0.75rem;
            margin-bottom: 1rem;
            overflow: hidden;
        }}

        .ai-page-header {{
            background: var(--gray-50);
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }}

        .ai-page-url {{
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.875rem;
            color: var(--primary-dark);
        }}

        .ai-score {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .score-bar {{
            width: 100px;
            height: 8px;
            background: var(--gray-200);
            border-radius: 4px;
            overflow: hidden;
        }}

        .score-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }}

        .score-fill.excellent {{ background: var(--success); }}
        .score-fill.good {{ background: var(--info); }}
        .score-fill.fair {{ background: var(--warning); }}
        .score-fill.poor {{ background: var(--danger); }}

        .ai-page-content {{
            padding: 1rem;
            display: none;
        }}

        .ai-page.expanded .ai-page-content {{
            display: block;
        }}

        .ai-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }}

        .ai-summary-card {{
            background: var(--gray-50);
            padding: 1rem;
            border-radius: 0.5rem;
        }}

        .ai-summary-title {{
            font-weight: 600;
            font-size: 0.875rem;
            color: var(--gray-700);
            margin-bottom: 0.5rem;
        }}

        .ai-summary-text {{
            color: var(--gray-600);
            font-size: 0.875rem;
        }}

        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 3rem;
            color: var(--gray-500);
        }}

        .empty-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 2rem;
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.875rem;
        }}

        .footer a {{
            color: white;
            text-decoration: none;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}

            .header-top {{
                flex-direction: column;
            }}

            .scan-meta {{
                text-align: left;
            }}

            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        /* Collapsible */
        .collapsible-toggle {{
            cursor: pointer;
            user-select: none;
        }}

        .collapsible-toggle::after {{
            content: '\\25BC';
            font-size: 0.75rem;
            margin-left: 0.5rem;
            transition: transform 0.2s;
        }}

        .collapsed .collapsible-toggle::after {{
            transform: rotate(-90deg);
        }}

        .collapsed .collapsible-content {{
            display: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="header-top">
                <div class="logo">
                    <div class="logo-icon">&#128270;</div>
                    <span class="logo-text">Web Scanner Report</span>
                </div>
                <div class="scan-meta">
                    <div>Scanned: {report.scan_started.strftime('%B %d, %Y at %H:%M')}</div>
                    <div>Duration: {duration}</div>
                </div>
            </div>
            <div class="url-display">{html.escape(report.base_url)}</div>
        </header>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon primary">&#128196;</div>
                <div class="stat-value">{report.pages_crawled}</div>
                <div class="stat-label">Pages Crawled</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon success">&#9989;</div>
                <div class="stat-value">{report.pages_analyzed}</div>
                <div class="stat-label">Pages Analyzed</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon warning">&#9888;</div>
                <div class="stat-value">{total_issues}</div>
                <div class="stat-label">Issues Found</div>
            </div>
            {_generate_fourth_stat_card(ai_stats, report)}
        </div>

        {_generate_ai_section(report, ai_stats)}

        {_generate_grammar_section(report)}

        {_generate_links_section(report)}

        {_generate_ocr_section(report)}

        {_generate_errors_section(report)}

        <!-- Footer -->
        <footer class="footer">
            <p>Generated by <strong>Web Scanner</strong> &mdash; Powered by Playwright & AI</p>
        </footer>
    </div>

    <script>
        // Toggle collapsible sections
        document.querySelectorAll('.ai-page-header').forEach(header => {{
            header.addEventListener('click', () => {{
                header.parentElement.classList.toggle('expanded');
            }});
        }});

        document.querySelectorAll('.section-header.collapsible-toggle').forEach(header => {{
            header.addEventListener('click', () => {{
                header.parentElement.classList.toggle('collapsed');
            }});
        }});

        // Expand first AI page by default
        const firstAiPage = document.querySelector('.ai-page');
        if (firstAiPage) firstAiPage.classList.add('expanded');
    </script>
</body>
</html>"""

    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def _generate_fourth_stat_card(ai_stats: dict, report: AnalysisReport) -> str:
    """Generate the fourth stat card (score or errors)."""
    if ai_stats.get("avg_score"):
        avg_score = ai_stats["avg_score"]
        return f'''<div class="stat-card score-card">
                <div class="stat-icon">&#11088;</div>
                <div class="stat-value">{avg_score:.1f}/10</div>
                <div class="stat-label">Avg Visual Score</div>
            </div>'''
    else:
        return f'''<div class="stat-card">
                <div class="stat-icon danger">&#10060;</div>
                <div class="stat-value">{len(report.errors)}</div>
                <div class="stat-label">Errors</div>
            </div>'''


def _generate_ai_section(report: AnalysisReport, ai_stats: dict) -> str:
    """Generate AI analysis section."""
    if not report.ai_analyses:
        return ""

    pages_html = ""
    for analysis in report.ai_analyses:
        score = analysis.visual_score or 0
        score_class = "excellent" if score >= 8 else "good" if score >= 6 else "fair" if score >= 4 else "poor"

        issues_html = ""
        all_issues = analysis.text_issues + analysis.html_issues + analysis.visual_issues
        for issue in sorted(all_issues, key=lambda x: {"critical": 0, "warning": 1, "info": 2}.get(x.severity, 3)):
            issues_html += f'''
            <div class="issue-item {issue.severity}">
                <div class="issue-header">
                    <span class="issue-title">{html.escape(issue.description[:100])}</span>
                    <span class="issue-category">{html.escape(issue.category)}</span>
                </div>
                {f'<div class="issue-description">{html.escape(issue.location)}</div>' if issue.location else ''}
                {f'<div class="issue-suggestion">&#128161; {html.escape(issue.suggestion)}</div>' if issue.suggestion else ''}
            </div>'''

        summaries_html = ""
        if analysis.text_summary or analysis.html_summary or analysis.visual_summary:
            summaries_html = '<div class="ai-summary">'
            if analysis.text_summary:
                text_summary_str = analysis.text_summary if isinstance(analysis.text_summary, str) else str(analysis.text_summary)
                summaries_html += f'''
                <div class="ai-summary-card">
                    <div class="ai-summary-title">&#128221; Text Analysis</div>
                    <div class="ai-summary-text">{html.escape(text_summary_str)}</div>
                </div>'''
            if analysis.html_summary:
                html_summary_str = analysis.html_summary if isinstance(analysis.html_summary, str) else str(analysis.html_summary)
                summaries_html += f'''
                <div class="ai-summary-card">
                    <div class="ai-summary-title">&#128187; HTML Analysis</div>
                    <div class="ai-summary-text">{html.escape(html_summary_str)}</div>
                </div>'''
            if analysis.visual_summary:
                # visual_summary can be a dict from enhanced AI response
                if isinstance(analysis.visual_summary, dict):
                    visual_summary_str = analysis.visual_summary.get("overall_quality", str(analysis.visual_summary))
                else:
                    visual_summary_str = str(analysis.visual_summary) if analysis.visual_summary else ""
                summaries_html += f'''
                <div class="ai-summary-card">
                    <div class="ai-summary-title">&#127912; Visual Analysis</div>
                    <div class="ai-summary-text">{html.escape(visual_summary_str)}</div>
                </div>'''
            summaries_html += '</div>'

        # Add text corrections section if available
        text_corrections_html = ""
        if hasattr(analysis, 'text_corrections') and analysis.text_corrections:
            text_corrections_html = '<div style="margin-top: 1rem;"><h4 style="color: var(--gray-700); margin-bottom: 0.5rem;">&#9998; Text Corrections</h4>'
            for tc in analysis.text_corrections[:10]:
                confidence_str = f" (confidence: {tc.confidence}/5)" if hasattr(tc, 'confidence') and tc.confidence else ""
                text_corrections_html += f'''
                <div class="issue-item info" style="border-color: var(--success);">
                    <div class="issue-header">
                        <span class="issue-title" style="text-decoration: line-through; color: var(--danger);">{html.escape(tc.original)}</span>
                        <span class="issue-category">Text Correction{confidence_str}</span>
                    </div>
                    <div class="issue-suggestion" style="font-weight: 600;">&#10004; {html.escape(tc.correction)}</div>
                    <div class="issue-description">{html.escape(tc.explanation)}</div>
                </div>'''
            text_corrections_html += '</div>'

        # Build score HTML separately to avoid nested f-string issues
        score_html = ""
        if analysis.visual_score:
            score_width = score * 10
            score_html = f'''<div class="ai-score">
                    <span>{score:.1f}/10</span>
                    <div class="score-bar">
                        <div class="score-fill {score_class}" style="width: {score_width}%"></div>
                    </div>
                </div>'''

        issues_list_html = f'<ul class="issue-list">{issues_html}</ul>' if issues_html else '<div class="empty-state"><div class="empty-icon">&#9989;</div><p>No issues found</p></div>'

        pages_html += f'''
        <div class="ai-page">
            <div class="ai-page-header">
                <span class="ai-page-url">{html.escape(analysis.url)}</span>
                {score_html}
            </div>
            <div class="ai-page-content">
                {summaries_html}
                {issues_list_html}
                {text_corrections_html}
            </div>
        </div>'''

    return f'''
    <section class="section">
        <div class="section-header collapsible-toggle">
            <h2 class="section-title">&#129302; AI-Powered Analysis</h2>
            <div>
                <span class="badge badge-danger">{ai_stats.get("critical", 0)} critical</span>
                <span class="badge badge-warning">{ai_stats.get("warning", 0)} warnings</span>
                <span class="badge badge-info">{ai_stats.get("info", 0)} info</span>
            </div>
        </div>
        <div class="collapsible-content">
            {pages_html}
        </div>
    </section>'''


def _generate_grammar_section(report: AnalysisReport) -> str:
    """Generate grammar issues section."""
    if not report.grammar_issues:
        return ""

    issues_html = ""
    for issue in report.grammar_issues[:50]:  # Limit to 50
        issues_html += f'''
        <div class="issue-item warning">
            <div class="issue-header">
                <span class="issue-title">{html.escape(issue.message)}</span>
                <span class="issue-category">{html.escape(issue.category or 'Grammar')}</span>
            </div>
            <div class="issue-context">...{html.escape(issue.context)}...</div>
            {f'<div class="issue-suggestion">&#128161; Suggestions: {html.escape(", ".join(issue.suggestions[:3]))}</div>' if issue.suggestions else ''}
        </div>'''

    more = f'<p style="text-align: center; color: var(--gray-500);">...and {len(report.grammar_issues) - 50} more issues</p>' if len(report.grammar_issues) > 50 else ''

    return f'''
    <section class="section">
        <div class="section-header collapsible-toggle">
            <h2 class="section-title">&#128221; Grammar Issues</h2>
            <span class="badge badge-warning">{len(report.grammar_issues)} issues</span>
        </div>
        <div class="collapsible-content">
            <ul class="issue-list">{issues_html}</ul>
            {more}
        </div>
    </section>'''


def _generate_links_section(report: AnalysisReport) -> str:
    """Generate broken links section."""
    if not report.link_issues:
        return ""

    issues_html = ""
    for issue in report.link_issues[:50]:
        issues_html += f'''
        <div class="issue-item critical">
            <div class="issue-header">
                <span class="issue-title">{html.escape(issue.target_url[:80])}</span>
                <span class="issue-category">{html.escape(issue.error_type or 'Broken')}</span>
            </div>
            <div class="issue-description">Source: {html.escape(issue.source_url)}</div>
            <div class="issue-description" style="color: var(--danger);">&#10060; {html.escape(issue.error_message or 'Link is broken')}</div>
        </div>'''

    more = f'<p style="text-align: center; color: var(--gray-500);">...and {len(report.link_issues) - 50} more broken links</p>' if len(report.link_issues) > 50 else ''

    return f'''
    <section class="section">
        <div class="section-header collapsible-toggle">
            <h2 class="section-title">&#128279; Broken Links</h2>
            <span class="badge badge-danger">{len(report.link_issues)} broken</span>
        </div>
        <div class="collapsible-content">
            <ul class="issue-list">{issues_html}</ul>
            {more}
        </div>
    </section>'''


def _generate_ocr_section(report: AnalysisReport) -> str:
    """Generate OCR issues section."""
    if not report.ocr_issues:
        return ""

    issues_html = ""
    for issue in report.ocr_issues[:30]:
        issues_html += f'''
        <div class="issue-item info">
            <div class="issue-header">
                <span class="issue-title">{html.escape(issue.issue_type)}</span>
                <span class="issue-category">OCR ({issue.confidence:.0%} confidence)</span>
            </div>
            <div class="issue-description">{html.escape(issue.description)}</div>
        </div>'''

    return f'''
    <section class="section collapsed">
        <div class="section-header collapsible-toggle">
            <h2 class="section-title">&#128065; OCR Issues</h2>
            <span class="badge badge-info">{len(report.ocr_issues)} issues</span>
        </div>
        <div class="collapsible-content">
            <ul class="issue-list">{issues_html}</ul>
        </div>
    </section>'''


def _generate_errors_section(report: AnalysisReport) -> str:
    """Generate errors section."""
    if not report.errors:
        return ""

    errors_html = ""
    for error in report.errors:
        errors_html += f'''
        <div class="issue-item critical">
            <div class="issue-description">{html.escape(error)}</div>
        </div>'''

    return f'''
    <section class="section collapsed">
        <div class="section-header collapsible-toggle">
            <h2 class="section-title">&#9888; Errors</h2>
            <span class="badge badge-danger">{len(report.errors)} errors</span>
        </div>
        <div class="collapsible-content">
            <ul class="issue-list">{errors_html}</ul>
        </div>
    </section>'''
