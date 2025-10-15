// src/api/videos.js
import { fetchJson } from "./client";

export async function uploadVideo(file) {
  const fd = new FormData();
  fd.append("file", file); // must be 'file'
  return fetchJson("/videos", { method: "POST", body: fd });
}

export async function startAnalysis(analysisId, mlModules, traditionalModules) {
  return fetchJson(`/analyses/${analysisId}/start`, {
    method: "POST",
    json: {
      modules: mlModules,
      traditional: traditionalModules
    }
  });
}