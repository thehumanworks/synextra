/**
 * Normalize LaTeX delimiters from `\[...\]` / `\(...\)` to `$$...$$` / `$...$`
 * so that remark-math (which only recognizes dollar-sign delimiters) can parse them.
 *
 * LLMs commonly output both delimiter styles; this ensures consistent rendering
 * regardless of which style the model chose.
 */
export function normalizeLatexDelimiters(text: string): string {
  return text
    .replaceAll(/\\\[([\s\S]*?)\\\]/g, (_, content: string) => `$$${content}$$`)
    .replaceAll(/\\\((.*?)\\\)/g, (_, content: string) => `$${content}$`);
}
