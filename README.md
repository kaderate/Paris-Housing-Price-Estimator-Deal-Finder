# Paris Rent Estimator & Deal Finder 

**An end-to-end Data Science pipeline to scrape real-time Parisian rental listings, estimate fair market prices using Machine Learning, and detect undervalued deals.**

---

## Project Overview
Finding an apartment at a fair price in Paris is a major challenge due to high demand and significant price variance. 

This project automates the entire data lifecycle to detect market anomalies:
1. **Automated Scraping**: Crawls live rental listings in Paris using [Playwright](https://playwright.dev/).
2. **Data Cleaning & Filtering**: Purges outliers and cleans structural features using [Pandas](https://pandas.pydata.org/).
3. **ML Modeling**: Estimates rental prices using a `RandomForestRegressor` with target log-transformation (`log1p`) and column-specific preprocessing.
4. **Deal Detection Engine**: Isolates listings priced $\ge 15\%$ below their estimated market value using **unbiased out-of-fold predictions**.

---

## Pipeline Architecture

```text
┌────────────────────────┐      ┌─────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│      Web Scraping      │ ───> │     Data Cleaning       │ ───> │    Machine Learning    │ ───> │      Deal Engine       │
│  (Playwright - Python) │      │   (Pandas & Outliers)   │      │ (Random Forest & Pipe) │      │ (Out-of-fold anomalies)│
└────────────────────────┘      └─────────────────────────┘      └────────────────────────┘      └────────────────────────┘
```

1. **Scraping** ([scrap.py](file:///Users/ennio/Documents/Projet_Scrap/scrap.py)): Extracts rental price, surface area ($m^2$), room count, district (arrondissement), and energy efficiency rating (DPE).
2. **Preprocessing** ([model.py](file:///Users/ennio/Documents/Projet_Scrap/model.py)): 
   * Filters out extreme rental outliers (prices > 3000€ and price/$m^2$ outside the 15€–80€ range).
   * Feature engineering: calculates `Surface par pieces` (average room size) to capture layout density.
3. **Modeling** ([model.py](file:///Users/ennio/Documents/Projet_Scrap/model.py)):
   * Uses `ColumnTransformer` to One-Hot Encode spatial locations (`Arrondissement`) while preserving `DPE` as a numerical/ordinal feature (ratings scaled from G=1 to A=7).
   * Fits a `RandomForestRegressor` on log-transformed targets to handle right-skewed pricing distributions.
4. **Evaluation & Deal Search**:
   * Uses `cross_val_predict` to obtain unbiased estimations for all properties.
   * Compares the listed price against the model's prediction. Listings with a discount $\ge 15\%$ are exported to [Appartement_interessant.csv](file:///Users/ennio/Documents/Projet_Scrap/Appartement_interessant.csv).

---

## Model Performance & Results Explanation
The pipeline is evaluated using 5-fold cross-validation on the entire dataset to compute unbiased metrics on the original rental price scale (Euros):
* **Mean Absolute Error (MAE)**: **209.15 €**
* **R² Score (Coefficient of Determination)**: **0.766 (76.6%)**

### How to interpret these results?
1. **R² of 76.6%**: Our features (`Surface`, `Arrondissement`, `Pieces`, `DPE`, and `Surface par pieces`) capture over three-quarters of the rent variation in Paris. Considering the simplicity of these inputs, this is an outstanding baseline.
2. **MAE of ~209€**: On average, the model's price estimation deviates by 209€ from the actual listed price. Given that Parisian rents in our dataset range up to 3000€ (with a median around 1300€–1500€), this corresponds to an average relative error of roughly **14% to 16%**.
3. **The Unpredictable Variance (Noise)**: Real estate prices are heavily influenced by qualitative features that our scraper cannot capture:
   * **Furnished Status**: Furnished flats usually command a 10% to 15% rent premium in Paris.
   * **Building Assets**: Elevators, higher floors with natural light, terraces, balconies, or views (e.g., Eiffel Tower).
   * **Condition**: A brand new renovated flat vs. a run-down unit.
   * **Micro-location**: Proximity to a specific prestigious street or metro station.

### Impact on the Deal Finder
Since our target discount threshold is set to **$\ge 15\%$**, it operates right at the margin of the model's average error. Therefore:
* Some flagged "deals" may be **justified lower prices** (e.g., a noisy 6th floor apartment without an elevator).
* The script serves as a **first-pass intelligent recommendation system**, filtering out 98% of the market noise so a human-in-the-loop can quickly review the remaining high-potential listings.

---

## 📁 Repository Structure
* [main.py](file:///Users/ennio/Documents/Projet_Scrap/main.py): Pipeline orchestrator.
* [scrap.py](file:///Users/ennio/Documents/Projet_Scrap/scrap.py): Playwright script to fetch real-time listings (with per-page retries and a run history).
* [model.py](file:///Users/ennio/Documents/Projet_Scrap/model.py): Data cleaning, preprocessing pipeline, ML training, and deal extraction.
* `report.py`: Generates a human-readable Markdown summary of the detected deals.
* `config.py`: Central place for URLs, file paths, and thresholds (outlier bounds, discount threshold).
* `tests/`: Unit tests (pytest) covering data cleaning and deal-detection logic.
* `Data_Loyer.csv`: Latest scraped raw listings dataset.
* `Data_Loyer_historique.csv`: Cumulative, de-duplicated history of listings seen across scraping runs.
* [Appartement_interessant.csv](file:///Users/ennio/Documents/Projet_Scrap/Appartement_interessant.csv): Exported deals under market value.
* `rapport_bonnes_affaires.md`: Markdown report of the current best deals, regenerated on every run.

---

## ⚙️ Installation & Usage

1. **Clone the repository**:
   ```bash
   git clone https://github.com/BL1ZZ4RD-PY/Paris-Housing-Price-Estimator-Deal-Finder.git
   cd Paris-Housing-Price-Estimator-Deal-Finder
   ```

2. **Create a virtual environment and install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```
   > On macOS with Homebrew Python, running `pip install` outside a virtual environment raises an `externally-managed-environment` error (PEP 668). Using a `venv` as shown above avoids this.

3. **Run the pipeline**:
   ```bash
   python main.py
   ```
   Optionally restrict the detected deals to your own search criteria:
   ```bash
   python main.py --surface-min 20 --surface-max 40 --budget-min 800 --budget-max 1200
   ```
   All four flags are optional and can be combined freely (`--surface-min`, `--surface-max`, `--budget-min`, `--budget-max`).

4. **Run the test suite**:
   ```bash
   pytest
   ```
