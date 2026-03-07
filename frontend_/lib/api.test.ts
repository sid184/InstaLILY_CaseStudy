/**
 * Tests for lib/api.ts
 *
 * Uses Jest to mock fetch() so we can test retry logic, error handling,
 * and response parsing without a running backend.
 *
 * Run:  npx jest lib/api.test.ts --verbose
 */

import { sendMessage, ApiError } from "./api";
import { ChatResponse } from "./types";


// ---------------------------------------------------------------------------
// Mock fetch globally
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
global.fetch = mockFetch;

// Helper: create a mock Response object
function mockResponse(body: object, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
    headers: new Headers({ "content-type": "application/json" }),
  } as Response;
}

// A valid ChatResponse matching our backend's shape
const VALID_RESPONSE: ChatResponse = {
  message: "Hello! How can I help you find parts?",
  products: [],
  tool_calls: [],
  conversation_id: null,
};

beforeEach(() => {
  mockFetch.mockReset();
});


// ---------------------------------------------------------------------------
// Successful requests
// ---------------------------------------------------------------------------

describe("sendMessage — successful requests", () => {

  test("returns a ChatResponse on 200", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(VALID_RESPONSE));

    const result = await sendMessage("hi");

    expect(result.message).toBe("Hello! How can I help you find parts?");
    expect(result.products).toEqual([]);
    expect(result.tool_calls).toEqual([]);
  });

  test("sends correct request body", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(VALID_RESPONSE));

    await sendMessage("find part PS3406971", [
      { role: "user", content: "hello" },
      { role: "assistant", content: "hi there" },
    ], "conv-123");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/chat");
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/json");

    const body = JSON.parse(options.body);
    expect(body.message).toBe("find part PS3406971");
    expect(body.history).toHaveLength(2);
    expect(body.conversation_id).toBe("conv-123");
  });

  test("omits conversation_id when not provided", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(VALID_RESPONSE));

    await sendMessage("hi");

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.conversation_id).toBeUndefined();
  });

  test("defaults history to empty array", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(VALID_RESPONSE));

    await sendMessage("hi");

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.history).toEqual([]);
  });
});


// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

describe("sendMessage — error handling", () => {

  test("throws ApiError on 422 (validation error)", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse({ detail: "message field required" }, 422)
    );

    await expect(sendMessage("")).rejects.toThrow(ApiError);
  });

  test("ApiError includes status code", async () => {
    mockFetch.mockResolvedValue(
      mockResponse({ detail: "bad request" }, 400)
    );

    try {
      await sendMessage("test");
      fail("should have thrown");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(400);
    }
  });

  test("does not retry on 4xx errors", async () => {
    mockFetch.mockResolvedValue(
      mockResponse({ detail: "bad request" }, 400)
    );

    await expect(sendMessage("test")).rejects.toThrow(ApiError);
    // Should only call fetch once — no retries for client errors
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });
});


// ---------------------------------------------------------------------------
// Retry logic
// ---------------------------------------------------------------------------

describe("sendMessage — retry logic", () => {

  test("retries on 500 and succeeds on second attempt", async () => {
    mockFetch
      .mockResolvedValueOnce(mockResponse({ error: "server error" }, 500))
      .mockResolvedValueOnce(mockResponse(VALID_RESPONSE));

    const result = await sendMessage("hi");

    expect(result.message).toBe("Hello! How can I help you find parts?");
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  test("retries on network failure and succeeds", async () => {
    mockFetch
      .mockRejectedValueOnce(new Error("fetch failed"))
      .mockResolvedValueOnce(mockResponse(VALID_RESPONSE));

    const result = await sendMessage("hi");

    expect(result.message).toBe("Hello! How can I help you find parts?");
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  test("gives up after MAX_RETRIES and throws", async () => {
    mockFetch.mockResolvedValue(
      mockResponse({ error: "server error" }, 500)
    );

    await expect(sendMessage("hi")).rejects.toThrow("API returned 500");
    // 1 original + 2 retries = 3 total
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });

  test("gives up after MAX_RETRIES on network failure", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));

    await expect(sendMessage("hi")).rejects.toThrow("network down");
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });
});
