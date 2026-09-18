import React, { useState } from "react";
import "./SearchBar.css";

export interface SearchBarProps {
  onSearch: (query: string) => void;
  placeholder?: string;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  onSearch,
  placeholder = "Search 50k+ accounts by domain, hostname, or IP (e.g. techsoup.org)..."
}) => {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(query.trim());
  };

  const handleClear = () => {
    setQuery("");
    onSearch("");
  };

  // Allow pressing Escape to clear search
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && query) {
      handleClear();
    }
  };

  return (
    <form className="search-bar-container" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <span className="search-icon-adornment">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </span>
        <input
          type="text"
          className="search-main-input"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        {query && (
          <button
            type="button"
            className="search-clear-btn"
            onClick={handleClear}
            title="Clear search (Esc)"
          >
            ✕
          </button>
        )}
      </div>
      <button type="submit" className="search-submit-btn">
        <span>Search</span>
      </button>
    </form>
  );
};

export default SearchBar;
