"""
Unit tests for pure metadata analysis functions.

Tests isolated computational logic without external dependencies:
- parse_frame_hashes: FFmpeg framemd5 parsing
- detect_duplicate_frames: Hash comparison
- detect_metadata_anomalies: Video metadata validation
- detect_image_metadata_anomalies: Image metadata validation
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from api.metadata_utils.metadata_analysis import (
    parse_frame_hashes,
    detect_duplicate_frames,
    detect_metadata_anomalies,
    detect_image_metadata_anomalies
)


class TestParseFrameHashes:
    """Test FFmpeg framemd5 output parsing."""

    def test_parse_frame_hashes_normal_video_stream(self):
        """Test parsing normal framemd5 output with only video stream."""
        raw_hashes = [
            "# ffmpeg framemd5 v1",
            "0, 0, 0, 1, 1382400, 4bb9a97ce56aabe079b3205a1492aab2",
            "0, 1, 1, 1, 1382400, 5cc1ba8df67bcbf18ab4216b2583bcc3",
            "0, 2, 2, 1, 1382400, 6dd2cb9eg78cdcg29bc5327c3694cdd4"
        ]

        result = parse_frame_hashes(raw_hashes)

        assert len(result) == 3
        assert result[0] == "4bb9a97ce56aabe079b3205a1492aab2"
        assert result[1] == "5cc1ba8df67bcbf18ab4216b2583bcc3"
        assert result[2] == "6dd2cb9eg78cdcg29bc5327c3694cdd4"

    def test_parse_frame_hashes_filters_audio_stream(self):
        """Test that audio stream (stream 1) is filtered out."""
        raw_hashes = [
            "# ffmpeg framemd5 v1",
            "0, 0, 0, 1, 1382400, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",  # Video
            "1, 0, 0, 1, 4096, bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",     # Audio (should be filtered)
            "0, 1, 1, 1, 1382400, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2",  # Video
            "1, 1, 1, 1, 4096, cccccccccccccccccccccccccccccccc",     # Audio (should be filtered)
        ]

        result = parse_frame_hashes(raw_hashes)

        # Only video stream (stream 0) hashes should be extracted
        assert len(result) == 2
        assert result[0] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1"
        assert result[1] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2"

    def test_parse_frame_hashes_ignores_comments(self):
        """Test that comment lines (starting with #) are ignored."""
        raw_hashes = [
            "# ffmpeg framemd5 v1",
            "# container: MP4",
            "0, 0, 0, 1, 1382400, abcd1234abcd1234abcd1234abcd1234",
            "# another comment",
            "0, 1, 1, 1, 1382400, efgh5678efgh5678efgh5678efgh5678"
        ]

        result = parse_frame_hashes(raw_hashes)

        assert len(result) == 2
        assert all(len(h) == 32 for h in result)

    def test_parse_frame_hashes_empty_input(self):
        """Test handling of empty input."""
        result = parse_frame_hashes([])
        assert result == []

    def test_parse_frame_hashes_malformed_lines(self):
        """Test handling of malformed lines (fewer than 6 fields)."""
        raw_hashes = [
            "# ffmpeg framemd5 v1",
            "0, 0, 0, 1, 1382400, abcd1234abcd1234abcd1234abcd1234",
            "malformed line",
            "0, 0",  # Only 2 fields
            "0, 1, 1, 1, 1382400, efgh5678efgh5678efgh5678efgh5678"
        ]

        result = parse_frame_hashes(raw_hashes)

        # Only valid lines with 6+ fields and stream 0 should be parsed
        assert len(result) == 2


class TestDetectDuplicateFrames:
    """Test duplicate frame detection using hash comparison."""

    def test_detect_duplicate_frames_no_duplicates(self):
        """Test with all unique hashes."""
        raw_hashes = [
            "# ffmpeg framemd5 v1",
            "0, 0, 0, 1, 1382400, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
            "0, 1, 1, 1, 1382400, bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "0, 2, 2, 1, 1382400, cccccccccccccccccccccccccccccccc"
        ]

        result = detect_duplicate_frames(raw_hashes)

        assert result == []

    def test_detect_duplicate_frames_with_duplicates(self):
        """Test with duplicate frames (repeated hash)."""
        raw_hashes = [
            "# ffmpeg framemd5 v1",
            "0, 0, 0, 1, 1382400, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
            "0, 1, 1, 1, 1382400, bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "0, 2, 2, 1, 1382400, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",  # Duplicate of frame 0
            "0, 3, 3, 1, 1382400, cccccccccccccccccccccccccccccccc",
            "0, 4, 4, 1, 1382400, bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",  # Duplicate of frame 1
            "0, 5, 5, 1, 1382400, bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"   # Another duplicate of frame 1
        ]

        result = detect_duplicate_frames(raw_hashes)

        # Should find 2 duplicate groups
        assert len(result) == 2

        # Find the 'aaaa...' group
        group_a = next(d for d in result if d['hash'] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1")
        assert group_a['count'] == 2
        assert set(group_a['frame_indices']) == {0, 2}

        # Find the 'bbbb...' group
        group_b = next(d for d in result if d['hash'] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        assert group_b['count'] == 3
        assert set(group_b['frame_indices']) == {1, 4, 5}

    def test_detect_duplicate_frames_empty_input(self):
        """Test with empty input."""
        result = detect_duplicate_frames([])
        assert result == []

    def test_detect_duplicate_frames_single_frame(self):
        """Test with single frame (no duplicates possible)."""
        raw_hashes = [
            "# ffmpeg framemd5 v1",
            "0, 0, 0, 1, 1382400, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1"
        ]

        result = detect_duplicate_frames(raw_hashes)
        assert result == []


class TestDetectMetadataAnomalies:
    """Test video metadata anomaly detection."""

    def test_no_anomalies_complete_metadata(self):
        """Test with complete, valid metadata."""
        metadata = {
            'FileType': 'MP4',
            'MIMEType': 'video/mp4',
            'CreateDate': '2024:01:15 10:30:00',
            'ModifyDate': '2024:01:15 10:35:00',
            'VideoCodec': 'H.264',
            'ImageWidth': 1920,
            'ImageHeight': 1080,
            'Make': 'Apple',
            'Model': 'iPhone 12',
            'Software': 'iOS 15.0'
        }

        result = detect_metadata_anomalies(metadata)

        # All categories should be empty
        assert result['missing_fields'] == []
        assert result['timestamp_issues'] == []
        assert result['software_anomalies'] == []
        assert result['gps_inconsistencies'] == []

    def test_missing_critical_fields(self):
        """Test detection of missing critical fields."""
        metadata = {
            'Make': 'Canon',
            # Missing: FileType, MIMEType, CreateDate, VideoCodec, ImageWidth, ImageHeight
        }

        result = detect_metadata_anomalies(metadata)

        # Should detect missing critical fields
        assert len(result['missing_fields']) > 0
        critical_missing = next(m for m in result['missing_fields'] if m['type'] == 'critical')
        assert 'FileType' in critical_missing['fields']
        assert 'CreateDate' in critical_missing['fields']
        assert 'VideoCodec' in critical_missing['fields']

    def test_missing_all_device_info(self):
        """Test detection when all device info is missing."""
        metadata = {
            'FileType': 'MP4',
            'MIMEType': 'video/mp4',
            'CreateDate': '2024:01:15 10:30:00',
            'VideoCodec': 'H.264',
            'ImageWidth': 1920,
            'ImageHeight': 1080,
            # Missing: Make, Model, Software (all device fields)
        }

        result = detect_metadata_anomalies(metadata)

        # Should detect missing device info
        assert len(result['missing_fields']) > 0
        device_missing = next(m for m in result['missing_fields'] if m['type'] == 'device_info')
        assert 'Make' in device_missing['fields']
        assert 'Model' in device_missing['fields']
        assert 'Software' in device_missing['fields']

    def test_timestamp_inconsistency_create_after_modify(self):
        """Test detection of impossible timestamp (create > modify)."""
        metadata = {
            'FileType': 'MP4',
            'MIMEType': 'video/mp4',
            'CreateDate': '2024:01:15 12:00:00',  # Created later
            'ModifyDate': '2024:01:15 10:00:00',  # Modified earlier (impossible!)
            'VideoCodec': 'H.264',
            'ImageWidth': 1920,
            'ImageHeight': 1080
        }

        result = detect_metadata_anomalies(metadata)

        # Should detect timestamp issue
        assert len(result['timestamp_issues']) > 0
        ts_issue = result['timestamp_issues'][0]
        assert ts_issue['type'] == 'create_after_modify'
        assert ts_issue['create'] == '2024:01:15 12:00:00'
        assert ts_issue['modify'] == '2024:01:15 10:00:00'

    def test_editing_software_detected(self):
        """Test detection of editing software in metadata."""
        test_cases = [
            ('Adobe Premiere Pro CC 2023', 'premiere'),
            ('Final Cut Pro 10.6', 'final cut'),
            ('DaVinci Resolve 18', 'davinci'),
            ('FFmpeg 4.4.2', 'ffmpeg'),
            ('HandBrake 1.5.0', 'handbrake')
        ]

        for software_value, keyword in test_cases:
            metadata = {
                'FileType': 'MP4',
                'MIMEType': 'video/mp4',
                'CreateDate': '2024:01:15 10:30:00',
                'VideoCodec': 'H.264',
                'ImageWidth': 1920,
                'ImageHeight': 1080,
                'Software': software_value
            }

            result = detect_metadata_anomalies(metadata)

            # Should detect editing software
            assert len(result['software_anomalies']) > 0
            sw_anomaly = result['software_anomalies'][0]
            assert 'editing software' in sw_anomaly['note'].lower()
            assert sw_anomaly['software'] == software_value

    def test_gps_out_of_range(self):
        """Test detection of GPS coordinates out of valid range."""
        # Test invalid latitude
        metadata = {
            'FileType': 'MP4',
            'MIMEType': 'video/mp4',
            'CreateDate': '2024:01:15 10:30:00',
            'VideoCodec': 'H.264',
            'ImageWidth': 1920,
            'ImageHeight': 1080,
            'GPSLatitude': '95.0',  # Invalid: > 90
            'GPSLongitude': '-122.4194'
        }

        result = detect_metadata_anomalies(metadata)

        # Should detect GPS anomaly
        assert len(result['gps_inconsistencies']) > 0
        gps_issue = next(g for g in result['gps_inconsistencies'] if g['field'] == 'GPSLatitude')
        assert 'out of valid range' in gps_issue['note']

    def test_empty_metadata(self):
        """Test handling of empty/None metadata."""
        result = detect_metadata_anomalies({})

        # Should return empty anomaly structure
        assert result == {
            'missing_fields': [],
            'timestamp_issues': [],
            'software_anomalies': [],
            'gps_inconsistencies': []
        }

        # Test None case
        result_none = detect_metadata_anomalies(None)
        assert result_none == {
            'missing_fields': [],
            'timestamp_issues': [],
            'software_anomalies': [],
            'gps_inconsistencies': []
        }


class TestDetectImageMetadataAnomalies:
    """Test image metadata anomaly detection."""

    def test_no_anomalies_complete_image_metadata(self):
        """Test with complete, valid image metadata."""
        metadata = {
            'FileType': 'JPEG',
            'MIMEType': 'image/jpeg',
            'CreateDate': '2024:01:15 10:30:00',
            'ModifyDate': '2024:01:15 10:35:00',
            'ImageWidth': 4032,
            'ImageHeight': 3024,
            'Make': 'Apple',
            'Model': 'iPhone 12 Pro',
            'Software': 'iOS 15.0'
        }

        result = detect_image_metadata_anomalies(metadata)

        # All categories should be empty
        assert result['missing_fields'] == []
        assert result['timestamp_issues'] == []
        assert result['software_anomalies'] == []
        assert result['gps_inconsistencies'] == []

    def test_missing_critical_image_fields(self):
        """Test detection of missing critical image fields."""
        metadata = {
            'Make': 'Canon',
            # Missing: FileType, MIMEType, CreateDate, ImageWidth, ImageHeight
        }

        result = detect_image_metadata_anomalies(metadata)

        # Should detect missing critical fields
        assert len(result['missing_fields']) > 0
        critical_missing = next(m for m in result['missing_fields'] if m['type'] == 'critical')
        assert 'FileType' in critical_missing['fields']
        assert 'CreateDate' in critical_missing['fields']
        assert 'ImageWidth' in critical_missing['fields']

    def test_image_editing_software_detected(self):
        """Test detection of image editing software."""
        test_cases = [
            'Adobe Photoshop CC 2023',
            'GIMP 2.10',
            'Affinity Photo',
            'Canva Editor'
        ]

        for software_value in test_cases:
            metadata = {
                'FileType': 'JPEG',
                'MIMEType': 'image/jpeg',
                'CreateDate': '2024:01:15 10:30:00',
                'ImageWidth': 4032,
                'ImageHeight': 3024,
                'Software': software_value
            }

            result = detect_image_metadata_anomalies(metadata)

            # Should detect editing software
            assert len(result['software_anomalies']) > 0
            sw_anomaly = result['software_anomalies'][0]
            assert 'editing software' in sw_anomaly['note'].lower()

    def test_incomplete_gps_coordinates(self):
        """Test detection of incomplete GPS data (only lat or only long)."""
        # Only latitude present
        metadata = {
            'FileType': 'JPEG',
            'MIMEType': 'image/jpeg',
            'CreateDate': '2024:01:15 10:30:00',
            'ImageWidth': 4032,
            'ImageHeight': 3024,
            'GPSLatitude': '37.7749',
            # Missing GPSLongitude
        }

        result = detect_image_metadata_anomalies(metadata)

        # Should detect incomplete GPS
        assert len(result['gps_inconsistencies']) > 0
        gps_issue = result['gps_inconsistencies'][0]
        assert gps_issue['type'] == 'incomplete_gps'
        assert 'incomplete' in gps_issue['note'].lower()

    def test_timestamp_create_after_modify(self):
        """Test image timestamp inconsistency detection."""
        metadata = {
            'FileType': 'JPEG',
            'MIMEType': 'image/jpeg',
            'CreateDate': '2024:01:15 12:00:00',  # Later
            'ModifyDate': '2024:01:15 10:00:00',  # Earlier (impossible)
            'ImageWidth': 4032,
            'ImageHeight': 3024
        }

        result = detect_image_metadata_anomalies(metadata)

        # Should detect timestamp issue
        assert len(result['timestamp_issues']) > 0
        ts_issue = result['timestamp_issues'][0]
        assert ts_issue['type'] == 'create_after_modify'

    def test_uses_datetimeoriginal_fallback(self):
        """Test that DateTimeOriginal is used if CreateDate is missing."""
        metadata = {
            'FileType': 'JPEG',
            'MIMEType': 'image/jpeg',
            'DateTimeOriginal': '2024:01:15 12:00:00',  # Fallback
            'ModifyDate': '2024:01:15 10:00:00',
            'ImageWidth': 4032,
            'ImageHeight': 3024
        }

        result = detect_image_metadata_anomalies(metadata)

        # Should still detect timestamp issue using DateTimeOriginal
        assert len(result['timestamp_issues']) > 0
