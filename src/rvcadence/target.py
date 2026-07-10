from __future__ import annotations

from astropy.coordinates import EarthLocation, SkyCoord


def resolve_target_name(name: str) -> SkyCoord:
    """
    Resolve a target name (e.g. "K2-182", "TOI-198 b") to sky coordinates via
    CDS Sesame. Prints the resolved coordinate for explicit user confirmation.
    Raises astropy's own NameResolveError directly on failure — no retry,
    no caching.
    """
    coord = SkyCoord.from_name(name)
    print(f"Resolved target '{name}' to {coord.to_string('hmsdms')} (ICRS)")
    return coord


def resolve_site_name(name: str) -> EarthLocation:
    """
    Resolve an observatory site name (e.g. "Paranal Observatory") via
    astropy's site registry. Prints the resolved location for explicit user
    confirmation. Raises astropy's own exception directly on failure — no
    retry, no caching.
    """
    location = EarthLocation.of_site(name)
    geo = location.to_geodetic()
    print(f"Resolved site '{name}' to lat={geo.lat.deg:.4f}, lon={geo.lon.deg:.4f}, height={geo.height:.0f}")
    return location
