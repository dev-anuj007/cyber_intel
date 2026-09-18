import React from "react";
import "./Input.css";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  icon?: React.ReactNode;
  rightElement?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  hint,
  icon,
  rightElement,
  className = "",
  id,
  ...props
}) => {
  const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, "-")}` : undefined);

  return (
    <div className={`ui-input-group ${error ? "has-error" : ""} ${className}`}>
      {label && (
        <label htmlFor={inputId} className="ui-input-label">
          {label}
        </label>
      )}
      <div className="ui-input-wrapper">
        {icon && <span className="ui-input-prefix-icon">{icon}</span>}
        <input id={inputId} className={`ui-input ${icon ? "with-icon" : ""}`} {...props} />
        {rightElement && <div className="ui-input-right-element">{rightElement}</div>}
      </div>
      {error && <p className="ui-input-error-msg">{error}</p>}
      {hint && !error && <p className="ui-input-hint-msg">{hint}</p>}
    </div>
  );
};

export default Input;
