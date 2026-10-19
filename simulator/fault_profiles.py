"""Single source of truth for sensors, fault signatures and log event codes.

Everything synthetic (training data, live telemetry, machine logs, Knowledge
Base incidents) is derived from these definitions so the model, the logs and
the KB stay consistent with each other.

All values are SYNTHETIC and chosen to be plausible for a ~55 kW centrifugal
water pump running at 1480 rpm. They are not engineering reference values.
"""

# Feature order is the model contract: RCF CSV, XGBoost CSV, Lambda and
# SageMaker inference all use exactly this order.
FEATURES = [
    "temperature_c",          # bearing housing temperature
    "vibration_mm_s",         # overall vibration velocity RMS
    "discharge_pressure_bar",
    "flow_m3h",
    "motor_current_a",
    "rpm",
]

UNITS = {
    "temperature_c": "degC",
    "vibration_mm_s": "mm/s RMS",
    "discharge_pressure_bar": "bar",
    "flow_m3h": "m3/h",
    "motor_current_a": "A",
    "rpm": "rpm",
}

# Normal operating point: (mean, std of sensor noise)
NORMAL = {
    "temperature_c": (62.0, 1.2),
    "vibration_mm_s": (2.4, 0.22),
    "discharge_pressure_bar": (6.0, 0.08),
    "flow_m3h": (120.0, 1.8),
    "motor_current_a": (41.5, 0.7),
    "rpm": (1480.0, 3.0),
}

MACHINES = {
    "PUMP-01": {"site": "Plant A", "line": "Cooling loop 1", "offset": {"temperature_c": 0.8, "flow_m3h": 1.5}},
    "PUMP-02": {"site": "Plant A", "line": "Cooling loop 2", "offset": {"temperature_c": -0.6, "vibration_mm_s": 0.15}},
    "PUMP-03": {"site": "Plant A", "line": "Process water", "offset": {"discharge_pressure_bar": 0.1, "motor_current_a": 0.6}},
    "PUMP-04": {"site": "Plant B", "line": "Boiler feed", "offset": {"temperature_c": 1.5, "rpm": 3.0}},
    "PUMP-05": {"site": "Plant B", "line": "Wash-down", "offset": {"flow_m3h": -2.0, "vibration_mm_s": 0.1}},
}

# Class index is the XGBoost label. 0 must stay "normal".
CLASSES = ["normal", "bearing_wear", "cavitation", "seal_leak", "motor_overload", "misalignment"]

# Feature deltas at severity 1.0. Live/training data scale these by severity
# (0.0-1.0). `noise_mult` widens noise on the listed features while faulted.
FAULTS = {
    "bearing_wear": {
        "title": "Bearing wear",
        "delta": {"temperature_c": 16.0, "vibration_mm_s": 5.0, "motor_current_a": 2.0, "rpm": -5.0},
        "noise_mult": {"vibration_mm_s": 1.8},
        "log_codes": ["VIB-201", "TMP-110", "LUB-150", "TMP-190", "VIB-290"],
    },
    "cavitation": {
        "title": "Cavitation",
        "delta": {"temperature_c": 3.0, "vibration_mm_s": 3.0, "discharge_pressure_bar": -1.6,
                  "flow_m3h": -22.0, "motor_current_a": -3.0, "rpm": 4.0},
        "noise_mult": {"vibration_mm_s": 3.0, "discharge_pressure_bar": 3.0, "flow_m3h": 2.5},
        "log_codes": ["PRS-305", "FLW-320", "VIB-202"],
    },
    "seal_leak": {
        "title": "Mechanical seal leak",
        "delta": {"temperature_c": 2.0, "vibration_mm_s": 0.6, "discharge_pressure_bar": -1.1,
                  "flow_m3h": -10.0, "motor_current_a": 1.0},
        "noise_mult": {},
        "log_codes": ["SEL-510", "PRS-306", "SEL-590", "FLW-320"],
    },
    "motor_overload": {
        "title": "Motor overload",
        "delta": {"temperature_c": 14.0, "vibration_mm_s": 0.8, "discharge_pressure_bar": 0.3,
                  "flow_m3h": 2.0, "motor_current_a": 20.0, "rpm": -12.0},
        "noise_mult": {"motor_current_a": 2.0},
        "log_codes": ["ELC-410", "ELC-412", "ELC-490", "TMP-110"],
    },
    "misalignment": {
        "title": "Shaft misalignment",
        "delta": {"temperature_c": 7.0, "vibration_mm_s": 4.0, "flow_m3h": -2.0, "motor_current_a": 3.5},
        "noise_mult": {"vibration_mm_s": 1.4},
        "log_codes": ["VIB-205", "VIB-201", "TMP-110"],
        # Misalignment is typically preceded by maintenance on the coupling.
        "precursor_codes": ["MNT-610"],
    },
}

