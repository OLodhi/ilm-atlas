"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CitationCard } from "./citation-card";
import type { Citation } from "@/lib/types";

interface CitationLightboxProps {
  citation: Citation | null;
  index: number; // 1-based source number
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CitationLightbox({
  citation,
  index,
  open,
  onOpenChange,
}: CitationLightboxProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto p-0">
        <DialogHeader className="sr-only">
          <DialogTitle>Source {index}</DialogTitle>
        </DialogHeader>
        {citation && (
          <div className="p-4">
            <CitationCard citation={citation} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
