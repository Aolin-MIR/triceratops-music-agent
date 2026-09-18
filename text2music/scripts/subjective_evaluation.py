import pandas as pd
import statsmodels.formula.api as smf
import numpy as np

# ---------------------------------------------------------
# 1. LOAD & RESHAPE (Fixing the ValueError)
# ---------------------------------------------------------
# We use index_col=[0,1] to immediately set Participant and Seed as the index.
# This prevents them from being treated as regular columns that conflict later.
df = pd.read_csv('/data/home/acw769/text2score/text2music/scripts/Results_Formatted.csv', header=[0, 1])

# 2. Identify the first two columns (Participant and Seed)
#    In a multi-header load, these often get messy names like "Participant" and "Unnamed..."
#    We force rename them to ensure we can target them.
#    (We target the LEVEL 0 names of the first two columns)
df.rename(columns={df.columns[0]: 'Participant', df.columns[1]: 'Seed'}, inplace=True)

# 3. Drop the "Separator" columns
#    Your CSV has double commas ",," which creates columns named "Unnamed" filled with NaN.
#    We drop any column where the top header contains "Unnamed".
df = df.loc[:, ~df.columns.get_level_values(0).str.contains('Unnamed')]

# 4. Set the Index Explicitly
#    Now that we have clean columns, we move Participant and Seed to the index.
#    We use the first level of the column MultiIndex to find them.
df = df.set_index([('Participant', 'Unnamed: 0_level_1'), ('Seed', 'Unnamed: 1_level_1')])

# 5. Clean up Index Names
df.index.names = ['Participant', 'Seed']

# 6. Stack and Reset
#    Now we safely stack the remaining columns (Metric and Model).
df_long = df.stack(level=[0, 1]).reset_index()

# 7. Rename the final columns
df_long.columns = ['Participant', 'Seed', 'Metric', 'Model', 'Score']

# Force numeric scores
df_long['Score'] = pd.to_numeric(df_long['Score'], errors='coerce')

print("--- Data Successfully Reshaped ---")
print(df_long.head())




# ---------------------------------------------------------
# 2. RUN ANALYSIS & GENERATE LATEX
# ---------------------------------------------------------

# Define the order of metrics for your table (optional, matches your example)
ordered_metrics = ['Prompt Adherence', 'Readability', 'Musicality', 'Authenticity', 'Usability']
results_store = []

print("Running LMMs...")

for metric in ordered_metrics:
    # Filter data
    data_subset = df_long[df_long['Metric'] == metric].copy()
    
    # A. Calculate Arithmetic Means (MOS) for the table
    means = data_subset.groupby('Model')['Score'].mean()
    
    # B. Run LMM for P-values
    # Note: We wrap this in try/except in case of convergence warnings, though your data looks fine
    try:
        model = smf.mixedlm(
            "Score ~ C(Model, Treatment(reference='Text2Score'))", 
            data=data_subset, 
            groups=data_subset["Participant"], 
            vc_formula={"Seed": "0 + C(Seed)"}
        )
        fit = model.fit()
        
        # Extract p-values specifically for the models
        # The names will look like: C(Model, Treatment(reference='Text2Score'))[T.ComposerX]
        p_vals = fit.pvalues
        
        cx_p = p_vals[fit.model.exog_names.index("C(Model, Treatment(reference='Text2Score'))[T.ComposerX]")]
        midi_p = p_vals[fit.model.exog_names.index("C(Model, Treatment(reference='Text2Score'))[T.MidiLLM]")]
        
    except Exception as e:
        print(f"Error fitting {metric}: {e}")
        cx_p = 1.0
        midi_p = 1.0

    # Store results
    results_store.append({
        'Metric': metric,
        'T2S_Mean': means.get('Text2Score', 0),
        'CX_Mean': means.get('ComposerX', 0),
        'CX_P': cx_p,
        'Midi_Mean': means.get('MidiLLM', 0),
        'Midi_P': midi_p
    })

# ---------------------------------------------------------
# 3. PRINT LATEX TABLE BODY
# ---------------------------------------------------------

def format_p(p):
    if p < 0.001:
        return "$<0.001$"
    else:
        return f"${p:.3f}$"

print("\n" + "="*30 + " LATEX OUTPUT " + "="*30)
print(r"% Paste this inside your tabular environment")

for row in results_store:
    metric = row['Metric']
    t2s = f"\\textbf{{{row['T2S_Mean']:.2f}}}" # Bold the main model mean
    cx_mean = f"{row['CX_Mean']:.2f}"
    cx_p = format_p(row['CX_P'])
    midi_mean = f"{row['Midi_Mean']:.2f}"
    midi_p = format_p(row['Midi_P'])
    
    # Construct the row string
    # Format: Metric & Text2Score & ComposerX Mean & P-val & MidiLLM Mean & P-val \\
    latex_row = f"{metric} & {t2s} & {cx_mean} & {cx_p} & {midi_mean} & {midi_p} \\\\"
    print(latex_row)

print("="*74)
