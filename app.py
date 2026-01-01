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

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="EBA-HQR Research", layout="wide")
st.markdown("""
    <style>
    .stApp, .stMarkdown, h1, h2, h3, p, label, li, span { color: #000000 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚛️ Entropy-Based Adaptive Hybrid Quantum Representation (EBA-HQR)")

# --- 2. SECURE CONNECTION ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    # LOAD KEY FROM SECRETS
    if "QISKIT_TOKEN" in st.secrets:
        api_token = st.secrets["QISKIT_TOKEN"]
        st.success("✅ Secure Key Found.")
    else:
        api_token = st.text_input("Enter Token (Local Mode):", type="password")

    # Backend Selection
    mode = st.radio("Backend:", ["💻 Local Simulator", "☁️ IBM Real Hardware"])
    use_cloud = True if "Real" in mode else False
    
    threshold = st.slider("Entropy Threshold", 0.1, 1.0, 0.6)

# --- 3. DATA LOADING ---
@st.cache_data
def load_data():
    if os.path.exists('mnist_data.npz'):
        data = np.load('mnist_data.npz')
        return data['images']
    return None

# --- 4. ALGORITHM ---
def calculate_entropy(block):
    flat = block.flatten()
    values, counts = np.unique(flat, return_counts=True)
    probs = counts / counts.sum()
    return -np.sum(probs * np.log2(probs))

def generate_map(image, thresh):
    h, w = image.shape
    rows, cols = h // 4, w // 4
    d_map = np.zeros((rows, cols))
    for i in range(rows):
        for j in range(cols):
            block = image[i*4:(i+1)*4, j*4:(j+1)*4]
            if calculate_entropy(block) > thresh:
                d_map[i, j] = 1 # NEQR
            else:
                d_map[i, j] = 0 # FRQI
    return d_map

def build_circuit(method):
    qc = QuantumCircuit(5)
    for i in range(4): qc.h(i)
    qc.barrier()
    if method == "NEQR": qc.x(4)
    else: qc.ry(1.57, 4)
    qc.measure_all()
    return qc

# --- 5. UI & EXECUTION ---
col1, col2 = st.columns(2)
dataset = load_data()

with col1:
    st.subheader("Input")
    if dataset is not None:
        idx = st.slider("Index", 0, len(dataset)-1, 0)
        img = dataset[idx]
        img_small = cv2.resize(img, (16, 16))
        st.image(img_small, width=150, caption="Real MNIST Data")
        d_map = generate_map(img_small, threshold)
    else:
        st.error("Missing 'mnist_data.npz' file in GitHub!")
        st.stop()

with col2:
    st.subheader("Entropy Map")
    fig, ax = plt.subplots()
    ax.imshow(d_map, cmap='viridis')
    st.pyplot(fig)

st.divider()
if st.button("RUN EXPERIMENT"):
    if use_cloud:
        if not api_token:
            st.error("No API Token found in Secrets!")
            st.stop()
        
        try:
            # === THE CRITICAL FIX IS HERE ===
            # We explicitly force channel='ibm_quantum'
            service = QiskitRuntimeService(channel="ibm_quantum", token=api_token)
            
            backend = service.least_busy(operational=True, simulator=False)
            st.write(f"🌍 Connected to IBM Quantum: **{backend.name}**")
            
            with st.spinner("Running on Quantum Hardware..."):
                qc = build_circuit("NEQR")
                pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
                isa_circuit = pm.run(qc)
                sampler = Sampler(backend)
                job = sampler.run([isa_circuit])
                st.success(f"Job ID: {job.job_id()}")
                st.bar_chart(job.result()[0].data.meas.get_counts())
                
        except Exception as e:
            st.error(f"Connection Error: {e}")
    else:
        st.write("💻 Running Locally...")
        backend = Aer.get_backend('qasm_simulator')
        qc = build_circuit("NEQR")
        job = backend.run(transpile(qc, backend), shots=1024)
        st.bar_chart(job.result().get_counts())
