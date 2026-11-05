(* ============================================================================
   PROJECT: Industrial Reservoir Level Control (P&ID ISA-5.1 + 4-20 mA Loop)
   STANDARD: IEC 61131-3 Structured Text (CODESYS / Siemens SCL / Studio 5000)
   AUTHOR: Rogerio Eduardo Moreira Menegueli
   DESCRIPTION:
     4-20 mA analog transmitter scaling (LIT-101, FIT-102) with broken-wire
     detection (< 3.6 mA or > 21.0 mA) and a discrete PID with output clamping.
     Only LSHH is an input to this block; low-level action belongs to the
     documented source/suction process and is not inferred from tank LT-101.
   ============================================================================ *)

FUNCTION_BLOCK FB_Level_PID_Controller
VAR_INPUT
    bEnable             : BOOL := TRUE;
    rRawCurrent_mA      : REAL := 12.0;     (* 4.0 to 20.0 mA from LIT-101 *)
    rSetpoint_Pct       : REAL := 65.0;     (* Desired Tank Level [0..100%] *)
    rKp                 : REAL := 2.4;      (* Proportional Gain *)
    rKi                 : REAL := 0.35;     (* Integral Gain [1/s] *)
    rKd                 : REAL := 0.15;     (* Derivative Gain [s] *)
    rDt_s               : REAL := 0.1;      (* Sample Time [s] *)
    bLevelSwitchHH      : BOOL := FALSE;    (* LSHH-101 High-High Hardwired Switch *)
END_VAR

VAR_OUTPUT
    rLevel_Pct          : REAL := 0.0;      (* Scaled Tank Level [0..100%] *)
    rVfdCommand_Pct     : REAL := 0.0;      (* Pump VFD Speed Command [0..100%] *)
    rAnalogOut_mA       : REAL := 4.0;      (* 4-20 mA Output to VFD AI1 *)
    bFaultWireBreak     : BOOL := FALSE;    (* NAMUR NE43 Fault (< 3.6 mA or > 21.0 mA) *)
    bPumpRunEnable      : BOOL := FALSE;    (* Contactor / VFD Run Permissive *)
END_VAR

VAR
    rError              : REAL := 0.0;
    rPrevError          : REAL := 0.0;
    rIntegral           : REAL := 0.0;
    rDerivative         : REAL := 0.0;
    rUnsatOutput        : REAL := 0.0;
END_VAR

(* 1. NAMUR NE43 4-20 mA Transmitter Diagnostics & Scaling *)
IF (rRawCurrent_mA < 3.6) OR (rRawCurrent_mA > 21.0) THEN
    bFaultWireBreak := TRUE;
    bPumpRunEnable  := FALSE;
    rVfdCommand_Pct := 0.0;
    rAnalogOut_mA   := 4.0;
    RETURN;
ELSE
    bFaultWireBreak := FALSE;
END_IF;

rLevel_Pct := ((rRawCurrent_mA - 4.0) / 16.0) * 100.0;
IF rLevel_Pct < 0.0 THEN rLevel_Pct := 0.0; END_IF;
IF rLevel_Pct > 100.0 THEN rLevel_Pct := 100.0; END_IF;

(* 2. Process permissives. LSHH is the high-level stop input. *)
IF NOT bEnable OR bLevelSwitchHH OR (rLevel_Pct >= 95.0) THEN
    bPumpRunEnable  := FALSE;
    rVfdCommand_Pct := 0.0;
    rAnalogOut_mA   := 4.0;
    rIntegral       := 0.0;
    RETURN;
END_IF;

(* 3. Discrete PID with Clamping Anti-Windup *)
rError      := rSetpoint_Pct - rLevel_Pct;
rIntegral   := rIntegral + (rError * rKi * rDt_s);
IF rIntegral > 100.0 THEN rIntegral := 100.0; END_IF;
IF rIntegral < 0.0   THEN rIntegral := 0.0;   END_IF;

rDerivative := (rError - rPrevError) / rDt_s;
rPrevError  := rError;

rUnsatOutput := (rKp * rError) + rIntegral + (rKd * rDerivative);
IF rUnsatOutput > 100.0 THEN
    rVfdCommand_Pct := 100.0;
ELSIF rUnsatOutput < 0.0 THEN
    rVfdCommand_Pct := 0.0;
ELSE
    rVfdCommand_Pct := rUnsatOutput;
END_IF;

bPumpRunEnable := (rVfdCommand_Pct > 2.0);
rAnalogOut_mA  := 4.0 + (rVfdCommand_Pct / 100.0) * 16.0;
END_FUNCTION_BLOCK
