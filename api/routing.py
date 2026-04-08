"""Deterministic domain routing (Task 4.2). No LLM call.

Each query is matched against keyword sets for legal / commercial /
financial / technical. Multiple matches return multiple domains. No match
defaults to legal.

The matched list drives system-prompt selection in api/prompts.py.
"""

from __future__ import annotations

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "legal": [
        "contract", "clause", "fidic", "dispute", "dab", "daab", "termination",
        "breach", "notice", "engineer", "claim", "liability", "indemnity",
        "arbitration", "particular conditions", "time at large", "force majeure",
        "suspension", "taking-over", "defects notification",
    ],
    "commercial": [
        "eot", "extension of time", "delay", "prolongation", "disruption",
        "variation", "compensation event", "programme", "critical path",
        "concurrent delay", "float", "acceleration", "scl protocol",
        "baseline programme", "as-built programme",
    ],
    "financial": [
        "evm", "earned value", "cpi", "spi", "eac", "etc", "vac", "cost control",
        "budget", "forecast", "cash flow", "valuation", "payment certificate",
        "retention", "final account", "reconciliation", "cost to complete",
    ],
    "technical": [
        "ncr", "itp", "defect", "snag", "inspection", "test",
        "specification", "method statement", "rfi", "submittal",
        "decennial", "latent defect", "workmanship", "material approval",
    ],
}


def route_query(query: str) -> list[str]:
    query_lower = query.lower()
    matched = [
        domain
        for domain, keywords in DOMAIN_KEYWORDS.items()
        if any(kw in query_lower for kw in keywords)
    ]
    return matched if matched else ["legal"]
