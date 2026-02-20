"use client";

import { useState, useCallback, useLayoutEffect, useRef, type ReactNode } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";
import { renderTextWithCitations } from "@/lib/markdown-citations";
import { CitationLightbox } from "@/components/research/citation-lightbox";
import type { Citation } from "@/lib/types";

interface CitationMarkdownProps {
  content: string;
  citations: Citation[];
}

/**
 * Wraps react-markdown with custom component overrides that inject clickable
 * citation badges for `[N]` references. Manages lightbox state internally.
 */
export function CitationMarkdown({ content, citations }: CitationMarkdownProps) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const savedScrollRef = useRef(0);
  const needsRestoreRef = useRef(false);

  const saveScrollPos = useCallback(() => {
    const el = document.querySelector("[data-chat-scroll]") as HTMLElement | null;
    if (el) savedScrollRef.current = el.scrollTop;
    needsRestoreRef.current = true;
  }, []);

  // Restore scroll position synchronously after DOM update (before paint)
  useLayoutEffect(() => {
    if (needsRestoreRef.current) {
      needsRestoreRef.current = false;
      const el = document.querySelector("[data-chat-scroll]") as HTMLElement | null;
      if (el) el.scrollTop = savedScrollRef.current;
    }
  });

  const handleCitationClick = useCallback(
    (index: number) => {
      saveScrollPos();
      setLightboxIndex(index);
    },
    [saveScrollPos]
  );

  /**
   * Process children of a markdown element, replacing `[N]` text nodes
   * with CitationLink components showing the source name.
   */
  function processChildren(children: ReactNode): ReactNode {
    if (typeof children === "string") {
      const nodes = renderTextWithCitations(children, citations, handleCitationClick);
      return nodes.length === 1 ? nodes[0] : <>{nodes}</>;
    }
    if (Array.isArray(children)) {
      return children.map((child, i) => {
        if (typeof child === "string") {
          const nodes = renderTextWithCitations(child, citations, handleCitationClick);
          return <span key={i}>{nodes}</span>;
        }
        return child;
      });
    }
    return children;
  }

  const components: Components = {
    p: ({ children }) => <p>{processChildren(children)}</p>,
    li: ({ children }) => <li>{processChildren(children)}</li>,
    strong: ({ children }) => <strong>{processChildren(children)}</strong>,
    em: ({ children }) => <em>{processChildren(children)}</em>,
    blockquote: ({ children }) => <blockquote>{processChildren(children)}</blockquote>,
    h2: ({ children }) => <h2>{processChildren(children)}</h2>,
    h3: ({ children }) => <h3>{processChildren(children)}</h3>,
  };

  const activeCitation =
    lightboxIndex !== null && lightboxIndex >= 1 && lightboxIndex <= citations.length
      ? citations[lightboxIndex - 1]
      : null;

  return (
    <>
      <Markdown remarkPlugins={[remarkBreaks]} components={components}>
        {content}
      </Markdown>
      <CitationLightbox
        citation={activeCitation}
        index={lightboxIndex ?? 0}
        open={lightboxIndex !== null}
        onOpenChange={(open) => {
          if (!open) {
            saveScrollPos();
            setLightboxIndex(null);
          }
        }}
      />
    </>
  );
}
