import React from "react";

/**
 * Metadata forensics display components
 *
 * Shows results from industry-standard metadata analysis:
 * - Anomalies (missing fields, timestamp issues, software, GPS)
 * - Container integrity (FFmpeg structural validation)
 * - Frame hashes (duplicate detection)
 */

export function MetadataAnomaliesSummary({ metadata }) {
  const anomalies = metadata?.metadata?.anomalies || {};
  const totalAnomalies =
    (anomalies.missing_fields?.length || 0) +
    (anomalies.timestamp_issues?.length || 0) +
    (anomalies.software_anomalies?.length || 0) +
    (anomalies.gps_inconsistencies?.length || 0);

  if (totalAnomalies === 0) {
    return (
      <div className="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
        <p className="text-green-700 font-semibold">✓ No metadata anomalies detected</p>
      </div>
    );
  }

  return (
    <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 mb-4">
      <p className="text-yellow-800 font-semibold mb-2">
        ⚠ {totalAnomalies} metadata {totalAnomalies === 1 ? "anomaly" : "anomalies"} detected
      </p>

      {/* Missing Fields */}
      {anomalies.missing_fields?.map((issue, idx) => (
        <div key={`missing-${idx}`} className="text-sm text-yellow-700 ml-4 mb-1">
          • {issue.note}
        </div>
      ))}

      {/* Timestamp Issues */}
      {anomalies.timestamp_issues?.map((issue, idx) => (
        <div key={`timestamp-${idx}`} className="text-sm text-yellow-700 ml-4 mb-1">
          • {issue.note}
        </div>
      ))}

      {/* Software Anomalies */}
      {anomalies.software_anomalies?.map((issue, idx) => (
        <div key={`software-${idx}`} className="text-sm text-yellow-700 ml-4 mb-1">
          • {issue.note}
        </div>
      ))}

      {/* GPS Inconsistencies */}
      {anomalies.gps_inconsistencies?.map((issue, idx) => (
        <div key={`gps-${idx}`} className="text-sm text-yellow-700 ml-4 mb-1">
          • {issue.note}
        </div>
      ))}
    </div>
  );
}

export function IntegrityStatus({ metadata }) {
  const integrity = metadata?.integrity || {};
  const status = integrity.integrity_status || "UNKNOWN";

  const statusColors = {
    PASSED: "bg-green-50 border-green-500 text-green-700",
    FAILED: "bg-red-50 border-red-500 text-red-700",
    UNKNOWN: "bg-gray-50 border-gray-500 text-gray-700",
  };

  const color = statusColors[status] || statusColors.UNKNOWN;

  return (
    <div className={`border-l-4 p-4 mb-4 ${color}`}>
      <p className="font-semibold">Container Integrity: {status}</p>
      {integrity.errors?.length > 0 && (
        <div className="mt-2 text-sm">
          <p className="font-medium">Errors detected:</p>
          <ul className="ml-4 mt-1 space-y-1">
            {integrity.errors.slice(0, 3).map((err, idx) => (
              <li key={idx}>• {err}</li>
            ))}
          </ul>
          {integrity.errors.length > 3 && (
            <p className="ml-4 mt-1 italic">... and {integrity.errors.length - 3} more</p>
          )}
        </div>
      )}
    </div>
  );
}

export function FrameHashesSummary({ metadata }) {
  const frameHashes = metadata?.frame_hashes || {};
  const duplicates = frameHashes.duplicates || [];
  const frameCount = frameHashes.count;

  if (duplicates.length === 0) {
    // If count is 0 or undefined, frame hash analysis likely failed
    if (!frameCount || frameCount === 0) {
      return (
        <div className="bg-gray-50 border-l-4 border-gray-400 p-4 mb-4">
          <p className="text-gray-700 font-semibold">Frame hash analysis unavailable</p>
        </div>
      );
    }

    return (
      <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
        <p className="text-blue-700 font-semibold">
          ✓ No duplicate frames detected ({frameCount} unique frames)
        </p>
      </div>
    );
  }

  return (
    <div className="bg-orange-50 border-l-4 border-orange-500 p-4 mb-4">
      <p className="text-orange-700 font-semibold mb-2">
        ⚠ {duplicates.length} duplicate frame pattern(s) detected
      </p>
      <div className="text-sm text-orange-600 ml-4">
        {duplicates.slice(0, 3).map((dup, idx) => (
          <div key={idx} className="mb-1">
            • Frame hash {dup.hash.slice(0, 8)}... appears {dup.count} times (indices:{" "}
            {dup.frame_indices.slice(0, 5).join(", ")}
            {dup.frame_indices.length > 5 ? "..." : ""})
          </div>
        ))}
        {duplicates.length > 3 && (
          <p className="italic mt-1">... and {duplicates.length - 3} more patterns</p>
        )}
      </div>
    </div>
  );
}
