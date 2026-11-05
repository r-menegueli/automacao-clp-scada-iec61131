"""Discrete simulation model for the conceptual QTA and reservoir controllers."""

from dataclasses import dataclass


@dataclass
class QTAController:
    """Automatic QTA sequence; state numbers match ``FB_QTA_Controller.st``."""

    auto_mode: bool = True
    emergency_stop: bool = False
    utility_voltage_v: float = 380.0
    utility_freq_hz: float = 60.0
    gen_voltage_v: float = 0.0
    gen_freq_hz: float = 0.0
    oil_pressure_ok: bool = True
    coolant_temp_ok: bool = True
    fbk_breaker_mains: bool = False
    fbk_breaker_gen: bool = False

    state: int = 0
    cmd_fuel_solenoid: bool = False
    cmd_starter_motor: bool = False
    cmd_close_mains_52r: bool = False
    cmd_close_gen_52g: bool = False
    alarm_general: bool = False
    crank_attempts: int = 0
    timer_s: float = 0.0

    def _latch_fault(self) -> None:
        self.state = 99
        self.cmd_fuel_solenoid = False
        self.cmd_starter_motor = False
        self.cmd_close_mains_52r = False
        self.cmd_close_gen_52g = False
        self.alarm_general = True

    def step(self, dt_s: float = 0.5) -> None:
        if dt_s <= 0:
            raise ValueError("dt_s must be greater than zero")

        utility_healthy = (
            323.0 <= self.utility_voltage_v <= 418.0
            and 57.0 <= self.utility_freq_hz <= 63.0
        )
        gen_healthy = (
            372.4 <= self.gen_voltage_v <= 387.6
            and 59.4 <= self.gen_freq_hz <= 60.6
        )

        # Oil and coolant permissives are checked once the generator indicates
        # healthy operation; a stopped engine can naturally have no oil pressure.
        if (
            self.emergency_stop
            or (gen_healthy and (not self.oil_pressure_ok or not self.coolant_temp_ok))
            or (self.fbk_breaker_mains and self.fbk_breaker_gen)
            or self.state == 99
        ):
            self._latch_fault()
            return

        if self.state == 0:  # Utility standby
            self.cmd_fuel_solenoid = False
            self.cmd_starter_motor = False
            self.cmd_close_gen_52g = False
            self.cmd_close_mains_52r = utility_healthy and not self.fbk_breaker_gen
            if self.auto_mode and not utility_healthy:
                self.timer_s = 0.0
                self.state = 1

        elif self.state == 1:  # Confirm utility failure for 3 s
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = False
            self.cmd_fuel_solenoid = False
            self.cmd_starter_motor = False
            self.timer_s += dt_s
            if utility_healthy:
                self.timer_s = 0.0
                self.state = 0
            elif self.timer_s >= 3.0:
                self.crank_attempts = 1
                self.timer_s = 0.0
                self.state = 2

        elif self.state == 2:  # Crank for up to 5 s
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = False
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = True
            self.timer_s += dt_s
            if gen_healthy:
                self.cmd_starter_motor = False
                self.timer_s = 0.0
                self.state = 4
            elif self.timer_s >= 5.0:
                self.cmd_starter_motor = False
                self.timer_s = 0.0
                self.state = 3

        elif self.state == 3:  # 5 s pause between crank attempts
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = False
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = False
            self.timer_s += dt_s
            if gen_healthy:
                self.timer_s = 0.0
                self.state = 4
            elif self.timer_s >= 5.0:
                if self.crank_attempts >= 3:
                    self._latch_fault()
                else:
                    self.crank_attempts += 1
                    self.timer_s = 0.0
                    self.state = 2

        elif self.state == 4:  # 5 s generator stabilization
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = False
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = False
            self.timer_s += dt_s
            if not gen_healthy:
                if self.crank_attempts >= 3:
                    self._latch_fault()
                else:
                    self.crank_attempts += 1
                    self.timer_s = 0.0
                    self.state = 2
            elif self.timer_s >= 5.0:
                self.timer_s = 0.0
                self.state = 5

        elif self.state == 5:  # Open 52-R, prove open, then 1.5 s dead time
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = False
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = False
            if not gen_healthy:
                self._latch_fault()
            elif self.fbk_breaker_mains:
                self.timer_s = 0.0
            else:
                self.timer_s += dt_s
                if self.timer_s >= 1.5:
                    self.cmd_close_gen_52g = True
                    self.timer_s = 0.0
                    self.state = 6

        elif self.state == 6:  # Generator on load
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = False
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = not self.fbk_breaker_mains
            if not gen_healthy:
                self._latch_fault()
            elif utility_healthy:
                self.timer_s = 0.0
                self.state = 7

        elif self.state == 7:  # Utility must remain healthy for 120 s
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = False
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = not self.fbk_breaker_mains
            self.timer_s += dt_s
            if not utility_healthy:
                self.timer_s = 0.0
                self.state = 6
            elif self.timer_s >= 120.0:
                self.cmd_close_gen_52g = False
                self.timer_s = 0.0
                self.state = 8

        elif self.state == 8:  # Open 52-G, prove open, then 1.5 s dead time
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = False
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = False
            if not utility_healthy:
                self.timer_s = 0.0
                self.state = 5 if gen_healthy else 99
            elif self.fbk_breaker_gen:
                self.timer_s = 0.0
            else:
                self.timer_s += dt_s
                if self.timer_s >= 1.5:
                    self.cmd_close_mains_52r = True
                    self.timer_s = 0.0
                    self.state = 9

        elif self.state == 9:  # 180 s no-load cool-down
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = False
            self.cmd_close_gen_52g = False
            self.cmd_close_mains_52r = utility_healthy and not self.fbk_breaker_gen
            if not utility_healthy:
                self.timer_s = 0.0
                self.state = 5 if gen_healthy else 1
            else:
                self.timer_s += dt_s
                if self.timer_s >= 180.0:
                    self.cmd_fuel_solenoid = False
                    self.crank_attempts = 0
                    self.timer_s = 0.0
                    self.state = 0

        if self.cmd_close_mains_52r and self.cmd_close_gen_52g:
            self._latch_fault()
        elif self.cmd_close_mains_52r and self.fbk_breaker_gen:
            self.cmd_close_mains_52r = False
        elif self.cmd_close_gen_52g and self.fbk_breaker_mains:
            self.cmd_close_gen_52g = False


