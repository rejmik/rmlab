"""Souřadnice: převod S-JTSK (RÚIAN) → WGS84 a vzdálenosti."""
import math

_transformer = None


def _get_transformer():
    global _transformer
    if _transformer is None:
        from pyproj import Transformer
        # EPSG:5514 = S-JTSK / Krovak East North (záporné hodnoty)
        _transformer = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)
    return _transformer


def sjtsk_to_wgs84(y: float, x: float):
    """RÚIAN udává kladné Y, X v metrech. Vrací (lat, lon)."""
    lon, lat = _get_transformer().transform(-y, -x)
    return lat, lon


def sjtsk_batch_to_wgs84(ys, xs):
    t = _get_transformer()
    lons, lats = t.transform([-y for y in ys], [-x for x in xs])
    return list(lats), list(lons)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bbox(lat, lon, radius_km):
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon
