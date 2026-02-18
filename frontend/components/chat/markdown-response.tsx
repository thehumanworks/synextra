import { memo, useMemo, type ComponentPropsWithoutRef } from "react";
import { cjk } from "@streamdown/cjk";
import { code } from "@streamdown/code";
import { math } from "@streamdown/math";
import { Streamdown, type StreamdownProps } from "streamdown";

import { parseCitationReferenceHref } from "@/lib/chat/citation-reference-links";
import { cn } from "@/lib/utils";

const streamdownPlugins = { cjk, code, math };

export type MarkdownResponseProps = Omit<StreamdownProps, "plugins"> & {
  citationReferenceScopeId?: string;
  onCitationReferenceClick?: (index: number) => void;
};

export const MarkdownResponse = memo(
  ({
    className,
    citationReferenceScopeId,
    onCitationReferenceClick,
    components,
    ...props
  }: MarkdownResponseProps) => {
    const mergedComponents = useMemo(() => {
      if (!citationReferenceScopeId || !onCitationReferenceClick) return components;

      return {
        ...components,
        a: ({
          href,
          children,
          className: linkClassName,
          ...linkProps
        }: ComponentPropsWithoutRef<"a">) => {
          const index = parseCitationReferenceHref(href, citationReferenceScopeId);
          if (index != null) {
            return (
              <button
                type="button"
                className={cn("appearance-none text-left", linkClassName)}
                onClick={() => onCitationReferenceClick(index)}
              >
                {children}
              </button>
            );
          }

          return (
            <a
              {...linkProps}
              className={linkClassName}
              href={href}
              rel="noreferrer"
              target="_blank"
            >
              {children}
            </a>
          );
        },
      };
    }, [citationReferenceScopeId, components, onCitationReferenceClick]);

    return (
      <Streamdown
        className={cn(
          "size-full [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 text-sm leading-relaxed",
          className
        )}
        components={mergedComponents}
        plugins={streamdownPlugins}
        {...props}
      />
    );
  },
  (prevProps, nextProps) =>
    prevProps.children === nextProps.children &&
    prevProps.className === nextProps.className &&
    prevProps.isAnimating === nextProps.isAnimating &&
    prevProps.citationReferenceScopeId === nextProps.citationReferenceScopeId &&
    prevProps.onCitationReferenceClick === nextProps.onCitationReferenceClick
);

MarkdownResponse.displayName = "MarkdownResponse";
