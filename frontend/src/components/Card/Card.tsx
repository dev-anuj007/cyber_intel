import React from "react";
import "./Card.css";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "glass" | "solid" | "bordered" | "gradient";
  padding?: "none" | "sm" | "md" | "lg";
  children: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  variant = "glass",
  padding = "md",
  children,
  className = "",
  ...props
}) => {
  return (
    <div className={`ui-card ui-card-${variant} ui-card-pad-${padding} ${className}`} {...props}>
      {children}
    </div>
  );
};

export interface CardHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  children?: React.ReactNode;
}

export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  subtitle,
  action,
  children,
  className = "",
  ...props
}) => {
  return (
    <div className={`ui-card-header ${className}`} {...props}>
      {title || subtitle ? (
        <div className="ui-card-header-text">
          {title && <h3 className="ui-card-title">{title}</h3>}
          {subtitle && <p className="ui-card-subtitle">{subtitle}</p>}
        </div>
      ) : null}
      {action && <div className="ui-card-header-action">{action}</div>}
      {children}
    </div>
  );
};

export default Card;
