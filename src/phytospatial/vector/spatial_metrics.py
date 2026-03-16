import math
import logging
from typing import Any

import pandas as pd

from phytospatial.vector.layer import Vector
from phytospatial.vector.io import resolve_vector

log = logging.getLogger(__name__)

__all__ = [
    "compute_iou",
    "compute_giou",
    "compute_diou",
    "compute_ciou",
    "compute_dice",
    "analyze_geometric_similarity"
]

def compute_iou(geom_a: Vector, geom_b: Vector) -> float:
    """
    Computes the Intersection over Union (IoU) for two spatial geometries.

    Args:
        geom_a (Vector): The first geometry
        geom_b (Vector): The second geometry

    Returns:
        float: The intersection area divided by the union area.
    """
    if not geom_a.intersects(geom_b):
        return 0.0

    inter_area = geom_a.intersection(geom_b).area
    union_area = geom_a.union(geom_b).area

    return inter_area / union_area if union_area > 0 else 0.0

def compute_giou(geom_a: Vector, geom_b: Vector) -> float:
    """
    Computes the Generalized Intersection over Union (GIoU).

    Args:
        geom_a (Vector): The first geometry.
        geom_b (Vector): The second geometry.

    Returns:
        float: The GIoU metric value.
    """
    iou = compute_iou(geom_a, geom_b)
    union_area = geom_a.union(geom_b).area
    convex_area = geom_a.union(geom_b).convex_hull.area

    if convex_area <= 0:
        return iou

    return iou - (convex_area - union_area) / convex_area

def compute_diou(geom_a: Vector, geom_b: Vector) -> float:
    """
    Computes the Distance Intersection over Union (DIoU).

    Args:
        geom_a (Vector): The first geometry.
        geom_b (Vector): The second geometry.

    Returns:
        float: The DIoU metric value.
    """
    iou = compute_iou(geom_a, geom_b)
    c1, c2 = geom_a.centroid, geom_b.centroid
    dist_sq = (c1.x - c2.x)**2 + (c1.y - c2.y)**2

    b1, b2 = geom_a.bounds, geom_b.bounds
    minx, miny = min(b1[0], b2[0]), min(b1[1], b2[1])
    maxx, maxy = max(b1[2], b2[2]), max(b1[3], b2[3])
    diag_sq = (maxx - minx)**2 + (maxy - miny)**2

    if diag_sq <= 0:
        return iou

    return iou - (dist_sq / diag_sq)

def compute_ciou(geom_a: Vector, geom_b: Vector) -> float:
    """
    Computes the Complete Intersection over Union (CIoU).

    Args:
        geom_a (Vector): The first geometry.
        geom_b (Vector): The second geometry.

    Returns:
        float: The CIoU metric value.
    """
    iou = compute_iou(geom_a, geom_b)
    diou = compute_diou(geom_a, geom_b)

    b1, b2 = geom_a.bounds, geom_b.bounds
    w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
    w2, h2 = b2[2] - b2[0], b2[3] - b2[1]

    if h1 == 0 or h2 == 0:
        return diou

    v = (4 / (math.pi**2)) * math.pow(math.atan(w1 / h1) - math.atan(w2 / h2), 2)

    denominator = (1 - iou) + v
    alpha = v / denominator if denominator > 0 else 0.0

    return diou - alpha * v

def compute_dice(geom_a: Vector, geom_b: Vector) -> float:
    """
    Computes the Dice similarity coefficient (Sørensen–Dice index).

    Args:
        geom_a (Vector): The first geometry.
        geom_b (Vector): The second geometry.

    Returns:
        float: 2 * intersection area divided by the sum of individual areas.
    """
    if not geom_a.intersects(geom_b):
        return 0.0

    inter = geom_a.intersection(geom_b).area
    total_area = geom_a.area + geom_b.area

    return (2.0 * inter) / total_area if total_area > 0 else 0.0

@resolve_vector
def analyze_geometric_similarity(
    manual: Vector,
    automated: Vector,
    id_col: str = 'tree_id'
) -> pd.DataFrame:
    """
    Performs a comprehensive similarity analysis between two matched vector layers.

    Args:
        manual (Vector): Reference manual crown vector.
        automated (Vector): Automated crown vector for comparison.
        id_col (str): Join column present in both datasets.

    Returns:
        pd.DataFrame: A table containing matched IDs and all computed spatial metrics.
    """
    m_gdf = manual.data[[id_col, 'geometry']].copy()
    a_gdf = automated.data[[id_col, 'geometry']].copy()

    merged = pd.merge(m_gdf, a_gdf, on=id_col, suffixes=('_ref', '_auto'))

    results = []
    for _, row in merged.iterrows():
        g_ref = row['geometry_ref']
        g_auto = row['geometry_auto']

        results.append({
            id_col: row[id_col],
            'iou': compute_iou(g_ref, g_auto),
            'giou': compute_giou(g_ref, g_auto),
            'diou': compute_diou(g_ref, g_auto),
            'ciou': compute_ciou(g_ref, g_auto),
            'dice': compute_dice(g_ref, g_auto)
        })

    return pd.DataFrame(results)