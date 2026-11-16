# A) More details about this environment, in teacher role

Globally, the logic is to **provide here some complements versus the doc available to the students** [European-system_tutorial.md](../long_term_uc/European-system_tutorial.md):

1) Either some **detailed information related to UC modelling**, explaining some of the (simplifying) choices made when parameterizing the environment.

2) Or **some functionalities available in this environment that are not described in the student documentation**, in order to help students get started more easily with the tool.

To make the link between teachers and students doc **references to the sections of the students doc 
will be made hereafter**.

# B) About data

## B.1) General information

In folder [data](../../data)

Mainly **containing ERAA data** used to: (i) Calculate some metrics and plot some graphs in the "Data Crunch" session; (ii) Parametrize the UC problems simulated in this environment. 

N.B. (Now a bit old) **2023.2 edition data** is used; the main drawback being about the climatic years:
1) They are in fact "weather scenarios" - not obtained after a projection of climatic conditions in the future.
2) However named climatic years (CY) in the data and in this environment.

  Starting from 2024 edition, climatic projections are accounted for in ERAA; using these data instead would make the terminology used in this environment coherent (for a future edition of this course!).

## B.2) On composite - and possibly a bit complex! - fuel sources data

In folder [fuel_sources](../../data/fuel_sources)

It contains complementary data, provided for information but not all directly used in this code environment:
  
- [fuel_data_description.txt](../../data/fuel_sources/fuel_data_description.txt): detailed description of the data 
contained in this folder, i.e. the one in the two following files.
- [raw_params.json](../../data/fuel_sources/raw_params.json): detailed cost data, and CO2 emissions, 
per production type. 
  - **From this file, ONLY CO2 emissions are directly used in this environment**; 
  - Regarding detailed cost values (<span style="color:#32B032; font-weight:bold">energy_density_per_ton</span>, etc.), they are provided for information.
  - Finally, regarding the - very key for UC modelling! - <span style="color:#32B032; font-weight:bold">marginal_cost</span> values, they
  are obtained from [elec-europe_params_fixed.json](../../input/_env_params/elec-europe_params_fixed.json) (and can be overwritten 
by the ones of [fuel_sources_to-be_modif.json](../../input/long_term_uc/fuel_sources_to-be_modif.json), if 
present in the environment).
- [technology_datacrunch.json](../../data/fuel_sources/technology_datacrunch.json) 
  - Contains main technico-eco infos about the production types used in this environment. 
  - It is used in the "data crunch" session based on [data_crunch.ipynb](../../data_crunch.ipynb).

    N.B. [technology_datacrunch.json](../../data/fuel_sources/technology_datacrunch.json) (for data crunch) and [elec-europe_params_fixed.json](../../input/_env_params/elec-europe_params_fixed.json)
(for UC simulation) values are coherent; in particular the formula used to obtain <span style="color:#32B032; font-weight:bold">marginal_cost</span>
values from detailed parameters is 

  <span style="color:#32B032; font-weight:bold">marginal_cost</span> = cost_per_ton/(efficiency * energy_density_per_ton) + vom_cost, CO2 emission costs being optionally added elsewhere in the environment.

# C) On doc about this environment

As briefly explained above: 
- A **doc dedicated to the students** [European-system_tutorial.md](../long_term_uc/European-system_tutorial.md) to easily start with this environment, and the associated serious game. 
- The **present one to get more insights** - useful **for teachers** in particular.

The student doc does not describe all the functionalities available in this environment. Teachers (you!) may wish to introduce some of the more advanced features to students once they are comfortable with the basic ones.

# D) About input folder

Folder [input](../../input)

## D.1) On main functionalities the students will be playing with

Containing parameters to be changed by students to play with the different scripts of this environment.

Following are **additional info versus the ones detailed in** [European-system_tutorial.md](../long_term_uc/European-system_tutorial.md) - in Sec. II.1):