# level, short name, message template. {v} = relevant value, {m} = machine.
EVENT_CODES = {
    "SYS-001": ("INFO", "Heartbeat", "Controller heartbeat OK, uptime {v} h"),
    "SYS-002": ("INFO", "Pump start", "Pump start command executed by PLC"),
    "SYS-003": ("INFO", "Pump stop", "Pump stop command executed by PLC"),
    "OPS-020": ("INFO", "Shift handover", "Shift handover logged, no open issues reported"),
    "CTL-030": ("INFO", "Setpoint change", "Flow setpoint changed to {v} m3/h by operator"),
    "MNT-601": ("INFO", "Routine inspection", "Routine visual inspection completed, no findings"),
    "MNT-610": ("INFO", "Coupling work", "Coupling element replaced and shaft re-aligned (work order {v})"),
    "MNT-615": ("INFO", "Bearing regrease", "Drive-end and non-drive-end bearings regreased"),
    "MNT-620": ("INFO", "Fault cleared", "Maintenance reset: pump inspected and returned to normal operation (work order {v})"),
    "LUB-150": ("WARN", "Lubrication overdue", "Bearing lubrication interval overdue by {v} h"),
    "VIB-201": ("WARN", "High vibration", "Overall vibration {v} mm/s exceeds alert limit 4.5 mm/s"),
    "VIB-202": ("WARN", "Broadband vibration", "Broadband high-frequency vibration and crackling noise detected ({v} mm/s)"),
    "VIB-205": ("WARN", "Axial vibration", "Axial vibration component high, 2x running-speed peak dominant ({v} mm/s)"),
    "VIB-290": ("ERROR", "Vibration trip approach", "Vibration {v} mm/s approaching trip limit 9.0 mm/s"),
    "TMP-110": ("WARN", "Bearing temperature high", "Bearing temperature {v} degC exceeds alert limit 72 degC"),
    "TMP-190": ("ERROR", "Bearing temperature critical", "Bearing temperature {v} degC approaching trip limit 85 degC"),
    "PRS-305": ("WARN", "Low suction pressure", "Suction pressure low, NPSH margin reduced (discharge {v} bar)"),
    "PRS-306": ("WARN", "Discharge pressure decay", "Discharge pressure decaying slowly, now {v} bar"),
    "FLW-320": ("WARN", "Flow below setpoint", "Flow {v} m3/h below setpoint 120 m3/h"),
    "SEL-510": ("WARN", "Seal leak detector", "Seal leak detector reports wet condition"),
    "SEL-590": ("ERROR", "Seal leak rate high", "Seal leak rate above limit, drain sump level rising"),
    "ELC-410": ("WARN", "Motor overcurrent", "Motor current {v} A exceeds rated 48 A"),
    "ELC-412": ("WARN", "Phase imbalance", "Phase current imbalance {v}% detected"),
    "ELC-490": ("ERROR", "Thermal overload pre-trip", "Motor thermal overload relay at pre-trip, current {v} A"),
    "OPS-099": ("INFO", "Operator note", "{v}"),
}

ROUTINE_CODES = ["SYS-001", "OPS-020", "CTL-030", "MNT-601"]

# The workshop simulates ONE pump per run.
SIM_MACHINE_ID = "PUMP-01"

# Alert limits used for log emission (and quoted in KB docs).
LIMITS = {
    "vibration_alert": 4.5, "vibration_trip": 9.0,
    "temp_alert": 72.0, "temp_trip": 85.0,
    "current_rated": 48.0,
}
