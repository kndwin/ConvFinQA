import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./utils";

const markerVariants = cva(
  "relative flex min-h-4 w-full items-center gap-2 text-left text-sm text-muted-foreground",
  {
    variants: {
      variant: {
        default: "",
        border: "border-b border-border pb-2",
        separator:
          "before:mr-1 before:h-px before:flex-1 before:bg-border after:ml-1 after:h-px after:flex-1 after:bg-border",
      },
    },
    defaultVariants: { variant: "default" },
  },
);
function Marker({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof markerVariants>) {
  return (
    <div
      data-slot="marker"
      data-variant={variant}
      className={cn(markerVariants({ variant, className }))}
      {...props}
    />
  );
}
function MarkerIcon({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden="true"
      data-slot="marker-icon"
      className={cn("size-4 shrink-0 [&>svg]:size-full", className)}
      {...props}
    />
  );
}
function MarkerContent({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span data-slot="marker-content" className={cn("min-w-0 break-words", className)} {...props} />
  );
}
export { Marker, MarkerIcon, MarkerContent, markerVariants };
