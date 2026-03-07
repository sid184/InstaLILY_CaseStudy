"use client";

/**
 * CartSummary — persistent cart widget shown in the top-right.
 *
 * Displays item count badge, expands to show full cart with
 * item list, quantities, total price, and checkout button.
 */

import { useState } from "react";
import { useCart } from "./CartContext";


export default function CartSummary() {
  const { items, removeItem, clearCart, totalItems, totalPrice } = useCart();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      {/* Cart toggle button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-medium text-ps-gray-700 shadow-sm border border-ps-gray-200 hover:border-ps-blue hover:text-ps-blue transition-colors"
      >
        {/* Cart icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="h-5 w-5"
        >
          <path d="M2.25 2.25a.75.75 0 0 0 0 1.5h1.386c.17 0 .318.114.362.278l2.558 9.592a3.752 3.752 0 0 0-2.806 3.63c0 .414.336.75.75.75h15.75a.75.75 0 0 0 0-1.5H5.378A2.25 2.25 0 0 1 7.5 14.25h11.218a.75.75 0 0 0 .674-.421 60.358 60.358 0 0 0 2.96-7.228.75.75 0 0 0-.525-.965A60.864 60.864 0 0 0 5.68 4.509l-.232-.867A1.875 1.875 0 0 0 3.636 2.25H2.25ZM3.75 20.25a1.5 1.5 0 1 0 3 0 1.5 1.5 0 0 0-3 0ZM16.5 20.25a1.5 1.5 0 1 0 3 0 1.5 1.5 0 0 0-3 0Z" />
        </svg>
        Cart
        {/* Item count badge */}
        {totalItems > 0 && (
          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-ps-orange px-1.5 text-xs font-bold text-white">
            {totalItems}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-[calc(100vw-2rem)] rounded-lg border border-ps-gray-200 bg-white shadow-lg z-50 animate-fade-in-up sm:w-80">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-ps-gray-200 px-4 py-3">
            <h3 className="font-semibold text-ps-gray-900">
              Cart ({totalItems} {totalItems === 1 ? "item" : "items"})
            </h3>
            {items.length > 0 && (
              <button
                onClick={clearCart}
                className="text-xs text-ps-gray-500 hover:text-red-600 transition-colors"
              >
                Clear all
              </button>
            )}
          </div>

          {/* Cart items */}
          <div className="max-h-64 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-ps-gray-500">
                Your cart is empty.
                <br />
                Ask me about parts to get started!
              </div>
            ) : (
              <ul className="divide-y divide-ps-gray-100">
                {items.map((item) => (
                  <li
                    key={item.product.part_number}
                    className="flex items-center gap-3 px-4 py-3"
                  >
                    {/* Part info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-ps-blue">
                        {item.product.part_number}
                      </p>
                      <p className="truncate text-sm text-ps-gray-900">
                        {item.product.title}
                      </p>
                      <p className="text-sm font-medium text-ps-gray-700">
                        ${item.product.price.toFixed(2)}
                        {item.quantity > 1 && (
                          <span className="ml-1 text-xs text-ps-gray-500">
                            x{item.quantity}
                          </span>
                        )}
                      </p>
                    </div>

                    {/* Remove button */}
                    <button
                      onClick={() => removeItem(item.product.part_number)}
                      className="flex h-6 w-6 items-center justify-center rounded-full text-ps-gray-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                      title="Remove from cart"
                    >
                      &#10005;
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Footer with total and checkout */}
          {items.length > 0 && (
            <div className="border-t border-ps-gray-200 px-4 py-3">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-ps-gray-700">
                  Total
                </span>
                <span className="text-lg font-bold text-ps-gray-900">
                  ${totalPrice.toFixed(2)}
                </span>
              </div>
              <button
                onClick={() => {
                  alert(
                    `Checkout with ${totalItems} item(s) for $${totalPrice.toFixed(2)}\n\n(This is a demo — no real checkout)`,
                  );
                }}
                className="w-full rounded-lg bg-ps-orange py-2.5 text-sm font-medium text-white transition-colors hover:bg-ps-orange/90"
              >
                Proceed to Checkout
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
