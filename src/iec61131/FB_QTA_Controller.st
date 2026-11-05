(* Conceptual IEC 61131-3 state machine for an open-transition QTA.
   This source is not safety-rated or approved for direct plant use.
   State IDs match the simulation model and drawing P12-07. *)

FUNCTION_BLOCK FB_QTA_Controller
VAR_INPUT
    bAutoMode           : BOOL := TRUE;
    bEmergencyStop      : BOOL := FALSE;
    rUtilityVoltage_V   : REAL := 380.0;
    rUtilityFreq_Hz     : REAL := 60.0;
    rGenVoltage_V       : REAL := 0.0;
    rGenFreq_Hz         : REAL := 0.0;
    bOilPressureOK      : BOOL := TRUE;
    bCoolantTempOK      : BOOL := TRUE;
    bFbkBreakerMains    : BOOL := FALSE;
    bFbkBreakerGen      : BOOL := FALSE;
    rDt_s               : REAL := 0.1;
END_VAR

VAR_OUTPUT
    iState              : INT := 0;  (* 0 standby, 1 utility delay, 2 crank, 3 rest, 4 stabilize, 5 transfer to GMG, 6 GMG load, 7 utility return delay, 8 transfer to utility, 9 cooldown, 99 fault *)
    bCmdFuelSolenoid    : BOOL := FALSE;
    bCmdStarterMotor    : BOOL := FALSE;
    bCmdCloseMains_52R  : BOOL := FALSE;
    bCmdCloseGen_52G    : BOOL := FALSE;
    bAlarmGeneral       : BOOL := FALSE;
    iCrankAttempts      : INT := 0;
END_VAR

VAR
    rTimer_s            : REAL := 0.0;
    bUtilityHealthy     : BOOL := TRUE;
    bGenHealthy         : BOOL := FALSE;
END_VAR

bUtilityHealthy := (rUtilityVoltage_V >= 323.0) AND (rUtilityVoltage_V <= 418.0)
                   AND (rUtilityFreq_Hz >= 57.0) AND (rUtilityFreq_Hz <= 63.0);
bGenHealthy := (rGenVoltage_V >= 372.4) AND (rGenVoltage_V <= 387.6)
               AND (rGenFreq_Hz >= 59.4) AND (rGenFreq_Hz <= 60.6);

IF rDt_s <= 0.0 THEN
    iState := 99;
    bAlarmGeneral := TRUE;
END_IF;

IF bEmergencyStop OR (bGenHealthy AND (NOT bOilPressureOK OR NOT bCoolantTempOK))
   OR (bFbkBreakerMains AND bFbkBreakerGen) THEN
    iState := 99;
    bAlarmGeneral := TRUE;
END_IF;

IF iState = 99 THEN
    bCmdFuelSolenoid := FALSE;
    bCmdStarterMotor := FALSE;
    bCmdCloseMains_52R := FALSE;
    bCmdCloseGen_52G := FALSE;
    bAlarmGeneral := TRUE;
    RETURN;
END_IF;

