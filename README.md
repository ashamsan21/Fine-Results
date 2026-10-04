# Focus Coach MVP

Focus Coach turns a study goal into a closed learning loop: check in, focus,
retrieve, and adapt. It reports a simple readiness score and recommends
the next learning action. The MVP runs completely offline.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

## Enable Gemini

Create a `.env` file beside `app.py`:

```text
GEMINI_API_KEY=your_real_gemini_api_key
```

Restart Streamlit after saving the file. The sidebar will confirm that the key
was loaded. `.env` is excluded from Git so the key is not committed.

## Architecture

- `app.py` — Streamlit screens and navigation.
- `focusai/planner.py` — offline plan and recall-question generation.
- `focusai/evaluator.py` — offline recall scoring and feedback.
- `focusai/integrations.py` — replaceable voice and hardware interfaces.
- `focusai/models.py` — shared data models.

The hardware interface can later be replaced by a Raspberry Pi implementation
for the LCD, button, and buzzer.
