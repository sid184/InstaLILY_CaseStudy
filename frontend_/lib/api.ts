/**
 * API client for the PartSelect chat backend.
 *
 * Wraps fetch() with type safety, error handling, and retry logic.
 * All communication with the backend goes through sendMessage().
 */

import { ChatMessage, ChatResponse } from "./types";


// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;


// ---------------------------------------------------------------------------
// Custom error class
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}


// ---------------------------------------------------------------------------
// sendMessage — the main function the frontend calls
// ---------------------------------------------------------------------------

export async function sendMessage(
  message: string,
  history: ChatMessage[] = [],
  conversationId?: string,
): Promise<ChatResponse> {
  const body = JSON.stringify({
    message,
    history,
    ...(conversationId && { conversation_id: conversationId }),
  });

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });

      if (!response.ok) {
        const errorBody = await response.text();
        throw new ApiError(
          `API returned ${response.status}`,
          response.status,
          errorBody,
        );
      }

      const data: ChatResponse = await response.json();
      return data;

    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't retry client errors (4xx) — they won't succeed on retry
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
        throw error;
      }

      // Don't retry if we've exhausted attempts
      if (attempt === MAX_RETRIES) {
        break;
      }

      // Wait before retrying (server errors, network failures)
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
    }
  }

  throw lastError ?? new Error("Request failed");
}
