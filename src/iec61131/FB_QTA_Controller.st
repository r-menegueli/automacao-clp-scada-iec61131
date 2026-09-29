(* ============================================================================
   PROJECT: 250 kVA Standby Diesel Generator & Automatic Transfer Switch (QTA)
   STANDARD: IEC 61131-3 Structured Text (CODESYS / TIA Portal / OpenPLC)
   AUTHOR: Rogerio Eduardo Moreira Menegueli
   DESCRIPTION:
     Complete state-machine & interlocking logic for Utility (52-R) vs.
     Standby Generator (52-G) transfer with ANSI 27/59 voltage monitoring,
     crank retry sequence, warm-up, retransfer delay, and engine cooldown.
   ============================================================================ *)

FUNCTION_BLOCK FB_QTA_Controller
VAR_INPUT
    bAutoMode           : BOOL := TRUE;     (* Selector Switch in AUTO *)
    bEmergencyStop      : BOOL := FALSE;    (* Emergency Stop Button NC inverted *)
    rUtilityVoltage_V   : REAL := 380.0;    (* Line-to-Line Utility Voltage [V] *)
    rUtilityFreq_Hz     : REAL := 60.0;     (* Utility Frequency [Hz] *)
    rGenVoltage_V       : REAL := 0.0;      (* Generator Voltage [V] *)
    rGenFreq_Hz         : REAL := 0.0;      (* Generator Frequency [Hz] *)
    bOilPressureOK      : BOOL := TRUE;     (* Low Oil Pressure Switch *)
    bCoolantTempOK      : BOOL := TRUE;     (* High Coolant Temp Switch *)
    bFbkBreakerMains    : BOOL := FALSE;    (* Auxiliary Contact 52-R *)
    bFbkBreakerGen      : BOOL := FALSE;    (* Auxiliary Contact 52-G *)
    rDt_s               : REAL := 0.1;      (* Scan Cycle Time [s] *)
END_VAR

VAR_OUTPUT
    iState              : INT  := 0;        (* 0:Standby, 1:MainsFailDelay, 2:Cranking, 3:WarmUp, 4:OnGenerator, 5:RetransferDelay, 6:Cooldown, 99:Fault *)
    bCmdFuelSolenoid    : BOOL := FALSE;    (* K1 Fuel Solenoid Output *)
    bCmdStarterMotor    : BOOL := FALSE;    (* K2 Starter Cranking Output *)
    bCmdCloseMains_52R  : BOOL := FALSE;    (* Close Utility Contactor/ACB 52-R *)
    bCmdCloseGen_52G    : BOOL := FALSE;    (* Close Generator Contactor/ACB 52-G *)
    bAlarmGeneral       : BOOL := FALSE;    (* Horn / SCADA Alarm Bit *)
    iCrankAttempts      : INT  := 0;        (* Number of Start Attempts (Max 3) *)
END_VAR

VAR
    rTimer_s            : REAL := 0.0;
    bUtilityHealthy     : BOOL := TRUE;
    bGenHealthy         : BOOL := FALSE;
END_VAR

(* 1. ANSI 27/59 Utility & Generator Supervision *)
bUtilityHealthy := (rUtilityVoltage_V >= 342.0) AND (rUtilityVoltage_V <= 418.0) AND (rUtilityFreq_Hz >= 57.5) AND (rUtilityFreq_Hz <= 62.5);
bGenHealthy     := (rGenVoltage_V >= 350.0) AND (rGenVoltage_V <= 410.0) AND (rGenFreq_Hz >= 58.0) AND (rGenFreq_Hz <= 62.0);

(* 2. Critical Safety Interlock *)
IF bEmergencyStop OR NOT bOilPressureOK OR NOT bCoolantTempOK THEN
    iState             := 99;
    bCmdFuelSolenoid   := FALSE;
    bCmdStarterMotor   := FALSE;
    bCmdCloseMains_52R := FALSE;
    bCmdCloseGen_52G   := FALSE;
    bAlarmGeneral      := TRUE;
    RETURN;
END_IF;

