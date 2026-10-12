# Dataset Attribution

This project includes a **modified and reduced extract** of the [OpenCEM Dataset](https://github.com/OpenCEM-platform/opencem-dataset), originally collected from the CUHK-Shenzhen campus photovoltaic and battery microgrid.

- **Source repository:** https://github.com/OpenCEM-platform/opencem-dataset
- **Source measurement partition:** https://github.com/OpenCEM-platform/opencem-dataset/blob/main/data/measurements/2025-12-b.csv
- **Changes made:** selected inverter 1; selected December 17–19, 2025 in Asia/Shanghai; retained PV voltage, current, power, temperature and timestamps; removed unusable readings; reduced the measurement frequency to approximately one reading per two minutes; packaged 2,160 rows as `data/telemetry_sample.csv` for accelerated local replay.
- **Data license:** [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) as identified in the upstream dataset metadata and repository README. Preserve source attribution when sharing the derived CSV.
- **Upstream software repository license:** MIT. The upstream dataset and its software components have separate licensing statements; this file provides attribution for the data subset only.

## Academic reference

T. S. Bartels, R. Wu, X. Lu, Y. Lu, F. Xia, H. Yang, Y. Chen, and T. Li, "Bridging Natural Language and Microgrid Dynamics: A Context-Aware Simulator and Dataset," arXiv:2604.05429, 2026.

- Paper: https://arxiv.org/abs/2604.05429

The sample measurements are **historical recordings**, not readings taken by this project's authors or a currently connected physical inverter.
