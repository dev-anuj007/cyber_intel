import React from "react";
import "./Badge.css";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "critical" | "high" | "medium" | "low" | "info" | "success" | "neutral";
  size?: "sm" | "md";
  dot?: boolean;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = "neutral",
  size = "md",
  dot = false,
  children,
  className = "",
  ...props
}) => {
  return (
    <span className={`ui-badge ui-badge-${variant} ui-badge-${size} ${className}`} {...props}>
      {dot && <span className="ui-badge-dot" aria-hidden="true" />}
      <span className="ui-badge-text">{children}</span>
    </span>
  );
};

export default Badge;
