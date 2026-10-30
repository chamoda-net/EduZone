import type { ComponentProps, ReactNode } from "react";

import { cx } from "./cx";

export const inputClass =
  "min-h-11 w-full rounded-ez border border-border-strong bg-surface px-3.5 text-[0.9375rem] text-foreground " +
  "shadow-[inset_0_1px_2px_rgb(20_32_26/0.04)] outline-none transition-[border-color,box-shadow] duration-200 " +
  "placeholder:text-subtle hover:border-foreground/30 focus:border-brand focus:ring-4 focus:ring-brand/12 " +
  "aria-invalid:border-danger disabled:bg-sunken disabled:text-muted";

/** A labelled control. The label holds only the label text (hints and errors sit below it), so
 * screen readers announce a clean name. Controls with their own buttons inside (PasswordInput)
 * pass `htmlFor` with the input's id instead of being wrapped. */
export function Field({
  label,
  hint,
  error,
  optional,
  children,
  className,
  htmlFor,
}: {
  label: string;
  hint?: string;
  error?: string;
  optional?: string;
  children: ReactNode;
  className?: string;
  htmlFor?: string;
}) {
  const text = (
    <>
      {label}
      {optional && <span className="text-xs font-normal text-subtle">{optional}</span>}
    </>
  );
  const labelClass = "flex items-baseline justify-between gap-2 text-sm font-semibold text-foreground";
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      {htmlFor ? (
        <>
          <label htmlFor={htmlFor} className={labelClass}>{text}</label>
          {children}
        </>
      ) : (
        <label className="flex flex-col gap-1.5">
          <span className={labelClass}>{text}</span>
          {children}
        </label>
      )}
      {error ? (
        <span role="alert" className="text-xs font-medium text-danger">
          {error}
        </span>
      ) : (
        hint && <span className="text-xs leading-relaxed text-muted">{hint}</span>
      )}
    </div>
  );
}

export function Input(props: ComponentProps<"input">) {
  return <input {...props} className={cx(inputClass, props.className)} />;
}

export function Textarea(props: ComponentProps<"textarea">) {
  return <textarea rows={4} {...props} className={cx(inputClass, "py-2.5 leading-relaxed", props.className)} />;
}

const chevron =
  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' " +
  "stroke='%235c6862' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='m6 9 6 6 6-6'/></svg>\")";

export function Select(props: ComponentProps<"select">) {
  return (
    <select
      {...props}
      style={{ backgroundImage: chevron, backgroundSize: 16, backgroundPosition: "right 0.75rem center", backgroundRepeat: "no-repeat", ...props.style }}
      className={cx(inputClass, "appearance-none pr-10", props.className)}
    />
  );
}

export function Checkbox({ label, ...props }: ComponentProps<"input"> & { label: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 text-sm">
      <input type="checkbox" {...props} className={cx("mt-0.5 size-4.5 shrink-0 accent-brand", props.className)} />
      <span>{label}</span>
    </label>
  );
}
