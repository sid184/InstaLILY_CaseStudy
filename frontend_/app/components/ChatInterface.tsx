"use client";

/**
 * ChatInterface — the main chat UI component.
 *
 * Renders a message list with user/assistant bubbles, an input field,
 * a send button, loading indicator, follow-up suggestions, and
 * conversation history saved to localStorage.
 */

import { useState, useRef, useEffect, useCallback, FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import { sendMessage, ApiError } from "@/lib/api";
import { ChatMessage, ChatResponse, CompatibilityResult, DiagnosticResult, InstallationResult, Product, ToolCall } from "@/lib/types";
import ProductCard from "./ProductCard";
import InstallationCard from "./InstallationCard";
import CompatibilityBanner from "./CompatibilityBanner";
import DiagnosticCard from "./DiagnosticCard";
import CartSummary from "./CartSummary";
import ComparisonView from "./ComparisonView";
import { useCart } from "./CartContext";
import { useToast } from "./Toast";


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
  products?: Product[];
  installationResult?: InstallationResult | null;
  compatibilityResult?: CompatibilityResult | null;
  diagnosticResult?: DiagnosticResult | null;
  responseType?: "general" | "installation" | "compatibility" | "diagnostic";
  suggestedPrompts?: string[];
}

interface SavedConversation {
  id: string;
  title: string;
  timestamp: number;
  messages: DisplayMessage[];
}

const HISTORY_KEY = "partselect_conversations";
const MAX_SAVED = 20;


// ---------------------------------------------------------------------------
// ToolCallBadge
// ---------------------------------------------------------------------------

