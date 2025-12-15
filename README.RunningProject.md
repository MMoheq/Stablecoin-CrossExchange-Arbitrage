-- How to run Project and Get Results 

# 1) (optional) create + activate venv
python -m venv .venv
.venv\Scripts\Activate.ps1   # PowerShell

# 2) install dependencies
pip install -r requirements.txt

# 3) run Streamlit UI
streamlit run scripts/ui.py

# 4) run experiments
python experiments/monte_carlo_simulation.py
python experiments/final_cash_test.py
python experiments/test_astar_vol_toygraph.py
python experiments/run_h1_unit_tests.py
python experiments/run_h2_unit_tests.py
python experiments/run_h3_unit_tests.py
python experiments/run_h4_unit_tests.py
