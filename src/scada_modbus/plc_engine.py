"""
Industrial PLC & SCADA Simulation Engine (IEC 61131-3 Equivalent Logic + Modbus Register Map)
Author: Rogerio Eduardo Moreira Menegueli
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class QTAController:
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

    def step(self, dt_s: float = 0.5) -> None:
        utility_healthy = (342.0 <= self.utility_voltage_v <= 418.0) and (57.5 <= self.utility_freq_hz <= 62.5)
        gen_healthy = (350.0 <= self.gen_voltage_v <= 410.0) and (58.0 <= self.gen_freq_hz <= 62.0)

        if self.emergency_stop or not self.oil_pressure_ok or not self.coolant_temp_ok:
            self.state = 99
            self.cmd_fuel_solenoid = False
            self.cmd_starter_motor = False
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = False
            self.alarm_general = True
            return

        if self.state == 0:
            self.cmd_fuel_solenoid = False
            self.cmd_starter_motor = False
            self.cmd_close_gen_52g = False
            self.cmd_close_mains_52r = utility_healthy and not self.fbk_breaker_gen
            if self.auto_mode and not utility_healthy:
                self.timer_s = 0.0
                self.state = 1
        elif self.state == 1:
            self.cmd_close_mains_52r = False
            self.timer_s += dt_s
            if utility_healthy:
                self.state = 0
            elif self.timer_s >= 3.0:
                self.crank_attempts = 1
                self.timer_s = 0.0
                self.cmd_fuel_solenoid = True
                self.cmd_starter_motor = True
                self.state = 2
        elif self.state == 2:
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = False
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = True
            self.timer_s += dt_s
            if gen_healthy:
                self.cmd_starter_motor = False
                self.timer_s = 0.0
                self.state = 3
            elif self.timer_s >= 8.0:
                self.cmd_starter_motor = False
                if self.crank_attempts >= 3:
                    self.cmd_fuel_solenoid = False
                    self.alarm_general = True
                    self.state = 99
                else:
                    self.crank_attempts += 1
                    self.timer_s = 0.0
        elif self.state == 3:
            self.cmd_fuel_solenoid = True
            self.cmd_starter_motor = False
            self.cmd_close_mains_52r = False
            self.timer_s += dt_s
            if not gen_healthy:
                self.state = 2
            elif self.timer_s >= 5.0 and not self.fbk_breaker_mains:
                self.cmd_close_gen_52g = True
                self.timer_s = 0.0
                self.state = 4
        elif self.state == 4:
            self.cmd_fuel_solenoid = True
            self.cmd_close_mains_52r = False
            self.cmd_close_gen_52g = not self.fbk_breaker_mains
            if utility_healthy:
                self.timer_s = 0.0
                self.state = 5
        elif self.state == 5:
            self.cmd_fuel_solenoid = True
            self.timer_s += dt_s
            if not utility_healthy:
                self.state = 4
            elif self.timer_s >= 15.0:
                self.cmd_close_gen_52g = False
                self.cmd_close_mains_52r = not self.fbk_breaker_gen
                self.timer_s = 0.0
                self.state = 6
        elif self.state == 6:
            self.cmd_close_gen_52g = False
            self.cmd_close_mains_52r = utility_healthy and not self.fbk_breaker_gen
            self.cmd_fuel_solenoid = True
            self.timer_s += dt_s
            if not utility_healthy:
                self.state = 3
            elif self.timer_s >= 30.0:
                self.cmd_fuel_solenoid = False
                self.timer_s = 0.0
                self.state = 0

        if self.cmd_close_mains_52r and self.cmd_close_gen_52g:
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

    def step(self, raw_current_ma: float, dt_s: float = 0.1, lshh: bool = False) -> None:
        if raw_current_ma < 3.6 or raw_current_ma > 21.0:
            self.fault_wire_break = True
            self.pump_run_enable = False
            self.vfd_command_pct = 0.0
            self.analog_out_ma = 4.0
            return
        self.fault_wire_break = False
        self.level_pct = max(0.0, min(100.0, ((raw_current_ma - 4.0) / 16.0) * 100.0))

        if not self.enable or lshh or self.level_pct >= 95.0:
            self.pump_run_enable = False
            self.vfd_command_pct = 0.0
            self.analog_out_ma = 4.0
            self.integral = 0.0
            return

        error = self.setpoint_pct - self.level_pct
        self.integral = max(0.0, min(100.0, self.integral + error * self.ki * dt_s))
        derivative = (error - self.prev_error) / dt_s
        self.prev_error = error

        out = self.kp * error + self.integral + self.kd * derivative
        self.vfd_command_pct = max(0.0, min(100.0, out))
        self.pump_run_enable = self.vfd_command_pct > 2.0
        self.analog_out_ma = 4.0 + (self.vfd_command_pct / 100.0) * 16.0
