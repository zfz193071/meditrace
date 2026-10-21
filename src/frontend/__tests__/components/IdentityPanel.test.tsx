import { fireEvent, render, screen } from "@testing-library/react";
import IdentityPanel from "../../components/referral/IdentityPanel";

beforeEach(() => jest.resetAllMocks());

it("requires sign-in for a private workspace and leaves the public site accessible", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => ({ user: null, csrf_token: null, expires_at: null, login_available: true }),
  });
  render(<IdentityPanel workspace />);
  expect(await screen.findByRole("link", { name: "Continue with GitHub" })).toHaveAttribute(
    "href", "/api/v1/auth/github/start?return_path=%2Fworkspace",
  );
  expect(screen.getByText("Sign in to your private workspace")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to public site" })).toHaveAttribute("href", "/");
});

it("shows a signed-in account and revokes it with a CSRF-protected sign-out", async () => {
  (fetch as jest.Mock)
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      user: { id: "synthetic-user", display_name: "Synthetic Developer" },
      csrf_token: "csrf-sentinel", expires_at: "2035-01-01T00:00:00Z", login_available: true,
    }) })
    .mockResolvedValueOnce({ ok: true, status: 204 });
  render(<IdentityPanel workspace />);
  expect(await screen.findByText("Signed in as Synthetic Developer")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByText("You have signed out.")).toBeInTheDocument();
  expect(fetch).toHaveBeenLastCalledWith("/api/v1/auth/logout", {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "X-CSRF-Token": "csrf-sentinel" },
  });
  expect(screen.queryByText("Signed in as Synthetic Developer")).not.toBeInTheDocument();
});

it("hides signed-in state when a focus refresh detects expiry", async () => {
  (fetch as jest.Mock)
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      user: { id: "synthetic-user", display_name: "Synthetic Developer" },
      csrf_token: "csrf-sentinel", expires_at: "2035-01-01T00:00:00Z", login_available: true,
    }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      user: null, csrf_token: null, expires_at: null, login_available: true,
    }) });
  render(<IdentityPanel workspace />);
  await screen.findByText("Signed in as Synthetic Developer");
  fireEvent.focus(window);
  expect(await screen.findByText("Your session ended. Sign in again to continue.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
});

it("shows configuration or network errors without offering a fake login", async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => ({
    user: null, csrf_token: null, expires_at: null, login_available: false,
  }) });
  const { unmount } = render(<IdentityPanel />);
  await screen.findByText("Sign-in is not configured yet.");
  expect(screen.queryByText("Continue with GitHub")).not.toBeInTheDocument();
  unmount();
  (fetch as jest.Mock).mockRejectedValue(new Error("secret provider response"));
  render(<IdentityPanel />);
  await screen.findByRole("alert");
  expect(screen.queryByText(/secret provider response/)).not.toBeInTheDocument();
});

it("does not claim a failed logout succeeded and offers a retry", async () => {
  (fetch as jest.Mock)
    .mockResolvedValueOnce({ ok: true, json: async () => ({
      user: { id: "synthetic-user", display_name: "Synthetic Developer" },
      csrf_token: "csrf-sentinel", expires_at: "2035-01-01T00:00:00Z", login_available: true,
    }) })
    .mockRejectedValueOnce(new Error("offline"));
  render(<IdentityPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  await screen.findByText("Sign-out could not be confirmed. Please retry.");
  expect(screen.queryByText("You have signed out.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeEnabled();
});

it("does not reflect an unsafe return URL or untrusted callback error", async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => ({
    user: null, csrf_token: null, expires_at: null, login_available: true,
  }) });
  render(<IdentityPanel returnPath="https://evil.example" loginError="secret-provider-detail" />);
  expect(await screen.findByRole("link", { name: "Continue with GitHub" })).toHaveAttribute(
    "href", "/api/v1/auth/github/start?return_path=%2Fworkspace",
  );
  expect(screen.queryByText("secret-provider-detail")).not.toBeInTheDocument();
});
