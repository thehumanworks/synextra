import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders children content", () => {
    render(<Button>Run</Button>);

    expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
  });

  it("applies variant and size styles", () => {
    render(
      <Button variant="outline" size="sm">
        Small
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Small" });
    expect(button.className).toContain("border");
    expect(button.className).toContain("h-9");
  });

  it("supports disabled state", () => {
    render(<Button disabled>Disabled</Button>);

    expect(screen.getByRole("button", { name: "Disabled" })).toBeDisabled();
  });
});
