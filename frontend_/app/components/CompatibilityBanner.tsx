"use client";

import { CompatibilityResult } from "@/lib/types";
import ProductCard from "./ProductCard";

interface Props {
  result: CompatibilityResult;
}

export default function CompatibilityBanner({ result }: Props) {
  const { compatible, part, model_found, compatible_parts } = result;

  return (
    <div className="space-y-3">
      {/* Verdict banner */}
      {!model_found ? (
        <div className="flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium bg-amber-50 text-amber-800 border border-amber-200">
          <span className="text-base">⚠</span>
          <div>
            <p className="font-semibold">Model not found in our database</p>
            <p className="font-normal mt-0.5">
              We can&apos;t confirm compatibility for this model. Search directly on{" "}
              <a
                href="https://www.partselect.com"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-amber-900"
              >
                PartSelect.com
              </a>{" "}
              for accurate results.
            </p>
          </div>
        </div>
      ) : (
        <div
          className={`flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium ${
            compatible
              ? "bg-green-50 text-green-700 border border-green-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          <span className="text-base">{compatible ? "✓" : "✗"}</span>
          <span>
            {compatible
              ? "Compatible — this part fits your appliance model."
              : "Not compatible — this part does not fit your appliance model."}
          </span>
        </div>
      )}

      {/* The queried part */}
      {part && <ProductCard product={part} />}

      {/* Alternatives when incompatible and model IS known */}
      {!compatible && model_found && compatible_parts.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ps-gray-600">
            Parts that do fit your model:
          </p>
          <div className="space-y-2">
            {compatible_parts.slice(0, 3).map((p) => (
              <ProductCard key={p.part_number} product={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
