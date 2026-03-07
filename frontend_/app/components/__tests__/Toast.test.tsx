/**
 * @jest-environment jsdom
 */

import { render, screen, act } from "@testing-library/react";
import { ToastProvider, useToast } from "../Toast";

// ---------------------------------------------------------------------------
// Helper component that triggers a toast
// ---------------------------------------------------------------------------

function ToastTrigger({ message, type }: { message: string; type?: "success" | "error" | "info" }) {
  const { showToast } = useToast();
  return (
    <button onClick={() => showToast(message, type)}>
      Show Toast
    </button>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Toast", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("shows a toast when triggered", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Item added!" />
      </ToastProvider>,
    );

    act(() => {
      screen.getByText("Show Toast").click();
    });

    expect(screen.getByText("Item added!")).toBeInTheDocument();
  });

  it("auto-dismisses after 3 seconds", () => {
    render(
      <ToastProvider>
        <ToastTrigger message="Temporary message" />
      </ToastProvider>,
    );

    act(() => {
      screen.getByText("Show Toast").click();
    });

    expect(screen.getByText("Temporary message")).toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(3000);
    });

    expect(screen.queryByText("Temporary message")).not.toBeInTheDocument();
  });

  it("can show multiple toasts at once", () => {
    function MultiTrigger() {
      const { showToast } = useToast();
      return (
        <>
          <button onClick={() => showToast("Toast 1")}>First</button>
          <button onClick={() => showToast("Toast 2")}>Second</button>
        </>
      );
    }

    render(
      <ToastProvider>
        <MultiTrigger />
      </ToastProvider>,
    );

    act(() => {
      screen.getByText("First").click();
      screen.getByText("Second").click();
    });

    expect(screen.getByText("Toast 1")).toBeInTheDocument();
    expect(screen.getByText("Toast 2")).toBeInTheDocument();
  });

  it("throws when used outside ToastProvider", () => {
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      render(<ToastTrigger message="fail" />);
    }).toThrow("useToast must be used within a <ToastProvider>");

    spy.mockRestore();
  });
});