- [elec-europe_params_to-be-modif.json](../../input/long_term_uc/elec-europe_params_to-be-modif.json):  
    - (optional, to be added in <span style="color:#32B032; font-weight:bold">extra_params</span> dictionary) <span style="color:#32B032; font-weight:bold">state_of_charge_init_pu</span>: to set an initial SoC per stock-like asset, add this key to <span style="color:#32B032; font-weight:bold">extra_params</span> dictionary, under the form {(stock-like) prod unit fulle name: initial SoC} (<span style="color:#257cbd; font-weight:bold">dictionary of floats in [0, 1]</span>). Default: 0.8 will be applied in UC model.
   
      Ex: add the following content to this JSON file (first/last bracket is the first-level one of this file)
  
      ```json
      {
        "extra_params": {
          "state_of_charge_init_pu": {
            "fra_hydro_reservoir": 0.8,
            "ger_hydro_reservoir": 0.2
          }
        }
      }      
      ```

      N.B. The trigrams of the countries have to be used in prod unit "full name" (the ones used in PyPSA model).
    - (optional, in <span style="color:#32B032; font-weight:bold">extra_params</span> dictionary) <span style="color:#32B032; font-weight:bold">co2_emis_price</span>: to add a cost associated to CO2 emissions
    in UC objective function (<span style="color:#257cbd; font-weight:bold">non-negative float</span>, €/tCO2eq.). Default: 0€/tCO2eq.
  
      N.B. In chosen approach, generator i <span style="color:#32B032; font-weight:bold">marginal_cost</span> attribute is increased with a term emission_factor_i * co2_emis_price / efficiency_i; 
      this CO2 emission cost has no dedicated term in obtained formulation (that can be read in .lp file). In turn, a global marginal cost as the one used in Data Crunch session can then be obtained.
    - (optional, in <span style="color:#32B032; font-weight:bold">extra_params</span> dictionary) <span style="color:#32B032; font-weight:bold">use_demand_adder_files</span>: use demand-adder files in folder [demand](../../input/long_term_uc/optional/demand). If present, their data will be added - per climatic year, and date - to the one of ERAA data (<span style="color:#257cbd; font-weight:bold">boolean</span>). 
  
      Default: false (and ERAA raw data from [demand](../../data/ERAA_2023-2/demand) will be used).
    - (optional) <span style="color:#32B032; font-weight:bold">add_date_tag_to_output</span>: to **add a tag indicating the run date** to the obtained data/figure output folders (<span style="color:#257cbd; font-weight:bold">boolean</span>). 
  
      Default: no such tag, in this case a previous run results may be overwritten.
    
      N.B. This tag is applied prioritarily versus the run index one (activated with parameter <span style="color:#32B032; font-weight:bold">add_run_idx_tag_to_output</span>, as done in initial version of the environment made available to the students).
    - (optional) <span style="color:#32B032; font-weight:bold">save_explicit_corresp_for_lp_elts</span>: save two files with 
    correspondence between PyPSA "abstract" variable/constraint names (e.g., x_i for variables) and explicit ones? (<span style="color:#257cbd; font-weight:bold">boolean</span>)
  
      Default: do not save these files.
    
      N.B. The variable names mapping is not necessarily complete, in the sense that a variable x_j may be absent for some index j, 
   whereas variables x_{j-k} and x_{j+k'} are provided. In the present model, this situation typically arises for spillage variables, 
   which are undefined for some production units e.g., DSR units and batteries. By contrast, the mapping between constraints is complete 
   and well-defined for all indices between 1 and the number of modeled constraints.
    - (optional) <span style="color:#32B032; font-weight:bold">save_link_capa_dual_vars</span>: save dual variables associated to link capacity constraints in a .csv file (in [data](../../output/long_term_uc/data)) (<span style="color:#257cbd; font-weight:bold">boolean</span>).
  
      Default: false (no such files obtained in [data](../../output/long_term_uc/data)).
    - (optional) <span style="color:#32B032; font-weight:bold">save_custom_const_dual_vars</span>: idem, but for "custom" constraints, the "sumprod" ones described below - and used currently only to set upper bounds on CO2 emissions (<span style="color:#257cbd; font-weight:bold">boolean</span>).
  
      Default: false (no such files obtained in [data](../../output/long_term_uc/data)).
  
      N.B. The obtained file *sumprod-const-duals_{ty}_{cy}_{uc run start}.csv* has two columns: (i) Name of the constraint, with a suffix joining the "initials" of the countries associated to the considered constraint (first letter of the country, excepting "ip" for Iberian-Peninsula and "it" for Italy), excepting if whole Europe is considered then "_eur" is used; (ii) Value of the dual variable (a float).
  
    - (optional) <span style="color:#32B032; font-weight:bold">plot_link_capa_saturation</span>: plot sunburst graph with 3-levels (1. Non-oriented link name, 2. Direction, 3. Period of the day)
    to illustrate in an aggregate manner the saturation of link capacities (<span style="color:#257cbd; font-weight:bold">boolean</span>). 

      Default: false (no such files obtained in [figures](../../output/long_term_uc/figures)).

## D.2) On optional functionalities

### D.2.1) To model more precisely hydraulic assets

To add (i) **Min./max. generation** or (ii) **Filling levels** for the hydraulic assets, **associated data** (files described in 
Appendix A2.1 of students doc) **can be provided**: 
1) Either in ERAA data [hydro](../../data/ERAA_2023-2/hydro) folder. 
2) Or in adding/filling files in [optional input folder](../../input/long_term_uc/optional). 

