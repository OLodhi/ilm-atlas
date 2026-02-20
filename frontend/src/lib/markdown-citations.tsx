"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Citation } from "@/lib/types";
import {
  CHUNK_TYPE_BADGE_VARIANTS,
} from "@/lib/constants";

interface CitationLinkProps {
  citation: Citation;
  onClick: () => void;
}

export function CitationLink({ citation, onClick }: CitationLinkProps) {
  const badgeStyle =
    CHUNK_TYPE_BADGE_VARIANTS[citation.chunk_type] ??
    CHUNK_TYPE_BADGE_VARIANTS.paragraph;

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        "inline-flex items-center gap-1",
        "mx-0.5 align-baseline text-[10px] font-semibold leading-none",
        "whitespace-nowrap rounded-full border px-2 py-1",
        "shadow-sm cursor-pointer transition-all",
        "hover:shadow-md hover:brightness-95 active:scale-95",
        badgeStyle
      )}
    >
      <svg
        viewBox="0 0 16 16"
        fill="currentColor"
        className="h-2.5 w-2.5 shrink-0 opacity-60"
        aria-hidden="true"
      >
        <path d="M4.5 2A2.5 2.5 0 0 0 2 4.5v2A2.5 2.5 0 0 0 4.5 9h.75a.75.75 0 0 0 0-1.5H4.5a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v.75a.75.75 0 0 0 1.5 0V4.5A2.5 2.5 0 0 0 6.5 2h-2zm5 5A2.5 2.5 0 0 0 7 9.5v2A2.5 2.5 0 0 0 9.5 14h2a2.5 2.5 0 0 0 2.5-2.5v-2A2.5 2.5 0 0 0 11.5 7h-2zm-1 2.5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-2z" />
      </svg>
      {citation.source}
    </button>
  );
}

const CITATION_RE = /\[(\d+)\]/g;

/**
 * Scan a string for `[N]` patterns and return an array of ReactNodes where
 * valid citation references are replaced with `CitationLink` components
 * showing the source name.
 */
export function renderTextWithCitations(
  text: string,
  citations: Citation[],
  onClick: (index: number) => void
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  // Reset regex state (global regexes are stateful)
  CITATION_RE.lastIndex = 0;

  while ((match = CITATION_RE.exec(text)) !== null) {
    const num = parseInt(match[1], 10);

    // Push text before the match
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    if (num >= 1 && num <= citations.length) {
      nodes.push(
        <CitationLink
          key={`cit-${match.index}`}
          citation={citations[num - 1]}
          onClick={() => onClick(num)}
        />
      );
    } else {
      // Invalid reference — keep as plain text
      nodes.push(match[0]);
    }

    lastIndex = match.index + match[0].length;
  }

  // Push remaining text
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}
