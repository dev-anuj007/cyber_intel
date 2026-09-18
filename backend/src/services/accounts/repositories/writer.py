"""Accounts Data Writer Repository."""

import sqlite3
from src.services.accounts.types import IAccountWriter, Account


class AccountWriter(IAccountWriter):

    def insert_account(self, conn: sqlite3.Connection, account: Account, priority_tier: str) -> int:
        """Insert account and all child entities (domains, assets, IPs, hostnames, ports, products, signals)."""
        cursor = conn.cursor()
        signal_count = len(account.signals)

        cursor.execute("SELECT id FROM accounts WHERE account_key = ?", (account.account_key,))
        row = cursor.fetchone()
        if row:
            account_id = row[0]
            cursor.execute(
                "UPDATE accounts SET signal_count = ?, priority_tier = ? WHERE id = ?",
                (signal_count, priority_tier, account_id),
            )
        else:
            cursor.execute(
                "INSERT INTO accounts (account_key, signal_count, priority_tier) VALUES (?, ?, ?)",
                (account.account_key, signal_count, priority_tier),
            )
            account_id = cursor.lastrowid

        self.clear_account_entities_by_id(conn, account_id)

        if account.domains:
            domains_data = [(account_id, d) for d in dict.fromkeys(account.domains)]
            cursor.executemany("INSERT INTO domains (account_id, domain) VALUES (?, ?)", domains_data)

        if account.assets:
            seen_assets = set()
            assets_data = []
            for a in account.assets:
                tup = (a.ip, a.port, a.hostname)
                if tup not in seen_assets:
                    seen_assets.add(tup)
                    assets_data.append((account_id, a.ip, a.port, a.hostname))
            if assets_data:
                cursor.executemany("INSERT INTO assets (account_id, ip, port, hostname) VALUES (?, ?, ?, ?)", assets_data)

        if account.ips:
            ips_data = [(account_id, ip) for ip in dict.fromkeys(account.ips)]
            cursor.executemany("INSERT INTO ips (account_id, ip) VALUES (?, ?)", ips_data)

        if account.hostnames:
            hostnames_data = [(account_id, h) for h in dict.fromkeys(account.hostnames)]
            cursor.executemany("INSERT INTO hostnames (account_id, hostname) VALUES (?, ?)", hostnames_data)

        if account.ports:
            ports_data = [(account_id, p) for p in sorted(set(account.ports))]
            cursor.executemany("INSERT INTO ports (account_id, port) VALUES (?, ?)", ports_data)

        if account.products:
            products_data = [(account_id, prod) for prod in dict.fromkeys(account.products)]
            cursor.executemany("INSERT INTO products (account_id, product) VALUES (?, ?)", products_data)

        if account.cloud_providers:
            providers_data = [(account_id, prov) for prov in dict.fromkeys(account.cloud_providers)]
            cursor.executemany("INSERT INTO cloud_providers (account_id, provider) VALUES (?, ?)", providers_data)

        if account.signals:
            seen_signals = set()
            signals_data = []
            for s in account.signals:
                s_sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
                tup = (s.name, s_sev, getattr(s, "category", ""), s.evidence)
                if tup not in seen_signals:
                    seen_signals.add(tup)
                    signals_data.append((account_id, s.name, s_sev, getattr(s, "category", ""), s.evidence))
            if signals_data:
                cursor.executemany(
                    "INSERT INTO signals (account_id, name, severity, category, evidence) VALUES (?, ?, ?, ?, ?)",
                    signals_data,
                )

        return account_id

    def clear_account_entities_by_id(self, conn: sqlite3.Connection, account_id: int) -> None:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM signals WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM cloud_providers WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM products WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM ports WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM hostnames WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM ips WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM assets WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM domains WHERE account_id = ?", (account_id,))

    def clear_accounts(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM signals")
        cursor.execute("DELETE FROM cloud_providers")
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM ports")
        cursor.execute("DELETE FROM hostnames")
        cursor.execute("DELETE FROM ips")
        cursor.execute("DELETE FROM assets")
        cursor.execute("DELETE FROM domains")
        cursor.execute("DELETE FROM accounts")
