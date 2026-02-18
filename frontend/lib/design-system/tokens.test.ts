import { describe, expect, it } from "vitest";

import { ds, stripBorderUtilities } from "./tokens";


describe("design-system tokens", () => {
  it("stripBorderUtilities removes border classes", () => {
    const result = stripBorderUtilities("p-2 border border-stone-800 divide-y");
    expect(result).not.toMatch(/\bborder/);
    expect(result).not.toMatch(/\bdivide/);
  });

  it("shell token is dark-first and excludes border utilities", () => {
    expect(ds.shell).toContain("bg-background");
    expect(ds.shell).not.toMatch(/\bborder/);
  });
});
