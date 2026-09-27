from typing import Any, Tuple


class AccountVersionCalculator:
    @staticmethod
    def calculate_next_version(accounts_service: Any, domain: str) -> Tuple[str, str]:
        base_key = f"domain:{domain}"
        existing_v1 = accounts_service.get_account(base_key) or accounts_service.get_account(domain)
        if not existing_v1:
            return base_key, "v1"

        v_num = 2
        while True:
            candidate_key = f"{base_key}:v{v_num}"
            if accounts_service.get_account(candidate_key):
                v_num += 1
            else:
                return candidate_key, f"v{v_num}"
