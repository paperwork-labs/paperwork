import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

import { DropZone } from "../drop-zone";

function setFilesOnInput(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, "files", {
    value: files,
    configurable: true,
  });
  fireEvent.change(input);
}

describe("DropZone", () => {
  it("rejects files over maxBytes", async () => {
    const onUpload = vi.fn();
    const { container } = render(
      <DropZone accept={["text/plain"]} maxBytes={10} onUpload={onUpload} multiple />,
    );
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x".repeat(20)], "big.txt", { type: "text/plain" });
    setFilesOnInput(input, [file]);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("exceeds max size"));
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("rejects wrong mime type", async () => {
    const onUpload = vi.fn();
    const { container } = render(<DropZone accept={["image/png"]} maxBytes={10000} onUpload={onUpload} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["hi"], "x.txt", { type: "text/plain" });
    setFilesOnInput(input, [file]);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Unsupported type"));
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("calls onUpload for valid file", async () => {
    const onUpload = vi.fn(async () => {});
    const { container } = render(<DropZone accept={["text/plain"]} maxBytes={10000} onUpload={onUpload} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["hello"], "ok.txt", { type: "text/plain" });
    setFilesOnInput(input, [file]);
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith([file]));
  });

  it("shows custom children", () => {
    render(
      <DropZone accept={["*/*"]} maxBytes={1000} onUpload={async () => {}}>
        <div data-testid="inner">Custom UI</div>
      </DropZone>,
    );
    expect(screen.getByTestId("inner")).toHaveTextContent("Custom UI");
  });

  it("opens file picker on Enter key on drop zone", async () => {
    const user = userEvent.setup();
    const onUpload = vi.fn(async () => {});
    const { container } = render(<DropZone accept={["text/plain"]} maxBytes={100} onUpload={onUpload} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click").mockImplementation(() => {});
    const zone = screen.getByRole("button", { name: /Drag files here/i });
    zone.focus();
    await user.keyboard("{Enter}");
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("handles drop with valid files", async () => {
    const onUpload = vi.fn(async () => {});
    render(<DropZone accept={["text/plain"]} maxBytes={10000} onUpload={onUpload} />);
    const zone = screen.getByRole("button", { name: /Drag files here/i });
    const file = new File(["d"], "dropped.txt", { type: "text/plain" });
    const dt = new DataTransfer();
    dt.items.add(file);
    fireEvent.drop(zone, { dataTransfer: dt });
    await waitFor(() => expect(onUpload).toHaveBeenCalledWith([file]));
  });

  it("handles paste with image file", async () => {
    const onUpload = vi.fn(async () => {});
    render(<DropZone accept={["image/png"]} maxBytes={10000} onUpload={onUpload} />);
    const zone = screen.getByRole("button", { name: /Drag files here/i });
    const file = new File([new Uint8Array([1, 2, 3])], "p.png", { type: "image/png" });
    fireEvent.paste(zone, {
      clipboardData: { files: [file] } as unknown as DataTransfer,
    });
    await waitFor(() => expect(onUpload).toHaveBeenCalled());
  });

  it("surfaces onUpload rejection", async () => {
    const onUpload = vi.fn(async () => {
      throw new Error("upload denied");
    });
    const { container } = render(<DropZone accept={["text/plain"]} maxBytes={10000} onUpload={onUpload} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "ok.txt", { type: "text/plain" });
    setFilesOnInput(input, [file]);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("upload denied"));
  });
});