For the students to get more realistic hydraulic results from the beginning, option 1) has been activated in version used for this course.

Note that **for both additional inputs (i) and (ii), the presence of a file for considered year, and country, will imply that such constraints will be 
added to the UC model** simulated (if file in proper format!).

### D.2.2) On "Sumprod" constraints: a more complex usage than the one actually described to the students for max. CO2 emissions is possible

Some **constraints expressed based on a weighted sum of production on a set of units and time-slots** can be very helpful 
to enrich the description of UC problems; typical cases are: 
1) An **upper bound on CO2 emissions**. 
2) A **minimal amount of production** generated **from a subset of units** (based on some "taxonomy").
3) A maximal UC cost.

N.B. In current version of students doc, only CO2 emissions upper bound functionality is described.

**Functionally** - enriching the description made in students doc:
  - In [input/long_term_uc/elec-europe_params_to-be-modif.json](../../input/long_term_uc/elec-europe_params_to-be-modif.json): 
    - In <span style="color:#32B032; font-weight:bold">extra_params</span> dictionary
      - With following fields:
        - <span style="color:#32B032; font-weight:bold">max_co2_emis_constraints</span> (resp. <span style="color:#32B032; font-weight:bold">max_prod_cost</span>) for an upper bound on CO2 emissions (resp. UC cost)
        - When defining the <span style="color:#32B032; font-weight:bold">cases</span>, the additional key <span style="color:#32B032; font-weight:bold">temporal_granularity</span> can be used: <span style="color:#32B032; font-weight:bold">day</span>, <span style="color:#32B032; font-weight:bold">week</span> or <span style="color:#32B032; font-weight:bold">whole_period</span>. 
        
          Default: "whole_period", the one used by students in current version of the environment (without specifying this attribute value). 
        
          N.B. When weekly periods are considered they are starting on Mondays.
       - In <span style="color:#32B032; font-weight:bold">cases</span> definition, <span style="color:#32B032; font-weight:bold">upper_bound</span> 
       can be either a <span style="color:#257cbd; font-weight:bold">float</span>, or <span style="color:#257cbd; font-weight:bold">list of float</span>. 
       If float, either it corresponds to a case with 
         <span style="color:#32B032; font-weight:bold">temporal_granularity</span>=whole_period, or in which the same bound will be applied to each period. 
      
        N.B.

         (i) <span style="color:#32B032; font-weight:bold">upper_bound</span> can
         be replaced by <span style="color:#32B032; font-weight:bold">lower_bound</span> (resp. <span style="color:#32B032; font-weight:bold">equal</span>) if a lower bound (resp. equality) constraint is to be applied. 
         
         (ii) If a vector is provided, its size must correspond to the number of (daily/weekly) periods in considered
         optimization period. If not the case, or the number of time-slots in considered model does not correspond, 
         the code will raise an error/warning. 
    
         (iii) When a weekly temporal granularity is used and some weeks are only 
         partial (with strictly less than 7 days) a proportional factor is applied in the code to lower the value written
         in this JSON (which must be interpreted as corresponding to a whole week, to be comparable with other ones in
         provided vector).
    
