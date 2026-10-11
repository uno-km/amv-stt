# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import math
import random
from typing import List


def euclidean_distance(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate Euclidean distance between two vectors."""
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have the same dimension")
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have the same dimension")
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a ** 2 for a in vec_a))
    norm_b = math.sqrt(sum(b ** 2 for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def cosine_distance_matrix(vectors: List[List[float]]) -> List[List[float]]:
    """Calculate cosine distance matrix for a list of vectors."""
    n = len(vectors)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            if i == j:
                matrix[i][j] = 0.0
            else:
                sim = cosine_similarity(vectors[i], vectors[j])
                dist = 1.0 - sim
                matrix[i][j] = dist
                matrix[j][i] = dist
    return matrix

class KMeans:
    """Pure Python K-Means clustering implementation."""

    def __init__(self, n_clusters: int, max_iter: int = 100, tolerance: float = 1e-4, seed: int = 42):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.tolerance = tolerance
        self.seed = seed
        self.centroids: List[List[float]] = []
        self.labels_: List[int] = []
        self.inertia_: float = 0.0
        random.seed(self.seed)

    def fit(self, vectors: List[List[float]]) -> 'KMeans':
        if not vectors:
            raise ValueError("Empty vectors list")
        n_samples = len(vectors)
        dim = len(vectors[0])

        if n_samples < self.n_clusters:
            # Adaptive clustering for short audio segments
            self.centroids = [v.copy() for v in vectors]
            self.labels_ = list(range(n_samples))
            self.inertia_ = 0.0
            return self

        # Initialize centroids deterministically with seed
        random.seed(self.seed)
        indices = random.sample(range(n_samples), self.n_clusters)
        self.centroids = [vectors[i].copy() for i in indices]

        for _ in range(self.max_iter):
            # Assign labels
            self.labels_ = self.predict(vectors)

            # Update centroids
            new_centroids = [[0.0] * dim for _ in range(self.n_clusters)]
            counts = [0] * self.n_clusters

            for i, label in enumerate(self.labels_):
                counts[label] += 1
                for d in range(dim):
                    new_centroids[label][d] += vectors[i][d]

            for c in range(self.n_clusters):
                if counts[c] > 0:
                    for d in range(dim):
                        new_centroids[c][d] /= counts[c]
                else:
                    # If empty cluster, pick a random vector
                    new_centroids[c] = vectors[random.randint(0, n_samples - 1)].copy()

            # Check convergence
            diff = sum(euclidean_distance(c1, c2) for c1, c2 in zip(self.centroids, new_centroids))
            self.centroids = new_centroids
            if diff < self.tolerance:
                break

        # Calculate inertia
        self.inertia_ = 0.0
        for i, label in enumerate(self.labels_):
            self.inertia_ += euclidean_distance(vectors[i], self.centroids[label]) ** 2

        return self

    def predict(self, vectors: List[List[float]]) -> List[int]:
        labels = []
        for vec in vectors:
            min_dist = float('inf')
            best_label = 0
            for i, centroid in enumerate(self.centroids):
                dist = euclidean_distance(vec, centroid)
                if dist < min_dist:
                    min_dist = dist
                    best_label = i
            labels.append(best_label)
        return labels
