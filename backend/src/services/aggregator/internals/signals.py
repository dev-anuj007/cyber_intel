from typing import List

from src.services.accounts.types import SecuritySignal, SignalSeverity


class SignalDetector:
    def detect_signals(self, features: dict) -> List[SecuritySignal]:
        signals = []

        if "eol-product" in (features.get("tags") or []):
            signals.append(
                SecuritySignal(
                    name="eol_product",
                    severity=SignalSeverity.HIGH,
                    category="technology_risk",
                    evidence="Product is tagged as end-of-life",
                )
            )

        kev_count = features.get("kev_count", 0)
        if kev_count > 0:
            signals.append(
                SecuritySignal(
                    name="kev_vulnerability",
                    severity=SignalSeverity.CRITICAL,
                    category="vulnerability",
                    evidence=f"{kev_count} vulnerability(s) listed in CISA KEV",
                )
            )

        max_cvss = features.get("max_cvss")
        if max_cvss is not None:
            if max_cvss >= 9.0:
                severity = SignalSeverity.CRITICAL
            elif max_cvss >= 7.0:
                severity = SignalSeverity.HIGH
            else:
                severity = None

            if severity:
                signals.append(
                    SecuritySignal(
                        name="high_severity_vulnerability",
                        severity=severity,
                        category="vulnerability",
                        evidence=f"Maximum CVSS score: {max_cvss}",
                    )
                )

        max_epss = features.get("max_epss")
        if max_epss is not None and max_epss >= 0.5:
            signals.append(
                SecuritySignal(
                    name="high_exploitation_probability",
                    severity=SignalSeverity.HIGH,
                    category="vulnerability",
                    evidence=f"Maximum EPSS score: {max_epss:.2f}",
                )
            )

        ransomware_count = features.get("ransomware_count", 0)
        if ransomware_count > 0:
            signals.append(
                SecuritySignal(
                    name="ransomware_associated_vulnerability",
                    severity=SignalSeverity.CRITICAL,
                    category="vulnerability",
                    evidence=f"{ransomware_count} vulnerability(s) associated with ransomware campaigns",
                )
            )

        vulnerability_count = features.get("vulnerability_count", 0)
        if vulnerability_count >= 5:
            signals.append(
                SecuritySignal(
                    name="multiple_vulnerabilities",
                    severity=SignalSeverity.MEDIUM,
                    category="vulnerability",
                    evidence=f"{vulnerability_count} vulnerabilities detected",
                )
            )

        port = features.get("port")
        if port is not None and port not in {80, 443}:
            signals.append(
                SecuritySignal(
                    name="non_standard_exposed_port",
                    severity=SignalSeverity.LOW,
                    category="attack_surface",
                    evidence=f"Exposed port: {port}",
                )
            )

        return signals