Example (enriched versus student one):

```json
{
  "extra_params": {
    "max_co2_emis_constraints": {
      "temporal_granularity": "week",
      "cases": [
        {
          "countries": [
            "france",
            "germany"
          ],
          "upper_bound": [
            1,
            2,
            3,
            4
          ]
        }
      ]
    }
  }
}
```

### D.2.3) Use "demand-adders"

Adding files *demand-adder_{year}_{country}.csv*, ERAA demand data can be modified (see very simple [demand-adder_2033_france.csv](../../input/long_term_uc/optional/demand/demand-adder_2033_france.csv) example). WARNING:
* These files must be in [demand](../../input/long_term_uc/optional/demand) folder.
* With name *demand-adder_{year}_{country}.csv*.
* With same format and columns as demand_{year}_{country}.csv files in folder [demand](../../data/ERAA_2023-2/demand). 

  N.B. Only <span style="color:#32B032; font-weight:bold">climatic_year</span> column can be removed; in this case it will be replaced by climatic year selected in current UC run.
* Only values correspnding to current UC period (between <span style="color:#32B032; font-weight:bold">uc_period_start</span>, and <span style="color:#32B032; font-weight:bold">uc_period_start</span> defined in [elec-europe_params_to-be-modif.json](../../input/long_term_uc/elec-europe_params_to-be-modif.json)) will be used in these files.

### D.2.4) On additional - "fixed" information that are provided in input folder

Even if not to be modified by the students, [input](../../input) folder contains the following additional infos: 
- **[NOT TO BE MODIFIED]** [elec-europe_params_fixed.json](../../input/_env_params/elec-europe_params_fixed.json): 
    - <span style="color:#32B032; font-weight:bold">aggreg_prod_types_def</span>: **correspondence between "aggregate" production types (the ones that will be used in this class) and the ones - more detailed - in ERAA data**. It will be used in the data reading phase; to simplify (diminish size!) of the used data in this UC exercise.
    - <span style="color:#32B032; font-weight:bold">gps_coordinates</span>: the ones of the capitals excepting meta-countries with coordinates of Rotterdam for "benelux", Madrid for "iberian-peninsula", and Stockholm for "scandinavia". 
  
      N.B. Only for plotting - very schematic - representation of the "network" associated to your UC model.
    - <span style="color:#32B032; font-weight:bold">eraa_edition</span>: edition of ERAA data used - 2023.2 (one/two ERAA editions per year from 2021).
    - <span style="color:#32B032; font-weight:bold">pypsa_unit_params_per_agg_pt</span>: definition of main PyPSA 
    generators/storage_units attributes to be used in the environment; some of these values will be overwritten based on JSON files to be modified.
    - <span style="color:#32B032; font-weight:bold">units_complem_params_per_agg_pt</span>: indicates from which data/input PyPSA generators/storage_units attributes will be overwritten.
  
      N.B. Specific case of <span style="color:#32B032; font-weight:bold">power_capa</span> that can modified based on ERAA data, and the JSON files to be modified by the students (even_if <span style="color:#32B032; font-weight:bold">from_eraa_data</span> is uniquely mentioned here).

- **[NOT TO BE MODIFIED]** [functional_available-values.json](../../input/_env_params/functional_available-values.json):  
    - <span style="color:#32B032; font-weight:bold">datatypes</span>: list of **type of data names**. Used only for the data crunch session; based on script [my_little_europe_data_analysis.py](../my_little_europe_data_analysis.py) (not used for EELISA2026 course).
  
- **[NOT TO BE MODIFIED]** [pypsa_static_params.json](../../input/_env_params/pypsa_static_params.json):  
    - <span style="color:#32B032; font-weight:bold">min_unit_params_per_agg_pt</span>: list of minimal parameters to be provided when creating different types of generators in PyPSA; otherwise the execution will stop raising an error.
    - <span style="color:#32B032; font-weight:bold">generator_params_default_vals</span>: default values applied when creating PyPSA generators.

# E) On outputs

In folder [output](../../output)

