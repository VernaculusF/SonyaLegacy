from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sonya.selfmod.proposal import ProposalStore
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class CapabilityGap:
    """A detected missing capability.

    Created when the internal process notices a failed action pattern
    or an explicit "I cannot do X" in continuity events.
    """

    gap_id: str
    description: str
    detected_from_event_seq: int | None = None
    proposal_id: str | None = None
    status: str = "open"  # open, proposed, resolved
    created_at: str = ""


class GapDetector:
    """Detects capability gaps from recent continuity events.

    Looks for internal.cognitive_tick events with triggers containing
    failure patterns. Creates CapabilityGap objects in substrate and
    optionally bridges them to SelfModificationProposal.

    See: SKILL_SYSTEM_PLAN, SELF_REWRITE_STANCE §1.
    """

    # Keywords in continuity event payloads that signal a gap
    _GAP_SIGNALS: tuple[str, ...] = (
        "cannot",
        "no_skill",
        "missing_capability",
        "failed_action",
        "not_implemented",
    )

    def __init__(self, substrate: Substrate, stream: ContinuityStream) -> None:
        self._sub = substrate
        self._stream = stream

    def scan_recent(self, since_seq: int = 0) -> list[CapabilityGap]:
        """Scan continuity events since `since_seq` for gap signals."""
        gaps: list[CapabilityGap] = []
        # Exclude detector self-output and noisy event types whose payloads
        # are likely to contain the trigger words ('cannot', 'failed') as
        # legitimate text rather than capability gaps.
        # `internal.agent_session_outcome` — final agent summary often hedges
        # ('I cannot complete this in 8 steps' is not a capability gap, it's
        # a budget exhaustion).
        _SKIP_KINDS = {
            "internal.capability_gap",
            "internal.drift_signal",
            "internal.agent_step",
            "internal.agent_session_outcome",
            "internal.agent_session_complete",
            "incoming.telegram_message",
            "outgoing.response",
            "outgoing.telegram_response",
            "outgoing.telegram_initiative",
            "internal.thought",
            "internal.cognitive_tick",
        }
        # Cache of open-gap fingerprints so we don't INSERT 20 copies of
        # the same DNSError on the same URL.
        existing_fps: set[str] = self._load_open_gap_fingerprints()
        for event in self._stream.read_since(since_seq):
            if event.kind in _SKIP_KINDS:
                continue
            if not self._is_gap_signal(event.payload):
                continue
            fp = self._fingerprint(event.payload)
            if fp in existing_fps:
                continue  # already tracked
            gap = self._create_gap(
                description=self._extract_description(event.payload),
                event_seq=event.seq,
                fingerprint=fp,
            )
            existing_fps.add(fp)
            gaps.append(gap)
        return gaps

    def _fingerprint(self, payload: dict) -> str:
        """Stable fingerprint identifying *this kind* of gap.

        For tool-error payloads ({tool, arg, error_type, error_message}):
            "{tool}|{error_type}|{arg-host-prefix}"
        For everything else: first 80 chars of payload repr.
        """
        if isinstance(payload, dict):
            tool = payload.get("tool")
            err_t = payload.get("error_type")
            if tool and err_t:
                arg = str(payload.get("arg") or "")
                # Take just the host part of a URL arg so different URLs
                # on the same host fold together.
                host = ""
                if "://" in arg:
                    host = arg.split("://", 1)[1].split("/", 1)[0][:80]
                else:
                    host = arg[:80]
                return f"{tool}|{err_t}|{host}"
        return f"raw|{str(payload)[:80]}"

    def _load_open_gap_fingerprints(self) -> set[str]:
        """Reconstruct fingerprints of currently-open gaps from descriptions.

        Schema doesn't have a fingerprint column (yet), so we derive it from
        the payload signature embedded in the description by `_extract_description`.
        Cheap — only `open` gaps are scanned.
        """
        try:
            cursor = self._sub.connection.execute(
                "SELECT description FROM capability_gaps WHERE status = 'open'"
            )
            fps: set[str] = set()
            for (desc,) in cursor.fetchall():
                # Try to recover the payload-shape from the stored description.
                # description starts with "Gap detected from payload: {...}"
                # We re-fingerprint that text via a very forgiving rule: pull
                # 'tool' / 'error_type' / 'arg' substrings if present.
                if "tool" in desc and "error_type" in desc:
                    import re as _re
                    tm = _re.search(r"'tool': '([^']+)'", desc)
                    em = _re.search(r"'error_type': '([^']+)'", desc)
                    am = _re.search(r"'arg': '([^']+)'", desc)
                    if tm and em:
                        arg = am.group(1) if am else ""
                        host = ""
                        if "://" in arg:
                            host = arg.split("://", 1)[1].split("/", 1)[0][:80]
                        else:
                            host = arg[:80]
                        fps.add(f"{tm.group(1)}|{em.group(1)}|{host}")
                        continue
                fps.add(f"raw|{desc[:80]}")
            return fps
        except Exception:
            return set()

    def create_proposal_from_gap(
        self, gap: CapabilityGap, proposal_store: ProposalStore
    ) -> str:
        """Bridge a gap to a SelfModificationProposal. Returns proposal_id."""
        proposal = proposal_store.create(
            target_module="sonya.skills.registry",
            change_summary=f"Add skill to address gap: {gap.description}",
            proposed_by_principal_id="system.gap_detector",
        )
        # Update gap with proposal link
        self._sub.connection.execute(
            "UPDATE capability_gaps SET proposal_id = ?, status = 'proposed' WHERE gap_id = ?",
            (proposal.proposal_id, gap.gap_id),
        )
        self._sub.connection.commit()
        return proposal.proposal_id

    def _is_gap_signal(self, payload: dict) -> bool:
        text = str(payload).lower()
        return any(signal in text for signal in self._GAP_SIGNALS)

    def _extract_description(self, payload: dict) -> str:
        triggers = payload.get("triggers", [])
        if triggers:
            return f"Gap detected from triggers: {', '.join(str(t) for t in triggers)}"
        return f"Gap detected from payload: {str(payload)[:100]}"

    def _create_gap(
        self,
        description: str,
        event_seq: int | None = None,
        *,
        fingerprint: str | None = None,
    ) -> CapabilityGap:
        gap_id = f"gap-{uuid4().hex}"
        now = _utc_now_iso()
        # Schema has no fingerprint column; we keep the kwarg for symmetry
        # with scan_recent's dedup. The fingerprint is reconstructible from
        # the description via _load_open_gap_fingerprints.
        _ = fingerprint
        self._sub.connection.execute(
            "INSERT INTO capability_gaps(gap_id, description, detected_from_event_seq, status, created_at) "
            "VALUES (?, ?, ?, 'open', ?)",
            (gap_id, description, event_seq, now),
        )
        self._sub.connection.commit()
        return CapabilityGap(
            gap_id=gap_id,
            description=description,
            detected_from_event_seq=event_seq,
            status="open",
            created_at=now,
        )
