"use client";

/**
 * CartContext — shared cart state across components.
 *
 * Provides addItem, removeItem, clearCart, and the cart items list
 * to any component wrapped in <CartProvider>.
 */

import { createContext, useContext, useState, ReactNode } from "react";
import { Product } from "@/lib/types";


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CartItem {
  product: Product;
  quantity: number;
}

interface CartContextType {
  items: CartItem[];
  addItem: (product: Product) => void;
  removeItem: (partNumber: string) => void;
  clearCart: () => void;
  totalItems: number;
  totalPrice: number;
}


// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const CartContext = createContext<CartContextType | null>(null);

export function useCart(): CartContextType {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart must be used within a <CartProvider>");
  }
  return context;
}


// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  function addItem(product: Product) {
    setItems((prev) => {
      const existing = prev.find(
        (item) => item.product.part_number === product.part_number,
      );
      if (existing) {
        // Increment quantity if already in cart
        return prev.map((item) =>
          item.product.part_number === product.part_number
            ? { ...item, quantity: item.quantity + 1 }
            : item,
        );
      }
      // Add new item
      return [...prev, { product, quantity: 1 }];
    });
  }

  function removeItem(partNumber: string) {
    setItems((prev) => prev.filter((item) => item.product.part_number !== partNumber));
  }

  function clearCart() {
    setItems([]);
  }

  const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);
  const totalPrice = items.reduce(
    (sum, item) => sum + item.product.price * item.quantity,
    0,
  );

  return (
    <CartContext.Provider
      value={{ items, addItem, removeItem, clearCart, totalItems, totalPrice }}
    >
      {children}
    </CartContext.Provider>
  );
}
