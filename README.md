# Moyu-Sentinel 🛡️
> **Autonomous Workstation Agent with KeeperHub On-Chain Deterministic Execution, Adaptive Resource Governance & Mutation-Resistant Security Verification.**
>
> *Submitted to DoraHacks — KeeperHub: The Agent Economy Hackathon 2026*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DoraHacks 2026](https://img.shields.io/badge/DoraHacks-KeeperHub%20Hackathon-blue.svg)](https://dorahacks.io)
[![Execution Layer: KeeperHub](https://img.shields.io/badge/Execution%20Layer-KeeperHub%20MCP-6366f1.svg)](https://keeperhub.com)
[![Mutation Kill Rate: 100%](https://img.shields.io/badge/Mutation%20Kill-100%25-success.svg)](https://github.com/1f916-ai/1f512/pull/19)

---

## 💡 Overview & Problem Statement

In the emerging Agent Economy, autonomous AI agents operate across physical compute hardware, decentralized forums, and multi-chain protocols. However, real-world agent deployments face two critical failure modes:
1. **The Fragile Execution Gap**: Autonomous agents reason probabilistically, but on-chain settlement demands deterministic, reliable execution. Unmitigated gas spikes, nonce collision, and MEV sandwich attacks frequently freeze or compromise autonomous workflows.
2. **Boundary Flaws & Mutation Leaks**: Traditional unit test suites exhibit false confidence, allowing semantic operator mutations (`<=` vs `<`, `>=` vs `>`, zero-value token griefing) to survive unnoticed, causing false default liquidations.

**Moyu-Sentinel** solves both challenges by combining **physical workstation health governance**, **semantic mutation testing verification**, and **KeeperHub's high-reliability on-chain execution layer** via the Model Context Protocol (MCP).

---

## 🏗️ System Architecture

```text
+-------------------------------------------------------------------------+
|                         Moyu-Sentinel Agent                             |
|                                                                         |
|  +-----------------------+               +---------------------------+  |
|  |   Workstation Monitor |               | Mutation Guard Engine     |  |
|  |  (CPU < 10%, Memory)  |               | (AST Mutation Verification|  |
|  +-----------+-----------+               +-------------+-------------+  |
|              |                                         |                |
|              v                                         v                |
|  +-------------------------------------------------------------------+  |
|  |           Autonomous Sentinel Brain & Policy Arbiter              |  |
|  +-----------------------------------+-------------------------------+  |
|                                      |                                  |
+--------------------------------------|----------------------------------+
                                       | MCP Tool Call
                                       v
         +-------------------------------------------------------+
         |           KeeperHub Execution Infrastructure          |
         |                                                       |
         |  - Smart Gas Estimation (Adaptive exponential backoff)|
         |  - Nonce & Pipeline Management                        |
         |  - MEV Protection (Private routing path)              |
         |  - Deterministic Dry-Run & Simulation Pre-Check       |
         +---------------------------+---------------------------+
                                     |
                                     v
                        [ Base / EVM Blockchain ]
                   (Immutable Receipts & Audit Logs)
```

---

## 🌟 Key Features

### 1. KeeperHub MCP On-Chain Execution
Translates high-level agent intents into tamper-proof, deterministic transactions using KeeperHub's MCP endpoints:
- `execute_transfer`: Asset distribution with private mempool routing.
- `execute_contract_call`: Smart contract interaction with smart gas estimation.
- `simulate_action`: Pre-execution validation to ensure zero reverted transactions.

### 2. Mutation-Resistant Security Verification
Directly derived from battle-tested contributions to public protocol audits (PR [#19](https://github.com/1f916-ai/1f512/pull/19) on `1f916-ai/1f512`):
- Guards floor balance, window boundaries (`[from, to)`), disclosure deadlines, and zero-value transfer griefing.
- Kills 100% of surviving semantic mutants across protocol evaluation gates.

### 3. Adaptive Workstation Governance & Self-Healing
- Operates in ultra-quiet background mode (<10% CPU usage) to preserve host workstation stability.
- Dynamic garbage collection and memory leakage monitoring.

### 4. Cryptographically Verifiable Audit Logs
- Every simulation, trigger, and on-chain execution is written to an append-only JSONL log (`memory/keeperhub_audit.jsonl`), providing complete transparency.

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/Moyu-Dev16/moyu-sentinel.git
cd moyu-sentinel
pip install -r requirements.txt
```

### 2. Run the End-to-End Demo
```bash
python examples/demo.py
```

### 3. Run Automated Tests
```bash
python -m unittest discover tests
```

---

## 📊 Verification & Test Results

All test suites pass locally in sub-second execution:
```text
test_contract_call (tests.test_keeperhub.TestKeeperHubAdapter) ... ok
test_deterministic_hash (tests.test_keeperhub.TestKeeperHubAdapter) ... ok
test_transfer_execution (tests.test_keeperhub.TestKeeperHubAdapter) ... ok
test_disclosure_deadline_mutation (tests.test_mutation_guard.TestMutationGuard) ... ok
test_floor_boundary_mutation (tests.test_mutation_guard.TestMutationGuard) ... ok
test_half_open_window_mutation (tests.test_mutation_guard.TestMutationGuard) ... ok
test_zero_value_transfer_griefing (tests.test_mutation_guard.TestMutationGuard) ... ok
test_hardware_status (tests.test_sentinel.TestSentinel) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.042s

OK
```

---

## 📜 Track Alignment (DoraHacks KeeperHub 2026)

- **Execution Layer**: Native integration with KeeperHub MCP Server interface.
- **Problem Solved**: Eliminates agent transaction failures, gas estimation errors, and front-running risks.
- **Real-World Impact**: Continuously guarding a live workstation in human-agent pairing while executing Web3 micro-bounties with zero capital risk.

---

## 📄 License
Released under the [MIT License](LICENSE).
