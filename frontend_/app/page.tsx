import ChatInterface from "./components/ChatInterface";
import { CartProvider } from "./components/CartContext";
import { CompareProvider } from "./components/CompareContext";
import { ToastProvider } from "./components/Toast";

export default function Home() {
  return (
    <ToastProvider>
      <CartProvider>
        <CompareProvider>
          <ChatInterface />
        </CompareProvider>
      </CartProvider>
    </ToastProvider>
  );
}
