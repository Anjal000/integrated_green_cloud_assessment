# IGCAF · Green Cloud Lab

A runnable **Python + Streamlit** research prototype accompanying the *Evolution of Green Cloud Computing* literature review.

## Run locally

1. Install Python 3.10+.
2. Unzip the project and open a terminal inside the `igcaf_streamlit` folder.
3. Create a virtual environment (recommended):

   Windows PowerShell:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   macOS/Linux:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Install dependencies and launch:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
5. Open the printed local address (usually `http://localhost:8501`).

## What the simulator does

- Generates reproducible task arrivals, CPU load, duration and deadlines.
- Simulates three geographical regions with synthetic electricity carbon intensity, PUE, water usage factors and prices.
- Compares **Traditional**, **Consolidation**, **Carbon-aware** and **Integrated IGCAF** policies using identical input tasks.
- Reports energy (kWh), operational and allocated embodied emissions (kgCO₂e), water (litres), electricity cost, deadline success and carbon intensity per completed task.
- Exports a policy summary CSV, hourly results CSV and complete experiment JSON.

## Design assumptions and important cautions

- The simulator models one-hour slots and fractional CPU capacity per server; it is not a hardware-level digital twin.
- All regional input data are invented *example scenarios*, **not live regional carbon data** or estimates of real locations.
- Energy model: a server draws configurable idle watts plus a linear CPU-utilization term. Off servers draw 0 W in this simplified model. A configurable transition energy is charged when inactive servers become active.
- Traditional policy keeps all servers powered, and schedules on the first feasible time in region 1; this is a deliberately inefficient reference, not a representative optimized production cloud.
- Consolidation packs tasks more tightly; carbon-aware policy chooses locations/hours with lower *modeled* operational emissions; IGCAF uses combined energy, emissions, water, cost and latency/delay scores, plus a simple 6% low-load power saving assumption.
- Power Usage Effectiveness (PUE) is applied to total simulated IT energy, including wake transitions.
- Regional water intensity is applied per *facility* kWh, as an illustrative operational water measure.
- Allocated embodied emissions are based on *active server-hours* for convenience, not a complete life-cycle allocation (which would include idle installed equipment). Label any paper results accordingly.
- Deadline failures are reported, and any carbon saving alongside different numbers of completed tasks must be interpreted carefully.
- No network/replication overhead is modeled; environmental gains cannot be generalized from this synthetic prototype.

## Fair experiment design

For your paper, fix the same random seed, number of servers, workload and regional factors across policies. Report both absolute totals and per-completed-task indicators and ensure deadline success rates are reasonably comparable. Sweep seeds, server fleet sizes, and task counts to assess sensitivity. Describe all input assumptions and report any SLA differences rather than hiding them.

## Run tests

```bash
pytest -q
```

## Paper connection

Implements a **conceptual illustrative simulation** for IGCAF section 9, not a peer-reviewed or experimentally validated improvement. The scoring heuristic is not an exact optimization solver. Compare the measured simulated outputs as a proposed exploratory study, not real energy savings.

## Credits / measurement reference

Green Software Foundation, [Software Carbon Intensity specification](https://sci.greensoftware.foundation/) — reference for operational and embodied carbon accounting per functional unit. The app's metric is intentionally labelled *SCI-like* because hardware life-cycle allocation is simplified.
