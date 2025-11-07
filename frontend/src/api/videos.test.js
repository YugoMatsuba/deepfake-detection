import { jest, describe, it, expect, beforeAll, afterAll, beforeEach } from "@jest/globals";

const mockFetchJson = jest.fn();

await jest.unstable_mockModule("./client.js", () => ({
  fetchJson: mockFetchJson,
}));

const { uploadVideo, startAnalysis } = await import("./videos.js");

const OriginalFormData = global.FormData;

class MockFormData {
  constructor() {
    this.appended = [];
  }

  append(key, value) {
    this.appended.push([key, value]);
  }
}

describe("videos API helpers", () => {
  beforeAll(() => {
    global.FormData = MockFormData;
  });

  afterAll(() => {
    global.FormData = OriginalFormData;
  });

  beforeEach(() => {
    mockFetchJson.mockReset();
  });

  it("uploadVideo posts form data with file", async () => {
    const fakeFile = { name: "video.mp4" };
    mockFetchJson.mockResolvedValue({ analysis_id: "abc" });

    await uploadVideo(fakeFile);

    expect(mockFetchJson).toHaveBeenCalledTimes(1);
    const [path, options] = mockFetchJson.mock.calls[0];
    expect(path).toBe("/videos");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(MockFormData);
    expect(options.body.appended).toEqual([["file", fakeFile]]);
  });

  it("startAnalysis posts selected modules", async () => {
    const ml = ["xception"];
    const traditional = ["histogram"];
    mockFetchJson.mockResolvedValue({ ok: true });

    await startAnalysis("analysis-123", ml, traditional);

    expect(mockFetchJson).toHaveBeenCalledWith("/analyses/analysis-123/start", {
      method: "POST",
      json: {
        modules: ml,
        traditional,
      },
    });
  });
});
