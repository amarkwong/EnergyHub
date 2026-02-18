"""Energy Expert: TOU rate deduplication, validation, and catalog auditing."""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Legacy government feed-in tariff (FiT) knowledge
# ---------------------------------------------------------------------------
# Australian states offered premium solar feed-in tariffs (44c/kWh in NSW/QLD,
# 48c/kWh in SA) that closed to new applicants around 2011-2012.  Only
# customers who were already enrolled before the cut-off continue to receive
# these rates — they are **grandfathered**.  A new customer switching to a plan
# that lists one of these tariffs will NOT receive the legacy rate; they will
# get the retailer's standard FiT (typically 3-12c/kWh).
#
# The CDR plan data still includes these tariffs because they apply to
# grandfathered customers.  When comparing plans for a user who does NOT
# already hold one of these legacy FiTs, we must exclude them — otherwise
# the plan appears artificially cheap due to the inflated feed-in credit.
#
# Known legacy FiT labels (non-exhaustive — rate-based filtering is safer):
#   - "Solar bonus scheme - Premium FiT"   (NSW 44c)
#   - "Government Regulated Feed-in-Tariff" (QLD 44c)
#   - "Government contribution"             (QLD 44c)
#   - "Single Rate Solar FiT"              (SA 44c / 48c)
#   - "TOU Rate Solar FiT"                 (SA 44c)
#   - "Premium FiT" / "Solar Bonus"         (various)
#
# Heuristic: any FiT >= 30 c/kWh is almost certainly a legacy government
# scheme, since no current retail FiT approaches that level.
# ---------------------------------------------------------------------------
LEGACY_FIT_RATE_THRESHOLD_CENTS = 30.0


class EnergyExpertService:
    """Analyse and fix retail plan catalog data quality issues."""

    @staticmethod
    def is_legacy_feed_in_tariff(fit: dict[str, Any]) -> bool:
        """Return True if a feed-in tariff entry is a legacy government scheme.

        Uses both rate-based (>= 30 c/kWh) and name-based heuristics so that
        new naming variants are still caught by the rate check.
        """
        rate = fit.get("unit_price_cents_per_kwh")
        if rate is not None and rate >= LEGACY_FIT_RATE_THRESHOLD_CENTS:
            return True
        name = (fit.get("name") or "").lower()
        legacy_keywords = ("solar bonus", "premium fit", "government")
        return any(kw in name for kw in legacy_keywords)

    @classmethod
    def filter_retail_feed_in_tariffs(
        cls, feed_in_tariffs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return only feed-in tariffs available to new/switching customers.

        Excludes legacy government schemes (44c/48c) that are grandfathered
        and not available to customers who don't already hold them.
        """
        return [
            f for f in feed_in_tariffs
            if f.get("unit_price_cents_per_kwh") is not None
            and not cls.is_legacy_feed_in_tariff(f)
        ]

    @staticmethod
    def deduplicate_tou_rates(tou_rates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate TOU rate entries (same name/rate/window/days)."""
        seen: set[tuple] = set()
        deduped: list[dict[str, Any]] = []
        for entry in tou_rates:
            key = (
                entry.get("name"),
                entry.get("rate_cents_per_kwh"),
                entry.get("start_time"),
                entry.get("end_time"),
                tuple(entry["days"]) if entry.get("days") else None,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    @classmethod
    def validate_plan_rates(cls, plan: dict[str, Any]) -> list[str]:
        """Return warnings for a single plan's TOU rates and feed-in tariffs."""
        warnings: list[str] = []

        # Check for legacy government feed-in tariffs
        feed_in_tariffs = plan.get("feed_in_tariffs") or []
        legacy_count = sum(1 for f in feed_in_tariffs if cls.is_legacy_feed_in_tariff(f))
        if legacy_count > 0:
            warnings.append(f"legacy_government_fit:{legacy_count}")

        tou_rates = plan.get("tou_rates") or []
        if not tou_rates:
            return warnings

        # Check for duplicate rates
        seen: set[tuple] = set()
        dup_count = 0
        for entry in tou_rates:
            key = (
                entry.get("name"),
                entry.get("rate_cents_per_kwh"),
                entry.get("start_time"),
                entry.get("end_time"),
                tuple(entry["days"]) if entry.get("days") else None,
            )
            if key in seen:
                dup_count += 1
            seen.add(key)
        if dup_count > 0:
            warnings.append(f"duplicate_rates:{dup_count}")

        # Suspicious rate count (more than 10 entries is unusual)
        if len(tou_rates) > 10:
            warnings.append(f"suspicious_rate_count:{len(tou_rates)}")

        # Check weekday coverage (Mon-Fri = 0-4)
        weekday_covered = set()
        weekend_covered = set()
        for entry in tou_rates:
            days = entry.get("days") or []
            for d in days:
                if d in (0, 1, 2, 3, 4):
                    weekday_covered.add(d)
                elif d in (5, 6):
                    weekend_covered.add(d)

        if tou_rates and len(weekday_covered) == 0:
            warnings.append("missing_weekday_coverage")
        if tou_rates and len(weekend_covered) == 0:
            warnings.append("missing_weekend_coverage")

        return warnings

    @classmethod
    def normalize_plan_catalog(cls, plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate TOU rates across all plans in a catalog."""
        for plan in plans:
            if plan.get("tou_rates"):
                plan["tou_rates"] = cls.deduplicate_tou_rates(plan["tou_rates"])
        return plans

    @classmethod
    def audit_catalog(cls, plans: list[dict[str, Any]]) -> dict[str, Any]:
        """Full audit report with per-plan details."""
        plans_with_issues: list[dict[str, Any]] = []
        total_duplicates = 0
        total_warnings = 0

        for plan in plans:
            warnings = cls.validate_plan_rates(plan)
            if warnings:
                total_warnings += len(warnings)
                dups = sum(
                    int(w.split(":")[1])
                    for w in warnings
                    if w.startswith("duplicate_rates:")
                )
                total_duplicates += dups
                plans_with_issues.append({
                    "retailer": plan.get("retailer"),
                    "plan_name": plan.get("plan_name"),
                    "tou_rate_count": len(plan.get("tou_rates") or []),
                    "warnings": warnings,
                })

        return {
            "total_plans": len(plans),
            "plans_with_issues": len(plans_with_issues),
            "total_duplicate_rates": total_duplicates,
            "total_warnings": total_warnings,
            "details": plans_with_issues,
        }
