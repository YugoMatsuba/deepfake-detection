import subprocess
import json
import os
import re
from datetime import datetime

def extract_metadata(video_path):
    """Extract metadata using ExifTool."""
    try:
        cmd = ["exiftool", "-j", video_path]  # now using system PATH
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)[0]
        return data
    except subprocess.CalledProcessError as e:
        print(f"❌ Error extracting metadata for {video_path}: {e}")
        return None


def check_integrity_ffmpeg(video_path):
    """Use FFmpeg to check structural integrity of the video container."""
    cmd = ["ffmpeg", "-v", "error", "-i", video_path, "-f", "null", "-"]  # now using system PATH
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stderr.strip()


def parse_ffmpeg_log(stderr_text):
    """Convert raw FFmpeg error log into a human-readable summary."""
    errors = []

    # Match decoding errors for macroblocks
    mb_errors = re.findall(r'error while decoding MB (\d+) (\d+)', stderr_text)
    for mb in mb_errors:
        errors.append(f"Macroblock at row {mb[0]}, column {mb[1]} failed to decode")

    # Top block unavailable
    if "top block unavailable" in stderr_text:
        errors.append("Top block unavailable for requested intra mode")

    # Reference errors
    references = re.findall(r'Reference (\d+) >= (\d+)', stderr_text)
    for ref in references:
        errors.append(f"Invalid reference: Reference {ref[0]} >= {ref[1]}")

    status = "PASSED" if not errors else "FAILED"

    return {
        "integrity_status": status,
        "errors": errors,
        "summary": f"Video integrity check {status}"
    }


def generate_frame_hashes(video_path):
    """Generate per-frame MD5 hashes using FFmpeg, capture them in memory, and return as a list."""
    cmd = ["ffmpeg", "-i", video_path, "-f", "framemd5", "-"]  # '-' = output to stdout
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(f"❌ Error generating frame hashes: {result.stderr}")
        return None

    hashes = result.stdout.strip().splitlines()  # each line is a frame hash
    return hashes


def analyze_video(video_path, output_file=None):
    """Analyze a single video file and save a JSON report."""
    if not os.path.exists(video_path):
        print(f"❌ File not found: {video_path}")
        return

    print(f"🔍 Analyzing: {video_path}")

    # --- 1. Extract metadata
    metadata = extract_metadata(video_path)

    # --- 2. Check structural integrity
    ffmpeg_raw = check_integrity_ffmpeg(video_path)
    integrity_result = parse_ffmpeg_log(ffmpeg_raw)

    # --- 3. Generate frame hashes (in memory)
    frame_hashes = generate_frame_hashes(video_path)

    # --- 4. Build report
    report = {
        "analyzed_at": datetime.now().isoformat(),
        "video_file": os.path.abspath(video_path),
        "metadata": metadata,
        "ffmpeg_integrity_check": integrity_result,
        "frame_hashes_count": len(frame_hashes) if frame_hashes else 0
    }

    # --- 5. Save report
    if not output_file:
        base = os.path.splitext(os.path.basename(video_path))[0]
        output_file = f"{base}_analysis_report.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Analysis complete. Report saved to: {output_file}")
    return report


if __name__ == "__main__":
    # To test add your path here in your computer
    video_path = r"C:\University Material\IT Project\IT Project App\deepfake_AI\backend\uploads\fake1IntegrityTest.mp4"
    analyze_video(video_path)
