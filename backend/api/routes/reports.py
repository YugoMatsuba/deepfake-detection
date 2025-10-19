# backend/api/routes/reports.py
"""
PDF report generation and listing endpoints.

Routes:
- GET /api/reports - List available reports (users see own, admins see all)
- GET /api/reports/<analysis_id>/pdf - Generate and download PDF report
"""
from __future__ import annotations
import io
from datetime import datetime
from typing import List, Dict, Any

from flask import Blueprint, jsonify, send_file, g
from sqlalchemy import select
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from api import get_db
from api.auth_utils import require_user, check_analysis_ownership_or_admin
from models import Analysis, User

reports_bp = Blueprint("reports", __name__)


@reports_bp.get("/reports")
@require_user
def list_reports():
    """
    List available analysis reports for current user.

    Regular users see only their own reports.
    Admin/owner users see all reports.

    Response (200):
    [
      {
        "analysis_id": "uuid",
        "original_filename": "suspicious_video.mp4",
        "status": "succeeded",
        "created_at": "2025-10-19T...",
        "completed_at": "2025-10-19T...",
        "has_ml_results": true,
        "has_traditional_results": true
      },
      ...
    ]

    Response (401/403): error message
    """
    with get_db() as db:
        user = g.user  # Set by @require_user decorator

        # Build query based on role
        query = select(Analysis).where(Analysis.status == "succeeded")

        # Regular users: only their own analyses
        if user.role not in ("admin", "owner"):
            query = query.where(Analysis.user_id == user.id)

        # Admin/owner: all succeeded analyses (no filter needed)

        # Execute query and order by most recent first
        query = query.order_by(Analysis.created_at.desc())
        analyses = db.execute(query).scalars().all()

        # Build response
        reports = []
        for analysis in analyses:
            result_json = analysis.result_json or {}

            reports.append({
                "analysis_id": analysis.id,
                "original_filename": analysis.original_filename or "unknown.mp4",
                "status": analysis.status,
                "created_at": analysis.created_at.isoformat(),
                "completed_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
                "has_ml_results": bool(result_json.get("ml")),
                "has_traditional_results": bool(result_json.get("traditional"))
            })

        return jsonify(reports), 200


@reports_bp.get("/reports/<analysis_id>/pdf")
@require_user
def download_pdf_report(analysis_id: str):
    """
    Generate and download PDF report for an analysis.

    Users can download their own reports.
    Admin/owner can download any report.

    Response (200): PDF file download
    Response (403/404/500): error message
    """
    with get_db() as db:
        # Check access (ownership or admin)
        analysis = check_analysis_ownership_or_admin(db, analysis_id)

        # Ensure analysis is completed
        if analysis.status != "succeeded":
            return jsonify(error=f"Analysis not completed (status: {analysis.status})"), 400

        # Generate PDF in memory
        buffer = io.BytesIO()
        pdf = _generate_pdf_report(analysis, buffer)

        # Rewind buffer for reading
        buffer.seek(0)

        # Derive filename from original video filename
        original_name = analysis.original_filename or "analysis"
        # Strip extension from original name
        if "." in original_name:
            base_name = original_name.rsplit(".", 1)[0]
        else:
            base_name = original_name

        filename = f"{base_name}_report.pdf"

        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )


