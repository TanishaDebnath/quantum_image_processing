import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import cv2
import os
from math import log2
from qiskit import QuantumCircuit, transpile
from qiskit_aer import Aer
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="EBA-HQR Research Platform", layout="wide")

# Force Black Text for High Visibility
st.markdown("""
    <style>
    .stApp, .stMarkdown, h1, h2, h3, p, label, li, span { color: #000000 !important; }
    div[role="radiogroup"] label {
        color: #000000 !important;
        font-weight: bold !important;
        background-color: #ffffff;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #cccccc;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("⚛️ Entropy-Based Adaptive Hybrid Quantum Representation (EBA-HQR)")
st.write("**Research Prototype:** Validating Hybrid Compression on Real Data.")

# --- 2. SIDEBAR & SECURE CONNECTION ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    # SECURITY: Load API Key from Streamlit Secrets
    if "QISKIT_TOKEN" in st.secrets:
        api_token = st.secrets["QISKIT_TOKEN"]
        st.success("✅ API Key Loaded securely from Cloud.")
    else:
        api_token = st.text_input("Enter IBM API Token (Local Mode):", type="password")
    
    entropy_threshold = st.slider("Entropy Threshold (α)", 0.0, 2.0, 0.6, 0.1)
    
    st.divider()
    
    execution_mode = st.radio(
        "Backend Selection:",
        ["💻 Local Simulator (Fast Validation)", "☁️ IBM Real Hardware (Research Deployment)"],
        index=0
    )
    use_cloud = True if "Real" in execution_mode else False

# --- 3. DATA LOADING ---
@st.cache_data
def load_local_mnist():
    if os.path.exists('mnist_data.npz'):
        data = np.load('mnist_data.npz')
        return data['images']
    return None

# --- 4. ALGORITHM (EBA-HQR) ---
def calculate_entropy(block):
    flat = block.flatten()
    values, counts = np.unique(flat, return_counts=True)
    probs = counts / counts.sum()
    return -np.sum(probs * np.log2(probs))

def generate_decision_map(image, threshold):
    h, w = image.shape
    block_size = 4
    rows, cols = h // block_size, w // block_size
    decision_map = np.zeros((rows, cols))
    
    for i in range(rows):
        for j in range(cols):
            block = image[i*block_size:(i+1)*block_size, j*block_size:(j+1)*block_size]
            if calculate_entropy(block) > threshold: 
                decision_map[i, j] = 1 # NEQR
            else:
                decision_map[i, j] = 0 # FRQI
    return decision_map

def build_circuit(method):
    qc = QuantumCircuit(5) 
    for i in range(4): qc.h(i)
    qc.barrier()
    if method == "NEQR":
        qc.x(4) 
    else:
        qc.ry(1.57, 4)
    qc.measure_all()
    return qc

# --- 5. VISUAL INTERFACE ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Input Data")
    source = st.radio("Select Source:", ["MNIST Dataset (Real)", "Upload Custom Image"])
    
    raw_img = None
    if source == "MNIST Dataset (Real)":
        dataset = load_local_mnist()
        if dataset is not None:
            idx = st.slider("Select Image Index", 0, len(dataset)-1, 0)
            raw_img = dataset[idx]
        else:
            st.error("⚠️ 'mnist_data.npz' not found. Please upload it to GitHub.")
    else:
        uploaded = st.file_uploader("Upload Image", type=['png', 'jpg'])
        if uploaded:
            file_bytes = np.asarray(bytearray(uploaded.read()), dtype=np.uint8)
            raw_img = cv2.imdecode(file_bytes, cv2.IMREAD_GRAYSCALE)

    if raw_img is not None:
        img_small = cv2.resize(raw_img, (16, 16))
        st.image(img_small, caption="Processed Input (16x16)", width=200)
        decision_map = generate_decision_map(img_small, entropy_threshold)

with col2:
    if raw_img is not None:
        st.subheader("2. Entropy Decision Map")
        fig, ax = plt.subplots()
        im = ax.imshow(decision_map, cmap='viridis')
        plt.colorbar(im)
        st.pyplot(fig)

# --- 6. EXECUTION LOGIC ---
st.divider()
if st.button("RUN EXPERIMENT"):
    if raw_img is None:
        st.error("Load data first.")
    else:
        if use_cloud:
            if not api_token:
                st.error("API Token missing! Add 'QISKIT_TOKEN' to Streamlit Secrets.")
                st.stop()
            try:
                # FIXED: Explicitly set channel to 'ibm_quantum'
                service = QiskitRuntimeService(channel="ibm_quantum", token=api_token)
                backend = service.least_busy(operational=True, simulator=False)
                st.write(f"🌍 Connected to IBM Cloud: **{backend.name}**")
                
                with st.spinner("Submitting to Quantum Queue..."):
                    qc = build_circuit("NEQR")
                    pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
                    isa_circuit = pm.run(qc)
                    sampler = Sampler(backend)
                    job = sampler.run([isa_circuit])
                    st.success(f"Job Submitted! ID: {job.job_id()}")
                    st.info("Waiting for results (this happens on IBM servers)...")
                    result = job.result()
                    st.bar_chart(result[0].data.meas.get_counts())
                    
            except Exception as e:
                st.error(f"Cloud Connection Error: {e}")
                st.help("Ensure your API Token is correct in Streamlit Secrets.")
        else:
            st.write("💻 Running Locally...")
            backend = Aer.get_backend('qasm_simulator')
            qc = build_circuit("NEQR")
            job = backend.run(transpile(qc, backend), shots=1024)
            st.bar_chart(job.result().get_counts())
