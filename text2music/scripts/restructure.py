import os
import shutil
from pathlib import Path

# Set the root directory for your baseline
root_dir = '/gpfs/scratch/acw769/text2score/midillm_outputs_2'  # Update this to your actual path

# Iterate through each subdirectory (1, 2, 3, etc.)
subdirs = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]

for subdir in subdirs:
    subdir_path = os.path.join(root_dir, subdir)
    
    # Define target paths
    mid_folder = os.path.join(subdir_path, 'mid')
    xml_folder = os.path.join(subdir_path, 'xml')
    
    # Create the folders if they don't exist
    os.makedirs(mid_folder, exist_ok=True)
    os.makedirs(xml_folder, exist_ok=True)
    
    # Define file paths
    old_midi = os.path.join(subdir_path, 'midi.mid')
    old_xml = os.path.join(subdir_path, 'midi.xml')
    
    # Move the MIDI file
    if os.path.exists(old_midi):
        shutil.move(old_midi, os.path.join(mid_folder, 'midi.mid'))
        print(f"Moved MIDI in {subdir}")
        
    # Move the XML file
    if os.path.exists(old_xml):
        shutil.move(old_xml, os.path.join(xml_folder, 'midi.xml'))
        print(f"Moved XML in {subdir}")

print("\nRestructuring complete!")