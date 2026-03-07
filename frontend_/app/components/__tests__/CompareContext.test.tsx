/**
 * @jest-environment jsdom
 */

import { renderHook, act } from "@testing-library/react";
import { CompareProvider, useCompare } from "../CompareContext";
import { Product } from "@/lib/types";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function makeProduct(partNumber: string): Product {
  return {
    part_number: partNumber,
    title: `Part ${partNumber}`,
    price: 29.99,
    brand: "TestBrand",
    appliance_type: "refrigerator",
    in_stock: true,
    url: "https://example.com",
    image_url: null,
    rating: 4.0,
    review_count: 5,
    manufacturer_part_number: null,
    description: null,
    installation: null,
    compatibility: [],
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CompareContext", () => {
  function wrapper({ children }: { children: React.ReactNode }) {
    return <CompareProvider>{children}</CompareProvider>;
  }

  it("starts empty", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });
    expect(result.current.compareItems).toEqual([]);
    expect(result.current.isCompareOpen).toBe(false);
    expect(result.current.maxReached).toBe(false);
  });

  it("adds a product to compare", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });

    act(() => result.current.addToCompare(makeProduct("PS1")));

    expect(result.current.compareItems).toHaveLength(1);
    expect(result.current.isComparing("PS1")).toBe(true);
  });

  it("auto-opens panel when 2+ items are added", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });

    act(() => result.current.addToCompare(makeProduct("PS1")));
    expect(result.current.isCompareOpen).toBe(false);

    act(() => result.current.addToCompare(makeProduct("PS2")));
    expect(result.current.isCompareOpen).toBe(true);
  });

  it("prevents adding more than 3 items", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });

    act(() => result.current.addToCompare(makeProduct("PS1")));
    act(() => result.current.addToCompare(makeProduct("PS2")));
    act(() => result.current.addToCompare(makeProduct("PS3")));

    expect(result.current.maxReached).toBe(true);

    act(() => result.current.addToCompare(makeProduct("PS4")));
    expect(result.current.compareItems).toHaveLength(3);
  });

  it("prevents duplicate items", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });

    act(() => result.current.addToCompare(makeProduct("PS1")));
    act(() => result.current.addToCompare(makeProduct("PS1")));

    expect(result.current.compareItems).toHaveLength(1);
  });

  it("removes an item and auto-closes below 2", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });

    act(() => result.current.addToCompare(makeProduct("PS1")));
    act(() => result.current.addToCompare(makeProduct("PS2")));
    expect(result.current.isCompareOpen).toBe(true);

    act(() => result.current.removeFromCompare("PS1"));
    expect(result.current.compareItems).toHaveLength(1);
    expect(result.current.isCompareOpen).toBe(false);
  });

  it("clears all items", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });

    act(() => result.current.addToCompare(makeProduct("PS1")));
    act(() => result.current.addToCompare(makeProduct("PS2")));
    act(() => result.current.clearCompare());

    expect(result.current.compareItems).toEqual([]);
    expect(result.current.isCompareOpen).toBe(false);
  });

  it("throws when used outside CompareProvider", () => {
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      renderHook(() => useCompare());
    }).toThrow("useCompare must be used within a <CompareProvider>");

    spy.mockRestore();
  });
});
