"""Build the hashed, addressable Evidence Graph from an unpacked package.

Deterministic: same package bytes -> same graph (hashes, keys, ordering).
No model calls in this module or anything it imports.
"""
from __future__ import annotations

from pathlib import Path

from iqr.ingest import extract
from iqr.ingest.resolver import LocalPackageResolver, PackageResolver
from iqr.ingest.unpack import unpack_package
from iqr.schemas.evidence_graph import EvidenceGraph


def build_evidence_graph(package_ref: str,
                         resolver: PackageResolver | None = None) -> EvidenceGraph:
    resolver = resolver or LocalPackageResolver()
    package_dir = resolver.resolve(package_ref)
    leaves, unpack_errors = unpack_package(package_dir)
    graph = EvidenceGraph(package_id=Path(package_ref).name)
    graph.errors.extend(unpack_errors)

    children: dict[str, list[str]] = {}
    for leaf in leaves:
        graph.leaves[leaf.file_hash] = leaf
        if leaf.parent_hash:
            children.setdefault(leaf.parent_hash, []).append(leaf.file_hash)

    for leaf in leaves:
        try:
            if leaf.kind == "xlsx":
                cells, embedded_images = extract.extract_workbook(leaf)
                for cf in cells:
                    graph.cells[EvidenceGraph.cell_key(cf.file_hash, cf.sheet, cf.cell)] = cf
                for imf in embedded_images:
                    graph.images[imf.file_hash] = imf
            elif leaf.kind == "image":
                imf = extract.extract_image(leaf)
                graph.images[imf.file_hash] = imf
            elif leaf.kind == "email" and leaf.logical_path.lower().endswith(".eml"):
                ef = extract.extract_email(leaf, children.get(leaf.file_hash, []))
                graph.emails[ef.message_id] = ef
            elif leaf.kind == "email" and leaf.logical_path.lower().endswith(".msg"):
                ef = extract.extract_msg_email(leaf, children.get(leaf.file_hash, []))
                graph.emails[ef.message_id] = ef
            elif leaf.kind == "xlsb":
                for cf in extract.extract_xlsb(leaf):
                    graph.cells[EvidenceGraph.cell_key(cf.file_hash, cf.sheet, cf.cell)] = cf
            elif leaf.kind == "docx":
                doc_fact, doc_images = extract.extract_docx(leaf)
                graph.docs[leaf.file_hash] = doc_fact
                for imf in doc_images:
                    graph.images[imf.file_hash] = imf
        except Exception as e:
            # the leaf stays in the graph (hashed, in custody) but its facts
            # are absent -> downstream checks abstain honestly with a gap
            graph.errors.append(
                f"unreadable artifact, facts not extracted: {leaf.logical_path} "
                f"({type(e).__name__}: {e})")
    return graph
