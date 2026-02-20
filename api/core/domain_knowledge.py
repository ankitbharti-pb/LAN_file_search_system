"""Centralised insurance-domain constants.

Merges the acronym, synonym and normalisation dictionaries that were
previously scattered across ``search/query_preprocessor.py`` and
``indexing/keyword_index.py``.
"""

from typing import List

# ---------------------------------------------------------------------------
# Insurance acronyms  (merged superset from both modules)
# ---------------------------------------------------------------------------
INSURANCE_ACRONYMS: dict[str, str] = {
    # Certificate and documentation
    "coi": "certificate of insurance",
    "acord": "association for cooperative operations research and development",
    # Liability types
    "gl": "general liability",
    "cgl": "commercial general liability",
    "pl": "professional liability",
    "pol": "professional liability",
    "el": "employers liability",
    # Workers compensation
    "wc": "workers compensation",
    "wci": "workers compensation insurance",
    # Directors and officers
    "d&o": "directors and officers",
    "dno": "directors and officers",
    "do": "directors officers",
    # Errors and omissions
    "e&o": "errors and omissions",
    "eno": "errors and omissions",
    # Property and casualty
    "p&c": "property and casualty",
    "pc": "property casualty",
    # Employment practices
    "epli": "employment practices liability insurance",
    "epl": "employment practices liability",
    # Business types
    "bop": "business owners policy",
    "cpp": "commercial package policy",
    # Auto coverage
    "um": "uninsured motorist",
    "uim": "underinsured motorist",
    "pip": "personal injury protection",
    "bi": "bodily injury",
    "pd": "property damage",
    "comp": "comprehensive",
    "coll": "collision",
    # Other coverage types
    "cyb": "cyber liability",
    "cyber": "cyber liability",
    "aop": "all other perils",
    "bpp": "business personal property",
    "bii": "business income insurance",
    "ee": "extra expense",
    # Limits and deductibles
    "occ": "occurrence",
    "agg": "aggregate",
    "ded": "deductible",
    "sir": "self insured retention",
    # Process and documentation
    "fnol": "first notice of loss",
    "siu": "special investigations unit",
    "tpa": "third party administrator",
    "mga": "managing general agency",
    # Reinsurance
    "ri": "reinsurance",
    "xs": "excess",
    "qsr": "quota share reinsurance",
}

# ---------------------------------------------------------------------------
# Insurance-domain synonyms (used by keyword / BM25 index)
# ---------------------------------------------------------------------------
INSURANCE_SYNONYMS: dict[str, List[str]] = {
    "policy": ["coverage", "plan", "contract"],
    "premium": ["rate", "cost", "price", "payment"],
    "claim": ["loss", "incident", "occurrence"],
    "deductible": ["excess", "retention", "selfinsured"],
    "coverage": ["protection", "insurance", "policy"],
    "endorsement": ["rider", "amendment", "addendum"],
    "underwriting": ["riskassessment", "evaluation"],
    "insured": ["policyholder", "client", "customer"],
    "beneficiary": ["payee", "recipient"],
    "carrier": ["insurer", "company", "provider"],
    "agent": ["broker", "producer", "representative"],
    "renewal": ["extension", "continuation"],
    "cancellation": ["termination", "void", "cancel"],
    "exclusion": ["exception", "limitation"],
    "limit": ["maximum", "cap", "ceiling"],
    "liability": ["responsibility", "obligation"],
    "peril": ["risk", "hazard", "danger"],
    "sublimit": ["sublimitation", "internalimit"],
    "coinsurance": ["costsharing", "copay"],
    "indemnity": ["compensation", "reimbursement"],
}

# ---------------------------------------------------------------------------
# Common insurance-term variations / misspellings
# ---------------------------------------------------------------------------
TERM_NORMALIZATIONS: dict[str, str] = {
    "policyholder": "policy holder",
    "coinsurance": "co insurance",
    "selfinsured": "self insured",
    "sublimit": "sub limit",
    "deductable": "deductible",
    "liabilty": "liability",
    "insurence": "insurance",
    "cliam": "claim",
    "prmeium": "premium",
    "renewel": "renewal",
}

# ---------------------------------------------------------------------------
# Document-type keywords (insurance domain)
# ---------------------------------------------------------------------------
DOC_TYPE_KEYWORDS: dict[str, list[str]] = {
    "policy_wording": ["policy wording", "policy document", "terms and conditions", "coverage terms", "policy terms", "wording"],
    "endorsement": ["endorsement", "amendment", "rider", "addendum", "policy change", "modification"],
    "certificate": ["certificate", "coi", "certificate of insurance", "proof of insurance", "cert"],
    "claim": ["claim", "claim form", "loss notice", "incident report", "claim submission", "fnol"],
    "underwriting": ["underwriting", "risk assessment", "underwriting guide", "risk evaluation", "uw guide"],
    "premium": ["premium", "rate", "pricing", "premium schedule", "rate sheet", "quote"],
    "process": ["process", "procedure", "workflow", "how to", "step by step", "sop", "guide"],
    "announcement": ["announcement", "update", "news", "bulletin", "notice", "memo"],
    "compliance": ["compliance", "regulatory", "audit", "regulation", "requirement", "filing"],
    "renewal": ["renewal", "renew", "expiration", "policy renewal", "renewal notice"],
    "cancellation": ["cancel", "cancellation", "termination", "policy cancellation", "non-renewal"],
    "coverage": ["coverage", "coverage summary", "declarations", "dec page", "limits"],
    "training": ["training", "onboarding", "education", "learning", "course"],
}

# ---------------------------------------------------------------------------
# Category keywords (maps query intent → preferred chunk categories)
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "procedure": ["how to", "steps", "process", "procedure", "workflow", "instructions", "guide"],
    "definition": ["what is", "define", "meaning", "definition", "what does", "what are"],
    "data": ["statistics", "numbers", "data", "metrics", "table", "figures", "amount"],
    "example": ["example", "case study", "illustration", "sample", "instance", "scenario"],
    "reference": ["reference", "citation", "source", "appendix", "annex", "schedule"],
    "narrative": ["background", "history", "overview", "context", "story"],
}

# ---------------------------------------------------------------------------
# Synthesis keywords (triggers LLM synthesis when detected in a query)
# ---------------------------------------------------------------------------
SYNTHESIS_KEYWORDS: list[str] = [
    "summarize",
    "explain",
    "compare",
    "difference",
    "relationship",
    "how does",
    "why",
    "what is the",
    "overview",
    "total",
    "average",
    "trend",
]

