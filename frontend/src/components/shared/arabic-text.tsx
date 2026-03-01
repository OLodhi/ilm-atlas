import { cn } from "@/lib/utils";

interface ArabicTextProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: "default" | "quran";
  className?: string;
}

export function ArabicText({
  children,
  variant = "default",
  className,
  ...rest
}: ArabicTextProps) {
  return (
    <div
      dir="rtl"
      lang="ar"
      className={cn(
        "font-amiri",
        variant === "quran"
          ? "text-2xl leading-[2.25]"
          : "text-xl leading-loose",
        className
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