CASE iState OF
    0: (* Utility standby *)
        bCmdFuelSolenoid := FALSE;
        bCmdStarterMotor := FALSE;
        bCmdCloseGen_52G := FALSE;
        bCmdCloseMains_52R := bUtilityHealthy AND NOT bFbkBreakerGen;
        rTimer_s := 0.0;
        IF bAutoMode AND NOT bUtilityHealthy THEN
            iState := 1;
        END_IF;

    1: (* Confirm utility failure for 3 s *)
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G := FALSE;
        bCmdFuelSolenoid := FALSE;
        bCmdStarterMotor := FALSE;
        rTimer_s := rTimer_s + rDt_s;
        IF bUtilityHealthy THEN
            rTimer_s := 0.0;
            iState := 0;
        ELSIF rTimer_s >= 3.0 THEN
            iCrankAttempts := 1;
            rTimer_s := 0.0;
            iState := 2;
        END_IF;

    2: (* Crank for up to 5 s *)
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G := FALSE;
        bCmdFuelSolenoid := TRUE;
        bCmdStarterMotor := TRUE;
        rTimer_s := rTimer_s + rDt_s;
        IF bGenHealthy THEN
            bCmdStarterMotor := FALSE;
            rTimer_s := 0.0;
            iState := 4;
        ELSIF rTimer_s >= 5.0 THEN
            bCmdStarterMotor := FALSE;
            rTimer_s := 0.0;
            iState := 3;
        END_IF;

    3: (* 5 s rest between attempts *)
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G := FALSE;
        bCmdFuelSolenoid := TRUE;
        bCmdStarterMotor := FALSE;
        rTimer_s := rTimer_s + rDt_s;
        IF bGenHealthy THEN
            rTimer_s := 0.0;
            iState := 4;
        ELSIF rTimer_s >= 5.0 THEN
            IF iCrankAttempts >= 3 THEN
                bCmdFuelSolenoid := FALSE;
                bAlarmGeneral := TRUE;
                iState := 99;
            ELSE
                iCrankAttempts := iCrankAttempts + 1;
                rTimer_s := 0.0;
                iState := 2;
            END_IF;
        END_IF;

    4: (* 5 s generator stabilization *)
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G := FALSE;
        bCmdFuelSolenoid := TRUE;
        bCmdStarterMotor := FALSE;
        rTimer_s := rTimer_s + rDt_s;
        IF NOT bGenHealthy THEN
            IF iCrankAttempts >= 3 THEN
                bCmdFuelSolenoid := FALSE;
                bAlarmGeneral := TRUE;
                iState := 99;
            ELSE
                iCrankAttempts := iCrankAttempts + 1;
                rTimer_s := 0.0;
                iState := 2;
            END_IF;
        ELSIF rTimer_s >= 5.0 THEN
            rTimer_s := 0.0;
            iState := 5;
        END_IF;

    5: (* Open 52-R, prove open, then 1.5 s dead time *)
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G := FALSE;
        bCmdFuelSolenoid := TRUE;
        bCmdStarterMotor := FALSE;
        IF NOT bGenHealthy THEN
            bAlarmGeneral := TRUE;
            iState := 99;
        ELSIF bFbkBreakerMains THEN
            rTimer_s := 0.0;
        ELSE
            rTimer_s := rTimer_s + rDt_s;
            IF rTimer_s >= 1.5 THEN
                bCmdCloseGen_52G := TRUE;
                rTimer_s := 0.0;
                iState := 6;
            END_IF;
        END_IF;

    6: (* Generator on load *)
        bCmdFuelSolenoid := TRUE;
        bCmdStarterMotor := FALSE;
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G := NOT bFbkBreakerMains;
        IF NOT bGenHealthy THEN
            bAlarmGeneral := TRUE;
            iState := 99;
        ELSIF bUtilityHealthy THEN
            rTimer_s := 0.0;
            iState := 7;
        END_IF;

    7: (* Utility must remain healthy for 120 s *)
        bCmdFuelSolenoid := TRUE;
        bCmdStarterMotor := FALSE;
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G := NOT bFbkBreakerMains;
        rTimer_s := rTimer_s + rDt_s;
        IF NOT bUtilityHealthy THEN
            rTimer_s := 0.0;
            iState := 6;
        ELSIF rTimer_s >= 120.0 THEN
            bCmdCloseGen_52G := FALSE;
            rTimer_s := 0.0;
            iState := 8;
        END_IF;

    8: (* Open 52-G, prove open, then 1.5 s dead time *)
        bCmdFuelSolenoid := TRUE;
        bCmdStarterMotor := FALSE;
        bCmdCloseMains_52R := FALSE;
        bCmdCloseGen_52G := FALSE;
        IF NOT bUtilityHealthy THEN
            rTimer_s := 0.0;
            IF bGenHealthy THEN
                iState := 5;
            ELSE
                iState := 99;
                bAlarmGeneral := TRUE;
            END_IF;
        ELSIF bFbkBreakerGen THEN
            rTimer_s := 0.0;
        ELSE
            rTimer_s := rTimer_s + rDt_s;
            IF rTimer_s >= 1.5 THEN
                bCmdCloseMains_52R := TRUE;
                rTimer_s := 0.0;
                iState := 9;
            END_IF;
        END_IF;

    9: (* 180 s no-load cool-down *)
        bCmdFuelSolenoid := TRUE;
        bCmdStarterMotor := FALSE;
        bCmdCloseGen_52G := FALSE;
        bCmdCloseMains_52R := bUtilityHealthy AND NOT bFbkBreakerGen;
        IF NOT bUtilityHealthy THEN
            rTimer_s := 0.0;
            IF bGenHealthy THEN
                iState := 5;
            ELSE
                iState := 1;
            END_IF;
        ELSE
            rTimer_s := rTimer_s + rDt_s;
            IF rTimer_s >= 180.0 THEN
                bCmdFuelSolenoid := FALSE;
                iCrankAttempts := 0;
                rTimer_s := 0.0;
                iState := 0;
            END_IF;
        END_IF;

ELSE
    iState := 99;
    bAlarmGeneral := TRUE;
END_CASE;

IF bCmdCloseMains_52R AND bCmdCloseGen_52G THEN
    iState := 99;
    bAlarmGeneral := TRUE;
END_IF;
IF bCmdCloseMains_52R AND bFbkBreakerGen THEN
    bCmdCloseMains_52R := FALSE;
END_IF;
IF bCmdCloseGen_52G AND bFbkBreakerMains THEN
    bCmdCloseGen_52G := FALSE;
END_IF;
END_FUNCTION_BLOCK
