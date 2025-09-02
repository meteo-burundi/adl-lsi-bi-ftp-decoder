from __future__ import annotations

import csv
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from adl_ftp_plugin.registries import FTPDecoder

MISSING_SENTINELS = {
    "-999999",
    "-999999.00",
    "-999990",
    "-999990.00",
    "-999.99",
    "-999",
    "",
    "NA",
    "NAN",
}

# Canonical field mapping: regex for the variable label -> (canonical_key, allowed_stats, preferred_stat)
CANONICAL_MAP = {
    r"\bBATTVoltage\b": ("battery_voltage", {"Inst", "Ave"}, "Inst"),
    r"\bINsideTEMP\b": ("logger_box_temperature", {"Ave", "Inst"}, "Ave"),
    r"\bRELHumidity\b": ("relative_humidity", {"Ave", "Inst"}, "Ave"),
    r"\bAIRTemp\b": ("air_temperature", {"Ave", "Inst"}, "Ave"),
    r"\bATMPressure\b": ("air_pressure", {"Ave", "Inst"}, "Ave"),  # hPa
    r"\bGLOBALRad\b": ("global_radiation", {"Ave", "Inst"}, "Ave"),  # W/m²
    r"\bWindDIR\b.*\bRisDir\b": ("wind_direction", {"RisDir"}, "RisDir"),  # degrees (resultant dir)
    r"\bWindSPEED\b": ("wind_speed", {"Ave", "Inst"}, "Ave"),  # m/s
    r"\bRAIN\b": ("precipitation_amount", {"Tot", "Inst"}, "Tot"),  # mm over interval
    r"^\s*Temperature \('C\)\s*Msr\.10": ("soil_surface_temperature", {"Ave", "Inst"}, "Ave"),
    r"\bVolMoisture\b": ("volumetric_soil_moisture", {"Ave", "Inst"}, "Ave"),
    r"\bSOILTemp\b": ("soil_temperature", {"Ave", "Inst"}, "Ave"),
    r"\bDirectRAD\b": ("direct_radiation", {"Ave", "Inst"}, "Ave"),
    r"\bSUNShine\b.*\bDuration\b": ("sunshine_duration", {"Duration"}, "Duration"),  # unit per logger setting
}

STAT_NORMALIZATION = {
    "Inst": "Inst",
    "Instantaneous": "Inst",
    "Min": "Min",
    "Ave": "Ave",
    "Avg": "Ave",
    "Max": "Max",
    "StdDev": "StdDev",
    "Tot": "Tot",
    "RisDir": "RisDir",
    "PrevDir": "PrevDir",
    "RisVel": "RisVel",
    "StdDevDir": "StdDevDir",
    "CalmPerc": "CalmPerc",
    "Duration": "Duration",
    "ValidDataPerc": "ValidDataPerc",
}


def _is_missing(s: str) -> bool:
    return s.strip().upper() in MISSING_SENTINELS


def _to_float_or_none(s: str) -> Optional[float]:
    if _is_missing(s):
        return None
    try:
        f = float(s)
        if math.isfinite(f):
            return f
    except Exception:
        return None
    return None


def _combine_headers(row_vars: List[str], row_stats: List[str]) -> List[str]:
    """Merge the two header rows into 'Variable | Stat' names."""
    
    def norm(x: str) -> str:
        return re.sub(r"\s+", " ", x.strip())
    
    v = [norm(x) for x in row_vars]
    s = [norm(x) for x in row_stats]
    if len(v) < len(s):
        v += [""] * (len(s) - len(v))
    if len(s) < len(v):
        s += [""] * (len(v) - len(s))
    return [f"{vv} | {ss}" if ss else vv for vv, ss in zip(v, s)]


def _extract_var_and_stat(combined_header: str) -> tuple[str, Optional[str]]:
    if " | " in combined_header:
        left, right = combined_header.split(" | ", 1)
        stat = STAT_NORMALIZATION.get(right.strip(), right.strip())
        return left.strip(), stat
    return combined_header.strip(), None


def _choose_canonical(left_name: str, stat: Optional[str]) -> Optional[str]:
    for pattern, (canonical, allowed_stats, preferred) in CANONICAL_MAP.items():
        if re.search(pattern, left_name, flags=re.IGNORECASE):
            # WindDIR and SUNShine Duration keys encode preferred stat in mapping; accept immediately
            if preferred in {"RisDir", "Duration"}:
                return canonical
            chosen = stat or preferred
            if chosen in allowed_stats:
                return canonical
            return canonical  # fall back to our canonical even if stat wording is off
    return None


class LSIBurundiFTPDecoder(FTPDecoder):
    type = "lsi_burundi"
    compat_type = "lsi_burundi"
    display_name = "LSI Decoder - Burundi"
    
    def decode(self, file_path: str) -> List[dict]:
        """
        Parse the file and return list of dicts (observation_time, values).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        
        # Read lines, drop blank-only lines
        raw_lines: List[str] = path.read_text(encoding="utf-8", errors="replace").splitlines()
        rows_src = [ln for ln in raw_lines if ln.strip()]
        
        if len(rows_src) < 3:
            return []
        
        # Heuristic delimiter detection (tab vs comma)
        delimiter = "\t" if rows_src[0].count("\t") >= rows_src[0].count(",") else ","
        reader = csv.reader(rows_src, delimiter=delimiter)
        rows = list(reader)
        
        header_vars = rows[0]
        header_stats = rows[1]
        combined_headers = _combine_headers(header_vars, header_stats)
        
        # Locate timestamp column
        ts_idx = None
        for i, h in enumerate(combined_headers):
            left, _ = _extract_var_and_stat(h)
            if re.search(r"\bDate/?time\b", left, flags=re.IGNORECASE):
                ts_idx = i
                break
        if ts_idx is None:
            raise ValueError("Timestamp column (Date/time) not found")
        
        # Build data-column → canonical key map
        index_to_canonical: Dict[int, str] = {}
        for idx, h in enumerate(combined_headers):
            if idx == ts_idx:
                continue
            left, stat = _extract_var_and_stat(h)
            canonical = _choose_canonical(left, stat)
            if not canonical:
                continue
            
            # Only keep our preferred stat per canonical key
            if re.search(r"\bWindDIR\b", left, flags=re.IGNORECASE):
                if "RisDir" not in h and (stat or "") != "RisDir":
                    continue
            if "RAIN" in left.upper() and not ("Tot" in h or (stat or "") == "Tot"):
                continue
            
            # Keep the first seen index per canonical to avoid duplicates
            if canonical not in index_to_canonical.values():
                index_to_canonical[idx] = canonical
        
        out: List[dict] = []
        for row in rows[2:]:
            if len(row) <= ts_idx:
                continue
            ts_raw = row[ts_idx].strip()
            if not ts_raw:
                continue
            
            # Parse ISO or "YYYY-MM-DD HH:MM:SS"
            obs_time: Optional[datetime] = None
            try:
                obs_time = datetime.fromisoformat(ts_raw)
            except Exception:
                try:
                    obs_time = datetime.fromisoformat(ts_raw.replace(" ", "T"))
                except Exception:
                    continue  # skip unparseable rows
            
            values: Dict[str, Optional[Union[float, int]]] = {}
            
            for idx, canonical in index_to_canonical.items():
                if idx >= len(row):
                    continue
                v = row[idx]
                num = _to_float_or_none(v)
                values[canonical] = num
            
            # Only append rows that carry at least one usable value
            if any(v is not None for v in values.values()):
                out.append(
                    {
                        "observation_time": obs_time.isoformat(),
                        "values": values,
                    }
                )
        return out
