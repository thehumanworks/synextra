import { cn } from "@/lib/utils";

/**
 * Tailwind border utilities create a harsh, high-contrast look in a dark-first UI.
 * This helper strips them so components stay "borderless" and rely on subtle
 * shadows / rings / background layers.
 */
export function stripBorderUtilities(className: string): string {
  const tokens = className.split(/\s+/).filter(Boolean);
  const filtered = tokens.filter((token) => {
    if (token === "border") return false;
    if (token.startsWith("border-")) return false;
    if (token.startsWith("border/")) return false;
    if (token.startsWith("border_")) return false;
    if (token.startsWith("divide")) return false;
    return true;
  });
  return filtered.join(" ");
}

export const ds = {
  shell: stripBorderUtilities(
    cn(
      "min-h-screen",
      "bg-background text-foreground",
      "antialiased",
      "selection:bg-primary/25 selection:text-foreground"
    )
  ),
  container: cn("mx-auto w-full max-w-5xl px-4 py-10 md:py-14"),
  headerTitle: cn(
    "text-4xl md:text-5xl",
    "tracking-tight",
    "text-transparent bg-clip-text",
    "bg-gradient-to-r from-stone-100 via-stone-300 to-stone-500"
  ),
  headerSubtitle: cn("mt-3 max-w-2xl text-sm md:text-base text-muted-foreground"),
  emphasis: cn("font-serif italic text-stone-100"),

  panel: stripBorderUtilities(
    cn(
      "rounded-2xl",
      "bg-card/70",
      "backdrop-blur",
      "shadow-lg shadow-black/25",
      "ring-1 ring-white/10"
    )
  ),
  panelInner: cn("p-5 md:p-6"),

  chatList: cn("flex flex-col gap-4"),
  inputRow: cn("mt-6 flex flex-col gap-3"),

  smallLabel: "text-xs uppercase tracking-wider text-muted-foreground",
};
