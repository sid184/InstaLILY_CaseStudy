"use client";

/**
 * CompareContext — shared state for product comparison.
 *
 * Tracks which products are selected for side-by-side comparison.
 * Maximum 3 products can be compared at once.
 */

import { createContext, useContext, useState, ReactNode } from "react";
import { Product } from "@/lib/types";


// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_COMPARE = 3;


// ---------------------------------------------------------------------------
// Context type
// ---------------------------------------------------------------------------

interface CompareContextType {
  compareItems: Product[];
  addToCompare: (product: Product) => void;
  removeFromCompare: (partNumber: string) => void;
  clearCompare: () => void;
  isComparing: (partNumber: string) => boolean;
  isCompareOpen: boolean;
  setIsCompareOpen: (open: boolean) => void;
  maxReached: boolean;
}


// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const CompareContext = createContext<CompareContextType | null>(null);

export function useCompare(): CompareContextType {
  const context = useContext(CompareContext);
  if (!context) {
    throw new Error("useCompare must be used within a <CompareProvider>");
  }
  return context;
}


// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function CompareProvider({ children }: { children: ReactNode }) {
  const [compareItems, setCompareItems] = useState<Product[]>([]);
  const [isCompareOpen, setIsCompareOpen] = useState(false);

  function addToCompare(product: Product) {
    setCompareItems((prev) => {
      if (prev.length >= MAX_COMPARE) return prev;
      if (prev.some((p) => p.part_number === product.part_number)) return prev;
      const next = [...prev, product];
      // Auto-open comparison view when 2+ items are selected
      if (next.length >= 2) setIsCompareOpen(true);
      return next;
    });
  }

  function removeFromCompare(partNumber: string) {
    setCompareItems((prev) => {
      const next = prev.filter((p) => p.part_number !== partNumber);
      if (next.length < 2) setIsCompareOpen(false);
      return next;
    });
  }

  function clearCompare() {
    setCompareItems([]);
    setIsCompareOpen(false);
  }

  function isComparing(partNumber: string) {
    return compareItems.some((p) => p.part_number === partNumber);
  }

  const maxReached = compareItems.length >= MAX_COMPARE;

  return (
    <CompareContext.Provider
      value={{
        compareItems,
        addToCompare,
        removeFromCompare,
        clearCompare,
        isComparing,
        isCompareOpen,
        setIsCompareOpen,
        maxReached,
      }}
    >
      {children}
    </CompareContext.Provider>
  );
}
