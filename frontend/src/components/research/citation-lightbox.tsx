"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { CitationCard } from "./citation-card";
import type { Citation } from "@/lib/types";

interface CitationLightboxProps {
  citation: Citation | null;
  index: number; // 1-based source number
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Non-modal dialog for viewing citation details. Uses modal={false} to avoid
 * react-remove-scroll which resets the chat thread's scroll position.
 * Renders a custom overlay since Radix omits it for non-modal dialogs.
 */
export function CitationLightbox({
  citation,
  index,
  open,
  onOpenChange,
}: CitationLightboxProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange} modal={false}>
      <DialogPrimitive.Portal>
        {/* Custom overlay — Radix skips its own overlay when modal={false} */}
        <div
          className="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
          data-state={open ? "open" : "closed"}
          onClick={() => onOpenChange(false)}
          aria-hidden
        />
        <DialogPrimitive.Content
          className="fixed left-[50%] top-[50%] z-50 grid w-full max-w-xl translate-x-[-50%] translate-y-[-50%] border bg-background shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg max-h-[85vh] overflow-y-auto p-0"
          onOpenAutoFocus={(e) => e.preventDefault()}
          onCloseAutoFocus={(e) => e.preventDefault()}
        >
          <DialogPrimitive.Title className="sr-only">
            Source {index}
          </DialogPrimitive.Title>
          {citation && (
            <div className="p-4">
              <CitationCard citation={citation} />
            </div>
          )}
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