@dataclass
class LevelPIDController:
    enable: bool = True
    setpoint_pct: float = 65.0
    kp: float = 2.4
    ki: float = 0.35
    kd: float = 0.15
    integral: float = 0.0
    prev_error: float = 0.0

    level_pct: float = 0.0
    vfd_command_pct: float = 0.0
    analog_out_ma: float = 4.0
    fault_wire_break: bool = False
    pump_run_enable: bool = False

    def _stop(self) -> None:
        self.pump_run_enable = False
        self.vfd_command_pct = 0.0
        self.analog_out_ma = 4.0
        self.integral = 0.0
        self.prev_error = 0.0

    def step(self, raw_current_ma: float, dt_s: float = 0.1, lshh: bool = False) -> None:
        if dt_s <= 0:
            raise ValueError("dt_s must be greater than zero")
        if raw_current_ma < 3.6 or raw_current_ma > 21.0:
            self.fault_wire_break = True
            self._stop()
            return

        self.fault_wire_break = False
        self.level_pct = max(0.0, min(100.0, ((raw_current_ma - 4.0) / 16.0) * 100.0))
        if not self.enable or lshh or self.level_pct >= 95.0:
            self._stop()
            return

        error = max(-100.0, min(100.0, self.setpoint_pct - self.level_pct))
        self.integral = max(0.0, min(100.0, self.integral + error * self.ki * dt_s))
        derivative = (error - self.prev_error) / dt_s
        self.prev_error = error
        output = self.kp * error + self.integral + self.kd * derivative
        self.vfd_command_pct = max(0.0, min(100.0, output))
        self.pump_run_enable = self.vfd_command_pct > 2.0
        self.analog_out_ma = 4.0 + (self.vfd_command_pct / 100.0) * 16.0
