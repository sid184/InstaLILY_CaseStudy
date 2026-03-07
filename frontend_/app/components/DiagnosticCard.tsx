"use client";

import { DiagnosticResult, Product } from "@/lib/types";
import ProductCard from "./ProductCard";
import { useCart } from "./CartContext";
import { useToast } from "./Toast";

interface Props {
  result: DiagnosticResult;
}

function topPart(parts: Product[]): Product | null {
  if (!parts.length) return null;
  return [...parts].sort((a, b) => {
    const scoreA = (a.rating ?? 0) * Math.log1p(a.review_count ?? 0);
    const scoreB = (b.rating ?? 0) * Math.log1p(b.review_count ?? 0);
    return scoreB - scoreA;
  })[0];
}

function StarRating({ rating }: { rating: number }) {
  const full = Math.round(rating);
  return (
    <span className="text-amber-400 text-xs">
      {"★".repeat(full)}{"☆".repeat(5 - full)}
      <span className="ml-1 text-ps-gray-500">{rating.toFixed(1)}</span>
    </span>
  );
}

export default function DiagnosticCard({ result }: Props) {
  const { addItem } = useCart();
  const { showToast } = useToast();

  const { matched_symptom, parts } = result;

  if (!parts || parts.length === 0) {
    return (
      <div className="rounded-lg border border-ps-gray-200 bg-ps-gray-50 p-4 text-sm text-ps-gray-500">
        No parts found for this symptom.
      </div>
    );
  }

  const best = topPart(parts);
  const applianceType = parts[0]?.appliance_type;
  const applianceLabel = applianceType
    ? applianceType.charAt(0).toUpperCase() + applianceType.slice(1)
    : null;

  return (
    <div className="space-y-3">
      {/* Diagnosis summary */}
      <div className="rounded-lg border border-ps-gray-200 bg-white px-4 py-4 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-ps-gray-500 mb-3">
          Diagnosis Summary
        </p>

        <div className="flex flex-col gap-3">
          {/* Confirmed symptom */}
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ps-teal/10 text-ps-teal text-sm">
              ✓
            </div>
            <div>
              <p className="text-xs font-semibold text-ps-gray-500 uppercase tracking-wide">Symptom confirmed</p>
              <p className="text-sm font-medium text-ps-gray-900 mt-0.5">
                {matched_symptom ?? "Your reported issue"}
                {applianceLabel && (
                  <span className="ml-2 rounded-full bg-ps-teal/10 px-2 py-0.5 text-xs font-medium text-ps-teal">
                    {applianceLabel}
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Top recommendation */}
          {best && (
            <>
              <div className="ml-3 h-px bg-ps-gray-100" />
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-500 text-sm">
                  ★
                </div>
                <div>
                  <p className="text-xs font-semibold text-ps-gray-500 uppercase tracking-wide">Top recommended fix</p>
                  <p className="text-sm font-medium text-ps-gray-900 mt-0.5">{best.title}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-sm font-semibold text-ps-teal">${best.price.toFixed(2)}</span>
                    {best.rating != null && <StarRating rating={best.rating} />}
                    {best.review_count != null && (
                      <span className="text-xs text-ps-gray-400">
                        {best.review_count.toLocaleString()} review{best.review_count !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Part count */}
          <div className="ml-3 h-px bg-ps-gray-100" />
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ps-gray-100 text-ps-gray-600 text-sm font-bold">
              {parts.length}
            </div>
            <div className="pt-0.5">
              <p className="text-sm text-ps-gray-700">
                {parts.length === 1
                  ? "1 part is known to fix this symptom"
                  : `${parts.length} parts are known to fix this symptom`}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Parts list */}
      <div className="space-y-2">
        {parts.map((product) => (
          <ProductCard
            key={product.part_number}
            product={product}
            onAddToCart={(p) => {
              addItem(p);
              showToast(`${p.part_number} added to cart`);
            }}
          />
        ))}
      </div>
    </div>
  );
}
