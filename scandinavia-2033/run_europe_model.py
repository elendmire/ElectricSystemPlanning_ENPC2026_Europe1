"""
Run the official ERAA-PyPSA European model (my_little_europe_lt_uc.py) for a full year,
WITHOUT touching the user's input files.

The repository is copied to a temporary folder, the two input JSON files are written there,
the model is run, and the result files are copied to scandinavia-2033/data/europe_runs/<run_name>/.

Usage (from the repository root, with the project .venv):
    .venv/bin/python scandinavia-2033/run_europe_model.py baseline_2025
    .venv/bin/python scandinavia-2033/run_europe_model.py reference_2033
    .venv/bin/python scandinavia-2033/run_europe_model.py plan_S3 scandinavia-2033/scandinavia.json
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
ERAA = ROOT / "data" / "ERAA_2023-2"
COUNTRIES = ["benelux", "france", "germany", "iberian-peninsula", "italy", "poland", "scandinavia"]

# ERAA production type (generation-capa csv) -> aggregated type used by the official model
ERAA_TO_AGG = {
    "Batteries": "batteries", "Biofuel": "biofuel", "Demand Side Response capacity": "dsr", "Gas": "gas",
    "Hard Coal": "coal", "Lignite": "coal", "Coal": "coal", "Hydro - Pondage": "hydro_pondage",
    "Hydro - Pump Storage Closed Loop": "hydro_pump_storage_closed_loop",
    "Hydro - Pump Storage Open Loop": "hydro_pump_storage_open_loop", "Hydro - Reservoir": "hydro_reservoir",
    "Hydro - Run of River": "hydro_run_of_river", "Nuclear": "nuclear", "Oil": "oil",
    "Others non-renewable": "others_fatal", "Others renewable": "others_fatal", "Solar PV": "solar_pv",
    "Solar Thermal": "solar_thermal", "Wind Offshore": "wind_offshore", "Wind Onshore": "wind_onshore",
}


def eraa_capacities(country: str, year: int) -> dict:
    """Aggregated power capacities (MW) from the ERAA csv; storage = injection/turbine power."""
    df = pd.read_csv(ERAA / "generation_capas" / f"generation-capa_{year}_{country}.csv", sep=";")
    df["production_type"] = df["production_type"].str.strip()
    out = {}
    for _, r in df.iterrows():
        agg = ERAA_TO_AGG.get(r["production_type"])
        if agg is None:
            continue
        p = max(r["power_capacity"], r["power_capacity_turbine"], r["power_capacity_injection"])
        out[agg] = out.get(agg, 0.0) + float(p)
    return {k: round(v, 2) for k, v in out.items() if v > 0}


def eraa_intercos(year: int, factor: float = 1.0) -> dict:
    df = pd.read_csv(ERAA / "interco_capas" / f"interco-capas_{year}.csv", sep=";")
    caps = {}
    for _, r in df.iterrows():
        caps[f"{r.zone_origin}2{r.zone_destination}"] = caps.get(f"{r.zone_origin}2{r.zone_destination}", 0) + r.value
    return {k: int(round(v * factor)) for k, v in caps.items()}  # official checker requires int values


def run(run_name: str, target_year: int, capacities: dict, intercos: dict, climatic_year: int = 1989,
        period_start: str = "1900/1/1", period_end: str = "1900/12/30"):
    out_dir = HERE / "data" / "europe_runs" / run_name
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for item in ["src", "data", "input", "my_little_europe_lt_uc.py"]:
            s = ROOT / item
            (shutil.copytree if s.is_dir() else shutil.copy)(s, tmp / item)
        (tmp / ".git").mkdir()  # the official code locates the project root via a .git folder
        (tmp / "output" / "long_term_uc").mkdir(parents=True)

        p = tmp / "input/long_term_uc/elec-europe_params_to-be-modif.json"
        params = json.loads(p.read_text())
        params.update({"selected_countries": COUNTRIES, "selected_target_year": target_year,
                       "selected_climatic_year": climatic_year, "mode": "solo", "team": "scandinavia",
                       "uc_period_start": period_start, "uc_period_end": period_end, "output_tag": run_name})
        params["interco_capas_tb_overwritten"] = {**params.get("interco_capas_tb_overwritten", {}), **intercos}
        p.write_text(json.dumps(params, indent=2))
        (tmp / "input/long_term_uc/countries/scandinavia.json").write_text(json.dumps(
            {"team": "scandinavia", "selected_prod_types": {}, "capacities_tb_overwritten": capacities}, indent=2))

        log = subprocess.run([sys.executable, "my_little_europe_lt_uc.py"], cwd=tmp, capture_output=True, text=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "run.log").write_text(log.stdout + log.stderr)
        res = tmp / "output/long_term_uc" / f"data_{run_name}"
        if not res.exists():
            raise RuntimeError(f"Run {run_name} failed, see {out_dir / 'run.log'}")
        for f in res.iterdir():
            if f.suffix in (".csv", ".json"):
                shutil.copy(f, out_dir / f.name)
        figs = tmp / "output/long_term_uc" / f"figures_{run_name}"
        if figs.exists():
            shutil.copytree(figs, out_dir / "figures", dirs_exist_ok=True)
        (out_dir / "run_inputs.json").write_text(json.dumps(
            {"target_year": target_year, "climatic_year": climatic_year, "capacities": capacities,
             "intercos": intercos}, indent=2))
    print(f"{run_name}: done -> {out_dir}")


if __name__ == "__main__":
    name = sys.argv[1]
    if name == "baseline_2025":
        # Today's system: 2025 capacities and 2025 interconnections everywhere
        run(name, 2025, {c: eraa_capacities(c, 2025) for c in COUNTRIES}, eraa_intercos(2025))
    elif name == "reference_2033":
        # Neighbours as planned by ERAA 2033, interconnections doubled vs today (European target)
        run(name, 2033, {c: eraa_capacities(c, 2033) for c in COUNTRIES}, eraa_intercos(2025, factor=2))
    elif name.startswith("plan"):
        # Same as reference, but Scandinavia with the capacities of a plan file, e.g.
        #   run_europe_model.py plan_S3 scandinavia-2033/results/scandinavia_S3.json
        plan_file = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "scandinavia.json"
        plan = json.loads(plan_file.read_text())["capacities_tb_overwritten"]["scandinavia"]
        caps = {c: eraa_capacities(c, 2033) for c in COUNTRIES}
        caps["scandinavia"] = plan
        run(name, 2033, caps, eraa_intercos(2025, factor=2))
    else:
        raise SystemExit(f"unknown run {name}")
