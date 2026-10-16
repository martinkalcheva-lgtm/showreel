import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import styles from "./StreamConnectingIndicator.module.less";

interface StreamConnectingIndicatorProps {
  /** Status line under the animation (e.g. 「连接中」). */
  label: ReactNode;
  /** Optional secondary hint. */
  hint?: ReactNode;
  /** Light page chrome vs dark stream surfaces (phone / browser viewport). */
  tone?: "default" | "onDark";
  /** Compact for phone bezel / dock panels. */
  size?: "md" | "sm";
}

/**
 * Shared connecting / waiting-frame indicator for remote browser & desktop.
 * Quiet spinning glyph instead of the retired mascot loop.
 */
export default function StreamConnectingIndicator({
  label,
  hint,
  tone = "default",
  size = "md",
}: StreamConnectingIndicatorProps) {
  const rootClass = [
    styles.root,
    tone === "onDark" ? styles.onDark : "",
    size === "sm" ? styles.sizeSm : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rootClass}>
      <LoaderCircle
        className={styles.spinner}
        size={size === "sm" ? 24 : 36}
        strokeWidth={1.5}
        aria-hidden
      />
      <div className={styles.label}>{label}</div>
      {hint ? <div className={styles.hint}>{hint}</div> : null}
    </div>
  );
}
