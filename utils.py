import logging
from sentence_transformers import SentenceTransformer
import torch
import warnings
from tqdm import tqdm
import faiss
import numpy as np

def setup_logging():
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.cuda.is_available():
        return torch.device("cuda")
    else:
        return torch.device("cpu")

def load_model(model_name, device):
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, message="You try to use a model that was created with version")
            warnings.filterwarnings("ignore", category=FutureWarning, message="`resume_download` is deprecated and will be removed in version 1.0.0")
            model = SentenceTransformer(model_name).to(device)
        return model
    except Exception as e:
        logging.error(f"Error loading model {model_name}: {e}")
        raise

def dedupe(strings, model_name="Snowflake/snowflake-arctic-embed-xs", threshold=0.97):
    try:
        device = get_device()
        model = load_model(model_name, device)
    except Exception as e:
        logging.error(f"Initialization error: {e}")
        return []

    logging.info("Starting deduplication")
    
    # Eliminate exact duplicates
    try:
        stripped_strings = [s.strip() for s in strings]
        unique_strings = list(set(stripped_strings))
        logging.info(f"Removed exact duplicates, {len(strings) - len(unique_strings)} duplicates found.")
    except Exception as e:
        logging.error(f"Error eliminating exact duplicates: {e}")
        return []

    # Encode strings
    try:
        embeddings = model.encode(unique_strings, convert_to_tensor=True, device=device).cpu().numpy()
        d = embeddings.shape[1]
    except Exception as e:
        logging.error(f"Error encoding strings: {e}")
        return []

    # Build FAISS index
    try:
        index = faiss.IndexFlatL2(d)
        if device.type == 'cuda':
            res = faiss.StandardGpuResources()
            index = faiss.index_cpu_to_gpu(res, 0, index)
        index.add(embeddings)
    except Exception as e:
        logging.error(f"Error building FAISS index: {e}")
        return []

    # Query the index for duplicates
    try:
        distances, indices = index.search(embeddings, k=2)
        unique_indices = set()
        for i in tqdm(range(len(distances)), desc="Checking similarities"):
            if distances[i][1] >= threshold:
                unique_indices.add(i)
        unique = [unique_strings[i] for i in unique_indices]
    except Exception as e:
        logging.error(f"Error querying FAISS index: {e}")
        return []

    logging.info("Deduplication complete")
    return unique

def read_file(file_path):
    try:
        with open(file_path) as file:
            lines = [line.rstrip() for line in file]
        return lines
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        raise

def write_file(file_path, lines):
    try:
        with open(file_path, "w") as file:
            for line in lines:
                file.write(line + "\n")
        logging.info(f"Output written to {file_path}")
    except Exception as e:
        logging.error(f"Error writing to file {file_path}: {e}")
        raise
