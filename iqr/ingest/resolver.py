"""Resolve a GRC package into a local directory of artifacts.

In production this pulls from GRC / SharePoint / a watched mailbox; in dev and
test it simply points at a fixture directory. Kept behind this interface so
the rest of the system never knows the difference.
"""
from __future__ import annotations

from pathlib import Path


class PackageResolver:
    def resolve(self, package_ref: str) -> Path:
        raise NotImplementedError


class LocalPackageResolver(PackageResolver):
    """Dev/test resolver: the package_ref is a directory on disk."""

    def resolve(self, package_ref: str) -> Path:
        p = Path(package_ref)
        if not p.is_dir():
            raise FileNotFoundError(f"GRC package directory not found: {package_ref}")
        return p
