"use client";

/**
 * ProductCard — displays a single product returned by the agent.
 *
 * Horizontal layout: image on the left, info on the right.
 * Shows part title, part number, stock badge, price, and action buttons.
 */

import { useState } from "react";
import { Product } from "@/lib/types";
import { useCompare } from "./CompareContext";


// ---------------------------------------------------------------------------
// Star rating display
// ---------------------------------------------------------------------------

function StarRating({ rating, reviewCount }: { rating: number; reviewCount: number | null }) {
  const stars = [];
  for (let i = 1; i <= 5; i++) {
    if (i <= Math.floor(rating)) {
      stars.push(<span key={i} className="text-yellow-400">&#9733;</span>);
    } else if (i - rating < 1) {
      stars.push(<span key={i} className="text-yellow-400">&#9733;</span>);
    } else {
      stars.push(<span key={i} className="text-ps-gray-300">&#9733;</span>);
    }
  }

  return (
    <div className="flex items-center gap-1">
      <div className="flex text-sm">{stars}</div>
      {reviewCount !== null && (
        <span className="text-xs text-ps-gray-500">({reviewCount})</span>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// ProductCard
// ---------------------------------------------------------------------------

interface ProductCardProps {
  product: Product;
  onAddToCart?: (product: Product) => void;
}

export default function ProductCard({ product, onAddToCart }: ProductCardProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const { addToCompare, removeFromCompare, isComparing, maxReached } = useCompare();

  const showImage = product.image_url && !imgFailed;
  const inCompare = isComparing(product.part_number);

  return (
    <div className="flex flex-col sm:flex-row overflow-hidden rounded-lg border border-ps-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      {/* Product image — left side */}
      <div className="relative flex h-40 sm:h-auto sm:w-36 shrink-0 items-center justify-center bg-ps-gray-50 p-4">
        {showImage ? (
          <img
            src={product.image_url!}
            alt={product.title}
            className="max-h-full max-w-full object-contain"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center text-ps-gray-300">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="h-12 w-12"
            >
              <path
                fillRule="evenodd"
                d="M1.5 6a2.25 2.25 0 0 1 2.25-2.25h16.5A2.25 2.25 0 0 1 22.5 6v12a2.25 2.25 0 0 1-2.25 2.25H3.75A2.25 2.25 0 0 1 1.5 18V6ZM3 16.06V18c0 .414.336.75.75.75h16.5A.75.75 0 0 0 21 18v-1.94l-2.69-2.689a1.5 1.5 0 0 0-2.12 0l-.88.879.97.97a.75.75 0 1 1-1.06 1.06l-5.16-5.159a1.5 1.5 0 0 0-2.12 0L3 16.061Zm10.125-7.81a1.125 1.125 0 1 1 2.25 0 1.125 1.125 0 0 1-2.25 0Z"
                clipRule="evenodd"
              />
            </svg>
            <span className="mt-1 text-xs text-ps-gray-500">No image</span>
          </div>
        )}
      </div>

      {/* Product info — right side */}
      <div className="flex flex-1 flex-col p-4">
        {/* Title */}
        <h3 className="text-base font-semibold leading-snug text-ps-gray-900">
          {product.title}
        </h3>

        {/* Part number + stock badge */}
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <p className="text-xs text-ps-gray-500">
            Part #{product.part_number}
            {product.manufacturer_part_number && (
              <span className="ml-1">({product.manufacturer_part_number})</span>
            )}
          </p>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              product.in_stock
                ? "bg-ps-green-light text-ps-green"
                : "bg-red-50 text-red-600"
            }`}
          >
            {product.in_stock ? "In Stock" : "Out of Stock"}
          </span>
        </div>

        {/* Brand & appliance type */}
        <p className="mt-1 text-xs text-ps-gray-500">
          {product.brand} &middot;{" "}
          {product.appliance_type.charAt(0).toUpperCase() +
            product.appliance_type.slice(1)}
        </p>

        {/* Rating */}
        {product.rating !== null && (
          <div className="mt-1">
            <StarRating rating={product.rating} reviewCount={product.review_count} />
          </div>
        )}

        {/* Installation difficulty */}
        {product.installation?.difficulty && (
          <p className="mt-1 text-xs text-ps-gray-500">
            <span className="font-medium text-ps-gray-700">Install:</span>{" "}
            {product.installation.difficulty}
            {product.installation.time && ` — ${product.installation.time}`}
          </p>
        )}

        {/* Collapsible details — description, tools, symptoms, compatible models */}
        {(product.description || product.symptoms.length > 0 || product.compatible_models.length > 0 || product.installation?.tools) && (
          <div className="mt-2">
            <button
              onClick={() => setShowDetails(prev => !prev)}
              className="text-xs text-ps-teal hover:underline focus:outline-none"
            >
              {showDetails ? "Hide details ▲" : "Show details ▼"}
            </button>
            {showDetails && (
              <div className="mt-2 space-y-2 text-xs text-ps-gray-700 border-t border-ps-gray-100 pt-2">
                {product.description && (
                  <p>{product.description}</p>
                )}
                {product.installation?.tools && (
                  <p>
                    <span className="font-medium">Tools needed:</span>{" "}
                    {product.installation.tools}
                  </p>
                )}
                {product.symptoms.length > 0 && (
                  <div>
                    <p className="font-medium">Fixes these symptoms:</p>
                    <ul className="mt-0.5 list-disc list-inside space-y-0.5">
                      {product.symptoms.slice(0, 5).map(s => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {product.compatible_models.length > 0 && (
                  <p>
                    <span className="font-medium">Compatible models:</span>{" "}
                    {product.compatible_models.slice(0, 6).join(", ")}
                    {product.compatible_models.length > 6 && (
                      <span className="text-ps-gray-400"> +{product.compatible_models.length - 6} more</span>
                    )}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Price */}
        <p className="mt-2 text-lg font-bold text-ps-gray-900">
          ${product.price.toFixed(2)}
        </p>

        {/* Action buttons */}
        <div className="mt-3 flex flex-wrap gap-2">
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-ps-gray-300 px-4 py-2 text-center text-sm font-medium text-ps-gray-700 transition-colors hover:bg-ps-gray-50"
          >
            View Details
          </a>
          {product.in_stock && onAddToCart && (
            <button
              onClick={() => onAddToCart(product)}
              className="rounded-lg bg-[#2B7A78] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#1F5F5D]"
            >
              Add to Cart
            </button>
          )}
          <button
            onClick={() =>
              inCompare
                ? removeFromCompare(product.part_number)
                : addToCompare(product)
            }
            disabled={!inCompare && maxReached}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              inCompare
                ? "bg-[#1F5F5D] text-white hover:bg-[#2B7A78]"
                : "border border-ps-gray-300 text-ps-gray-700 hover:border-ps-teal hover:text-ps-teal disabled:opacity-40 disabled:cursor-not-allowed"
            }`}
          >
            {inCompare ? "Remove from Compare" : maxReached ? "Max 3" : "Compare"}
          </button>
        </div>
      </div>
    </div>
  );
}
