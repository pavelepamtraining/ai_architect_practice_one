# LLM Security Demo - Streamlit App

Interactive web application demonstrating OWASP LLM vulnerabilities and mitigations using OpenRouter API.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get OpenRouter API Key

1. Visit https://openrouter.ai/
2. Sign up for a free account
3. Navigate to "Keys" section
4. Create a new API key
5. export OPENROUTER_API_KEY="..."

### 3. Run the App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Assumptions and Scope

### Assumptions

- The application is a demonstration system, not a production enterprise service.
- The LLM is accessed via OpenRouter API and may return non-deterministic outputs.
- The system prompt in the vulnerable agent intentionally contains simulated sensitive data for educational purposes.
- Users interacting with the app may attempt malicious inputs (prompt injection, data extraction).
- Network calls to the LLM provider are assumed to be available but unreliable (timeouts, malformed responses possible).
- The secure agent relies on heuristics (pattern detection, redaction, validation) rather than formal guarantees.

### In Scope

- Demonstration of key OWASP LLM risks:
    - Prompt Injection
    - System Prompt Leakage
    - Misinformation / Hallucination
    - Unbounded Resource Consumption
- Implementation of:
  - Vulnerable vs. Secure agents
  - Input validation and injection detection
  - Output redaction of sensitive data 
  - Basic factual validation layer 
  - Resource constraints (input length, token limits)
  - Interactive testing via Streamlit UI
  - Side-by-side comparison

### Out of Scope

- Full enterprise-grade security controls (e.g., authentication, authorization, audit logging)
- Advanced prompt injection defenses (e.g., sandboxed execution, formal policy engines)
- Fine-grained access control to internal data sources
- Real-time monitoring, alerting, or incident response systems
- Formal evaluation of model robustness across large datasets
- Protection against adversarial attacks at the model level (e.g., jailbreak-resistant training)
- Guarantees of factual correctness (only heuristic validation is implemented)

### Scenario

This application simulates an internal company assistant (SecureCorp AI) used by employees to query policies and documentation.

Two versions of the agent are provided, users can:

- Execute predefined attacks (injection, leakage, misinformation, resource abuse)
- Compare responses between vulnerable and secure implementations
- Submit custom queries to evaluate system behavior


## Key Components

- Streamlit UI: Interactive frontend for testing and visualization
- Agent Layer: Core logic implementing vulnerable and secure behaviors
- LLM Integration OpenRouter API

## Summary of Results

- Real OWASP LLM vulnerabilities in a baseline system
- Concrete exploit examples showing actual attack success
- Practical mitigation layers implemented defensively
- Quantitative improvement measured via attack success rate

### Key Findings

- Vulnerable agent: High attack success rate across all categories
- Secure agent: Significant risk reduction through layered defenses
- Residual risks: Sophisticated attacks and edge cases remain possible