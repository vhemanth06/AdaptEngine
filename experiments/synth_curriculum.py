"""Synthetic curriculum generator for benchmarking (experiments/synth_curriculum.py).

Generates seeded layered DAG curricula and activities matching the JSON schema
of curriculum_8node.json and activities_8node.json.
Note: These curricula are synthetic and unreviewed.
"""

import json
import os
import random
from typing import Tuple


def generate_synthetic_curriculum(n_concepts: int, seed: int = 2026) -> Tuple[dict, dict]:
    """Generate layered DAG curriculum and activity catalog for N concepts."""
    rng = random.Random(seed)

    # Layered DAG generation
    # Concepts C1 to CN
    # Layer 0 has roots; last layer has the single goal concept CN
    concepts = []
    concept_ids = [f"C{i}" for i in range(1, n_concepts + 1)]

    # Determine layers: e.g., 2-4 concepts per layer
    if n_concepts <= 8:
        layer_sizes = [2, 3, 2, 1] if n_concepts == 8 else [n_concepts]
    else:
        # Generate layers such that the last layer has exactly 1 concept (the goal)
        remaining = n_concepts - 1
        layer_sizes = []
        # first layer 2-3 roots
        first_size = min(remaining, rng.randint(2, 3))
        layer_sizes.append(first_size)
        remaining -= first_size
        while remaining > 0:
            if remaining <= 4:
                layer_sizes.append(remaining)
                remaining = 0
            else:
                sz = rng.randint(2, 4)
                layer_sizes.append(sz)
                remaining -= sz
        layer_sizes.append(1)  # Final goal concept

    # Assign concepts to layers
    layers = []
    idx = 0
    for sz in layer_sizes:
        layers.append(concept_ids[idx : idx + sz])
        idx += sz

    # Assign prerequisites
    for l_idx, layer in enumerate(layers):
        if l_idx == 0:
            for cid in layer:
                concepts.append(
                    {
                        "concept_id": cid,
                        "description": f"Synthetic Concept {cid}",
                        "prerequisites": [],
                    }
                )
        else:
            prev_layer = layers[l_idx - 1]
            for cid in layer:
                # Pick 1 or 2 prerequisites from previous layer
                num_prereqs = min(len(prev_layer), rng.randint(1, 2))
                prereqs = sorted(rng.sample(prev_layer, num_prereqs))
                concepts.append(
                    {
                        "concept_id": cid,
                        "description": f"Synthetic Concept {cid}",
                        "prerequisites": prereqs,
                    }
                )

    # Generate activities
    # 1 lesson + 4 exercises per concept
    activities = []
    difficulties = [0.20, 0.40, 0.60, 0.80]
    durations = [1, 2, 2, 3]

    for cid in concept_ids:
        activities.append(
            {
                "activity_id": f"L-{cid}",
                "type": "LESSON",
                "target_concept": cid,
                "duration": 4,
                "text": f"Lesson for {cid}",
                "_note": "synthetic unreviewed",
            }
        )
        for i, (diff, dur) in enumerate(zip(difficulties, durations), start=1):
            activities.append(
                {
                    "activity_id": f"E-{cid}-{i}",
                    "type": "EXERCISE",
                    "target_concept": cid,
                    "duration": dur,
                    "difficulty": diff,
                    "text": f"Exercise {i} for {cid}",
                    "_note": "synthetic unreviewed",
                }
            )

    curr_dict = {"schema_version": 1, "concepts": concepts}
    act_dict = {"schema_version": 1, "activities": activities}
    return curr_dict, act_dict


def write_synthetic_curriculum(out_dir: str, n_concepts: int, seed: int = 2026) -> Tuple[str, str]:
    """Write synthetic curriculum and activities to JSON files in out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    curr_dict, act_dict = generate_synthetic_curriculum(n_concepts, seed)
    curr_path = os.path.join(out_dir, f"curriculum_synth_{n_concepts}.json")
    act_path = os.path.join(out_dir, f"activities_synth_{n_concepts}.json")

    with open(curr_path, "w") as f:
        json.dump(curr_dict, f, indent=2)
    with open(act_path, "w") as f:
        json.dump(act_dict, f, indent=2)

    return curr_path, act_path