function ToolCallBadge({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);

  const labels: Record<string, string> = {
    search_products: "Searched Products",
    check_compatibility: "Checked Compatibility",
    diagnose_problem: "Diagnosed Problem",
    get_related_parts: "Found Related Parts",
    get_installation_guide: "Fetched Install Guide",
  };

  const label = labels[toolCall.tool] || toolCall.tool;

  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1 rounded-full bg-ps-teal-light px-3 py-1 text-xs font-medium text-[#1F5F5D] hover:bg-ps-teal/10 transition-colors"
      >
        <span className="text-ps-teal">&#9881;</span>
        {label}
        <span className="ml-1 text-ps-gray-500">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <pre className="mt-1 rounded bg-ps-gray-50 p-2 text-xs text-ps-gray-700 overflow-x-auto">
          {JSON.stringify(toolCall.args, null, 2)}
        </pre>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// FormattedResponse
// ---------------------------------------------------------------------------

function FormattedResponse({ content }: { content: string }) {
  const hasAnswer = /recommended|here'?s what I found|here'?s what|based on|I found/i.test(content);

  return (
    <div>
      {hasAnswer && (
        <div className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-ps-teal-light px-3 py-1 text-xs font-bold uppercase tracking-wide text-[#1F5F5D]">
          Answer Found
        </div>
      )}

      <div className="prose prose-2xl max-w-none text-ps-gray-900 prose-headings:text-ps-gray-900 prose-headings:font-bold prose-headings:uppercase prose-headings:tracking-wide prose-headings:mt-4 prose-headings:mb-2 prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-a:text-ps-teal prose-strong:text-ps-gray-900">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// FollowUpSuggestions — contextual quick-reply chips after assistant messages
// ---------------------------------------------------------------------------

function getFollowUpSuggestions(message: DisplayMessage): string[] {
  switch (message.responseType) {
    case "installation":
      return [
        "Is this part compatible with my model?",
        "How difficult is this repair?",
        "Show me similar parts",
      ];
    case "compatibility": {
      const compatible = message.compatibilityResult?.compatible;
      const modelFound = message.compatibilityResult?.model_found;
      if (!modelFound) {
        return [
          "Search for a different model number",
          "Show me refrigerator parts",
          "Show me dishwasher parts",
        ];
      }
      return compatible
        ? [
            "How do I install this part?",
            "What other parts might I need?",
            "Show me similar alternatives",
          ]
        : [
            "Show me compatible alternatives",
            "What models does this part fit?",
            "Search for a different part",
          ];
    }
    case "diagnostic":
      return [
        "How do I install this part?",
        "Is this compatible with my model?",
        "What is the price of this part?",
      ];
    default:
      return [
        "Find a part by part number",
        "Check if a part fits my model",
        "Diagnose a problem with my appliance",
      ];
  }
}


// ---------------------------------------------------------------------------
// Conversation history helpers
// ---------------------------------------------------------------------------

function loadConversations(): SavedConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveConversation(messages: DisplayMessage[], existingId?: string) {
  if (typeof window === "undefined" || messages.length === 0) return;

  const conversations = loadConversations();
  const firstUserMsg = messages.find((m) => m.role === "user");
  const title = firstUserMsg
    ? firstUserMsg.content.slice(0, 50) + (firstUserMsg.content.length > 50 ? "..." : "")
    : "New conversation";

  const id = existingId || crypto.randomUUID();

  const existingIdx = conversations.findIndex((c) => c.id === id);
  const entry: SavedConversation = { id, title, timestamp: Date.now(), messages };

  if (existingIdx >= 0) {
    conversations[existingIdx] = entry;
  } else {
    conversations.unshift(entry);
  }

  // Keep only the most recent
  localStorage.setItem(HISTORY_KEY, JSON.stringify(conversations.slice(0, MAX_SAVED)));
  return id;
}

function deleteConversation(id: string) {
  const conversations = loadConversations().filter((c) => c.id !== id);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(conversations));
}


// ---------------------------------------------------------------------------
// ChatInterface — main component
// ---------------------------------------------------------------------------

export default function ChatInterface() {
  const { addItem } = useCart();
  const { showToast } = useToast();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [localId, setLocalId] = useState<string | undefined>();
  const [showHistory, setShowHistory] = useState(false);
  const [savedConversations, setSavedConversations] = useState<SavedConversation[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load history on mount
  useEffect(() => {
    setSavedConversations(loadConversations());
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Save conversation whenever messages change
  useEffect(() => {
    if (messages.length > 0) {
      const id = saveConversation(messages, localId);
      if (id && !localId) setLocalId(id);
      setSavedConversations(loadConversations());
    }
  }, [messages, localId]);

  function buildHistory(): ChatMessage[] {
    return messages.map((msg) => ({
      role: msg.role,
      content: msg.content,
    }));
  }

  const submitMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    const userMessage: DisplayMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setError(null);
    setIsLoading(true);

    try {
      const history = buildHistory();
      const response: ChatResponse = await sendMessage(
        trimmed,
        history,
        conversationId,
      );

      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }

      const assistantMessage: DisplayMessage = {
        role: "assistant",
        content: response.message,
        toolCalls:
          response.tool_calls.length > 0 ? response.tool_calls : undefined,
        products:
          response.products.length > 0 ? response.products : undefined,
        installationResult: response.installation_result ?? null,
        compatibilityResult: response.compatibility_result ?? null,
        diagnosticResult: response.diagnostic_result ?? null,
        responseType: response.response_type ?? "general",
        suggestedPrompts: response.suggested_prompts ?? [],
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Server error (${err.status}). Please try again.`);
      } else {
        setError("Could not reach the server. Please check your connection.");
      }
    } finally {
      setIsLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, conversationId]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await submitMessage(input);
  }

  function startNewConversation() {
    setMessages([]);
    setConversationId(undefined);
    setLocalId(undefined);
    setError(null);
    setShowHistory(false);
  }

  function loadSavedConversation(conv: SavedConversation) {
    setMessages(conv.messages);
    setLocalId(conv.id);
    setConversationId(undefined);
    setError(null);
    setShowHistory(false);
  }

  function handleDeleteConversation(id: string) {
    deleteConversation(id);
    setSavedConversations(loadConversations());
    if (localId === id) {
      startNewConversation();
    }
  }

  return (
    <div className="flex h-screen flex-col bg-white">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-ps-gray-200 bg-white px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <img
            src="/partselect-logo.png"
            alt="PartSelect"
            className="h-10 w-auto"
          />
        </div>
        <div className="flex items-center gap-3 sm:gap-6">
          {/* History toggle */}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center gap-1.5 rounded-full border border-ps-gray-200 px-3 py-2 text-sm text-ps-gray-700 hover:border-ps-teal hover:text-ps-teal transition-colors"
            title="Conversation history"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <span className="hidden sm:inline">History</span>
          </button>
          {/* New conversation */}
          <button
            onClick={startNewConversation}
            className="flex items-center gap-1.5 rounded-full border border-ps-gray-200 px-3 py-2 text-sm text-ps-gray-700 hover:border-ps-teal hover:text-ps-teal transition-colors"
            title="New conversation"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span className="hidden sm:inline">New</span>
          </button>
          <div className="hidden sm:block text-right">
            <p className="text-sm font-semibold text-ps-gray-900">1-866-319-8402</p>
            <p className="text-xs text-ps-gray-500">Monday to Saturday, 8am - 8pm EST</p>
          </div>
          <CartSummary />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* History sidebar */}
        {showHistory && (
          <div className="w-72 shrink-0 border-r border-ps-gray-200 bg-ps-gray-50 overflow-y-auto animate-fade-in-up">
            <div className="p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ps-gray-500 mb-3">
                Recent Conversations
              </h3>
              {savedConversations.length === 0 ? (
                <p className="text-sm text-ps-gray-500">No conversations yet.</p>
              ) : (
                <div className="space-y-1">
                  {savedConversations.map((conv) => (
                    <div
                      key={conv.id}
                      className={`group flex items-start gap-2 rounded-lg p-2 cursor-pointer transition-colors ${
                        localId === conv.id
                          ? "bg-ps-teal-light"
                          : "hover:bg-ps-gray-100"
                      }`}
                    >
                      <button
                        onClick={() => loadSavedConversation(conv)}
                        className="flex-1 text-left min-w-0"
                      >
                        <p className="text-sm font-medium text-ps-gray-900 truncate">
                          {conv.title}
                        </p>
                        <p className="text-xs text-ps-gray-500">
                          {new Date(conv.timestamp).toLocaleDateString()}
                        </p>
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id); }}
                        className="opacity-0 group-hover:opacity-100 shrink-0 rounded p-1 text-ps-gray-400 hover:text-red-600 hover:bg-red-50 transition-all"
                        title="Delete"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-3.5 w-3.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Main chat area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Message list */}
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div className="mx-auto max-w-5xl space-y-4">
              {/* Welcome screen */}
              {messages.length === 0 && !isLoading && (
                <div className="py-6 text-center">
                  <h2 className="mb-3 text-6xl font-bold text-ps-gray-900">
                    PartSelect Parts Assistant
                  </h2>
                  <p className="mb-5 text-2xl text-ps-gray-500 max-w-lg mx-auto">
                    I can help you identify refrigerator and dishwasher parts, verify
                    compatibility, and walk through repair steps. Share a part number,
                    model number, or symptom to begin.
                  </p>

                  {/* Example prompts as simple rounded chips */}
                  <div className="flex flex-wrap justify-center gap-2">
                    {[
                      "Do you have part PS11752778?",
                      "My Whirlpool ice maker stopped working",
                      "Refrigerator water filter replacement",
                      "Is PS3406971 compatible with my WDT780SAEM1?",
                      "My dishwasher won't drain",
                    ].map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => setInput(suggestion)}
                        className="rounded-full border border-ps-gray-200 bg-white px-4 py-2 text-sm text-ps-gray-700 hover:border-ps-teal hover:text-ps-teal transition-colors shadow-sm"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Messages */}
              {messages.map((msg, i) => (
                <div key={i} className="animate-fade-in-up">
                  <div
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[90%] sm:max-w-[80%] rounded-2xl px-4 py-3 ${
                        msg.role === "user"
                          ? "border border-[#2B7A78] bg-[#2B7A78] text-white shadow-sm"
                          : "bg-white border border-ps-gray-200 text-ps-gray-900 shadow-sm"
                      }`}
                    >
                      {msg.role === "user" ? (
                        <p className="whitespace-pre-wrap text-2xl leading-relaxed">
                          {msg.content}
                        </p>
                      ) : (
                        <FormattedResponse content={msg.content} />
                      )}

                      {/* Tool call badges */}
                      {msg.toolCalls && msg.toolCalls.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1 border-t border-ps-gray-200 pt-2">
                          {msg.toolCalls.map((tc, j) => (
                            <ToolCallBadge key={j} toolCall={tc} />
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Discriminated rendering based on response_type */}
                  {msg.responseType === "installation" && msg.installationResult ? (
                    <div className="mt-3">
                      <InstallationCard result={msg.installationResult} />
                    </div>
                  ) : msg.responseType === "compatibility" && msg.compatibilityResult ? (
                    <div className="mt-3">
                      <CompatibilityBanner result={msg.compatibilityResult} />
                    </div>
                  ) : msg.responseType === "diagnostic" && msg.diagnosticResult ? (
                    <div className="mt-3">
                      <DiagnosticCard result={msg.diagnosticResult} />
                    </div>
                  ) : msg.products && msg.products.length > 0 ? (
                    <div className="mt-3 space-y-3">
                      {msg.products.map((product) => (
                        <ProductCard key={product.part_number} product={product} onAddToCart={(p) => {
                          addItem(p);
                          showToast(`${p.part_number} added to cart`);
                        }} />
                      ))}
                    </div>
                  ) : null}

                  {/* Follow-up suggestion chips — only on the last assistant message */}
                  {msg.role === "assistant" && i === messages.length - 1 && !isLoading && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(msg.suggestedPrompts && msg.suggestedPrompts.length > 0 ? msg.suggestedPrompts : getFollowUpSuggestions(msg)).map((suggestion) => (
                        <button
                          key={suggestion}
                          onClick={() => submitMessage(suggestion)}
                          className="rounded-full border border-ps-gray-200 bg-white px-3 py-1.5 text-xs text-ps-gray-600 hover:border-ps-teal hover:text-ps-teal transition-colors shadow-sm"
                        >
                          {suggestion} &rarr;
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {/* Loading indicator */}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-[#D1D5DB] bg-[#F8FAFC] px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1">
                        <div className="h-2 w-2 animate-bounce rounded-full bg-[#2B7A78] [animation-delay:-0.3s]" />
                        <div className="h-2 w-2 animate-bounce rounded-full bg-[#2B7A78] [animation-delay:-0.15s]" />
                        <div className="h-2 w-2 animate-bounce rounded-full bg-[#2B7A78]" />
                      </div>
                      <span className="text-xs font-medium text-[#374151]">
                        Assistant is typing...
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Error message */}
              {error && (
                <div className="mx-auto max-w-md rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              {/* Scroll anchor */}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input area */}
          <div className="border-t border-ps-gray-200 bg-white px-4 py-4">
            <form
              onSubmit={handleSubmit}
              className="mx-auto max-w-5xl"
            >
              <div className="relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about refrigerator or dishwasher parts..."
                  disabled={isLoading}
                  className="w-full rounded-full border border-ps-gray-300 py-4 pl-6 pr-16 text-2xl text-ps-gray-900 placeholder:text-ps-gray-500 focus:border-ps-teal focus:outline-none focus:ring-2 focus:ring-ps-teal/20 disabled:bg-ps-gray-50 disabled:text-ps-gray-500"
                />
                <button
                  type="submit"
                  disabled={isLoading || !input.trim()}
                  className="absolute right-1.5 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-[#2B7A78] bg-[#2B7A78] text-white shadow-sm transition-colors hover:border-[#1F5F5D] hover:bg-[#1F5F5D] active:scale-95 disabled:border-[#D1D5DB] disabled:bg-[#E5E7EB] disabled:text-[#6B7280] disabled:cursor-not-allowed"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    className="h-5 w-5"
                  >
                    <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                  </svg>
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* Comparison panel */}
      <ComparisonView />
    </div>
  );
}
