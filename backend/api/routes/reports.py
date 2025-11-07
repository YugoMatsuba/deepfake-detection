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

from flask import Blueprint, jsonify, send_file, g, request
from sqlalchemy import select, func
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from api import get_db
from api.auth_utils import require_user, check_analysis_ownership_or_admin
from api.config.ml_thresholds import get_classification, get_methodology_description
from models import Analysis, User

reports_bp = Blueprint("reports", __name__)


@reports_bp.get("/reports")
@require_user
def list_reports():
    """
    List available analysis reports for current user with pagination.

    Query params:
    - limit: max results (default 50, max 500)
    - offset: pagination offset (default 0)

    Regular users see only their own reports (no username field).
    Admin/owner users see all reports with username field.

    Response (200):
    {
      "reports": [
        {
          "analysis_id": "uuid",
          "original_filename": "suspicious_video.mp4",
          "status": "succeeded",
          "created_at": "2025-10-19T...",
          "completed_at": "2025-10-19T...",
          "has_ml_results": true,
          "has_traditional_results": true,
          "username": "john_doe"  // Only present for admin/owner users
        },
        ...
      ],
      "total": 123,
      "limit": 50,
      "offset": 0
    }

    Response (401/403): error message
    """
    # Pagination params
    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))

    with get_db() as db:
        user = g.user  # Set by @require_user decorator
        is_admin = user.role in ("admin", "owner")

        # Build query based on role - join with User table if admin
        if is_admin:
            # Admin: get all analyses with username
            query = (
                select(Analysis, User.username)
                .join(User, Analysis.user_id == User.id)
                .where(Analysis.status == "succeeded")
                .order_by(Analysis.created_at.desc())
            )
            # Get total count
            count_query = (
                select(func.count())
                .select_from(Analysis)
                .where(Analysis.status == "succeeded")
            )
            total = db.execute(count_query).scalar()

            # Apply pagination
            results = db.execute(query.limit(limit).offset(offset)).all()
        else:
            # Regular users: only their own analyses, no need for username
            query = (
                select(Analysis)
                .where(Analysis.status == "succeeded", Analysis.user_id == user.id)
                .order_by(Analysis.created_at.desc())
            )
            # Get total count
            count_query = (
                select(func.count())
                .select_from(Analysis)
                .where(Analysis.status == "succeeded", Analysis.user_id == user.id)
            )
            total = db.execute(count_query).scalar()

            # Apply pagination
            results = [(analysis, None) for analysis in db.execute(query.limit(limit).offset(offset)).scalars().all()]

        # Build response
        reports = []
        for analysis, username in results:
            result_json = analysis.result_json or {}

            report = {
                "analysis_id": analysis.id,
                "original_filename": analysis.original_filename or "unknown.mp4",
                "media_type": analysis.media_type,
                "status": analysis.status,
                "created_at": analysis.created_at.isoformat(),
                "completed_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
                "has_ml_results": bool(result_json.get("ml")),
                "has_traditional_results": bool(result_json.get("traditional"))
            }

            # Only include username for admins
            if is_admin and username:
                report["username"] = username

            reports.append(report)

        return jsonify({
            "reports": reports,
            "total": total,
            "limit": limit,
            "offset": offset
        }), 200


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

        # Calculate overall ensemble score
        ensemble_result = _calculate_top5_ensemble_score(ml_results)

        # Add summary paragraph with overall score
        if ensemble_result:
            score_pct = f"{ensemble_result['score'] * 100:.1f}%"
            classification = ensemble_result['classification']

            summary_text = (
                f"<b>Overall Synthetic Media Score: {score_pct}</b><br/>"
                f"Classification: {classification}<br/>"
                f"<i>(Overall averaged from top 5 highest-scoring frames across all models)</i>"
            )
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))

        ml_data = [["Model", "Deepfake Score", "Suspicious Frames", "Assessment"]]

        # Add overall ensemble row first
        if ensemble_result:
            ensemble_score_pct = f"{ensemble_result['score'] * 100:.1f}%"
            ml_data.append([
                "OVERALL",
                ensemble_score_pct,
                "—",
                ensemble_result['classification']
            ])

        # Add individual model rows
        for model_name, model_data in ml_results.items():
            score = model_data.get("score")
            frames = model_data.get("frames", [])

            # Count frames with score > 0.5
            suspicious_count = sum(1 for f in frames if f.get("score", 0) > 0.5)

            if score is not None:
                score_pct = f"{score * 100:.1f}%"
                assessment = get_classification(score)
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

        trad_data = [["Method", "Max Z-score"]]

        for method_name, method_data in traditional_results.items():
            score = method_data.get("score")

            if score is not None:
                score_display = f"{score:.2f}"
            else:
                score_display = "N/A"

            method_display = method_name.upper()
            if method_name == "ela":
                method_display = "ELA (Error Level Analysis)"
            elif method_name == "noise":
                method_display = "Noise Analysis"
            elif method_name == "lbp":
                method_display = "LBP (Local Binary Pattern)"

            trad_data.append([method_display, score_display])

        trad_table = Table(trad_data, colWidths=[4 * inch, 2.5 * inch])
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
    footer_text = f"<i>Report generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}</i>"
    story.append(Paragraph(footer_text, styles['Normal']))

    # Build PDF
    doc.build(story)


def _calculate_top5_ensemble_score(ml_results: Dict[str, Any]):
    """
    Calculate top-5 ensemble score from ML results.

    For each frame:
    1. Calculate ensemble average: (xception + spsl + ucf) / 3
    2. Sort all ensemble scores descending
    3. Take mean of top 5 scores

    Args:
        ml_results: ML results dict with model data

    Returns:
        Dict with {score: 0.85, classification: "Likely fake"} or None
    """
    if not ml_results:
        return None

    # Extract models
    models = ['xception', 'spsl', 'ucf']
    model_data = {name: ml_results.get(name) for name in models}

    # Check if we have data
    if not any(model_data.values()):
        return None

    # Collect frame scores by index
    frame_scores_map = {}  # frame_index -> {xception: score, spsl: score, ucf: score}

    for model_name, data in model_data.items():
        if not data:
            continue
        frames = data.get("frames", [])
        for frame in frames:
            index = frame.get("index")
            score = frame.get("score")
            if index is not None and score is not None:
                if index not in frame_scores_map:
                    frame_scores_map[index] = {}
                frame_scores_map[index][model_name] = score

    # Calculate ensemble scores for frames with all 3 models
    ensemble_scores = []
    for index, scores in frame_scores_map.items():
        if all(model in scores for model in models):
            ensemble_score = (scores['xception'] + scores['spsl'] + scores['ucf']) / 3
            ensemble_scores.append(ensemble_score)

    if not ensemble_scores:
        return None

    # Sort descending
    ensemble_scores.sort(reverse=True)

    # Take top 5 (or all if fewer than 5)
    top_n = min(5, len(ensemble_scores))
    top5_scores = ensemble_scores[:top_n]

    # Calculate mean
    mean_score = sum(top5_scores) / len(top5_scores)

    # Get classification
    classification = get_classification(mean_score)

    return {
        "score": mean_score,
        "classification": classification
    }


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
