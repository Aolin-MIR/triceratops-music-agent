import numpy as np
from scipy import stats

def load_clean_data(filepath):
    """Loads data from txt, ignores headers, and drops NaNs."""
    clean_data = []
    
    try:
        with open(filepath, 'r') as file:
            for line in file:
                line = line.strip().lower()
                
                # Skip the header, empty lines, and explicit 'nan' strings
                if not line or 'compression' in line or line == 'nan':
                    continue
                
                try:
                    clean_data.append(float(line))
                except ValueError:
                    pass # Ignore any other non-numeric text gracefully
                    
    except FileNotFoundError:
        print(f"Error: Could not find file '{filepath}'")
        return np.array([])
        
    return np.array(clean_data)

def main():
    # --- CONFIGURATION ---
    # Replace these strings with the actual paths to your text files
    text2score_file = '/data/home/acw769/text2score/text2music/scripts/results/text2score_gemma_31B_compression.txt'
    baseline_file = '/data/home/acw769/text2score/text2music/scripts/results/text2score_glm_compression.txt'
    # ---------------------
    
    # Load and clean the data
    t2s_data = load_clean_data(text2score_file)
    base_data = load_clean_data(baseline_file)
    
    if len(t2s_data) == 0 or len(base_data) == 0:
        print("Error: One or both datasets are empty. Check your filepaths.")
        return
    
    # Calculate means for the report
    t2s_mean = np.mean(t2s_data)
    base_mean = np.mean(base_data)
    
    # Perform Welch's t-test (equal_var=False)
    # nan_policy='omit' is a fallback just in case any np.nan objects made it through
    t_stat, p_val = stats.ttest_ind(t2s_data, base_data, equal_var=False, nan_policy='omit')
    
    # Print the results
    print("=== COMPRESSION RATIO SIGNIFICANCE TEST ===")
    print(f"Text2Score: N = {len(t2s_data):<4} | Mean = {t2s_mean:.4f}")
    print(f"Baseline:   N = {len(base_data):<4} | Mean = {base_mean:.4f}")
    print("-" * 43)
    
    # Format p-value output
    if np.isnan(p_val):
        print("Result: Could not calculate p-value (check data variance/size).")
    else:
        print(f"t-statistic: {t_stat:.4f}")
        if p_val < 0.001:
            print("p-value:     < 0.001 ***")
        else:
            print(f"p-value:     {p_val:.4f}")
        
        # Significance conclusion
        if p_val < 0.05:
            print("\nConclusion: The difference is statistically significant (p < 0.05).")
        else:
            print("\nConclusion: The difference is NOT statistically significant (p >= 0.05).")

if __name__ == "__main__":
    main()