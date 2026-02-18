import { describe, expect, it } from "vitest";
import { normalizeLatexDelimiters } from "./latex-delimiters";

describe("normalizeLatexDelimiters", () => {
  it("converts display math \\[...\\] to $$...$$", () => {
    const input = "Before \\[x^2 + y^2 = z^2\\] after";
    expect(normalizeLatexDelimiters(input)).toBe(
      "Before $$x^2 + y^2 = z^2$$ after",
    );
  });

  it("converts inline math \\(...\\) to $...$", () => {
    const input = "The value \\(E = mc^2\\) is famous.";
    expect(normalizeLatexDelimiters(input)).toBe(
      "The value $E = mc^2$ is famous.",
    );
  });

  it("handles multiline display math", () => {
    const input = "Equation:\n\\[\nL = \\frac{1}{2} \\rho v^2 S C_L\n\\]\nEnd.";
    expect(normalizeLatexDelimiters(input)).toBe(
      "Equation:\n$$\nL = \\frac{1}{2} \\rho v^2 S C_L\n$$\nEnd.",
    );
  });

  it("handles multiple display blocks", () => {
    const input = "\\[a + b\\] and \\[c + d\\]";
    expect(normalizeLatexDelimiters(input)).toBe("$$a + b$$ and $$c + d$$");
  });

  it("handles multiple inline expressions", () => {
    const input = "\\(x\\) plus \\(y\\) equals \\(z\\)";
    expect(normalizeLatexDelimiters(input)).toBe("$x$ plus $y$ equals $z$");
  });

  it("handles mixed display and inline math", () => {
    const input =
      "Inline \\(a\\) and display:\n\\[\nb = c\n\\]\nMore inline \\(d\\).";
    expect(normalizeLatexDelimiters(input)).toBe(
      "Inline $a$ and display:\n$$\nb = c\n$$\nMore inline $d$.",
    );
  });

  it("returns text unchanged when there are no LaTeX delimiters", () => {
    const input = "Just plain text with [brackets] and (parens).";
    expect(normalizeLatexDelimiters(input)).toBe(input);
  });

  it("does not touch already dollar-delimited math", () => {
    const input = "Already $inline$ and $$display$$ math.";
    expect(normalizeLatexDelimiters(input)).toBe(input);
  });

  it("handles empty math expressions", () => {
    expect(normalizeLatexDelimiters("\\(\\)")).toBe("$$");
    expect(normalizeLatexDelimiters("\\[\\]")).toBe("$$$$");
  });

  it("handles display math with nested LaTeX commands", () => {
    const input =
      "\\[\\mathrm{MultiHead}(Q,K,V)=\\mathrm{Concat}(\\mathrm{head}_1,\\ldots,\\mathrm{head}_h)W^O\\]";
    expect(normalizeLatexDelimiters(input)).toBe(
      "$$\\mathrm{MultiHead}(Q,K,V)=\\mathrm{Concat}(\\mathrm{head}_1,\\ldots,\\mathrm{head}_h)W^O$$",
    );
  });

  it("handles inline math with subscripts and superscripts", () => {
    const input = "where \\(d_k = d_v = d_{model}/h = 64\\)";
    expect(normalizeLatexDelimiters(input)).toBe(
      "where $d_k = d_v = d_{model}/h = 64$",
    );
  });
});
