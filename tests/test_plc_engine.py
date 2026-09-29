from src.scada_modbus.plc_engine import QTAController, LevelPIDController

def test_qta_blackout_transfer_and_retransfer():
    plc = QTAController()
    plc.step(0.5)
    assert plc.state == 0
    assert plc.cmd_close_mains_52r is True
    assert plc.cmd_close_gen_52g is False

    # Simulate Utility Blackout (0 V)
    plc.utility_voltage_v = 0.0
    for _ in range(7):
        plc.step(0.5)
    assert plc.state == 2
    assert plc.cmd_fuel_solenoid is True
    assert plc.cmd_starter_motor is True
    assert plc.cmd_close_mains_52r is False

    # Generator reaches nominal voltage/frequency
    plc.gen_voltage_v = 380.0
    plc.gen_freq_hz = 60.0
    for _ in range(12):
        plc.step(0.5)
    assert plc.state == 4
    assert plc.cmd_close_gen_52g is True
    assert plc.cmd_close_mains_52r is False

    # Utility restored -> Retransfer delay -> Cooldown -> Standby
    plc.utility_voltage_v = 380.0
    for _ in range(32):
        plc.step(0.5)
    assert plc.state == 6
    assert plc.cmd_close_mains_52r is True
    assert plc.cmd_close_gen_52g is False

def test_pid_4_20ma_and_namur_fault():
    pid = LevelPIDController(setpoint_pct=70.0)
    # 12 mA = 50% level -> below 70% setpoint -> VFD runs
    pid.step(raw_current_ma=12.0, dt_s=0.5)
    assert not pid.fault_wire_break
    assert abs(pid.level_pct - 50.0) < 1e-3
    assert pid.vfd_command_pct > 40.0
    assert pid.pump_run_enable is True

    # Broken wire (2.1 mA < 3.6 mA NAMUR NE43) -> Safe shutdown
    pid.step(raw_current_ma=2.1, dt_s=0.5)
    assert pid.fault_wire_break is True
    assert pid.pump_run_enable is False
    assert pid.vfd_command_pct == 0.0
