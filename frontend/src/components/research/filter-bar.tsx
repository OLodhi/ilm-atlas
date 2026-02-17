"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MADHAB_OPTIONS, CATEGORY_OPTIONS } from "@/lib/constants";

interface FilterBarProps {
  madhab: string;
  onMadhabChange: (value: string) => void;
  category: string;
  onCategoryChange: (value: string) => void;
}

export function FilterBar({
  madhab,
  onMadhabChange,
  category,
  onCategoryChange,
}: FilterBarProps) {
  return (
    <div className="flex gap-3">
      <Select value={madhab} onValueChange={onMadhabChange}>
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Madhab" />
        </SelectTrigger>
        <SelectContent>
          {MADHAB_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={category} onValueChange={onCategoryChange}>
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Category" />
        </SelectTrigger>
        <SelectContent>
          {CATEGORY_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
