/**
 * @jest-environment jsdom
 */

import { renderHook, act } from "@testing-library/react";
import { CartProvider, useCart } from "../CartContext";
import { Product } from "@/lib/types";

// ---------------------------------------------------------------------------
// Test fixture
// ---------------------------------------------------------------------------

const mockProduct: Product = {
  part_number: "PS123",
  title: "Test Part",
  price: 29.99,
  brand: "TestBrand",
  appliance_type: "refrigerator",
  in_stock: true,
  url: "https://example.com",
  image_url: null,
  rating: 4.5,
  review_count: 10,
  manufacturer_part_number: null,
  description: null,
  installation: null,
  compatibility: [],
};

const mockProduct2: Product = {
  ...mockProduct,
  part_number: "PS456",
  title: "Another Part",
  price: 19.99,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CartContext", () => {
  function wrapper({ children }: { children: React.ReactNode }) {
    return <CartProvider>{children}</CartProvider>;
  }

  it("starts with an empty cart", () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    expect(result.current.items).toEqual([]);
    expect(result.current.totalItems).toBe(0);
    expect(result.current.totalPrice).toBe(0);
  });

  it("adds an item to the cart", () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.addItem(mockProduct));

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].product.part_number).toBe("PS123");
    expect(result.current.items[0].quantity).toBe(1);
    expect(result.current.totalItems).toBe(1);
    expect(result.current.totalPrice).toBeCloseTo(29.99);
  });

  it("increments quantity for duplicate items", () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.addItem(mockProduct));
    act(() => result.current.addItem(mockProduct));

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].quantity).toBe(2);
    expect(result.current.totalItems).toBe(2);
    expect(result.current.totalPrice).toBeCloseTo(59.98);
  });

  it("adds multiple different items", () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.addItem(mockProduct));
    act(() => result.current.addItem(mockProduct2));

    expect(result.current.items).toHaveLength(2);
    expect(result.current.totalItems).toBe(2);
    expect(result.current.totalPrice).toBeCloseTo(49.98);
  });

  it("removes an item by part number", () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.addItem(mockProduct));
    act(() => result.current.addItem(mockProduct2));
    act(() => result.current.removeItem("PS123"));

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].product.part_number).toBe("PS456");
  });

  it("clears all items", () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.addItem(mockProduct));
    act(() => result.current.addItem(mockProduct2));
    act(() => result.current.clearCart());

    expect(result.current.items).toEqual([]);
    expect(result.current.totalItems).toBe(0);
    expect(result.current.totalPrice).toBe(0);
  });

  it("throws when used outside CartProvider", () => {
    // Suppress console.error for the expected error
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      renderHook(() => useCart());
    }).toThrow("useCart must be used within a <CartProvider>");

    spy.mockRestore();
  });
});
