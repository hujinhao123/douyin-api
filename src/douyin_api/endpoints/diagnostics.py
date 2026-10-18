"""Diagnostics: drift probe and page version."""

from __future__ import annotations

from fastapi import APIRouter, Request

from douyin_api.recovery import build_report, load_baseline, probe_all

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/probe")
async def probe(request: Request) -> dict:
    """Run every safely-probeable profile and classify any drift."""
    deps = request.app.state.deps
    probes = await probe_all(deps.client)
    baseline_path = deps.extra.get("baseline_path")
    baseline = load_baseline(baseline_path) if baseline_path else None
    return build_report(probes, baseline)


@router.get("/version")
async def version(request: Request) -> dict:
    deps = request.app.state.deps
    return {
        "adapter_version": deps.extra.get("adapter_version", "2026.10.17"),
        "signer": deps.extra.get("signer", "browser"),
        "signers_available": getattr(getattr(deps.client, "signer", None), "names", []),
        "session": deps.session_store.status(),
    }
