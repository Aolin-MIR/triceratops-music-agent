import pickle
from text2music.data.utils.xml2plan import get_partial_plan_text, get_full_plan_text

filepath = "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/SymphonyNet_Dataset_MXL_abci/outputs/5334345.pkl"
# filepath = "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/ASAP_MXL_abci/Beethoven/Piano_Sonatas/1-1/xml_score.pkl"

full_plan = get_full_plan_text(filepath)
print("Full Plan:")
print(full_plan)

# Write full plan to a text file
with open("/data/home/acw769/text2score/text2music/notebooks/full_plan.txt", "w", encoding="utf-8") as f:
    f.write(full_plan)

partial_plan = get_partial_plan_text(filepath, genre="classical piano")
print("\nPartial Plan:")
print(partial_plan)

# Write partial plan to a text file
with open("/data/home/acw769/text2score/text2music/notebooks/partial_plan.txt", "w", encoding="utf-8") as f:
    f.write(partial_plan)

# # Inspect Full Plan
# plan_path = "/data/ABC_Dataset/ABC_Dataset/SymphonyNet_Dataset_MXL_abci/outputs/1203.pkl"

# with open(plan_path, 'rb') as f:
#     plan = pickle.load(f)
# print(plan)