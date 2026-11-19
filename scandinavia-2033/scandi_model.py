"""
Scandinavia 2033 - hourly capacity planning / dispatch model (one year), PuLP + HiGHS.

Same cost logic as data_crunch.ipynb Appendix D (annualised CAPEX + FOM + fuel + CO2 + VOM),
extended with what Scandinavia needs:
  * hydro reservoirs with weekly inflows and a 109 TWh energy storage,
  * open-loop pumped hydro, batteries,
  * run-of-river hydro from the ERAA daily RoR file,
  * trade with Germany / Benelux / Poland at the hourly prices of the official European model,
  * policy constraints (CO2 cap, minimum RES / storage capacity, minimum net export).

Existing (2025) plants are "brownfield": they only pay FOM. New capacity pays annualised CAPEX + FOM.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import pulp

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
ERAA = ROOT / "data" / "ERAA_2023-2"
FUELS = ROOT / "data" / "fuel_sources"
ZONE = "scandinavia"
NEIGHBOURS = {"germany": "ger", "benelux": "ben", "poland": "pol"}
N_HOURS = 8760

# ---------------------------------------------------------------- data loading


def eraa_capacity_table(year: int) -> pd.DataFrame:
    df = pd.read_csv(ERAA / "generation_capas" / f"generation-capa_{year}_{ZONE}.csv", sep=";")
    df["production_type"] = df["production_type"].str.strip()
    return df.set_index("production_type")


def eraa_capacities(year: int) -> Dict[str, float]:
    """Model-level capacities (MW) from ERAA, Scandinavia."""
    t = eraa_capacity_table(year)
    g = lambda pt, col="power_capacity": float(t.loc[pt, col])
    return {
        "nuclear": g("Nuclear"),
        "wind_onshore": g("Wind Onshore"),
        "wind_offshore": g("Wind Offshore"),
        "solar_pv": g("Solar PV"),
        "biofuel": g("Biofuel"),
        "gas_ccgt": g("Gas"),          # existing gas fleet modelled as CCGT
        "gas_ocgt": 0.0,
        "coal": g("Hard Coal") + g("Lignite"),
        "oil": g("Oil"),
        "others_renewable": g("Others renewable"),
        "others_nonrenewable": g("Others non-renewable"),
        "dsr": g("Demand Side Response capacity"),
        "batteries": g("Batteries", "power_capacity_injection"),
        "batteries_energy": g("Batteries", "energy_capacity"),
        "hydro_ror": g("Hydro - Run of River", "power_capacity_turbine"),
        "hydro_reservoir": g("Hydro - Reservoir", "power_capacity_turbine"),
        "hydro_reservoir_energy": g("Hydro - Reservoir", "energy_capacity"),
        "phs_turbine": g("Hydro - Pump Storage Open Loop", "power_capacity_turbine"),
        "phs_pump": abs(g("Hydro - Pump Storage Open Loop", "power_capacity_pumping")),
        "phs_energy": g("Hydro - Pump Storage Open Loop", "energy_capacity"),
    }


def eraa_intercos(year: int) -> Dict[str, float]:
    """Scandinavian border capacities (MW) per neighbour, ERAA (both cable types summed)."""
    df = pd.read_csv(ERAA / "interco_capas" / f"interco-capas_{year}.csv", sep=";")
    out = {}
    for n in NEIGHBOURS:
        m = ((df.zone_origin == n) & (df.zone_destination == ZONE)) | ((df.zone_origin == ZONE) & (df.zone_destination == n))
        out[n] = float(df.loc[m, "value"].sum())
    return out


def load_timeseries(year: int, cy: int) -> pd.DataFrame:
    def read(path):
        d = pd.read_csv(path, sep=";")
        d = d[d.climatic_year == cy]
        return d["value"].to_numpy(dtype=float)[:N_HOURS]

    ts = pd.DataFrame({"demand": read(ERAA / "demand" / f"demand_{year}_{ZONE}.csv")})
    for tech in ["solar_pv", "wind_onshore", "wind_offshore"]:
        cf = read(ERAA / "res_capa-factors" / f"capa_factor_{tech}_{year}_{ZONE}.csv")
        ts[f"cf_{tech}"] = cf / 100 if cf.max() > 1.5 else cf  # % or p.u.
    ts.index = pd.date_range(f"{year}-01-01", periods=len(ts), freq="h")
    return ts


def build_hydro(year: int, cy: int = 1989) -> Dict:
    """
    Hydro inputs for Scandinavia, taken as given from the ERAA data files (no reconstruction).

    * Reservoir: turbine power + energy capacity from the ERAA capacity file, weekly natural
      inflows from PECD-hydro-weekly-inflows.csv (ERAA2024 data, identical for all climatic years).
    * Run-of-river: daily generation (GWh/day) from PECD-hydro-daily-ror-generation.csv for the
      chosen climatic year, spread uniformly over the 24 hours of each day (MW).
    """
    caps = eraa_capacities(year)
    inflow = pd.read_csv(ERAA / "hydro" / "PECD-hydro-weekly-inflows.csv", sep=";")
    inflow = inflow[(inflow.week <= 52)]
    sca_w = inflow[inflow.zone == ZONE].groupby("week")["cum_inflow_into_reservoirs"].mean().sort_index()  # MWh/week
    week_of_hour = np.minimum(np.arange(N_HOURS) // 168, 51)
    inflow_h = sca_w.to_numpy()[week_of_hour] / 168.0  # MWh per hour

    ror = pd.read_csv(ERAA / "hydro" / "PECD-hydro-daily-ror-generation.csv", sep=";")
    ror["value"] = pd.to_numeric(ror["value"], errors="coerce")
    sca = ror[(ror.zone == ZONE) & (ror.climatic_year == cy)].sort_values("day")
    if sca.empty or sca["value"].isna().any():
        raise ValueError(f"Missing Scandinavian RoR data for climatic year {cy} in the ERAA file")
    ror_daily_mw = sca["value"].to_numpy() * 1e3 / 24  # GWh/day -> MW
    ror_h = np.repeat(ror_daily_mw, 24)[:N_HOURS]

    # capacity factor of RoR per zone (information only)
    rows = []
    for z, g in ror.groupby("zone"):
        e_gwh = g.groupby("climatic_year")["value"].sum().mean()
        c = pd.read_csv(ERAA / "generation_capas" / f"generation-capa_2025_{z}.csv", sep=";")
        c["production_type"] = c["production_type"].str.strip()
        cap = c.loc[c.production_type == "Hydro - Run of River", ["power_capacity", "power_capacity_turbine"]].to_numpy().sum()
        rows.append({"zone": z, "ror_capacity_2025_MW": cap, "ror_energy_GWh": e_gwh,
                     "capacity_factor": e_gwh * 1e3 / (cap * 8760) if cap else np.nan})
    cf_table = pd.DataFrame(rows).set_index("zone")

    return {"inflow_h": inflow_h, "inflow_weekly": sca_w, "ror_h": ror_h, "ror_cf_table": cf_table, "caps": caps}


def tech_costs(co2_price: float) -> pd.DataFrame:
    """Per-technology cost and emission parameters (€/MW/yr, €/MWh, tCO2/MWh)."""
    tech = json.loads((FUELS / "technology_datacrunch.json").read_text())
    fuel = json.loads((FUELS / "fuels_datacrunch.json").read_text())
    mapping = {"nuclear": "Nuclear", "wind_onshore": "Wind Onshore", "wind_offshore": "Wind Offshore",
               "solar_pv": "Solar PV", "biofuel": "Biomass", "gas_ccgt": "CCGT", "gas_ocgt": "OCGT",
               "coal": "Hard Coal", "oil": "Oil", "hydro_ror": "Hydro ROR"}
    rows = {}
    for k, name in mapping.items():
        p = tech[name]
        annuity = p["CAPEX"] * p["WACC"] / (1 - (1 + p["WACC"]) ** -p["Lifetime"])
        f = fuel.get(p["Fuel type"], {"co2_emissions": 0, "cost_per_ton": 0, "energy_density_per_ton": 0})
        eff = p["Efficiency"] or 1.0
        fuel_cost = (f["cost_per_ton"] / f["energy_density_per_ton"] / eff) if f["energy_density_per_ton"] else 0.0
        co2 = f["co2_emissions"] / eff if p["Efficiency"] else 0.0
        rows[k] = {"capex_EUR_per_kW": p["CAPEX"] / 1e3, "annuity_EUR_per_MW_yr": annuity, "fom_EUR_per_MW_yr": p["FOM"],
                   "fuel_EUR_per_MWh": fuel_cost, "co2_t_per_MWh": co2, "co2_cost_EUR_per_MWh": co2 * co2_price,
                   "vom_EUR_per_MWh": p["VOM"]}
    df = pd.DataFrame(rows).T
    df.loc["others_renewable"] = 0.0
    # "Others non-renewable" = fossil CHP / waste units, must-run (heat-led) in ERAA.
    # No fuel cost here (paid by heat), but CO2 is counted: gas at 40 % electrical efficiency.
    df.loc["others_nonrenewable"] = 0.0
    df.loc["others_nonrenewable", "co2_t_per_MWh"] = fuel["gas"]["co2_emissions"] / 0.40
    df.loc["dsr", "vom_EUR_per_MWh"] = 300.0      # demand response activation cost (assumption)
    df = df.fillna(0.0)
    df["var_cost_EUR_per_MWh"] = df.fuel_EUR_per_MWh + df.co2_cost_EUR_per_MWh + df.vom_EUR_per_MWh
    return df


# Battery: same assumptions as data_crunch.ipynb Appendix D
BATTERY = {"capex_EUR_per_kWh": 300.0, "duration_h": 4.0, "wacc": 0.06, "lifetime": 15, "fom_share": 0.025,
           "efficiency_roundtrip": 0.81}
PHS_EFF = 0.75
VOLL = 20_000.0          # €/MWh, "Deficit" VOM in technology_datacrunch.json
TRADE_FEE = 0.5          # €/MWh, avoids simultaneous import/export


def battery_annual_cost_per_MW() -> float:
    b = BATTERY
    capex_mw = b["capex_EUR_per_kWh"] * 1e3 * b["duration_h"]
    annuity = capex_mw * b["wacc"] / (1 - (1 + b["wacc"]) ** -b["lifetime"])
    return annuity + b["fom_share"] * capex_mw


# ---------------------------------------------------------------- scenario model


@dataclass
class Scenario:
    name: str
    year: int = 2033
    cy: int = 1989
    invest: bool = True                       # False = dispatch only, capacities = base_capacities
    base_capacities: Optional[Dict[str, float]] = None   # existing fleet (default ERAA 2025)
    max_capacities: Dict[str, float] = field(default_factory=dict)  # upper bounds (MW)
    fixed_capacities: Dict[str, float] = field(default_factory=dict)  # imposed capacities, new part pays CAPEX
    intercos: Optional[Dict[str, float]] = None
    prices: Optional[pd.DataFrame] = None     # hourly neighbour prices, cols = germany/benelux/poland
    co2_price: float = 80.0
    co2_cap_t: Optional[float] = None
    min_vres_MW: Optional[float] = None       # wind + solar
    min_storage_MW: Optional[float] = None    # batteries + pumped hydro (turbine)
    min_net_export_MWh: Optional[float] = 0.0  # 0 = Scandinavia must not be a net importer
    allow_new: tuple = ("wind_onshore", "wind_offshore", "solar_pv", "gas_ocgt", "gas_ccgt", "batteries")


def solve(sc: Scenario, time_limit: int = 1800) -> Dict:
    ts = load_timeseries(sc.year, sc.cy)
    T = range(len(ts))
    hyd = build_hydro(sc.year, sc.cy)
    hcap = hyd["caps"]  # hydro / nuclear / dsr / others fixed at the scenario year (ERAA)
    base = dict(sc.base_capacities or eraa_capacities(2025))
    costs = tech_costs(sc.co2_price)
    ic = sc.intercos or eraa_intercos(2025)
    prices = sc.prices if sc.prices is not None else pd.DataFrame(0.0, index=range(len(ts)), columns=list(NEIGHBOURS))
    prices = prices.iloc[: len(ts)].reset_index(drop=True)
    n_t = len(ts)
    if len(prices) < n_t:  # official model gives 8712 h -> repeat last day
        prices = pd.concat([prices, prices.iloc[-(n_t - len(prices)):]], ignore_index=True)

    m = pulp.LpProblem(sc.name, pulp.LpMinimize)
    dispatchable = ["nuclear", "biofuel", "gas_ccgt", "gas_ocgt", "coal", "oil", "others_renewable",
                    "others_nonrenewable"]
    vres = ["wind_onshore", "wind_offshore", "solar_pv"]
    techs = dispatchable + vres

    # fixed (not investable) fleets come from the scenario year (hydro, nuclear, others, dsr)
    fixed_from_year = {"nuclear": hcap["nuclear"], "others_renewable": hcap["others_renewable"]}

    cap, new = {}, {}
    for k in techs + ["batteries"]:
        existing = fixed_from_year.get(k, base.get(k, 0.0))
        if not sc.invest:
            cap[k] = existing
            new[k] = 0.0
            continue
        if k in sc.fixed_capacities:
            cap[k] = float(sc.fixed_capacities[k])
            new[k] = max(cap[k] - existing, 0.0)
            continue
        if k in sc.allow_new:
            ub = sc.max_capacities.get(k)
            new[k] = pulp.LpVariable(f"new_{k}", 0, None if ub is None else max(ub - existing, 0))
            cap[k] = existing + new[k]
        elif k in ("coal", "oil", "biofuel", "others_nonrenewable"):
            # can be kept or retired (saves FOM), never extended
            cap[k] = pulp.LpVariable(f"cap_{k}", 0, existing)
            new[k] = 0.0
        else:
            cap[k] = existing
            new[k] = 0.0

    gen = {k: [pulp.LpVariable(f"g_{k}_{t}", 0) for t in T] for k in techs}
    ror = [pulp.LpVariable(f"g_ror_{t}", 0, hyd["ror_h"][t]) for t in T]
    res_g = [pulp.LpVariable(f"g_res_{t}", 0, hcap["hydro_reservoir"]) for t in T]
    res_spill = [pulp.LpVariable(f"spill_{t}", 0) for t in T]
    res_soc = [pulp.LpVariable(f"soc_res_{t}", 0, hcap["hydro_reservoir_energy"]) for t in T]
    phs_g = [pulp.LpVariable(f"g_phs_{t}", 0, hcap["phs_turbine"]) for t in T]
    phs_p = [pulp.LpVariable(f"p_phs_{t}", 0, hcap["phs_pump"]) for t in T]
    phs_soc = [pulp.LpVariable(f"soc_phs_{t}", 0, hcap["phs_energy"]) for t in T]
    bat_d = [pulp.LpVariable(f"bat_d_{t}", 0) for t in T]
    bat_c = [pulp.LpVariable(f"bat_c_{t}", 0) for t in T]
    bat_soc = [pulp.LpVariable(f"bat_soc_{t}", 0) for t in T]
    dsr = [pulp.LpVariable(f"dsr_{t}", 0, hcap["dsr"]) for t in T]
    ens = [pulp.LpVariable(f"ens_{t}", 0) for t in T]
    imp = {n: [pulp.LpVariable(f"imp_{n}_{t}", 0, ic[n]) for t in T] for n in NEIGHBOURS}
    exp = {n: [pulp.LpVariable(f"exp_{n}_{t}", 0, ic[n]) for t in T] for n in NEIGHBOURS}

    bat_energy = cap["batteries"] * BATTERY["duration_h"] if sc.invest else base.get("batteries_energy", cap["batteries"] * 2)
    eta = BATTERY["efficiency_roundtrip"] ** 0.5

    for t in T:
        for k in dispatchable:
            if k == "others_nonrenewable":
                m += gen[k][t] == cap[k]  # must-run (heat-led CHP)
            else:
                m += gen[k][t] <= cap[k]
        for k in vres:
            m += gen[k][t] <= cap[k] * ts[f"cf_{k}"].iat[t]
        m += bat_d[t] <= cap["batteries"]
        m += bat_c[t] <= cap["batteries"]
        m += bat_soc[t] <= bat_energy
        tp = t - 1 if t > 0 else n_t - 1  # cyclic year
        m += res_soc[t] == res_soc[tp] + hyd["inflow_h"][t] - res_g[t] - res_spill[t]
        m += phs_soc[t] == phs_soc[tp] + PHS_EFF * phs_p[t] - phs_g[t]
        m += bat_soc[t] == bat_soc[tp] + eta * bat_c[t] - bat_d[t] / eta
        supply = (pulp.lpSum(gen[k][t] for k in techs) + ror[t] + res_g[t] + phs_g[t] + bat_d[t] + dsr[t] + ens[t]
                  + pulp.lpSum(imp[n][t] - exp[n][t] for n in NEIGHBOURS))
        m += supply == ts["demand"].iat[t] + phs_p[t] + bat_c[t], f"balance_{t}"

    # ---- policy constraints
    emissions = pulp.lpSum(costs.loc[k, "co2_t_per_MWh"] * pulp.lpSum(gen[k]) for k in dispatchable)
    if sc.co2_cap_t is not None:
        m += emissions <= sc.co2_cap_t, "co2_cap"
    if sc.min_vres_MW is not None:
        m += pulp.lpSum(cap[k] for k in vres) >= sc.min_vres_MW, "min_vres"
    if sc.min_storage_MW is not None:
        m += cap["batteries"] + hcap["phs_turbine"] >= sc.min_storage_MW, "min_storage"
    net_export = pulp.lpSum(exp[n][t] - imp[n][t] for n in NEIGHBOURS for t in T)
    if sc.min_net_export_MWh is not None:
        m += net_export >= sc.min_net_export_MWh, "min_net_export"

    # ---- objective
    fixed = pulp.lpSum(costs.loc[k, "fom_EUR_per_MW_yr"] * cap[k] for k in techs if k in costs.index)
    capex = pulp.lpSum(costs.loc[k, "annuity_EUR_per_MW_yr"] * new[k] for k in techs)
    bat_cost = battery_annual_cost_per_MW() * new["batteries"]
    var = pulp.lpSum(costs.loc[k, "var_cost_EUR_per_MWh"] * pulp.lpSum(gen[k]) for k in techs)
    var += costs.loc["hydro_ror", "vom_EUR_per_MWh"] * pulp.lpSum(ror)
    var += costs.loc["dsr", "vom_EUR_per_MWh"] * pulp.lpSum(dsr) + VOLL * pulp.lpSum(ens)
    trade = pulp.lpSum((prices[n].iat[t] + TRADE_FEE) * imp[n][t] - (prices[n].iat[t] - TRADE_FEE) * exp[n][t]
                       for n in NEIGHBOURS for t in T)
    m += fixed + capex + bat_cost + var + trade

    status = m.solve(pulp.HiGHS(msg=False, timeLimit=time_limit))
    if pulp.LpStatus[status] != "Optimal":
        return {"name": sc.name, "status": pulp.LpStatus[status]}
    return _collect(sc, m, ts, hyd, costs, cap, new, gen, ror, res_g, res_spill, res_soc, phs_g, phs_p, phs_soc,
                    bat_d, bat_c, bat_soc, dsr, ens, imp, exp, techs, dispatchable, vres, prices, ic)


def _v(x):
    return x.value() if hasattr(x, "value") else float(x)


def _collect(sc, m, ts, hyd, costs, cap, new, gen, ror, res_g, res_spill, res_soc, phs_g, phs_p, phs_soc,
             bat_d, bat_c, bat_soc, dsr, ens, imp, exp, techs, dispatchable, vres, prices, ic) -> Dict:
    val = lambda lst: np.array([v.value() or 0.0 for v in lst])
    hourly = pd.DataFrame(index=ts.index)
    hourly["demand"] = ts["demand"].to_numpy()
    for k in techs:
        hourly[k] = val(gen[k])
    hourly["hydro_ror"] = val(ror)
    hourly["hydro_reservoir"] = val(res_g)
    hourly["phs_turbine"] = val(phs_g)
    hourly["phs_pumping"] = -val(phs_p)
    hourly["battery_discharge"] = val(bat_d)
    hourly["battery_charge"] = -val(bat_c)
    hourly["dsr"] = val(dsr)
    hourly["unserved"] = val(ens)
    for n in NEIGHBOURS:
        hourly[f"net_import_{n}"] = val(imp[n]) - val(exp[n])
    hourly["reservoir_soc_TWh"] = val(res_soc) / 1e6
    hourly["reservoir_spill"] = val(res_spill)
    hourly["battery_soc"] = val(bat_soc)
    for k in vres:
        hourly[f"curtail_{k}"] = _v(cap[k]) * ts[f"cf_{k}"].to_numpy() - hourly[k]
    try:
        hourly["scandinavia_price"] = [m.constraints[f"balance_{t}"].pi for t in range(len(ts))]
    except Exception:
        hourly["scandinavia_price"] = np.nan

    caps = {k: _v(cap[k]) for k in techs + ["batteries"]}
    caps.update({"hydro_ror": hyd["caps"]["hydro_ror"], "hydro_reservoir": hyd["caps"]["hydro_reservoir"],
                 "phs_turbine": hyd["caps"]["phs_turbine"], "dsr": hyd["caps"]["dsr"]})
    new_caps = {k: _v(new[k]) for k in techs + ["batteries"]}

    energy = (hourly.drop(columns=["reservoir_soc_TWh", "battery_soc", "scandinavia_price"]).sum() / 1e6).rename("TWh")
    emissions = {k: costs.loc[k, "co2_t_per_MWh"] * hourly[k].sum() for k in dispatchable}
    imp_tot = sum(hourly[f"net_import_{n}"].clip(lower=0).sum() for n in NEIGHBOURS)
    exp_tot = sum((-hourly[f"net_import_{n}"]).clip(lower=0).sum() for n in NEIGHBOURS)

    fom = sum(costs.loc[k, "fom_EUR_per_MW_yr"] * caps[k] for k in techs)
    capex = sum(costs.loc[k, "annuity_EUR_per_MW_yr"] * new_caps[k] for k in techs)
    capex += battery_annual_cost_per_MW() * new_caps["batteries"]
    var = sum(costs.loc[k, "var_cost_EUR_per_MWh"] * hourly[k].sum() for k in techs)
    var += costs.loc["hydro_ror", "vom_EUR_per_MWh"] * hourly["hydro_ror"].sum() + 300 * hourly["dsr"].sum()
    trade = sum((prices[n].to_numpy()[: len(hourly)] * hourly[f"net_import_{n}"].to_numpy()).sum() for n in NEIGHBOURS)
    vres_mwh = sum(_v(cap[k]) * ts[f"cf_{k}"].sum() for k in vres)

    summary = {
        "scenario": sc.name, "status": "Optimal", "year": sc.year, "climatic_year": sc.cy,
        "demand_TWh": hourly["demand"].sum() / 1e6,
        "co2_Mt": sum(emissions.values()) / 1e6,
        "co2_cap_Mt": None if sc.co2_cap_t is None else sc.co2_cap_t / 1e6,
        "vres_capacity_GW": sum(caps[k] for k in vres) / 1e3,
        "storage_capacity_GW": (caps["batteries"] + caps["phs_turbine"]) / 1e3,
        "interconnection_GW": sum(ic.values()) / 1e3,
        "imports_TWh": imp_tot / 1e6, "exports_TWh": exp_tot / 1e6, "net_export_TWh": (exp_tot - imp_tot) / 1e6,
        "unserved_energy_GWh": hourly["unserved"].sum() / 1e3,
        "unserved_hours": int((hourly["unserved"] > 1e-3).sum()),
        "vres_curtailment_TWh": sum(hourly[f"curtail_{k}"].sum() for k in vres) / 1e6,
        "vres_curtailment_pct": 100 * sum(hourly[f"curtail_{k}"].sum() for k in vres) / max(vres_mwh, 1),
        "reservoir_spill_TWh": hourly["reservoir_spill"].sum() / 1e6,
        "renewable_share_pct": 100 * (sum(hourly[k].sum() for k in vres + ["biofuel"]) + hourly["hydro_ror"].sum()
                                      + hourly["hydro_reservoir"].sum()) / hourly["demand"].sum(),
        "cost_capex_MEUR": capex / 1e6, "cost_fom_MEUR": fom / 1e6, "cost_variable_MEUR": var / 1e6,
        "cost_net_trade_MEUR": trade / 1e6, "cost_total_MEUR": (capex + fom + var + trade) / 1e6,
        "objective_MEUR": pulp.value(m.objective) / 1e6,
    }
    return {"name": sc.name, "status": "Optimal", "summary": summary, "capacities_MW": caps,
            "new_capacities_MW": new_caps, "energy_TWh": energy, "emissions_t": emissions, "hourly": hourly}


def load_europe_prices(run_name: str) -> pd.DataFrame:
    """Hourly marginal prices of Scandinavia's neighbours from an official-model run."""
    f = next((HERE / "data" / "europe_runs" / run_name).glob("marginal-prices_*.csv"))
    p = pd.read_csv(f, index_col=0)
    return pd.DataFrame({n: p[tri].to_numpy() for n, tri in NEIGHBOURS.items()})