def _generate_pdf_report(analysis: Analysis, buffer: io.BytesIO) -> None:
    """
    Generate summary-style PDF report for an analysis.

    Includes:
    - Video metadata
    - ML model scores with suspicious frame counts
    - Traditional forensics scores
    - Transparency/provenance metadata
    - List of suspicious segments

    Does NOT include:
    - Frame images or overlays
    - Full frame-by-frame scores
    """
    # Create PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=12,
        spaceBefore=20
    )

    # Title
    story.append(Paragraph("Deepfake Detection Report", title_style))
    story.append(Spacer(1, 0.3 * inch))

    # Video Information
    story.append(Paragraph("Video Information", heading_style))

    video_info_data = [
        ["Original Filename", analysis.original_filename or "N/A"],
        ["Analysis ID", analysis.id],
        ["Analysis Date", analysis.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")],
        ["Completion Date", analysis.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC") if analysis.updated_at else "N/A"],
        ["Status", analysis.status.upper()],
    ]

    # Add video metadata if available
    meta_json = analysis.meta_json or {}
    if meta_json:
        fps = meta_json.get("fps")
        frame_count = meta_json.get("frame_count")
        duration = meta_json.get("duration_sec")
        width = meta_json.get("width")
        height = meta_json.get("height")

        if fps:
            video_info_data.append(["Frame Rate", f"{fps:.2f} fps"])
        if frame_count:
            video_info_data.append(["Total Frames", str(int(frame_count))])
        if duration:
            video_info_data.append(["Duration", f"{duration:.2f} seconds"])
        if width and height:
            video_info_data.append(["Resolution", f"{int(width)}x{int(height)}"])

    video_table = Table(video_info_data, colWidths=[2.5 * inch, 4 * inch])
    video_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(video_table)
    story.append(Spacer(1, 0.3 * inch))

    # Analysis Results
    result_json = analysis.result_json or {}
    ml_results = result_json.get("ml", {})
    traditional_results = result_json.get("traditional", {})

    # ML Detection Results
    if ml_results:
        story.append(Paragraph("Machine Learning Analysis", heading_style))

        ml_data = [["Model", "Deepfake Score", "Suspicious Frames", "Assessment"]]

        for model_name, model_data in ml_results.items():
            score = model_data.get("score")
            frames = model_data.get("frames", [])

            # Count frames with score > 0.5
            suspicious_count = sum(1 for f in frames if f.get("score", 0) > 0.5)

            if score is not None:
                score_pct = f"{score * 100:.1f}%"
                assessment = _get_assessment(score)
            else:
                score_pct = "N/A"
                assessment = "Unknown"

            ml_data.append([
                model_name.upper(),
                score_pct,
                f"{suspicious_count} / {len(frames)}",
                assessment
            ])

        ml_table = Table(ml_data, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch, 2 * inch])
        ml_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(ml_table)
        story.append(Spacer(1, 0.3 * inch))

    # Traditional Forensics Results
    if traditional_results:
        story.append(Paragraph("Traditional Forensics Analysis", heading_style))

        trad_data = [["Method", "Score", "Assessment"]]

        for method_name, method_data in traditional_results.items():
            score = method_data.get("score")

            if score is not None:
                score_pct = f"{score * 100:.1f}%"
                assessment = _get_assessment(score)
            else:
                score_pct = "N/A"
                assessment = "Unknown"

            method_display = method_name.upper()
            if method_name == "ela":
                method_display = "ELA (Error Level Analysis)"
            elif method_name == "noise":
                method_display = "Noise Analysis"
            elif method_name == "lbp":
                method_display = "LBP (Local Binary Pattern)"

            trad_data.append([method_display, score_pct, assessment])

        trad_table = Table(trad_data, colWidths=[2.5 * inch, 1.5 * inch, 2.5 * inch])
        trad_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')]),
        ]))
        story.append(trad_table)
        story.append(Spacer(1, 0.3 * inch))

    # Metadata Forensics Results
    metadata_result = result_json.get("metadata", {})
    if metadata_result and not metadata_result.get("error"):
        story.append(Paragraph("Metadata Forensics Analysis", heading_style))

        metadata_data = [["Category", "Status / Findings"]]

        # Anomalies
        anomalies = metadata_result.get("metadata", {}).get("anomalies", {})
        total_anomalies = (
            len(anomalies.get("missing_fields", [])) +
            len(anomalies.get("timestamp_issues", [])) +
            len(anomalies.get("software_anomalies", [])) +
            len(anomalies.get("gps_inconsistencies", []))
        )

        if total_anomalies == 0:
            metadata_data.append(["Metadata Anomalies", "✓ None detected"])
        else:
            metadata_data.append(["Metadata Anomalies", f"⚠ {total_anomalies} detected"])

            # List specific anomalies (first 5)
            all_anomalies = []
            for issue in anomalies.get("missing_fields", []):
                all_anomalies.append(issue.get("note", "Unknown issue"))
            for issue in anomalies.get("timestamp_issues", []):
                all_anomalies.append(issue.get("note", "Unknown issue"))
            for issue in anomalies.get("software_anomalies", []):
                all_anomalies.append(issue.get("note", "Unknown issue"))
            for issue in anomalies.get("gps_inconsistencies", []):
                all_anomalies.append(issue.get("note", "Unknown issue"))

            for idx, anomaly in enumerate(all_anomalies[:5]):
                metadata_data.append(["", f"• {anomaly}"])

            if len(all_anomalies) > 5:
                metadata_data.append(["", f"... and {len(all_anomalies) - 5} more"])

        # Container Integrity
        integrity = metadata_result.get("integrity", {})
        integrity_status = integrity.get("integrity_status", "UNKNOWN")

        if integrity_status == "PASSED":
            metadata_data.append(["Container Integrity", "✓ PASSED"])
        elif integrity_status == "FAILED":
            error_count = len(integrity.get("errors", []))
            metadata_data.append(["Container Integrity", f"✗ FAILED ({error_count} errors)"])
        else:
            metadata_data.append(["Container Integrity", "? UNKNOWN"])

        # Duplicate Frames
        frame_hashes = metadata_result.get("frame_hashes", {})
        duplicates = frame_hashes.get("duplicates", [])
        total_frames = frame_hashes.get("count", 0)

        if len(duplicates) == 0:
            metadata_data.append(["Duplicate Frames", f"✓ None ({total_frames} unique)"])
        else:
            metadata_data.append(["Duplicate Frames", f"⚠ {len(duplicates)} patterns detected"])

        metadata_table = Table(metadata_data, colWidths=[2.5 * inch, 4 * inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),  # Orange header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fef3c7')]),
        ]))
        story.append(metadata_table)
        story.append(Spacer(1, 0.3 * inch))

    # Transparency & Provenance
    ml_provenance = meta_json.get("ml_provenance", {})
    if ml_provenance:
        story.append(Paragraph("Analysis Transparency", heading_style))

        prov_data = [
            ["Schema Version", ml_provenance.get("schema_version", "unknown")],
            ["Code Commit", ml_provenance.get("commit_hash", "unknown")[:12]],  # Short hash
            ["Device Used", ml_provenance.get("device", "unknown")],
            ["Analysis Timestamp", ml_provenance.get("timestamp", "unknown")],
        ]

        prov_table = Table(prov_data, colWidths=[2.5 * inch, 4 * inch])
        prov_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fef3c7')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Courier'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(prov_table)
        story.append(Spacer(1, 0.3 * inch))

    # Footer note
    story.append(Spacer(1, 0.5 * inch))
    footer_text = (
        "This report provides a summary of deepfake detection analysis. "
        "Scores represent the probability that the video contains manipulated content. "
        "Higher scores indicate greater likelihood of manipulation. "
        "All metadata is captured for reproducibility and transparency."
    )
    story.append(Paragraph(footer_text, styles['Normal']))

    # Build PDF
    doc.build(story)


def _get_assessment(score: float) -> str:
    """
    Convert numeric score to human-readable assessment.

    Args:
        score: Float between 0.0 and 1.0

    Returns:
        Assessment string: "Low Risk", "Medium Risk", "High Risk", "Critical"
    """
    if score < 0.3:
        return "Low Risk"
    elif score < 0.5:
        return "Medium Risk"
    elif score < 0.7:
        return "High Risk"
    else:
        return "Critical"
