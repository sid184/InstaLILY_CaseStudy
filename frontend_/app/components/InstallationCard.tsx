"use client";

import React from "react";
import { InstallationResult } from "@/lib/types";

interface Props {
  result: InstallationResult;
}

const DIFFICULTY_COLOR: Record<string, string> = {
  "really easy": "bg-green-50 text-green-700 border-green-200",
  "easy":        "bg-green-50 text-green-700 border-green-200",
  "moderate":    "bg-amber-50 text-amber-700 border-amber-200",
  "hard":        "bg-red-50 text-red-700 border-red-200",
  "really hard": "bg-red-50 text-red-700 border-red-200",
};

function difficultyColor(difficulty: string): string {
  return DIFFICULTY_COLOR[difficulty.toLowerCase()] ?? "bg-ps-gray-50 text-ps-gray-700 border-ps-gray-200";
}

export default function InstallationCard({ result }: Props) {
  if (!result.found || !result.installation) {
    return (
      <div className="rounded-lg border border-ps-gray-200 bg-ps-gray-50 p-4 text-sm text-ps-gray-500">
        No installation guide found for this part.
      </div>
    );
  }

  const { difficulty, time, tools, repair_story_title, repair_story_text } = result.installation;
  const toolList = tools ? tools.split(/,|;/).map(t => t.trim()).filter(Boolean) : [];
  const hasStory = !!(repair_story_title || repair_story_text);

  const steps = [
    hasStory && {
      label: "How a customer fixed this",
      content: (
        <div className="space-y-1">
          {repair_story_title && (
            <p className="text-sm font-medium text-ps-gray-900">"{repair_story_title}"</p>
          )}
          {repair_story_text && (
            <p className="text-sm text-ps-gray-700 leading-relaxed">{repair_story_text}</p>
          )}
        </div>
      ),
    },
    difficulty && {
      label: "Difficulty",
      content: (
        <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-semibold ${difficultyColor(difficulty)}`}>
          {difficulty}
        </span>
      ),
    },
    time && {
      label: "Estimated time",
      content: <span className="text-sm text-ps-gray-900">{time}</span>,
    },
    toolList.length > 0 && {
      label: "Tools needed",
      content: (
        <ul className="mt-1 space-y-1">
          {toolList.map(tool => (
            <li key={tool} className="flex items-center gap-2 text-sm text-ps-gray-700">
              <span className="h-4 w-4 rounded border border-ps-gray-300 bg-white inline-block shrink-0" />
              {tool}
            </li>
          ))}
        </ul>
      ),
    },
    {
      label: hasStory ? "More repair stories" : "Customer repair guides",
      content: result.url ? (
        <a
          href={result.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ backgroundColor: "#2B7A78" }}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 transition-opacity"
        >
          {hasStory ? "View all stories on PartSelect →" : "View customer repair stories →"}
        </a>
      ) : (
        <span className="text-sm text-ps-gray-500">Search on PartSelect.com for repair guides.</span>
      ),
    },
  ].filter(Boolean) as { label: string; content: React.ReactNode }[];

  return (
    <div className="rounded-lg border border-ps-gray-200 bg-white p-4 shadow-sm">
      <h4 className="mb-4 text-sm font-semibold text-ps-gray-900">
        Installation Guide{result.title ? ` — ${result.title}` : ""}
      </h4>

      <div className="flex flex-col gap-3">
        {steps.map((step, i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ps-teal text-white text-xs font-bold">
              {i + 1}
            </div>
            <div className="pt-0.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ps-gray-500 mb-1">
                {step.label}
              </p>
              {step.content}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
