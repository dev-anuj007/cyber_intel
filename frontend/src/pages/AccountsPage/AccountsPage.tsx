import React, { useState } from "react";
import { SearchBar, AccountList } from "../../components";
import { Account } from "../../types";
import "./AccountsPage.css";

export interface AccountsPageProps {
  onSelectAccount: (
    account: Account,
    initialTab?: "signals" | "perimeter" | "history" | "assets" | "ips" | "domains" | "tech"
  ) => void;
  tierFilter: string | null;
  onTierChange: (tier: string | null) => void;
}

export const AccountsPage: React.FC<AccountsPageProps> = ({
  onSelectAccount,
  tierFilter,
  onTierChange,
}) => {
  const [searchQuery, setSearchQuery] = useState("");

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    if (query.trim()) {
      onTierChange(null);
    }
  };

  return (
    <div className="accounts-page-container">
      <div className="accounts-page-search-wrapper">
        <SearchBar onSearch={handleSearch} />
      </div>
      <div className="accounts-page-list-wrapper">
        <AccountList
          searchQuery={searchQuery}
          tierFilter={tierFilter}
          onTierChange={onTierChange}
          onSelectAccount={onSelectAccount}
        />
      </div>
    </div>
  );
};

export default AccountsPage;