(* 3. Main ATS State Machine *)
CASE iState OF
    0: (* STANDBY ON UTILITY *)
        bCmdFuelSolenoid   := FALSE;
        bCmdStarterMotor   := FALSE;
        bCmdCloseGen_52G   := FALSE;
        bCmdCloseMains_52R := bUtilityHealthy AND NOT bFbkBreakerGen;
        IF bAutoMode AND NOT bUtilityHealthy THEN
            rTimer_s := 0.0;
            iState   := 1;
        END_IF;

    1: (* MAINS FAILURE CONFIRMATION DELAY (3.0 s) *)
        bCmdCloseMains_52R := FALSE;
        rTimer_s := rTimer_s + rDt_s;
        IF bUtilityHealthy THEN
            iState := 0;
        ELSIF rTimer_s >= 3.0 THEN
            iCrankAttempts := 1;
            rTimer_s       := 0.0;
            iState         := 2;
        END_IF;

    2: (* ENGINE CRANKING (Max 3 attempts of 8s crank) *)
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G   := FALSE;
        bCmdFuelSolenoid   := TRUE;
        bCmdStarterMotor   := TRUE;
        rTimer_s           := rTimer_s + rDt_s;
        IF bGenHealthy THEN
            bCmdStarterMotor := FALSE;
            rTimer_s         := 0.0;
            iState           := 3;
        ELSIF rTimer_s >= 8.0 THEN
            bCmdStarterMotor := FALSE;
            IF iCrankAttempts >= 3 THEN
                bCmdFuelSolenoid := FALSE;
                bAlarmGeneral    := TRUE;
                iState           := 99;
            ELSE
                iCrankAttempts := iCrankAttempts + 1;
                rTimer_s       := 0.0;
            END_IF;
        END_IF;

    3: (* GENERATOR WARM-UP & VOLTAGE STABILIZATION (5.0 s) *)
        bCmdFuelSolenoid   := TRUE;
        bCmdStarterMotor   := FALSE;
        bCmdCloseMains_52R := FALSE;
        rTimer_s           := rTimer_s + rDt_s;
        IF NOT bGenHealthy THEN
            iState := 2;
        ELSIF rTimer_s >= 5.0 AND NOT bFbkBreakerMains THEN
            bCmdCloseGen_52G := TRUE;
            rTimer_s         := 0.0;
            iState           := 4;
        END_IF;

    4: (* LOAD SUPPLIED BY GENERATOR (52-G CLOSED) *)
        bCmdFuelSolenoid   := TRUE;
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G   := NOT bFbkBreakerMains;
        IF bUtilityHealthy THEN
            rTimer_s := 0.0;
            iState   := 5;
        END_IF;

    5: (* UTILITY RETURN RETRANSFER DELAY (15.0 s) *)
        bCmdFuelSolenoid := TRUE;
        rTimer_s         := rTimer_s + rDt_s;
        IF NOT bUtilityHealthy THEN
            iState := 4;
        ELSIF rTimer_s >= 15.0 THEN
            bCmdCloseGen_52G   := FALSE;
            bCmdCloseMains_52R := NOT bFbkBreakerGen;
            rTimer_s           := 0.0;
            iState             := 6;
        END_IF;

    6: (* ENGINE UNLOADED COOLDOWN RUN (30.0 s) *)
        bCmdCloseGen_52G   := FALSE;
        bCmdCloseMains_52R := bUtilityHealthy AND NOT bFbkBreakerGen;
        bCmdFuelSolenoid   := TRUE;
        rTimer_s           := rTimer_s + rDt_s;
        IF NOT bUtilityHealthy THEN
            iState := 3;
        ELSIF rTimer_s >= 30.0 THEN
            bCmdFuelSolenoid := FALSE;
            rTimer_s         := 0.0;
            iState           := 0;
        END_IF;
END_CASE;

(* 4. Hard Electrical Interlock Assertion: Never assert both 52-R and 52-G *)
IF bCmdCloseMains_52R AND bCmdCloseGen_52G THEN
    bCmdCloseGen_52G := FALSE;
END_IF;
END_FUNCTION_BLOCK
