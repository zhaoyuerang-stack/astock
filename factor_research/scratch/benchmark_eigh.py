import time
import numpy as np
import scipy.linalg
import torch

def benchmark():
    N = 800
    print(f"Benchmarking eigh of {N}x{N} complex Hermitian matrix...")

    # Generate a random complex Hermitian matrix
    np.random.seed(42)
    A = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    H_np = (A + A.conj().T) / 2.0

    # 1. SciPy on CPU
    t0 = time.time()
    for _ in range(20):
        eigenvalues, eigenvectors = scipy.linalg.eigh(H_np)
        top_idx = np.argmax(eigenvalues)
        v1 = eigenvectors[:, top_idx]
    t_scipy = (time.time() - t0) / 20
    print(f"  SciPy on CPU: {t_scipy * 1000:.2f} ms")

    # 2. PyTorch on CPU
    H_cpu = torch.from_numpy(H_np)
    t0 = time.time()
    for _ in range(20):
        eigenvalues, eigenvectors = torch.linalg.eigh(H_cpu)
        top_idx = torch.argmax(eigenvalues.real)
        v1 = eigenvectors[:, top_idx]
    t_torch_cpu = (time.time() - t0) / 20
    print(f"  PyTorch on CPU: {t_torch_cpu * 1000:.2f} ms")

    # 3. PyTorch on MPS (if available)
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        H_mps = H_cpu.to(torch.complex64).to("mps")
        try:
            # Warm up
            _ = torch.linalg.eigh(H_mps)
            t0 = time.time()
            for _ in range(20):
                eigenvalues, eigenvectors = torch.linalg.eigh(H_mps)
                top_idx = torch.argmax(eigenvalues.real)
                v1 = eigenvectors[:, top_idx]
            t_torch_mps = (time.time() - t0) / 20
            print(f"  PyTorch on MPS: {t_torch_mps * 1000:.2f} ms")
        except Exception as e:
            print(f"  PyTorch on MPS failed: {e}")
    else:
        print("  MPS not available")

if __name__ == "__main__":
    benchmark()
