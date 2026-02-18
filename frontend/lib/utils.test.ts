import { describe, expect, it } from "vitest";

import { cn } from "@/lib/utils";

describe("cn", () => {
  it("combines classes in order", () => {
    expect(cn("alpha", "beta")).toBe("alpha beta");
  });

  it("merges conflicting Tailwind utility classes", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });

  it("handles empty and falsey values", () => {
    expect(cn(undefined, null, false, "", "py-2")).toBe("py-2");
  });
});
