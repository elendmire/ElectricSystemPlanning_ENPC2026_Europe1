"""
Feasibility check of the 2033 country files in input/long_term_uc/countries/*.json:
can the capacities be built in 7 years (2026-2033), and how much land do they need?

Writes scandinavia-2033/results/europe_2033_feasibility_check.xlsx
Run:  .venv/bin/python scandinavia-2033/feasibility_check.py
Reads the team files as they are at run time (nothing is modified).
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from run_europe_model import COUNTRIES, eraa_capacities

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "results" / "europe_2033_feasibility_check.xlsx"
YEARS = 7  # 2026 -> 2033
TECHS = ["solar_pv", "wind_onshore", "wind_offshore", "batteries", "nuclear", "gas", "coal", "biofuel", "oil",
         "hydro_reservoir", "hydro_run_of_river", "hydro_pump_storage_closed_loop", "hydro_pump_storage_open_loop",
         "dsr", "others_fatal"]
# approximate total land area (km2), public country statistics
AREA_KM2 = {"benelux": 72_500, "france": 543_900, "germany": 357_600, "iberian-peninsula": 598_200,
            "italy": 302_100, "poland": 312_700, "scandinavia": 1_216_900}
SOLAR_HA_PER_MW = 3.6      # NREL (Ong et al. 2013): 8.9 acres/MWac total area, utility-scale PV  [S20]
WIND_KM2_PER_MW = 0.25     # total wind-farm area incl. spacing; NREL range 19-145 acres/MW = 0.08-0.59 km2/MW [S21]

SOURCES = [
    ("S1", "Bundesnetzagentur – Growth in renewable energy in 2024 (DE: +16.2 GW PV, +2.5 GW net onshore, +0.7 GW offshore; ~15 GW onshore permits)",
     "https://www.bundesnetzagentur.de/SharedDocs/Pressemitteilungen/EN/2025/20250108_EE.html"),
    ("S2", "WindEurope – Wind energy in Europe: 2024 statistics (EU 12.9 GW; DE 4.0, FI 1.4, ES 1.2, SE 1.0 GW)",
     "https://windeurope.org/data/product/wind-energy-in-europe-2024-statistics-and-the-outlook-for-2025-2030/"),
    ("S2b", "Windtech International – summary of WindEurope 2024 statistics",
     "https://www.windtech-international.com/industry-news/wind-energy-capacity-in-europe-increased-by-16-4-gw-in-2024"),
    ("S3", "PV Tech – EU adds 66 GW of solar in 2024 (DE 16.1, ES 9.3, IT 6.4 GW)",
     "https://www.pv-tech.org/eu-adds-66gw-of-solar-pv-in-2024-as-residential-market-slumps/"),
    ("S4", "pv magazine – EU solar installations 65.5 GW in 2024 (SolarPower Europe)",
     "https://www.pv-magazine.com/2024/12/18/eu-solar-installations-hit-65-5-gw-in-2024-says-solarpower-europe"),
    ("S5", "CleanTechnica – Poland added about 4 GW of solar in 2024",
     "https://cleantechnica.com/2025/01/28/poland-added-about-4-gw-of-solar-power-in-2024/"),
    ("S6", "pv magazine – Netherlands installs 4.32 GW of solar in 2024 (other sources: ~3 GW)",
     "https://www.pv-magazine.com/2025/08/07/netherlands-installs-4-32-gw-of-solar-in-2024/"),
    ("S7", "IEA PVPS – National Survey Report Belgium 2024 (>=0.98 GW new PV)",
     "https://iea-pvps.org/national_survey/nsr-belgium-2024/"),
    ("S8", "pv magazine – Spain PNIEC 2023-2030: 76 GW solar by 2030",
     "https://pv-magazine.com/2024/09/25/spain-sets-new-2030-solar-target-of-76-gw/"),
    ("S9", "ESS News – Spain PNIEC: 22.5 GW storage by 2030",
     "https://www.ess-news.com/2024/09/27/spain-sets-new-2030-energy-storage-target-of-22-5-gw"),
    ("S10", "Cluster Energia – PNIEC 2023-2030 approved (62 GW wind incl. 3 GW offshore)",
     "https://clusterenergia.cat/news/the-spanish-government-approves-the-2023-2030-pniec-to-increase-energy-independence-and-boost-renewables"),
    ("S11", "Renewable Energy Industry – Spain nuclear phase-out (Almaraz 1 Nov 2027, full exit 2035)",
     "https://www.renewable-energy-industry.com/countries/article-6508-spain-withdraws-from-nuclear-energy"),
    ("S12", "Clean Energy Wire – 2% of German land area for onshore wind by 2032 (Wind-an-Land-Gesetz)",
     "https://www.cleanenergywire.org/news/two-percent-german-land-area-onshore-wind-2032-cabinet-approves-next-batch-energy-transition-laws"),
    ("S13", "RenewEconomy – Germany EEG 2023: 115 GW onshore, 215 GW solar, 30 GW offshore by 2030",
     "https://reneweconomy.com.au/germany-plans-32gw-of-new-wind-and-solar-a-year-to-meet-2030-renewables-target/"),
    ("S14", "Bloomberg – Denmark receives no bids in largest-ever offshore wind tender (5 Dec 2024)",
     "https://www.bloomberg.com/news/articles/2024-12-05/denmark-receives-no-bids-in-largest-ever-offshore-wind-tender"),
    ("S15", "offshoreWIND.biz – Sweden rejects 13 Baltic offshore wind farms on defence grounds (4 Nov 2024)",
     "https://www.offshorewind.biz/2024/11/04/sweden-rejects-13-offshore-wind-farms-green-lights-vattenfalls-poseidon-project/"),
    ("S16", "Supreme Court of Norway – HR-2021-1975-S (Fosen wind farms violate Sami rights, Oct 2021)",
     "https://www.domstol.no/en/supremecourt/rulings/2021/supreme-court-civil-cases/hr-2021-1975-s/"),
    ("S17", "Euronews – Finland wind power +2.43 GW in 2022 (record year)",
     "https://www.euronews.com/green/2023/01/12/finland-wind-power-increased-by-75-last-year-boosting-energy-security-and-climate-goals"),
    ("S18", "Wikipedia – Wind power in Sweden (~2.4 GW added in 2022) – secondary source, check",
     "https://en.wikipedia.org/wiki/Wind_power_in_Sweden"),
    ("S19", "pv magazine – Grid connection delays affect thousands of Dutch customers (Liander, 2026)",
     "https://www.pv-magazine.com/2026/06/05/grid-connection-delays-affect-thousands-of-dutch-customers-liander/"),
    ("S20", "NREL – Ong et al. 2013, Land-use requirements for solar power plants in the US (8.9 acres/MWac total)",
     "https://www.nrel.gov/docs/fy13osti/56290.pdf"),
    ("S21", "NREL – Denholm et al. 2009, Land-use requirements of modern wind power plants (19-145 acres/MW total area)",
     "https://www.osti.gov/biblio/964608"),
    ("S22", "Notes from Poland – Poland's first nuclear plant delayed to 2036 (Oct 2026)",
     "https://notesfrompoland.com/2026/10/03/poland-updates-nuclear-strategy-with-delays-to-launch-of-first-two-plants/"),
    ("S23", "oEnergetice – Poland launches offshore wind (Baltic Power first power 2026; target 5.9 GW by 2030)",
     "https://oenergetice.cz/en/international-energy/poland-continues-preparations-for-nuclear-power-plants-and-launches-offshore-wind-projects"),
    ("S24", "Watson Farley & Williams – Italian offshore wind: only one 30 MW farm (Taranto) operating",
     "https://www.wfw.com/articles/italian-offshore-wind-status-and-recent-developments/"),
    ("S25", "Watson Farley & Williams – Italy FER 2 decree: 3.8 GW offshore wind incentives 2024-2028",
     "https://www.wfw.com/articles/italys-new-fer-2-decree-focusses-on-the-incentives-for-offshore-wind-projects/"),
    ("S26", "ESS News – Terna receives 100 GW+ requests for MACSE storage tender",
     "https://www.ess-news.com/2024/12/03/italian-grid-company-terna-fields-100-gw-requests-for-macse-energy-storage-tender/"),
    ("S27", "Enerdata – France PPE3 2026-2035 (solar 48 GW 2030, onshore 31 GW 2030, offshore 15 GW 2035)",
     "https://www.enerdata.net/publications/daily-energy-news/france-unveils-its-new-energy-strategy-2026-2035-period.html"),
    ("S28", "Enerdata – France launches 10 GW offshore tenders under PPE3 (~2 GW operating today)",
     "https://www.enerdata.net/publications/daily-energy-news/france-launches-10-gw-offshore-wind-tenders-under-ppe-3.html"),
    ("S29", "SolarPower Europe – European battery storage +21.9 GWh in 2024 (fleet 61.1 GWh; DE, IT, UK lead)",
     "https://www.solarpowereurope.org/press-releases/new-report-european-battery-storage-grows-15-in-2024-eu-energy-storage-action-plan-needed"),
    ("S30", "ERAA 2023.2 capacity data (ENTSO-E), as provided in this repository",
     "data/ERAA_2023-2/generation_capas/"),
]

# historical reference: best recent annual addition (GW/yr) per country & technology
HIST = {
    ("germany", "solar_pv"): (16.2, "2024", "S1"),
    ("germany", "wind_onshore"): (2.5, "2024 net (gross ~3.3); 15 GW permitted in 2024", "S1"),
    ("germany", "wind_offshore"): (0.7, "2024", "S1"),
    ("iberian-peninsula", "solar_pv"): (9.3, "2024, Spain only", "S3"),
    ("iberian-peninsula", "wind_onshore"): (1.2, "2024, Spain only", "S2b"),
    ("italy", "solar_pv"): (6.4, "2024", "S3"),
    ("italy", "wind_offshore"): (0.0, "only 30 MW operating in total", "S24"),
    ("poland", "solar_pv"): (4.0, "2024", "S5"),
    ("benelux", "solar_pv"): (5.3, "2024: NL 4.3 + BE 1.0 (NL may be ~3 GW)", "S6, S7"),
    ("scandinavia", "wind_onshore"): (4.8, "2022 record: SE ~2.4 + FI 2.4 (NO, DK not found)", "S17, S18"),
    ("scandinavia", "wind_offshore"): (0.0, "no new Nordic offshore in 2024; DK tender 0 bids, SE refused 13 farms", "S2, S14, S15"),
    ("france", "wind_offshore"): (0.5, "~2 GW built in total since 2022", "S28"),
}

POLICY = [
    ("germany", "Onshore wind target 115 GW by 2030; 2% of land for wind by 2032", "S12, S13"),
    ("germany", "Solar target 215 GW by 2030; offshore 30 GW by 2030, 40 GW by 2035 (2035 goals may have been amended)", "S13"),
    ("iberian-peninsula", "Spain PNIEC 2030: 76 GW solar, 62 GW wind (3 GW offshore), 22.5 GW storage", "S8, S9, S10"),
    ("iberian-peninsula", "Spain nuclear exit: Almaraz 1 closes Nov 2027, full phase-out by 2035", "S11"),
    ("scandinavia", "Denmark: zero bids in largest-ever offshore wind tender (Dec 2024)", "S14"),
    ("scandinavia", "Sweden: 13 Baltic offshore wind farms (~32 GW) refused on defence grounds (Nov 2024)", "S15"),
    ("scandinavia", "Norway: Supreme Court ruled Fosen wind farms violate Sami reindeer-herding rights (2021) -> strong local opposition", "S16"),
    ("benelux", "Netherlands: severe grid congestion, thousands of customers waiting for connection", "S19"),
    ("poland", "First nuclear unit expected 2036; offshore wind target 5.9 GW by 2030, first power 2026", "S22, S23"),
    ("italy", "Offshore: 30 MW operating; FER 2 incentives for 3.8 GW 2024-2028; MACSE storage tender >100 GW requests", "S24, S25, S26"),
    ("france", "PPE3: solar 48 GW (2030), onshore wind 31 GW (2030), offshore ~4 GW (2030) / 15 GW (2035)", "S27, S28"),
    ("europe", "Battery storage installed in Europe in 2024: 21.9 GWh (all countries together)", "S29"),
]


def team_capacity(country, tech, sel, cap, e25):
    if sel is not None and tech not in sel:
        return 0.0
    return float(cap.get(tech, e25.get(tech, 0.0)))


def verdict(required, hist):
    if required <= 0.1:
        return "Realistic"
    if hist is None:
        return "Check"
    if hist <= 0.05:
        return "Unrealistic"
    r = required / hist
    return "Realistic" if r <= 1.0 else ("Ambitious" if r <= 2.0 else "Unrealistic")


def main():
    cap_rows, build_rows, land_rows, storage_rows = [], [], [], []
    for c in COUNTRIES:
        f = ROOT / "input/long_term_uc/countries" / f"{c}.json"
        d = json.loads(f.read_text())
        sel = d.get("selected_prod_types", {}).get(c)
        cap = d.get("capacities_tb_overwritten", {}).get(c, {})
        e25, e33 = eraa_capacities(c, 2025), eraa_capacities(c, 2033)
        for t in TECHS:
            a, b, x = e25.get(t, 0.0), e33.get(t, 0.0), team_capacity(c, t, sel, cap, e25)
            if a == b == x == 0:
                continue
            cap_rows.append({"Country": c, "Technology": t, "ERAA 2025 (GW)": a / 1e3, "ERAA 2033 (GW)": b / 1e3,
                             "Team file 2033 (GW)": x / 1e3, "Change vs 2025 (GW)": (x - a) / 1e3,
                             "Required build rate (GW/yr, 7 yrs)": (x - a) / 1e3 / YEARS,
                             "ERAA plan build rate (GW/yr)": (b - a) / 1e3 / YEARS,
                             "In selected_prod_types": "yes" if (sel is None or t in sel) else "NO (= 0 in model)"})
            if t in ("solar_pv", "wind_onshore", "wind_offshore", "batteries") and x - a > 0:
                h = HIST.get((c, t))
                req = (x - a) / 1e3 / YEARS
                build_rows.append({"Country": c, "Technology": t, "Required (GW/yr)": req,
                                   "Historical best (GW/yr)": None if h is None else h[0],
                                   "Historical note": (f"needs {(x - a) / 1e3 / YEARS * 2:.1f} GWh/yr (2 h) vs 21.9 GWh/yr installed in ALL of Europe in 2024"
                                                       if t == "batteries" else "no historical figure collected - check national statistics") if h is None else h[1],
                                   "Required / historical": None if (h is None or h[0] <= 0.05) else req / h[0],
                                   "Verdict": verdict(req, None if h is None else h[0]) if t != "batteries" else
                                   ("Unrealistic" if req * 2 > 0.5 * 21.9 else ("Ambitious" if req * 2 > 0.2 * 21.9 else "Realistic")),
                                   "Source": ("S29" if t == "batteries" else "-") if h is None else h[2]})
        s, w = team_capacity(c, "solar_pv", sel, cap, e25), team_capacity(c, "wind_onshore", sel, cap, e25)
        solar_km2 = s * SOLAR_HA_PER_MW / 100
        wind_km2 = w * WIND_KM2_PER_MW
        land_rows.append({"Country": c, "Land area (km2, approx.)": AREA_KM2[c], "Solar PV 2033 (GW)": s / 1e3,
                          "Solar area if 100% ground-mounted (km2)": solar_km2,
                          "Solar share of land (%)": 100 * solar_km2 / AREA_KM2[c],
                          "Onshore wind 2033 (GW)": w / 1e3, "Wind-farm area incl. spacing (km2)": wind_km2,
                          "Wind share of land (%)": 100 * wind_km2 / AREA_KM2[c],
                          "Land verdict": "Tight" if 100 * (solar_km2 + wind_km2) / AREA_KM2[c] > 5 else "OK"})
        st = ["batteries", "hydro_pump_storage_closed_loop", "hydro_pump_storage_open_loop"]
        s25 = sum(e25.get(t, 0) for t in st); s33 = sum(team_capacity(c, t, sel, cap, e25) for t in st)
        storage_rows.append({"Country": c, "Storage 2025 (GW)": s25 / 1e3, "Storage team 2033 (GW)": s33 / 1e3,
                             "Change (%)": 100 * (s33 / s25 - 1) if s25 else None,
                             "+20% target met": "YES" if s33 >= 1.2 * s25 else "NO"})

    # manual items from the review
    extra = [
        {"Country": "iberian-peninsula", "Technology": "hydro_reservoir", "Required (GW/yr)": 0.69, "Historical best (GW/yr)": None,
         "Historical note": "+4.8 GW of new dams in 7 years; large hydro takes >10 years", "Required / historical": None,
         "Verdict": "Unrealistic", "Source": "-"},
        {"Country": "iberian-peninsula", "Technology": "nuclear (0 GW)", "Required (GW/yr)": None, "Historical best (GW/yr)": None,
         "Historical note": "Spain's own plan keeps ~3 GW to 2030 and exits by 2035", "Required / historical": None,
         "Verdict": "Faster than official plan", "Source": "S11"},
        {"Country": "poland", "Technology": "coal (+2.9 GW)", "Required (GW/yr)": None, "Historical best (GW/yr)": None,
         "Historical note": "New coal capacity contradicts the -30% GHG target and is hard to finance under EU ETS", "Required / historical": None,
         "Verdict": "Unrealistic", "Source": "-"},
    ]
    build = pd.DataFrame(build_rows + extra)

    readme = pd.DataFrame({"Item": [
        "Purpose", "Inputs", "Build-rate method", "Verdict rule", "Batteries rule", "Land-use method", "Caveats", "Generated"],
        "Description": [
            "Check whether the 2033 capacities in input/long_term_uc/countries/*.json can be built in 7 years (2026-2033) and how much land they need.",
            "Team files as found on disk; ERAA 2023.2 capacities for 2025 and 2033 (S30). If a type is not in selected_prod_types it counts as 0; if it is listed but no capacity is given, the 2025 ERAA value is used (same rule as the official model).",
            "Required build rate = (team 2033 - ERAA 2025) / 7 years, compared with the best recent annual addition in that country (sheet Sources).",
            "Required / historical <= 1: Realistic; 1-2: Ambitious; > 2 or no history: Unrealistic.",
            "Batteries (assuming 2 h): Unrealistic if the country alone needs > 50% of Europe's 2024 battery additions (21.9 GWh, S29); Ambitious if > 20%.",
            f"Solar: {SOLAR_HA_PER_MW} ha/MW total area (NREL, S20) - upper bound, rooftop PV uses no land. Onshore wind: {WIND_KM2_PER_MW} km2/MW total area incl. spacing (inside NREL range, S21); the turbines themselves occupy only a small fraction, the rest can stay farmland.",
            "Historical figures are from secondary sources (news / industry reports) and differ slightly between sources; Norway and Denmark 2024 wind additions were not found. Country areas are approximate. Policy facts are as of the dates of the sources.",
            f"{date.today().isoformat()} by scandinavia-2033/feasibility_check.py"]})

    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        readme.to_excel(xw, sheet_name="README", index=False)
        build.to_excel(xw, sheet_name="Build_rate_check", index=False)
        pd.DataFrame(land_rows).to_excel(xw, sheet_name="Land_use", index=False)
        pd.DataFrame(storage_rows).to_excel(xw, sheet_name="Storage_target", index=False)
        pd.DataFrame(cap_rows).to_excel(xw, sheet_name="Capacities_by_country", index=False)
        pd.DataFrame(POLICY, columns=["Country", "Fact", "Source"]).to_excel(xw, sheet_name="Policy_context", index=False)
        pd.DataFrame(SOURCES, columns=["ID", "Description", "URL / location"]).assign(
            Accessed="2026-11-19").to_excel(xw, sheet_name="Sources", index=False)

    # formatting
    wb = load_workbook(OUT)
    fills = {"Realistic": "C6EFCE", "OK": "C6EFCE", "YES": "C6EFCE", "Ambitious": "FFEB9C", "Tight": "FFEB9C",
             "Faster than official plan": "FFEB9C", "Unrealistic": "FFC7CE", "NO": "FFC7CE", "Check": "D9D9D9"}
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="305496")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(12, width + 2), 90)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, float):
                    cell.number_format = "0.00"
                if isinstance(cell.value, str) and cell.value in fills:
                    cell.fill = PatternFill("solid", fgColor=fills[cell.value])
                if ws.title in ("README", "Policy_context", "Sources", "Build_rate_check"):
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(OUT)
    print("written", OUT)


if __name__ == "__main__":
    main()
