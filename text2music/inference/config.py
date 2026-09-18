import os
import urllib.request

# --- Weights Download Logic ---
WEIGHTS_DIR = './text2music/artifacts'
WEIGHTS_FILENAME = 'weights_text2score_finetune_p_size_16_p_length_2048_p_layers_20_c_layers_6_h_size_768_lr_0.0001_batch_16.pth'
INFERENCE_WEIGHTS_PATH = os.path.join(WEIGHTS_DIR, WEIGHTS_FILENAME)
WEIGHTS_URL = "https://huggingface.co/keshavbhandari/Text2Score/resolve/main/weights_text2score_finetune_p_size_16_p_length_2048_p_layers_20_c_layers_6_h_size_768_lr_0.0001_batch_16.pth?download=true"

def ensure_weights_exist():
    """Checks if the model weights exist locally, and downloads them if they don't."""
    if not os.path.exists(INFERENCE_WEIGHTS_PATH):
        print(f"Weights not found locally. Downloading from Hugging Face to {INFERENCE_WEIGHTS_PATH}...")
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        try:
            urllib.request.urlretrieve(WEIGHTS_URL, INFERENCE_WEIGHTS_PATH)
            print("Download complete!")
        except Exception as e:
            print(f"Error downloading weights: {e}")
            raise

# Execute the check when the config is loaded
ensure_weights_exist()

# --- Configurations for inference ---
NUM_SAMPLES = 1                                              # Number of samples to generate (only for generate mode)
TOP_K = 9                                                    # Top k for sampling
TOP_P = 0.9                                                  # Top p for sampling
TEMPERATURE = 1.2                                            # Temperature for sampling
ORIGINAL_OUTPUT_FOLDER = './text2music/artifacts/output/'
INTERLEAVED_OUTPUT_FOLDER = './text2music/artifacts/output/interleaved'
XML_OUTPUT_FOLDER = './text2music/artifacts/output/xml'

# --- Configurations for model ---
PATCH_STREAM = True                                          # Stream training / inference
PATCH_SIZE = 16                                              # Patch Size
PATCH_LENGTH = 2048                                          # Patch Length
CHAR_NUM_LAYERS = 6                                          # Number of layers in the decoder
PATCH_NUM_LAYERS = 20                                        # Number of layers in the encoder
HIDDEN_SIZE = 768                                            # Hidden Size