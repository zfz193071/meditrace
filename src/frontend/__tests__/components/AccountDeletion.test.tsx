import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AccountDeletion from "../../components/referral/AccountDeletion";
import { deleteAccount } from "../../lib/referral-api";

jest.mock("../../lib/referral-api", () => ({ deleteAccount: jest.fn() }));
const remove = jest.mocked(deleteAccount);

beforeEach(() => jest.resetAllMocks());

test("requires typed confirmation and reports accepted cleanup without claiming physical completion", async () => {
  remove.mockResolvedValue();
  const onDeleted = jest.fn();
  render(<AccountDeletion csrf="synthetic-csrf" onDeleted={onDeleted} />);
  const button = screen.getByRole("button", { name: "Delete account and all packets" });
  expect(button).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Type DELETE/), { target: { value: "DELETE" } });
  fireEvent.click(button);
  await waitFor(() => expect(onDeleted).toHaveBeenCalledTimes(1));
  expect(remove).toHaveBeenCalledWith("synthetic-csrf");
  expect(screen.getByText(/7 days after creation/)).toBeInTheDocument();
});

test("uncertain deletion preserves confirmation and asks for session refresh", async () => {
  remove.mockRejectedValue(new Error("private provider sentinel"));
  const onDeleted = jest.fn();
  render(<AccountDeletion csrf="synthetic-csrf" onDeleted={onDeleted} />);
  fireEvent.change(screen.getByLabelText(/Type DELETE/), { target: { value: "DELETE" } });
  fireEvent.click(screen.getByRole("button", { name: "Delete account and all packets" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Deletion could not be confirmed");
  expect(onDeleted).not.toHaveBeenCalled();
  expect(screen.queryByText("private provider sentinel")).not.toBeInTheDocument();
});