Data obtaining after having run one of the scripts of this environment. Two main subfolders are distinguished:
- **data_analysis**: for... data analysis script (XXX suppr ? XXX)
- **long_term_uc**: for the 1-country/European UC simulation. In this second subfolder 1-country/European output 
folders will be obtained, in which **data** (.csv files, and .lp with optim model solved) and **figures** (.png) 
outputs will be separated 

Normally the content of this folder is sufficiently detailed in students doc - Sec. II.4).

# F) More expert usage of this environment... its behaviour 

**(TO BE FINALIZED)**

Cf. parameters in [functional_params](../../src/functional_params), file by file:

- [plot_params.json](../../src/functional_params/plot_params.json): a few parameters for (color) palette 
definition - possibly using a standard one (e.g., the one of Eco2mix), linestyles, markers, orders of curves. 
It can be done on different dimensions (production types, zones, years, etc.)

<br>

- [usage_params.json](../../src/functional_params/usage_params.json): idem, to allow (or not)/parametrize some 
operations for the students. Per parameter:
  - <span style="color:#32B032; font-weight:bold">allow_adding_interco_capas</span>: possible to add some interconnection (pair of zones) w.r.t. the list in ERAA data? 
    
    Default: false
  - <span style="color:#32B032; font-weight:bold">allow_overwriting_eraa_interco_capa_vals</span>: possible to overwrite interco. capa values of ERAA? 
  (specifying values in [input/long_term_uc/elec-europe_params_to-be-modif.json](../../input/long_term_uc/elec-europe_params_to-be-modif.json)). 
    
    Default: false
  - <span style="color:#32B032; font-weight:bold">allow_manually_adding_demand</span>: possible to add supplementary demand in addition to ERAA one?  
    
    Default: false
  
    N.B. Not functional currently; could be used to integrate "exogeneous" Demand-Side-Response 
  (e.g. based on Time-of-Use tariff, set independently of the UC solution)
  - <span style="color:#32B032; font-weight:bold">allow_manually_adding_generators</span>: ?? 
    
    Default: false
    
    N.B. Idem
  - <span style="color:#32B032; font-weight:bold">apply_cf_techno_breakthrough</span>: apply some "breakthrough" on a technology associated to CF data. In this case, 
  CF values will be applied an increasing transformation to represent this improvement. 
    
    Default: false
  - <span style="color:#32B032; font-weight:bold">apply_per_country_json_file_params</span>: dictionary with following values, indicating for each of the scripts if run
  parameters for a given country must be obtained rom individual country/global european json input file: 
    - <span style="color:#32B032; font-weight:bold">data_analysis</span>: false 
    - <span style="color:#32B032; font-weight:bold">monozone_toy_uc_model</span>: true
    - <span style="color:#32B032; font-weight:bold">multizones_uc_model</span>: true
  
    Q: still useful? (in multizones_uc_model case, behaviour dependently on the chosen mode solo/europe)
  - <span style="color:#32B032; font-weight:bold">apply_per_prod_unit_init_soc</span>: allow to apply per prod unit init SoC values (in Eur. JSON file to be modified); otherwise common default value set when writing PyPSA model (currently 0.8). 
  
    Default: false
  - <span style="color:#32B032; font-weight:bold">get_optional_const_from_data_folder</span>: get data for optional constraints from data folder (available only to the 
  teachers) or input one (in which students can do some modifications)? Can be either a boolean, or a dictionary to 
  specifiy this property per type of constraint; in this latter case available keys are "hydro", "max_co2_emissions", 
  and "max_prod_cost"
  - <span style="color:#32B032; font-weight:bold">res_cf_stress_test_folder</span>: folder in which RES CF of the "stress test" will be found (different 
  folder from the one in which original CF ERAA data are found)
  - <span style="color:#32B032; font-weight:bold">res_cf_stress_test_cy</span>: CY to be used for RES CF stress test; for which associated data must be found in 
  the files provided in <span style="color:#32B032; font-weight:bold">res_cf_stress_test_folder</span> 
  - <span style="color:#32B032; font-weight:bold">use_first_year_capas_as_default</span>: use first year available (in ERAA data) to set generation capas by default, 
  i.e. before applying values set in input JSON per-country files. 
    
    Default: true.
  - <span style="color:#32B032; font-weight:bold">log_level</span>.

    Default: info.
