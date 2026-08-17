"use client";
import * as React from "react";
import { ArrowDown } from "lucide-react";
import {
  MessageScroller as Primitive,
  useMessageScroller,
  useMessageScrollerScrollable,
  useMessageScrollerVisibility,
} from "@shadcn/react/message-scroller";
import { Button } from "./button";
import { cn } from "./utils";

const MessageScrollerProvider = (props: React.ComponentProps<typeof Primitive.Provider>) => (
  <Primitive.Provider {...props} />
);
const MessageScroller = ({ className, ...props }: React.ComponentProps<typeof Primitive.Root>) => (
  <Primitive.Root
    data-slot="message-scroller"
    className={cn("group relative flex size-full min-h-0 flex-col overflow-hidden", className)}
    {...props}
  />
);
const MessageScrollerViewport = ({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Viewport>) => (
  <Primitive.Viewport
    data-slot="message-scroller-viewport"
    className={cn("size-full min-h-0 min-w-0 overflow-y-auto overscroll-contain", className)}
    {...props}
  />
);
const MessageScrollerContent = ({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Content>) => (
  <Primitive.Content className={cn("flex h-max min-h-full flex-col gap-4", className)} {...props} />
);
const MessageScrollerItem = ({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Item>) => (
  <Primitive.Item className={cn("min-w-0 shrink-0", className)} {...props} />
);
function MessageScrollerButton({
  className,
  direction = "end",
  ...props
}: React.ComponentProps<typeof Primitive.Button>) {
  return (
    <Primitive.Button
      direction={direction}
      className={cn(
        "absolute bottom-3 right-3 rounded-full border bg-background shadow-sm data-[active=false]:pointer-events-none data-[active=false]:opacity-0",
        className,
      )}
      render={<Button size="icon" variant="outline" />}
      {...props}
    >
      <ArrowDown className={direction === "start" ? "rotate-180" : undefined} />
      <span className="sr-only">{direction === "end" ? "Jump to latest" : "Scroll to start"}</span>
    </Primitive.Button>
  );
}
export {
  MessageScrollerProvider,
  MessageScroller,
  MessageScrollerViewport,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerButton,
  useMessageScroller,
  useMessageScrollerScrollable,
  useMessageScrollerVisibility,
};
