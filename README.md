# Support Agent Safety Evaluator (Streamlit edition)

Evaluate one support agent response against one failure scenario, scored
across three stakeholder lenses using DeepEval G-Eval with Gemini as judge.

- **User Resolution:** was the customer helped correctly?
- **Stakeholder Protection:** was anyone else harmed (company, other customers)?
- **Policy Compliance:** did the agent uphold policy under pressure?

11 scenario presets across 5 categories (Policy Hallucination, PII
Extraction, Authority Pressure, Wrong Action, Escalation Failure), plus a
custom scenario option. One run = 3 judge calls.

## Deploy free on Streamlit Community Cloud

1. Push this folder to a GitHub repo (public is fine, the API key is NOT in
   the code).
2. Go to share.streamlit.io, sign in with GitHub, choose **New app**.
3. Pick the repo and branch, set the main file to `streamlit_app.py`.
   In Advanced settings, choose Python 3.12 if asked.
4. Before deploying, open **Advanced settings, Secrets** and add:

   ```
   GOOGLE_API_KEY = "your key from Google AI Studio"
   ```

5. Click Deploy. The app builds automatically and gives you a public URL
   like `https://your-app-name.streamlit.app`.

Visitors never see the key. It stays in Streamlit's secrets store and the
app reads it at runtime.

## Run locally

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY="your key"
streamlit run streamlit_app.py
```

## Scenario sources

Test patterns from OWASP LLM Top 10 and documented red-team techniques.
Operational framing (severity, stakeholder impact, response) from enterprise
support operations experience.
