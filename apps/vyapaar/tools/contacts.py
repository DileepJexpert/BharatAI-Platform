"""Contact management with fuzzy Hindi name matching.

Standalone in-memory store for testing; real deployments use the DB layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from uuid import uuid4

HINDI_HONORIFICS = [
    "ji", "sahab", "sahib", "bhai", "behen", "seth", "sir", "madam",
    "uncle", "aunty", "didi", "anna", "bhaiya", "saheb",
]


def normalize_name(name: str) -> str:
    """Lowercase, strip honorifics, collapse whitespace."""
    name = name.lower().strip()
    words = [w for w in name.split() if w not in HINDI_HONORIFICS]
    return " ".join(words).strip()


@dataclass
class Contact:
    """In-memory contact record."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    name_normalized: str = ""
    phone_number: str | None = None
    contact_type: str = "customer"  # customer | supplier
    running_balance: int = 0  # paisa; +ve = they owe us, -ve = we owe them


@dataclass
class ContactMatchResult:
    match_type: str  # exact, fuzzy, multiple, none
    contact: Contact | None = None
    contacts: list[Contact] | None = None
    spoken_name: str = ""


# ── In-memory store ────────────────────────────────────────────

_contacts: list[Contact] = []


def clear_contacts() -> None:
    """Reset store (for tests)."""
    _contacts.clear()


def find_contact(spoken_name: str) -> ContactMatchResult:
    """Find a contact by spoken name with fuzzy matching."""
    normalized = normalize_name(spoken_name)
    if not normalized:
        return ContactMatchResult(match_type="none", spoken_name=spoken_name)

    if not _contacts:
        return ContactMatchResult(match_type="none", spoken_name=spoken_name)

    # 1. Exact match
    for c in _contacts:
        if c.name_normalized == normalized:
            return ContactMatchResult(match_type="exact", contact=c, spoken_name=spoken_name)

    # 2. Contains match
    contains = [
        c for c in _contacts
        if normalized in c.name_normalized or c.name_normalized in normalized
    ]
    if len(contains) == 1:
        return ContactMatchResult(match_type="fuzzy", contact=contains[0], spoken_name=spoken_name)

    # 3. Similarity match (SequenceMatcher > 0.75)
    scored = []
    for c in _contacts:
        ratio = SequenceMatcher(None, normalized, c.name_normalized).ratio()
        if ratio > 0.75:
            scored.append((c, ratio))

    scored.sort(key=lambda x: x[1], reverse=True)

    if len(scored) == 1:
        return ContactMatchResult(match_type="fuzzy", contact=scored[0][0], spoken_name=spoken_name)
    if len(scored) > 1:
        if scored[0][1] - scored[1][1] > 0.15:
            return ContactMatchResult(match_type="fuzzy", contact=scored[0][0], spoken_name=spoken_name)
        return ContactMatchResult(
            match_type="multiple",
            contacts=[s[0] for s in scored[:5]],
            spoken_name=spoken_name,
        )

    if len(contains) > 1:
        return ContactMatchResult(
            match_type="multiple", contacts=contains[:5], spoken_name=spoken_name
        )

    return ContactMatchResult(match_type="none", spoken_name=spoken_name)


def create_contact(
    name: str,
    contact_type: str = "customer",
    phone_number: str | None = None,
) -> Contact:
    """Create a new contact and add to store."""
    contact = Contact(
        name=name,
        name_normalized=normalize_name(name),
        phone_number=phone_number,
        contact_type=contact_type,
    )
    _contacts.append(contact)
    return contact


def get_or_create_contact(name: str, contact_type: str = "customer") -> Contact:
    """Find or create a contact by name."""
    match = find_contact(name)
    if match.contact:
        return match.contact
    return create_contact(name, contact_type)


def get_all_contacts() -> list[Contact]:
    """Return all contacts."""
    return list(_contacts)


def get_contacts_with_balance() -> list[Contact]:
    """Return contacts with non-zero running balance."""
    return [c for c in _contacts if c.running_balance != 0]
