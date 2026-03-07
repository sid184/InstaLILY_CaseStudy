/**
 * TypeScript types matching the backend Pydantic models (backend/models.py).
 *
 * These are the contracts between the frontend and the API.
 * If you change a model in models.py, update it here too.
 */


// ---------------------------------------------------------------------------
// Data Models (match Product and Installation in models.py)
// ---------------------------------------------------------------------------

export interface Installation {
  difficulty: string | null;
  time: string | null;
  tools: string | null;
  repair_story_title: string | null;
  repair_story_text: string | null;
}

export interface Product {
  part_number: string;
  title: string;
  price: number;
  brand: string;
  appliance_type: "refrigerator" | "dishwasher";
  url: string;
  image_url: string | null;
  description: string | null;
  rating: number | null;
  review_count: number | null;
  in_stock: boolean;
  symptoms: string[];
  compatible_models: string[];
  manufacturer_part_number: string | null;
  installation: Installation | null;
}


// ---------------------------------------------------------------------------
// API Request / Response (match ChatRequest, ChatResponse in models.py)
// ---------------------------------------------------------------------------

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  history: ChatMessage[];
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result_summary: string | null;
}

export interface InstallationResult {
  found: boolean;
  part_number?: string;
  title?: string;
  installation?: {
    difficulty: string | null;
    time: string | null;
    tools: string | null;
  };
  has_guide?: boolean;
  url?: string;
}

export interface CompatibilityResult {
  compatible: boolean;
  part: Product | null;
  model_found: boolean;
  compatible_parts: Product[];
}

export interface DiagnosticResult {
  matched_symptom: string | null;
  parts: Product[];
  strategy: "exact" | "vector" | "none";
}

export interface ChatResponse {
  message: string;
  products: Product[];
  tool_calls: ToolCall[];
  conversation_id: string | null;
  installation_result?: InstallationResult | null;
  compatibility_result?: CompatibilityResult | null;
  diagnostic_result?: DiagnosticResult | null;
  response_type?: "general" | "installation" | "compatibility" | "diagnostic";
  suggested_prompts?: string[];
}
