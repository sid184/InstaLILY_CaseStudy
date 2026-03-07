"use client";

/**
 * ComparisonView — side-by-side product comparison panel.
 *
 * Slides up from the bottom when 2+ products are selected for comparison.
 * Shows product attributes in aligned rows for easy comparison.
 */

import { useCompare } from "./CompareContext";
import { useCart } from "./CartContext";
import { useToast } from "./Toast";
import { Product } from "@/lib/types";


// ---------------------------------------------------------------------------
// Comparison row helper
// ---------------------------------------------------------------------------

function CompareRow({
  label,
  values,
}: {
  label: string;
  values: (string | null)[];
}) {
  return (
    <tr className="border-b border-ps-gray-100">
      <td className="py-2 pr-4 text-xs font-medium text-ps-gray-500 whitespace-nowrap">
        {label}
      </td>
      {values.map((value, i) => (
        <td key={i} className="py-2 px-4 text-sm text-ps-gray-900">
          {value || "—"}
        </td>
      ))}
    </tr>
  );
}


// ---------------------------------------------------------------------------
// ComparisonView
// ---------------------------------------------------------------------------

export default function ComparisonView() {
  const { compareItems, removeFromCompare, clearCompare, isCompareOpen, setIsCompareOpen } =
    useCompare();
  const { addItem } = useCart();
  const { showToast } = useToast();

  if (!isCompareOpen || compareItems.length < 2) return null;

  // Build comparison rows from product data
  function getRow(label: string, getter: (p: Product) => string | null): {
    label: string;
    values: (string | null)[];
  } {
    return {
      label,
      values: compareItems.map(getter),
    };
  }

  const rows = [
    getRow("Part Number", (p) => p.part_number),
    getRow("Brand", (p) => p.brand),
    getRow("Type", (p) =>
      p.appliance_type.charAt(0).toUpperCase() + p.appliance_type.slice(1),
    ),
    getRow("Price", (p) => `$${p.price.toFixed(2)}`),
    getRow("Rating", (p) =>
      p.rating !== null
        ? `${p.rating}/5${p.review_count ? ` (${p.review_count} reviews)` : ""}`
        : null,
    ),
    getRow("In Stock", (p) => (p.in_stock ? "Yes" : "No")),
    getRow("Difficulty", (p) => p.installation?.difficulty || null),
    getRow("Install Time", (p) => p.installation?.time || null),
    getRow("Tools Needed", (p) => p.installation?.tools || null),
  ];

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 flex max-h-[70vh] flex-col bg-white shadow-[0_-4px_20px_rgba(0,0,0,0.1)] animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-ps-gray-200 px-3 py-3 sm:px-6">
        <h3 className="text-sm font-semibold text-ps-gray-900">
          Comparing {compareItems.length} Products
        </h3>
        <div className="flex items-center gap-3">
          <button
            onClick={clearCompare}
            className="text-xs text-ps-gray-500 hover:text-red-600 transition-colors"
          >
            Clear all
          </button>
          <button
            onClick={() => setIsCompareOpen(false)}
            className="flex h-6 w-6 items-center justify-center rounded-full text-ps-gray-400 hover:bg-ps-gray-100 hover:text-ps-gray-700 transition-colors"
          >
            &#10005;
          </button>
        </div>
      </div>

      {/* Comparison table */}
      <div className="flex-1 overflow-auto px-3 py-4 sm:px-6">
        <table className="w-full min-w-[500px]">
          <thead>
            <tr className="border-b border-ps-gray-200">
              <th className="py-2 pr-4 text-left text-xs font-medium text-ps-gray-500">
                Attribute
              </th>
              {compareItems.map((product) => (
                <th key={product.part_number} className="py-2 px-4 text-left">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-xs font-bold text-ps-blue">
                        {product.part_number}
                      </p>
                      <p className="text-sm font-semibold text-ps-gray-900 max-w-48 truncate">
                        {product.title}
                      </p>
                    </div>
                    <button
                      onClick={() => removeFromCompare(product.part_number)}
                      className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs text-ps-gray-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                      title="Remove from comparison"
                    >
                      &#10005;
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <CompareRow key={row.label} label={row.label} values={row.values} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Action buttons row */}
      <div className="flex shrink-0 overflow-x-auto border-t border-ps-gray-200 px-3 py-3 sm:px-6">
        <div className="py-2 pr-4" />
        {compareItems.map((product) => (
          <div key={product.part_number} className="flex gap-2 px-4">
            {product.in_stock && (
              <button
                onClick={() => { addItem(product); showToast(`${product.part_number} added to cart`); }}
                className="rounded-lg bg-ps-teal px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#1F5F5D]"
              >
                Add to Cart
              </button>
            )}
            <a
              href={product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-ps-blue px-3 py-1.5 text-xs font-medium text-ps-blue transition-colors hover:bg-ps-blue-light"
            >
              View Details
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
