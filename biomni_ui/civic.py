"""CIViC (Clinical Interpretation of Variants in Cancer): curated variant evidence for a gene, from the public GraphQL API."""

from __future__ import annotations

import requests

from biomni_ui.cache import ttl_cache

CIVIC_API = "https://civicdb.org/api/graphql"


@ttl_cache(ttl=24 * 3600)
def civic_gene_variants(gene: str, max_results: int = 20) -> str:
    """The gene's CIViC summary, the number of curated variants, and the first variants with their variant types.

    Returns plain text. An unknown gene or a network failure is reported as text, not raised.
    """
    symbol = (gene or "").strip()
    if not symbol:
        return "Give a gene symbol, for example EGFR."
    n = max(1, min(int(max_results or 20), 100))
    query = (
        '{ gene(entrezSymbol: "%s") { name description variants(first: %d) { totalCount nodes { name variantTypes { name } } } } }'
        % (symbol.replace('"', ""), n)
    )
    try:
        r = requests.post(CIVIC_API, json={"query": query}, timeout=30)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        return f"CIViC query failed: {type(e).__name__}: {str(e)[:160]}"
    if data.get("errors"):
        return f"CIViC returned an error: {str(data['errors'][0].get('message', ''))[:200]}"
    gene_node = (data.get("data") or {}).get("gene")
    if not gene_node:
        return f"CIViC has no gene {symbol} (check the gene symbol)."
    variants = gene_node.get("variants") or {}
    lines = [f"CIViC: {gene_node.get('name')}, curated variants in all: {variants.get('totalCount', 0)}, first {n}:"]
    summary = " ".join((gene_node.get("description") or "").split())[:300]
    if summary:
        lines.append(f"Gene summary: {summary}")
    for node in variants.get("nodes") or []:
        types = ", ".join(t.get("name", "") for t in node.get("variantTypes") or [])
        lines.append(f"- {node.get('name')}｜{types}")
    lines.append("Source: CIViC (civicdb.org); the data are manually curated clinical interpretations.")
    return "\n".join(lines)


from biomni_ui import connectors as _connectors  # noqa: E402
_connectors.guard(globals())  # the switch of each database connector is checked on every call
