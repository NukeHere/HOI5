import time


class _PerformanceTimer:
    def __init__(self, profiler, name):
        self.profiler = profiler
        self.name = name
        self.started_at = 0.0

    def __enter__(self):
        self.started_at = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.profiler.add_sample(self.name, time.perf_counter() - self.started_at)
        return False


class _NoPerformanceTimer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class PerformanceProfiler:
    def __init__(self, smoothing=0.18):
        self.smoothing = smoothing
        self.enabled = False
        self.visible = False
        self.current_phase = None
        self.current_samples = {}
        self.latest = {}
        self.average = {}
        self.peak = {}
        self.disabled_timer = _NoPerformanceTimer()

    def set_visible(self, visible):
        self.visible = bool(visible)
        self.enabled = self.visible

    def begin_phase(self, phase):
        if not self.enabled:
            return
        self.current_phase = phase
        self.current_samples = {}

    def end_phase(self, phase):
        if not self.enabled or self.current_phase != phase:
            return
        phase_samples = dict(self.current_samples)
        self.latest[phase] = phase_samples
        average_samples = self.average.setdefault(phase, {})
        peak_samples = self.peak.setdefault(phase, {})
        for name, elapsed in phase_samples.items():
            previous = average_samples.get(name)
            average_samples[name] = elapsed if previous is None else previous + (elapsed - previous) * self.smoothing
            peak_samples[name] = max(peak_samples.get(name, 0.0), elapsed)
        self.current_phase = None
        self.current_samples = {}

    def measure(self, name):
        if not self.enabled:
            return self.disabled_timer
        return _PerformanceTimer(self, name)

    def add_sample(self, name, elapsed):
        if not self.enabled or self.current_phase is None:
            return
        self.current_samples[name] = self.current_samples.get(name, 0.0) + elapsed

    def average_ms(self, phase, name):
        return self.average.get(phase, {}).get(name, 0.0) * 1000.0

    def latest_ms(self, phase, name):
        return self.latest.get(phase, {}).get(name, 0.0) * 1000.0
