// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: ui.test.tsx.
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "danger";
type Size = "md" | "sm";

const base =
  "inline-block cursor-pointer font-semibold transition-[transform,background-color] duration-150 ease-out " +
  "active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt " +
  "disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100";

const variants: Record<Variant, string> = {
  primary: "bg-cobalt text-on-accent hover:bg-cobalt-d",
  ghost: "bg-transparent text-ink ring-1 ring-inset ring-rule hover:bg-surface",
  danger: "bg-transparent text-bad ring-1 ring-inset ring-bad hover:bg-surface",
};

const sizes: Record<Size, string> = {
  md: "rounded-[10px] px-4 py-2.5",
  sm: "rounded-lg px-3 py-1.5 text-[13px]",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size };

export function Button({
  variant = "primary",
  size = "md",
  type = "button",
  className = "",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...rest}
    />
  );
}
