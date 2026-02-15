#!/usr/bin/env python3
"""Collect host/container metrics and push them to Spark Swarm."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def _read_cpu_totals() -> tuple[float, float]:
    with open('/proc/stat', encoding='utf-8') as handle:
        first = handle.readline().strip()
    parts = first.split()
    if not parts or parts[0] != 'cpu' or len(parts) < 5:
        raise ValueError('unexpected /proc/stat format')

    values = [float(value) for value in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0.0)
    total = sum(values)
    return idle, total


def read_cpu_percent(sample_seconds: float = 0.2) -> float:
    idle_a, total_a = _read_cpu_totals()
    time.sleep(sample_seconds)
    idle_b, total_b = _read_cpu_totals()

    total_delta = total_b - total_a
    idle_delta = idle_b - idle_a
    if total_delta <= 0:
        return 0.0

    busy_ratio = 1.0 - (idle_delta / total_delta)
    return max(0.0, min(100.0, busy_ratio * 100.0))


def read_memory_snapshot() -> tuple[int, float]:
    values: dict[str, int] = {}
    with open('/proc/meminfo', encoding='utf-8') as handle:
        for line in handle:
            key, raw = line.split(':', 1)
            values[key] = int(raw.strip().split()[0])

    total_kib = values.get('MemTotal', 0)
    available_kib = values.get('MemAvailable', 0)
    if total_kib <= 0:
        return 0, 0.0

    used_kib = max(0, total_kib - available_kib)
    percent = max(0.0, min(100.0, (used_kib / total_kib) * 100.0))
    return used_kib * 1024, percent


def read_disk_snapshot() -> tuple[int, float]:
    usage = shutil.disk_usage('/')
    if usage.total <= 0:
        return 0, 0.0
    percent = max(0.0, min(100.0, (usage.used / usage.total) * 100.0))
    return usage.used, percent


def _parse_percent(raw: str) -> float:
    text = raw.strip().rstrip('%')
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_bytes(raw: str) -> int:
    text = raw.strip()
    match = re.match(r'^([0-9]*\.?[0-9]+)\s*([A-Za-z]+)?$', text)
    if not match:
        return 0

    value = float(match.group(1))
    unit = (match.group(2) or 'B').lower()

    binary_units = {
        'b': 1,
        'kib': 1024,
        'mib': 1024**2,
        'gib': 1024**3,
        'tib': 1024**4,
        'pib': 1024**5,
    }
    decimal_units = {
        'kb': 1000,
        'mb': 1000**2,
        'gb': 1000**3,
        'tb': 1000**4,
        'pb': 1000**5,
    }

    if unit in binary_units:
        return int(value * binary_units[unit])
    if unit in decimal_units:
        return int(value * decimal_units[unit])
    return int(value)


def _normalize_service_name(container_name: str) -> str:
    name = container_name.strip().replace('_', '-')
    prefix = 'platform-infra-'
    if name.startswith(prefix):
        name = name[len(prefix):]
    name = re.sub(r'-\d+$', '', name)
    return name


def collect_container_metrics() -> list[dict[str, object]]:
    command = [
        'docker',
        'stats',
        '--no-stream',
        '--format',
        '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}',
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print('docker not found; skipping container metrics', file=sys.stderr)
        return []
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or '').strip()
        print(f'docker stats failed; skipping container metrics: {stderr}', file=sys.stderr)
        return []

    containers: list[dict[str, object]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue

        parts = line.split('|', 3)
        if len(parts) != 4:
            continue

        name_raw, cpu_raw, mem_usage_raw, mem_perc_raw = parts
        memory_bytes_raw = mem_usage_raw.split('/', 1)[0].strip()

        containers.append(
            {
                'name': _normalize_service_name(name_raw),
                'cpu_percent': round(_parse_percent(cpu_raw), 2),
                'memory_bytes': _parse_bytes(memory_bytes_raw),
                'memory_percent': round(_parse_percent(mem_perc_raw), 2),
            }
        )

    return containers


def build_payload() -> dict[str, object]:
    host_name = os.getenv('METRICS_HOST_NAME', 'platform')
    memory_bytes, memory_percent = read_memory_snapshot()
    disk_bytes, disk_percent = read_disk_snapshot()
    payload = {
        'host': host_name,
        'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'metrics': {
            'cpu_percent': round(read_cpu_percent(), 2),
            'memory_bytes': float(memory_bytes),
            'memory_percent': round(memory_percent, 2),
            'disk_bytes': float(disk_bytes),
            'disk_percent': round(disk_percent, 2),
        },
        'containers': collect_container_metrics(),
    }
    return payload


def push_payload(payload: dict[str, object]) -> None:
    api_key = os.getenv('SPARK_SWARM_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('SPARK_SWARM_API_KEY is required')

    endpoint = os.getenv(
        'METRICS_INGEST_URL',
        'https://sparkswarm.com/api/v1/metrics/ingest',
    ).strip()

    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        endpoint,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            response_body = response.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'metrics ingest failed ({exc.code}): {detail}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'metrics ingest connection failed: {exc.reason}') from exc

    if status >= 400:
        raise RuntimeError(f'metrics ingest failed ({status}): {response_body}')

    print(f'metrics ingest ok ({status})')


def main() -> int:
    try:
        payload = build_payload()
        push_payload(payload)
    except Exception as exc:  # noqa: BLE001
        print(f'metrics collector error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
