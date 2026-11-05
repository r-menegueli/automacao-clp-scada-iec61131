from src.scada_modbus.plc_engine import QTAController, LevelPIDController


def advance(plc: QTAController, seconds: float, dt: float = 0.5) -> None:
    for _ in range(round(seconds / dt)):
        plc.step(dt)


def test_qta_open_transition_and_return_use_documented_delays():
    plc = QTAController(fbk_breaker_mains=True)
    plc.step(0.5)
    assert plc.state == 0
    assert plc.cmd_close_mains_52r is True
    assert plc.cmd_close_gen_52g is False

    plc.utility_voltage_v = 0.0
    advance(plc, 3.5)  # includes the scan that enters the 3 s delay state
    assert plc.state == 2
    assert plc.crank_attempts == 1

    # The engine becomes healthy; it must stabilize before transfer.
    plc.gen_voltage_v = 380.0
    plc.gen_freq_hz = 60.0
    plc.step(0.5)
    assert plc.state == 4
    advance(plc, 5.0)
    assert plc.state == 5
    assert plc.cmd_close_mains_52r is False
    assert plc.cmd_close_gen_52g is False

    # 52-G cannot close until 52-R feedback confirms open plus 1.5 s dead time.
    advance(plc, 1.0)
    assert plc.state == 5
    plc.fbk_breaker_mains = False
    advance(plc, 1.5)
    assert plc.state == 6
    assert plc.cmd_close_gen_52g is True
    plc.fbk_breaker_gen = True

    # Utility return must stay healthy for 120 s before opening 52-G.
    plc.utility_voltage_v = 380.0
    plc.step(0.5)
    assert plc.state == 7
    advance(plc, 119.5)
    assert plc.state == 7
    advance(plc, 0.5)
    assert plc.state == 8
    assert plc.cmd_close_gen_52g is False
    plc.fbk_breaker_gen = False
    advance(plc, 1.5)
    assert plc.state == 9
    assert plc.cmd_close_mains_52r is True
    assert not (plc.cmd_close_mains_52r and plc.cmd_close_gen_52g)

    plc.fbk_breaker_mains = True
    advance(plc, 180.0)
    assert plc.state == 0
    assert plc.cmd_fuel_solenoid is False
    assert plc.crank_attempts == 0


def test_qta_crank_retries_have_rest_and_latch_alarm_after_three_failures():
    plc = QTAController()
    plc.step(0.5)
    plc.utility_voltage_v = 0.0
    advance(plc, 3.5)  # includes the scan that enters the 3 s delay state
    assert plc.state == 2

    for attempt in range(3):
        advance(plc, 5.0)
        if attempt < 2:
            assert plc.state == 3
            assert plc.cmd_starter_motor is False
            advance(plc, 5.0)
            assert plc.state == 2
        else:
            assert plc.state == 3
            advance(plc, 5.0)

    assert plc.state == 99
    assert plc.crank_attempts == 3
    assert plc.alarm_general is True
    assert plc.cmd_fuel_solenoid is False
    assert plc.cmd_starter_motor is False


def test_qta_faults_on_conflicting_breaker_feedback():
    plc = QTAController(fbk_breaker_mains=True, fbk_breaker_gen=True)
    plc.step(0.5)
    assert plc.state == 99
    assert plc.alarm_general is True
    assert not plc.cmd_close_mains_52r
    assert not plc.cmd_close_gen_52g


def test_pid_4_20ma_fault_stops_and_resets_integrator():
    pid = LevelPIDController(setpoint_pct=70.0)
    pid.step(raw_current_ma=12.0, dt_s=0.5)
    assert not pid.fault_wire_break
    assert abs(pid.level_pct - 50.0) < 1e-3
    assert pid.vfd_command_pct > 40.0
    assert pid.pump_run_enable is True

    pid.step(raw_current_ma=2.1, dt_s=0.5)
    assert pid.fault_wire_break is True
    assert pid.pump_run_enable is False
    assert pid.vfd_command_pct == 0.0
    assert pid.integral == 0.0


def test_pid_high_high_switch_stops_pump():
    pid = LevelPIDController(setpoint_pct=70.0)
    pid.step(raw_current_ma=12.0, dt_s=0.5)
    pid.step(raw_current_ma=12.0, dt_s=0.5, lshh=True)
    assert pid.pump_run_enable is False
    assert pid.vfd_command_pct == 0.0
    assert pid.analog_out_ma == 4.0
