import { Children, type ReactNode } from "react";

/** A row of cards: swipeable on phones (one card and a peek of the next), a grid from `sm` up. */
export function Lane({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <div role="list" aria-label={label}
         className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-px-4 px-4 pb-3 [scrollbar-width:none] sm:mx-0 sm:grid sm:snap-none sm:grid-cols-2 sm:gap-5 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-4 [&::-webkit-scrollbar]:hidden">
      {Children.map(children, (child) => (
        <div role="listitem" className="flex w-[80%] max-w-80 shrink-0 snap-start sm:w-auto sm:max-w-none [&>*]:w-full">{child}</div>
      ))}
    </div>
  );
}
