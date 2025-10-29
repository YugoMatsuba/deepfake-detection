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
  const [mediaFilter, setMediaFilter] = useState("all"); // "all", "video", "image"
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 50;

  const navigate = useNavigate();
  const { user } = useAuth();

  useEffect(() => {
    fetchReports();
  }, [offset]);

  const fetchReports = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchJson(`/reports?limit=${limit}&offset=${offset}`);
      // Append to existing reports for "load more" behavior
      if (offset === 0) {
        setReports(data.reports);
      } else {
        setReports(prev => [...prev, ...data.reports]);
      }
      setTotal(data.total);
    } catch (err) {
      setError(err.message || "Failed to load reports");
    } finally {
      setLoading(false);
    }
  };

  const loadMore = () => {
    setOffset(offset + limit);
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

  const handleRerunAnalysis = (analysisId, mediaType) => {
    // Route based on media type
    if (mediaType === "image") {
      navigate(`/image-analysis/${analysisId}`);
    } else {
      // Video: navigate to frame-viewer
      navigate("/frame-viewer", {
        state: {
          analysisId: analysisId,
        },
      });
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

  // Filter reports based on media type
  const filteredReports = reports.filter((report) => {
    if (mediaFilter === "all") return true;
    const mediaType = report.media_type || "video"; // Default to video for backward compatibility
    return mediaType === mediaFilter;
  });

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
      <div className="w-full px-4 mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-semibold text-gray-900">Past Analyses</h1>
            <p className="text-gray-600 text-sm mt-1">
              {user?.role === "admin" || user?.role === "owner"
                ? "All completed analyses"
                : "Your completed analyses"}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Media Type Filter */}
            <select
              value={mediaFilter}
              onChange={(e) => setMediaFilter(e.target.value)}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 font-medium hover:bg-gray-50 transition focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All</option>
              <option value="video">Videos</option>
              <option value="image">Images</option>
            </select>

            <button
              onClick={() => navigate(-1)}
              className="px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 font-medium hover:bg-gray-50 active:bg-gray-100 transition"
            >
              Back
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
            {error}
          </div>
        )}

        {/* Analyses Table */}
        {filteredReports.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-8 text-center">
            <p className="text-gray-600">
              {reports.length === 0
                ? "No analyses available yet."
                : `No ${mediaFilter === "all" ? "" : mediaFilter} analyses found.`}
            </p>
            {reports.length === 0 && (
              <button
                onClick={() => navigate("/upload")}
                className="mt-4 px-4 py-2 rounded-lg border border-blue-600 bg-blue-600 text-white font-semibold hover:opacity-95 active:opacity-90 transition"
              >
                Upload Media
              </button>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[200px]">
                    Filename
                  </th>
                  {(user?.role === "admin" || user?.role === "owner") && (
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[120px]">
                      User
                    </th>
                  )}
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
                {filteredReports.map((report) => {
                  const mediaType = report.media_type || "video"; // Default to video for backward compatibility
                  return (
                  <tr key={report.analysis_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {/* Media type icon */}
                        {mediaType === "image" ? (
                          <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        )}
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {report.original_filename}
                          </div>
                          <div className="text-xs text-gray-500 font-mono">
                            {report.analysis_id.substring(0, 8)}...
                          </div>
                        </div>
                      </div>
                    </td>
                    {(user?.role === "admin" || user?.role === "owner") && (
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {report.username || "Unknown"}
                      </td>
                    )}
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
                        onClick={() => handleRerunAnalysis(report.analysis_id, mediaType)}
                        className="px-3 py-1.5 rounded-lg border border-green-600 bg-green-600 text-white font-medium hover:opacity-95 active:opacity-90 transition text-xs mr-2"
                      >
                        Reopen Analysis
                      </button>
                      {mediaType === "video" && (
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
                      )}
                      <button
                        onClick={() => setDeleteConfirm(report.analysis_id)}
                        disabled={deleting === report.analysis_id}
                        className="px-3 py-1.5 rounded-lg border border-red-600 text-red-600 font-medium hover:bg-red-50 active:bg-red-100 transition disabled:opacity-50 text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Load More Button */}
        {filteredReports.length < total && (
          <div className="mt-4 text-center">
            <button
              onClick={loadMore}
              disabled={loading}
              className="px-4 py-2 rounded-lg border border-blue-600 bg-blue-600 text-white hover:bg-blue-700 transition disabled:opacity-50"
            >
              {loading ? 'Loading...' : `Load More (${filteredReports.length} of ${total})`}
            </button>
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
