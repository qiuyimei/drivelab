"""Reproduce the narrow comma2k19 CSV extract; no application code is imported.

Only the repository's original one-minute CAN speed/steering sample is used.
There is no video, image, location, gyro, pressure or invented channel here.
"""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "original"
COMMIT = "4c7f1a6e1957745beadc1def0e7225f559b09a2a"
SEGMENT = "Example_1/b0c9d2329ad1606b|2018-08-02--08-34-47/40"
BASE = f"https://raw.githubusercontent.com/commaai/comma2k19/{COMMIT}/{SEGMENT.replace('|', '%7C')}/processed_log/CAN"
FILES = {
    "speed_t.npy": ("speed/t", "db54caa7d3f53611713bc5f8a82d2c19950d251a"),
    "speed_value.npy": ("speed/value", "6da9b94fbcfaaac9fe57dd53e5fe1f38d18970c4"),
    "steering_t.npy": ("steering_angle/t", "6fd8d82b1373588e3138b80e9d47f1fe0c22d3e0"),
    "steering_value.npy": ("steering_angle/value", "662e677be5f2ea19d76d5478fde21ec80935bd59"),
}

manifest = []
for filename, (source, expected_blob) in FILES.items():
    raw = (ORIGINAL / filename).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == expected_blob, (filename, blob, expected_blob)
    manifest.append({"local_file": "original/" + filename, "url": BASE + "/" + source,
                     "bytes": len(raw), "git_blob_sha1": blob,
                     "sha256": hashlib.sha256(raw).hexdigest()})

speed_t = np.load(ORIGINAL / "speed_t.npy", allow_pickle=False).reshape(-1)
speed = np.load(ORIGINAL / "speed_value.npy", allow_pickle=False).reshape(-1)
steering_t = np.load(ORIGINAL / "steering_t.npy", allow_pickle=False).reshape(-1)
steering = np.load(ORIGINAL / "steering_value.npy", allow_pickle=False).reshape(-1)
assert len(speed_t) == len(speed) and len(steering_t) == len(steering)
assert all(np.isfinite(x).all() for x in (speed_t, speed, steering_t, steering))
assert np.all(np.diff(speed_t) > 0) and np.all(np.diff(steering_t) > 0)

# Keep original CAN speed sample times only inside BOTH series' observed ranges.
# Steering is linearly interpolated onto these times; no value is extrapolated.
valid = (speed_t >= steering_t[0]) & (speed_t <= steering_t[-1])
kept_t = speed_t[valid]
kept_speed = speed[valid]
aligned_steering = np.interp(kept_t, steering_t, steering)
origin = float(kept_t[0])
relative_t = kept_t - origin
output = ROOT / "comma2k19-public-sample.csv"
with output.open("w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["time_s", "speed_mps", "steering_angle_deg"])
    for t, v, angle in zip(relative_t, kept_speed, aligned_steering):
        writer.writerow([f"{t:.9f}", f"{v:.9f}", f"{angle:.9f}"])

metadata = {
    "id": "comma2k19-public-sample",
    "display_name": "公开实测日志导入示例 · comma2k19",
    "classification": "public_measured_log_excerpt",
    "not_model_validation": True,
    "description": "公开实测数据的导入、单位和时间轴演示；不是本项目车辆动力学模型的实车标定证明。",
    "source_repository": "https://github.com/commaai/comma2k19",
    "source_commit": COMMIT,
    "source_segment": SEGMENT,
    "vehicle": "Toyota RAV4 (repository README identifies this dongle ID as RAV4)",
    "source_license": "MIT",
    "source_copyright": "Copyright (c) 2018 comma.ai",
    "license_file": "original/LICENSE-comma2k19.txt",
    "license_url": f"https://github.com/commaai/comma2k19/blob/{COMMIT}/LICENSE",
    "publication": {"title": "A Commute in Data: The comma2k19 Dataset", "authors": "Harald Schafer, Eder Santana, Andrew Haden, Riccardo Biasini", "year": 2018, "url": "https://arxiv.org/abs/1812.05752v1"},
    "units_source_url": f"https://github.com/commaai/comma2k19/blob/{COMMIT}/README.md#log-format",
    "steering_definition_source_url": "https://raw.githubusercontent.com/commaai/cereal/ab79999e5dc2de25c3eb0c9acbed47c9e81f5d79/car.capnp",
    "steering_definition_note": "The dataset's pinned openpilot submodule uses this cereal schema, where CarState.steeringAngle is under the 'steering wheel' section and measured in degrees. The exported dataset field itself is named CAN/steering_angle.",
    "available_channels": {"time_s": "seconds relative to first retained CAN speed sample", "speed_mps": "original CAN speed in m/s, not km/h", "steering_angle_deg": "CAN steering angle in degrees; steering-wheel convention of pinned openpilot schema"},
    "missing_channels": ["yaw_rate", "brake_pressure"],
    "original_time_basis": "device boot time in seconds",
    "original_speed_time_start_s": float(speed_t[0]),
    "original_speed_time_end_s": float(speed_t[-1]),
    "original_steering_time_start_s": float(steering_t[0]),
    "original_steering_time_end_s": float(steering_t[-1]),
    "retained_original_time_start_s": origin,
    "retained_original_time_end_s": float(kept_t[-1]),
    "duration_s": float(relative_t[-1]),
    "rows": len(kept_t),
    "original_speed_rows": len(speed_t),
    "original_steering_rows": len(steering_t),
    "dropped_speed_rows_outside_common_time": int((~valid).sum()),
    "speed_range_mps": [float(kept_speed.min()), float(kept_speed.max())],
    "steering_range_deg": [float(aligned_steering.min()), float(aligned_steering.max())],
    "transformations": ["Verify each downloaded binary against its Git blob SHA-1 from the pinned official tree.", "Read NumPy arrays with allow_pickle=False; require finite data and strictly increasing timestamps.", "Keep speed samples only within steering's observed time interval; do not extrapolate.", "Linearly interpolate steering on retained original speed sample timestamps; preserve speed measurements unchanged.", "Subtract the first retained CAN speed time to produce relative seconds; retain original time interval in metadata.", "Serialize to 9 decimal places. Do not filter, smooth, rescale speed, invent yaw/pressure, or derive a vehicle-model validation score."],
    "csv_file": output.name,
    "csv_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    "files": manifest,
    "suitability": {"allowed_demo_claims": ["Can parse a real public CAN log excerpt", "Can convert m/s to km/h", "Can handle asynchronous speed and steering sample times with documented linear interpolation", "Can retain missing channels as missing"], "prohibited_claims": ["The lightweight dynamics model has been validated or calibrated on this vehicle", "The excerpt reproduces a known controlled braking or lane-change experiment", "The dataset supplies brake pressure", "Phone gyro Z is automatically the platform's vehicle yaw-rate without frame/calibration verification"]}
}
(ROOT / "comma2k19-public-sample.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: metadata[k] for k in ("rows", "duration_s", "speed_range_mps", "steering_range_deg", "dropped_speed_rows_outside_common_time", "csv_sha256")}, ensure_ascii=False))
