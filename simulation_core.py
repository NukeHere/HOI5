from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from Constants import SIMULATION_HOURS_PER_TICK, SIMULATION_REAL_SECONDS_PER_TICK, SIMULATION_START_TIME
from game_models import MarketState


@dataclass
class GameTimeSnapshot:
    current_time: datetime
    paused: bool
    speed_level: int
    hours_per_tick: int
    tick_count: int
    market_tick_count: int


@dataclass
class SimulationCommand:
    command_type: str
    player_id: int | None = None
    payload: dict = field(default_factory=dict)
    client_id: str = "local"
    issued_at_tick: int = 0
    sequence: int = 0

class LocalSimulationServer:
    def __init__(self):
        self.current_time = SIMULATION_START_TIME
        self.paused = True
        self.speed_level = 1
        self.tick_count = 0
        self.market_tick_count = 0
        self.pending_market_ticks = 0
        self.accumulator = 0.0
        self.market_state = MarketState()
        self.next_market_execution_time = self.next_weekly_market_time(self.current_time)
        self.pending_commands = deque()
        self.command_handlers = {}
        self.next_command_sequence = 1

    @property
    def hours_per_tick(self):
        return SIMULATION_HOURS_PER_TICK[self.speed_level - 1]

    @staticmethod
    def next_weekly_market_time(current_time):
        days_until_monday = (0 - current_time.weekday()) % 7
        execution_time = datetime(
            current_time.year,
            current_time.month,
            current_time.day,
        ) + timedelta(days=days_until_monday)
        if execution_time <= current_time:
            execution_time += timedelta(days=7)
        return execution_time

    def update(self, delta_time):
        self.process_pending_commands()
        if self.paused:
            return

        self.accumulator += delta_time
        ticks_to_process = min(16, int(self.accumulator / SIMULATION_REAL_SECONDS_PER_TICK))
        if ticks_to_process <= 0:
            return

        self.accumulator -= ticks_to_process * SIMULATION_REAL_SECONDS_PER_TICK
        previous_time = self.current_time
        self.current_time += timedelta(hours=self.hours_per_tick * ticks_to_process)
        self.tick_count += ticks_to_process
        self.update_market_schedule(previous_time, self.current_time)

    def update_market_schedule(self, previous_time, current_time):
        while previous_time < self.next_market_execution_time <= current_time:
            self.pending_market_ticks += 1
            self.market_tick_count += 1
            self.market_state.last_execution_time = self.next_market_execution_time
            self.next_market_execution_time += timedelta(days=7)

    def consume_market_ticks(self):
        count = self.pending_market_ticks
        self.pending_market_ticks = 0
        return count

    def register_command_handler(self, command_type, handler):
        self.command_handlers[command_type] = handler

    def submit_command(self, command):
        if not isinstance(command, SimulationCommand):
            command = SimulationCommand(**command)
        command.issued_at_tick = self.tick_count
        command.sequence = self.next_command_sequence
        self.next_command_sequence += 1
        self.pending_commands.append(command)
        return command.sequence

    def process_pending_commands(self, max_commands=None):
        processed = 0
        while self.pending_commands and (max_commands is None or processed < max_commands):
            command = self.pending_commands.popleft()
            self.apply_command(command)
            processed += 1
        return processed

    def apply_command(self, command):
        if command.command_type == "toggle_pause":
            self.toggle_pause()
            return True
        if command.command_type == "change_speed":
            self.change_speed(command.payload.get("delta", 0))
            return True
        if command.command_type == "set_speed":
            self.set_speed_level(command.payload.get("speed_level", self.speed_level))
            return True

        handler = self.command_handlers.get(command.command_type)
        if handler:
            return handler(command)
        return False

    def set_paused(self, paused):
        self.paused = paused
        if paused:
            self.accumulator = 0.0

    def toggle_pause(self):
        self.set_paused(not self.paused)

    def set_speed_level(self, speed_level):
        self.speed_level = max(1, min(5, speed_level))

    def change_speed(self, delta):
        self.set_speed_level(self.speed_level + delta)

    def snapshot(self):
        return GameTimeSnapshot(
            current_time=self.current_time,
            paused=self.paused,
            speed_level=self.speed_level,
            hours_per_tick=self.hours_per_tick,
            tick_count=self.tick_count,
            market_tick_count=self.market_tick_count,
        )


class LocalSimulationClient:
    def __init__(self, server):
        self.server = server
        self.snapshot = server.snapshot()

    def sync_from_server(self):
        self.snapshot = self.server.snapshot()

    def request_command(self, command_type, player_id=None, payload=None, client_id="local"):
        self.server.submit_command(SimulationCommand(
            command_type=command_type,
            player_id=player_id,
            payload=payload or {},
            client_id=client_id,
        ))
        self.server.process_pending_commands()
        self.sync_from_server()

    def request_toggle_pause(self):
        self.request_command("toggle_pause")

    def request_speed_change(self, delta):
        self.request_command("change_speed", payload={"delta": delta})
