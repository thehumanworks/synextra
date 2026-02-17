import { memo } from "react";
import { cjk } from "@streamdown/cjk";
import { code } from "@streamdown/code";
import { math } from "@streamdown/math";
import { Streamdown, type StreamdownProps } from "streamdown";

import { cn } from "@/lib/utils";

const streamdownPlugins = { cjk, code, math };

export type MarkdownResponseProps = Omit<StreamdownProps, "plugins">;

export const MarkdownResponse = memo(
  ({ className, ...props }: MarkdownResponseProps) => (
    <Streamdown
      className={cn(
        "size-full [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 text-sm leading-relaxed",
        className
      )}
      plugins={streamdownPlugins}
      {...props}
    />
  ),
  (prevProps, nextProps) =>
    prevProps.children === nextProps.children &&
    prevProps.className === nextProps.className &&
    prevProps.isAnimating === nextProps.isAnimating
);

MarkdownResponse.displayName = "MarkdownResponse";
