"""Detached macro calculations. Workers receive values, never live game objects."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import multiprocessing


def best_supply_site(snapshot):
    points, candidates, radius, decay = snapshot
    best = None
    for key, strength, multiplier in candidates:
        q, r = key
        gain = 0
        for (pq, pr), weight, passability, current in points:
            distance = max(abs(q - pq), abs(r - pr), abs(q + r - pq - pr))
            if distance <= radius:
                expected = strength * decay ** distance * (.42 + passability * .58)
                gain += max(0, min(.6, expected) - current) * weight
        gain *= multiplier
        if gain > .05 and (best is None or gain > best[0]):
            best = gain, key
    return best


def regional_profiles(snapshot):
    rows, country_id, capital = snapshot
    lookup = {row[0]: row for row in rows}
    remaining = set(lookup)
    profiles = {}
    while remaining:
        seed = min(remaining)
        base = lookup[seed][1]
        queue = deque([seed])
        remaining.remove(seed)
        members = []
        while queue:
            key = queue.popleft()
            members.append(key)
            for other in lookup[key][7]:
                if other in remaining and lookup[other][1] == base:
                    remaining.remove(other)
                    queue.append(other)
        population = supply = 0
        buildings, output, borders = {}, {}, []
        for key in members:
            _, _, pop, score, coverage, flows, border, _ = lookup[key]
            population += pop
            supply += score
            for building, value in coverage.items():
                buildings[building] = buildings.get(building, 0) + value
            for resource, amount in flows.items():
                output[resource] = output.get(resource, 0) + amount
            if border:
                borders.append(key)
        importance = population / 100_000 + sum(buildings.get(key, 0) * weight for key, weight in
                    (("industry", 5), ("refinery", 6), ("oil_gas_rig", 4), ("supply_depot", 3)))
        if capital in members:
            importance += 30
        profiles[base, country_id, min(members)] = dict(tiles=tuple(members), population=population,
            supply=supply / max(1, len(members)), buildings=buildings, output=output,
            borders=borders, importance=importance)
    return profiles


class AIPlanningWorkers:
    def __init__(self, workers=1):
        self.executor = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"))
        self.pending = {}
        self.results = {}
        self.errors = {}
        self.closed = False

    def request(self, key, operation, snapshot, hour):
        previous = self.pending.get(key)
        if previous and previous[0].done():
            future, observed = self.pending.pop(key)
            try:
                self.results[key] = observed, future.result()
                self.errors.pop(key, None)
            except Exception as error:
                self.errors[key] = str(error)
        if key not in self.pending and not self.closed:
            try:
                self.pending[key] = self.executor.submit(operation, snapshot), hour
            except Exception as error:
                self.errors[key] = str(error)
                self.close()
        result = self.results.get(key)
        return result[1] if result and 0 <= hour - result[0] <= 168 else None

    def close(self):
        if not self.closed:
            self.closed = True
            for future, _ in self.pending.values():
                future.cancel()
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.pending.clear()
