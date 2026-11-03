"""Process workers receive only map dimensions and seed, never the live Game."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os


def generate_strip(width, height, seed, first, last):
    from world_generation import WorldGenerator
    from Constants import HEX_WID, HEX_HGT
    generator = WorldGenerator(width, height, seed)
    return [generator.generate_tile_data(q, r,
            100 + q * HEX_WID + (r % 2) * HEX_WID / 2, 100 + r * HEX_HGT * .75)
            for q in range(first, last) for r in range(height)]


class MapGenerationJob:
    def __init__(self, size, seed, workers=None):
        count = min(size, workers or min(3, max(1, (os.cpu_count() or 2) - 1)))
        self.executor = ProcessPoolExecutor(max_workers=count, mp_context=multiprocessing.get_context("spawn"))
        self.futures = [self.executor.submit(generate_strip, size, size, seed,
                        size * i // count, size * (i + 1) // count) for i in range(count)]
        self.closed = False

    def poll(self):
        if not all(future.done() for future in self.futures):
            return None
        try:
            return [tile for future in self.futures for tile in future.result()]
        finally:
            self.close()

    def close(self):
        if not self.closed:
            self.closed = True
            for future in self.futures:
                future.cancel()
            self.executor.shutdown(wait=False, cancel_futures=True)
