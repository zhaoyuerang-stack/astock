import time
import numpy as np
import scipy.linalg
import scipy.sparse.linalg

def power_iteration(H, num_simulations=50):
    n = H.shape[0]
    # Shift to ensure all eigenvalues are positive
    # Gershgorin bound for maximum eigenvalue
    row_sums = np.sum(np.abs(H), axis=1)
    shift = np.max(row_sums)
    H_shifted = H + shift * np.eye(n)

    # Start with a random vector
    b_k = np.random.randn(n) + 1j * np.random.randn(n)
    b_k = b_k / np.linalg.norm(b_k)

    for _ in range(num_simulations):
        # Calculate the matrix-by-vector product
        b_k1 = H_shifted @ b_k
        # Re-normalize the vector
        b_k1_norm = np.linalg.norm(b_k1)
        if b_k1_norm == 0:
            break
        b_k = b_k1 / b_k1_norm

    return b_k

def main():
    N = 800
    print(f"Comparing shifted power iteration vs scipy eigh for N={N}...")

    # Generate a random complex Hermitian matrix
    np.random.seed(42)
    A = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    H = (A + A.conj().T) / 2.0

    # 1. SciPy eigh
    t0 = time.time()
    for _ in range(10):
        eigenvalues, eigenvectors = scipy.linalg.eigh(H)
        top_idx = np.argmax(eigenvalues)
        v_eigh = eigenvectors[:, top_idx]
    t_eigh = (time.time() - t0) / 10
    print(f"  SciPy eigh: {t_eigh * 1000:.2f} ms")

    # 2. Scipy eigsh
    t0 = time.time()
    for _ in range(10):
        eigenvalues_sh, eigenvectors_sh = scipy.sparse.linalg.eigsh(H, k=1, which='LR')
        v_sh = eigenvectors_sh[:, 0]
    t_sh = (time.time() - t0) / 10
    print(f"  SciPy eigsh (k=1): {t_sh * 1000:.2f} ms")

    # 3. Power iteration
    t0 = time.time()
    for _ in range(10):
        v_power = power_iteration(H, num_simulations=30)
    t_power = (time.time() - t0) / 10
    print(f"  Power Iteration (30 iterations): {t_power * 1000:.2f} ms")

    # Compute cosine similarity (absolute value of inner product)
    cos_sim_sh = np.abs(np.vdot(v_eigh, v_sh)) / (np.linalg.norm(v_eigh) * np.linalg.norm(v_sh))
    cos_sim = np.abs(np.vdot(v_eigh, v_power)) / (np.linalg.norm(v_eigh) * np.linalg.norm(v_power))
    print(f"  Cosine Similarity (eigsh): {cos_sim_sh:.6f}")
    print(f"  Cosine Similarity (power iteration): {cos_sim:.6f}")

if __name__ == "__main__":
    main()
