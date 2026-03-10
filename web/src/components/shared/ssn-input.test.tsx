import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { SSNInput } from "./ssn-input";

describe("SSNInput", () => {
  it("renders with placeholder", () => {
    render(<SSNInput value="" onChange={() => {}} />);
    expect(screen.getByPlaceholderText("XXX-XX-XXXX")).toBeInTheDocument();
  });

  it("starts in password mode (hidden)", () => {
    render(<SSNInput value="123-45-6789" onChange={() => {}} />);
    const input = screen.getByPlaceholderText("XXX-XX-XXXX");
    expect(input).toHaveAttribute("type", "password");
  });

  it("toggles visibility on button click", async () => {
    const user = userEvent.setup();
    render(<SSNInput value="123-45-6789" onChange={() => {}} />);

    const toggle = screen.getByLabelText("Show SSN");
    await user.click(toggle);

    const input = screen.getByPlaceholderText("XXX-XX-XXXX");
    expect(input).toHaveAttribute("type", "text");

    const hideToggle = screen.getByLabelText("Hide SSN");
    await user.click(hideToggle);
    expect(input).toHaveAttribute("type", "password");
  });

  it("formats input with dashes via onChange", () => {
    const onChange = vi.fn();
    render(<SSNInput value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText("XXX-XX-XXXX");

    fireEvent.change(input, { target: { value: "123456789" } });

    expect(onChange).toHaveBeenCalledWith("123-45-6789");
  });

  it("strips non-digit characters", () => {
    const onChange = vi.fn();
    render(<SSNInput value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText("XXX-XX-XXXX");

    fireEvent.change(input, { target: { value: "12-34abc567" } });

    expect(onChange).toHaveBeenCalledWith("123-45-67");
  });

  it("limits to 9 digits", () => {
    const onChange = vi.fn();
    render(<SSNInput value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText("XXX-XX-XXXX");

    fireEvent.change(input, { target: { value: "1234567890000" } });

    expect(onChange).toHaveBeenCalledWith("123-45-6789");
  });

  it("formats partial SSN (3 digits)", () => {
    const onChange = vi.fn();
    render(<SSNInput value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText("XXX-XX-XXXX");

    fireEvent.change(input, { target: { value: "123" } });

    expect(onChange).toHaveBeenCalledWith("123");
  });

  it("formats partial SSN (5 digits)", () => {
    const onChange = vi.fn();
    render(<SSNInput value="" onChange={onChange} />);
    const input = screen.getByPlaceholderText("XXX-XX-XXXX");

    fireEvent.change(input, { target: { value: "12345" } });

    expect(onChange).toHaveBeenCalledWith("123-45");
  });

  it("disables input when disabled prop is set", () => {
    render(<SSNInput value="" onChange={() => {}} disabled />);
    expect(screen.getByPlaceholderText("XXX-XX-XXXX")).toBeDisabled();
  });

  it("has correct aria attributes on toggle", () => {
    render(<SSNInput value="" onChange={() => {}} />);
    const toggle = screen.getByLabelText("Show SSN");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  it("displays the actual value (not masked) in the input", () => {
    render(<SSNInput value="123-45-6789" onChange={() => {}} />);
    const input = screen.getByPlaceholderText("XXX-XX-XXXX") as HTMLInputElement;
    expect(input.value).toBe("123-45-6789");
  });
});
