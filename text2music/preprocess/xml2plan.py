import os
import pickle
import numpy as np
from text2music.data.utils.xml2plan import get_full_plan_pipeline

def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(i) for i in obj]
    elif isinstance(obj, set):
        return [convert_numpy(i) for i in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def convert_xml_list_to_plan_pkl(xml_file_list):
    """
    Convert a list of .xml files into .pkl plan files using get_full_plan_pipeline.
    Saves the .pkl file in the same folder as the .xml file.
    """

    os.makedirs("xml2plan_logs", exist_ok=True)

    for xml_path in xml_file_list:
        try:
            if not xml_path.endswith(".xml"):
                continue

            # Output file (.pkl in same directory)
            pkl_path = os.path.splitext(xml_path)[0] + ".pkl"
            os.makedirs(os.path.dirname(pkl_path), exist_ok=True)

            # Compute plan
            plan = get_full_plan_pipeline(xml_path)

            # Convert numpy objects to vanilla Python
            plan = convert_numpy(plan)

            # Save .pkl
            with open(pkl_path, "wb") as f:
                pickle.dump(plan, f)

        except Exception as e:
            # Log errors
            with open("xml2plan_logs/error_log.txt", "a", encoding="utf-8") as logf:
                logf.write(f"{xml_path}: {e}\n")
            continue

# Example usage:
# files = [
#     "/path/to/music1.xml",
#     "/path/to/music2.xml"
# ]
# convert_xml_list_to_plan_pkl(files)