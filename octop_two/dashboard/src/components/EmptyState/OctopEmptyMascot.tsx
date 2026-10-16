import { Bot } from "lucide-react";
import styles from "./EmptyState.module.less";

interface OctopEmptyMascotProps {
  className?: string;
  /** Square edge in px; default 160. */
  size?: number;
}

/**
 * Neutral empty-state mark (the Octop mascot was retired).
 * Soft gray rounded square with a quiet bot glyph — no mascot imagery.
 */
export function OctopEmptyMascot({
  className,
  size = 160,
}: OctopEmptyMascotProps) {
  return (
    <div
      className={className ? `${styles.mascot} ${className}` : styles.mascot}
      style={{
        width: size,
        height: size,
        borderRadius: Math.round(size * 0.16),
        background: "var(--fn-bg-tertiary, #f0f1f3)",
        border: "1px solid var(--fn-border-secondary, rgba(60, 60, 67, 0.1))",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
      aria-hidden
    >
      <Bot
        size={Math.round(size * 0.3)}
        strokeWidth={1.2}
        style={{ color: "var(--fn-text-quaternary, #bfbfbf)" }}
      />
    </div>
  );
}
