import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import BillingPanel, { safeCheckout } from "../../components/referral/BillingPanel";
import PaymentReturn from "../../components/referral/PaymentReturn";
import { workspaceApi as api } from "../../lib/referral-api/workspace";

jest.mock("../../lib/referral-api/workspace", () => ({
  workspaceApi: { membership: jest.fn(), capabilities: jest.fn(), checkout: jest.fn(), order: jest.fn() },
  errorMessage: () => "Request failed; retry safely", operationKey: () => "stable-operation-key",
}));
const order = { id: "00000000-0000-0000-0000-000000000001", state: "pending", environment: "test", amount: 500,
  currency: "usd", return_path: "/workspace", checkout_url: "https://checkout.stripe.com/c/pay/cs_test_demo" };
beforeEach(() => {
  jest.resetAllMocks();
  (api.membership as jest.Mock).mockResolvedValue({ remaining: 0, reserved: 0, real_ai_allowed: false });
  (api.capabilities as jest.Mock).mockResolvedValue({ payments_available: true });
});
afterEach(() => jest.useRealTimers());

it("uses explicit checkout with a stable retry key and never auto-generates", async () => {
  (api.checkout as jest.Mock).mockRejectedValueOnce(new Error()).mockResolvedValueOnce(order);
  render(<BillingPanel csrf="csrf" returnPath="/workspace" />);
  const button = screen.getByRole("button", { name: "Prepare test checkout" });
  await waitFor(() => expect(button).toBeEnabled());
  expect(api.checkout).not.toHaveBeenCalled();
  fireEvent.click(button);
  await screen.findByRole("alert");
  fireEvent.click(button);
  expect(await screen.findByRole("link", { name: "Continue to Stripe test checkout" })).toHaveAttribute("href", order.checkout_url);
  expect(api.checkout).toHaveBeenNthCalledWith(1, "/workspace", "csrf", "stable-operation-key");
  expect(api.checkout).toHaveBeenNthCalledWith(2, "/workspace", "csrf", "stable-operation-key");
});

it("blocks another purchase even when an active membership has no credits", async () => {
  (api.membership as jest.Mock).mockResolvedValue({ valid_until: "2099-01-01T00:00:00Z", remaining: 0, reserved: 0 });
  render(<BillingPanel csrf="csrf" />);
  await screen.findByText(/Active until/);
  expect(screen.getByRole("button", { name: "Prepare test checkout" })).toBeDisabled();
});

it("only reads the server order on return and exposes the saved workspace", async () => {
  (api.order as jest.Mock).mockResolvedValue({ ...order, state: "paid" });
  render(<PaymentReturn orderId={order.id} />);
  await screen.findByText("Server order: paid");
  expect(api.order).toHaveBeenCalledWith(order.id);
  expect(api.checkout).not.toHaveBeenCalled();
  expect(screen.getByRole("link", { name: "Return to saved work" })).toHaveAttribute("href", "/workspace");
});

it("bounds pending polling and stops on unmount", async () => {
  jest.useFakeTimers();
  (api.order as jest.Mock).mockResolvedValue(order);
  const view = render(<PaymentReturn orderId={order.id} />);
  await act(async () => {});
  for (let i=0; i<12; i++) await act(async () => { jest.advanceTimersByTime(3000); });
  expect(api.order).toHaveBeenCalledTimes(10);
  expect(screen.getByRole("button", { name: "Refresh order status" })).toBeEnabled();
  view.unmount();
  await act(async () => { jest.advanceTimersByTime(60_000); });
  expect(api.order).toHaveBeenCalledTimes(10);
});

it("rejects external return destinations and unsafe checkout URLs", async () => {
  expect(safeCheckout("https://checkout.stripe.com.evil.test/pay")).toBe(false);
  expect(safeCheckout("https://attacker@checkout.stripe.com/pay")).toBe(false);
  expect(safeCheckout("javascript:alert(1)")).toBe(false);
  (api.order as jest.Mock).mockResolvedValue({ ...order, state: "refunded", return_path: "https://evil.test" });
  render(<PaymentReturn orderId={order.id} />);
  await screen.findByText("Server order: refunded");
  expect(screen.getByRole("link", { name: "Return to saved work" })).toHaveAttribute("href", "/account");
});
