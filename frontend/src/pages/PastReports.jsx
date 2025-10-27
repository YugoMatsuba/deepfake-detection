import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../app/useAuth.js";
import { fetchJson } from "../api/client.js";

export default function PastReports() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [reopening, setReopening] = useState(null);

  const navigate = useNavigate();
  const { user } = useAuth();

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchJson("/reports");
      setReports(data);
    } catch (err) {
      setError(err.message || "Failed to load reports");
    } finally {
      setLoading(false);
    }
  };

  const downloadPDF = async (analysisId, filename) => {
    try {
      setDownloading(analysisId);

      const response = await fetch(`/api/reports/${analysisId}/pdf`, {
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Failed to download PDF");
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err.message || "Failed to download PDF");
    } finally {
      setDownloading(null);
    }
  };

  const handleDeleteAnalysis = async (analysisId) => {
    setDeleting(analysisId);
    try {
      const response = await fetch(`/api/analyses/${analysisId}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!response.ok) throw new Error("Failed to delete analysis");

      // Remove from local state
      setReports(reports.filter((r) => r.analysis_id !== analysisId));
      setDeleteConfirm(null);
    } catch (err) {
      setError(err.message || "Failed to delete analysis");
    } finally {
      setDeleting(null);
    }
  };

  const handleRerunAnalysis = async (analysisId) => {
    try {
      setReopening(analysisId);
      setError(null);

      // Fetch full analysis data
      const response = await fetch(`/api/analyses/${analysisId}`, {
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Failed to load analysis");
      }

      const analysisData = await response.json();

      // Extract data in format expected by FrameViewer
      const mlResults = analysisData.result?.ml || {};
      const traditionalResults = analysisData.result?.traditional || {};

      // Get ML frames (filter by score > 0.5 OR requested_adhoc)
      const mlFrames = [];
      Object.values(mlResults).forEach((model) => {
        if (model.frames) {
          model.frames.forEach((f) => {
            if (
              (f.score > 0.5 || f.requested_adhoc) &&
              !mlFrames.includes(f.index)
            ) {
              mlFrames.push(f.index);
            }
          });
        }
      });

      // Navigate to frame viewer with data
      navigate("/frame-viewer", {
        state: {
          analysisId: analysisData.analysis_id,
          fps: analysisData.result?.video?.fps || null,
          mlFrames: mlFrames.sort((a, b) => a - b),
          mlModels: mlResults,
          traditional: traditionalResults,
        },
      });
    } catch (err) {
      setError(err.message || "Failed to reopen analysis");
    } finally {
      setReopening(null);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return "N/A";
    const date = new Date(isoString);
    return date.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-gray-600">Loading reports...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-semibold text-gray-900">Past Reports</h1>
            <p className="text-gray-600 text-sm mt-1">
              {user?.role === "admin" || user?.role === "owner"
                ? "All completed analyses"
                : "Your completed analyses"}
            </p>
          </div>

          <button
            onClick={() => navigate(-1)}
            className="px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 font-medium hover:bg-gray-50 active:bg-gray-100 transition"
          >
            Back
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
            {error}
          </div>
        )}

        {/* Reports Table */}
        {reports.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-8 text-center">
            <p className="text-gray-600">No reports available yet.</p>
            <button
              onClick={() => navigate("/upload")}
              className="mt-4 px-4 py-2 rounded-lg border border-blue-600 bg-blue-600 text-white font-semibold hover:opacity-95 active:opacity-90 transition"
            >
              Upload a Video
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[200px]">
                    Video Filename
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[120px]">
                    Analysis Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[120px]">
                    Completed
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[140px]">
                    Results
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[240px]">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {reports.map((report) => (
                  <tr key={report.analysis_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {report.original_filename}
                      </div>
                      <div className="text-xs text-gray-500 font-mono">
                        {report.analysis_id.substring(0, 8)}...
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {formatDate(report.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {formatDate(report.completed_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex gap-2">
                        {report.has_ml_results && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            ML
                          </span>
                        )}
                        {report.has_traditional_results && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            Traditional
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-left text-sm">
                      <button
                        onClick={() => handleRerunAnalysis(report.analysis_id)}
                        disabled={reopening === report.analysis_id}
                        className="px-3 py-1.5 rounded-lg border border-green-600 bg-green-600 text-white font-medium hover:opacity-95 active:opacity-90 transition disabled:opacity-50 text-xs mr-2"
                      >
                        {reopening === report.analysis_id
                          ? "Opening..."
                          : "Rerun Analysis"}
                      </button>
                      <button
                        onClick={() =>
                          downloadPDF(
                            report.analysis_id,
                            report.original_filename.replace(/\.[^/.]+$/, "") +
                              "_report.pdf"
                          )
                        }
                        disabled={downloading === report.analysis_id}
                        className="px-3 py-1.5 rounded-lg border border-blue-600 bg-blue-600 text-white font-medium hover:opacity-95 active:opacity-90 transition disabled:opacity-50 text-xs mr-2"
                      >
                        {downloading === report.analysis_id
                          ? "Downloading..."
                          : "Download PDF"}
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(report.analysis_id)}
                        disabled={deleting === report.analysis_id}
                        className="px-3 py-1.5 rounded-lg border border-red-600 text-red-600 font-medium hover:bg-red-50 active:bg-red-100 transition disabled:opacity-50 text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Delete Confirmation Popup */}
        {deleteConfirm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md mx-4">
              <h2 className="text-xl font-bold text-red-600 mb-4">
                Delete Analysis?
              </h2>
              <p className="text-gray-700 mb-6">
                This will permanently delete this analysis record and all
                associated files. This action cannot be undone.
              </p>

              <div className="flex gap-3">
                <button
                  onClick={() => handleDeleteAnalysis(deleteConfirm)}
                  disabled={deleting === deleteConfirm}
                  className="flex-1 px-4 py-2 rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700 disabled:opacity-50 transition"
                >
                  {deleting === deleteConfirm
                    ? "Deleting..."
                    : "Delete Permanently"}
                </button>
                <button
                  onClick={() => setDeleteConfirm(null)}
                  disabled={deleting === deleteConfirm}
                  className="flex-1 px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 font-semibold hover:bg-gray-50 disabled:opacity-50 transition"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
