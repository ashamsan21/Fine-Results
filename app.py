import html
import hashlib
import os
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from focusai.evaluator import LocalRecallEvaluator
from focusai.gemini_checkin import transcribe_audio, transcribe_checkin
from focusai.gemini_evaluator import GeminiRecallEvaluator
from focusai.gemini_planner import GeminiStudyPlanner
from focusai.integrations import NoOpHardwareController, SilentVoiceCoach
from focusai.planner import LocalStudyPlanner
from focusai.voice_coach import generate_coaching_audio


load_dotenv()
st.set_page_config(page_title="Focus Coach", layout="centered")


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --ink: #17233d;
          --muted: #667085;
          --brand: #5a52d5;
          --brand-dark: #4038ae;
          --soft: #f1f0ff;
          --mint: #e8f7f1;
          --warm: #fff7e8;
          --line: #e5e7ef;
        }
        .stApp {
          background:
            radial-gradient(circle at 10% 0%, rgba(114,103,232,.10), transparent 30%),
            radial-gradient(circle at 95% 10%, rgba(77,184,145,.08), transparent 26%),
            #fbfbfd;
          color: var(--ink);
        }
        .block-container {max-width: 860px; padding-top: 2.2rem; padding-bottom: 5rem;}
        h1 {font-size: 2.55rem !important; letter-spacing: -.045em; color: var(--ink);}
        h2, h3 {letter-spacing: -.025em; color: var(--ink);}
        [data-testid="stCaptionContainer"] {color: var(--muted);}
        [data-testid="stVerticalBlockBorderWrapper"] {
          background: rgba(255,255,255,.88);
          border: 1px solid var(--line) !important;
          border-radius: 18px !important;
          box-shadow: 0 8px 30px rgba(31,40,74,.055);
        }
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea {
          border-radius: 12px;
          border-color: #d9dce8;
          background: #fff;
        }
        [data-testid="stTextInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus {
          border-color: var(--brand);
          box-shadow: 0 0 0 3px rgba(90,82,213,.12);
        }
        .stButton > button, .stDownloadButton > button {
          min-height: 44px;
          border-radius: 12px;
          font-weight: 700;
          transition: transform .15s ease, box-shadow .15s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
          transform: translateY(-1px);
          box-shadow: 0 7px 18px rgba(64,56,174,.14);
        }
        [data-testid="stBaseButton-primary"] {
          background: linear-gradient(135deg, var(--brand), var(--brand-dark));
          border: 0;
        }
        [data-testid="stProgress"] > div > div > div {background: var(--brand);}
        [data-testid="stAlert"] {border-radius: 14px;}
        .fc-kicker {
          color: var(--brand); font-size: .76rem; font-weight: 800;
          letter-spacing: .14em; text-transform: uppercase; margin-bottom: .35rem;
        }
        .fc-hero {
          padding: 1.3rem 1.4rem; margin: .8rem 0 1.3rem;
          border: 1px solid rgba(90,82,213,.16); border-radius: 18px;
          background: linear-gradient(135deg, rgba(241,240,255,.92), rgba(232,247,241,.78));
        }
        .fc-hero-title {font-size: 1.06rem; font-weight: 800; color: var(--ink);}
        .fc-hero-copy {margin-top: .35rem; color: #49536a; line-height: 1.55;}
        .fc-quote {
          margin: 1rem 0 1.5rem; padding: 1rem 1.2rem 1rem 1.3rem;
          border-left: 4px solid var(--brand); border-radius: 0 14px 14px 0;
          background: #fff; box-shadow: 0 5px 20px rgba(31,40,74,.045);
          color: #3f4860; font-weight: 650;
        }
        .fc-stage {
          display:inline-flex; align-items:center; padding:.28rem .68rem;
          border-radius:999px; background:var(--soft); color:var(--brand-dark);
          font-size:.76rem; font-weight:800; letter-spacing:.04em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def motivation(message: str) -> None:
    st.markdown(f'<div class="fc-quote">{html.escape(message)}</div>', unsafe_allow_html=True)


inject_theme()

PAGES = ("home", "focus", "recall", "results")
planner = LocalStudyPlanner()
evaluator = LocalRecallEvaluator()
voice = SilentVoiceCoach()
hardware = NoOpHardwareController()


def initialize_state() -> None:
    defaults = {
        "page": "home",
        "plan": None,
        "answers": [],
        "result": None,
        "focus_step": 0,
        "hint_level": 0,
        "recall_evidence": [],
        "evaluation_source": "offline",
        "evaluation_error": "",
        "planning_source": "offline",
        "planning_error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def build_session_report(plan, result, answers, evidence, evaluation_source) -> str:
    evidence_by_question = {
        item["question"]: len(item["files"]) for item in evidence
    }
    lines = [
        "# Focus Coach Session Report",
        "",
        f"**Date:** {datetime.now().strftime('%B %d, %Y')}",
        f"**Subject:** {plan.subject}",
        f"**Learning goal:** {plan.goal}",
        f"**Session length:** {plan.total_minutes} minutes",
        f"**Focus level:** {plan.energy}",
        f"**Evaluation:** {'Gemini AI' if evaluation_source == 'gemini' else 'Local completion and detail estimate'}",
        "",
        "## Learning result",
        "",
        f"**Understanding:** {result.score}%",
        f"**Questions answered:** {result.answered} of {result.total}",
        "",
        "## Coach diagnosis",
        "",
        result.diagnosis,
        "",
        "## Strengths",
        "",
        *[f"- {item}" for item in result.strengths],
        "",
        "## Areas to improve",
        "",
        *[f"- {item}" for item in result.next_steps],
        "",
        "## Learning-check responses",
        "",
    ]
    for number, question in enumerate(plan.questions, 1):
        answer = answers[number - 1].strip() or "No typed response; see attached work."
        attachment_count = evidence_by_question.get(number, 0)
        lines.extend(
            [
                f"### Question {number}",
                "",
                question.prompt,
                "",
                f"**Response:** {answer}",
                f"**Attachments:** {attachment_count}",
                "",
            ]
        )
    lines.extend(
        [
            "## Recommended next action",
            "",
            f"Continue with {plan.subject} for {result.recommended_minutes} minutes, "
            "then review the topic again tomorrow.",
        ]
    )
    return "\n".join(lines)


def go(page: str) -> None:
    if page not in PAGES:
        raise ValueError(f"Unknown page: {page}")
    st.session_state.page = page
    st.rerun()


def progress_header(active: int) -> None:
    labels = ["Check in", "Focus", "Retrieve", "Adapt"]
    st.caption("  ·  ".join(f"**{x}**" if i == active else x for i, x in enumerate(labels)))
    st.progress(active / (len(labels) - 1))
    st.markdown(f'<span class="fc-stage">STEP {active + 1} OF {len(labels)}</span>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_coaching_audio(messages: tuple, key_fingerprint: str) -> tuple:
    del key_fingerprint
    return generate_coaching_audio(messages)


def render_focus_timer(plan) -> None:
    cue_messages = []
    for index, step in enumerate(plan.steps):
        if index == 0:
            cue_messages.append(f"Let's begin with {step.title}. Focus on one task at a time.")
        else:
            cue_messages.append(f"Nice work. Move to {step.title}. You are making progress, keep going.")
    cue_messages.append("Focus session complete. Great effort. Now let's check what you remember.")

    eleven_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    audio_items = tuple()
    if eleven_key:
        try:
            fingerprint = hashlib.sha256(eleven_key.encode()).hexdigest()
            audio_items = cached_coaching_audio(tuple(cue_messages), fingerprint)
        except Exception:
            audio_items = tuple()

    segments = [
        {
            "title": step.title,
            "seconds": step.minutes * 60,
            "cue": cue_messages[index],
            "audio": audio_items[index] if index < len(audio_items) else "",
        }
        for index, step in enumerate(plan.steps)
    ]
    safe_segments = json.dumps(segments).replace("</", "<\\/")
    completion_cue = json.dumps(cue_messages[-1])
    completion_audio = json.dumps(audio_items[-1] if audio_items else "")
    components.html(
        f"""
        <div style="font-family:system-ui;text-align:center;padding:18px;border-radius:16px;
                    background:#f3f5ff;color:#17203b">
          <div style="font-size:13px;font-weight:650">TOTAL SESSION</div>
          <div id="clock" style="font-size:42px;font-weight:800;margin:4px">--:--</div>
          <div id="activity" style="font-size:18px;font-weight:750;margin-top:10px"></div>
          <div id="step-clock" style="font-size:26px;font-weight:700;margin:4px"></div>
          <div style="height:8px;background:#dfe2f3;border-radius:5px;margin:14px 8px;overflow:hidden">
            <div id="bar" style="height:100%;width:0;background:#5b55e7"></div>
          </div>
          <button id="toggle" onclick="toggle()" style="padding:9px 22px;border:0;border-radius:9px;
                  background:#5b55e7;color:white;font-weight:700">Start timer</button>
          <button onclick="resetTimer()" style="padding:9px 16px;border:0;background:transparent">Reset</button>
        </div>
        <script>
          const segments={safe_segments};
          const total=segments.reduce((sum,item)=>sum+item.seconds,0);
          let remaining=total, stepIndex=0, stepRemaining=segments[0].seconds;
          let running=false, interval=null, started=false;
          const clock=document.getElementById('clock'), stepClock=document.getElementById('step-clock');
          const activity=document.getElementById('activity'), bar=document.getElementById('bar');
          const toggleButton=document.getElementById('toggle');
          function formatTime(value) {{
            return String(Math.floor(value/60)).padStart(2,'0')+':'+String(value%60).padStart(2,'0');
          }}
          function speak(message,audioData) {{
            if(audioData) {{ new Audio('data:audio/mp3;base64,'+audioData).play(); return; }}
            if('speechSynthesis' in window) {{
              window.speechSynthesis.cancel(); window.speechSynthesis.speak(new SpeechSynthesisUtterance(message));
            }}
          }}
          function draw() {{
            clock.textContent=formatTime(remaining);
            stepClock.textContent=formatTime(stepRemaining)+' suggested';
            activity.textContent=(stepIndex+1)+' of '+segments.length+' · '+segments[stepIndex].title;
            bar.style.width=((total-remaining)/total*100)+'%';
          }}
          function toggle() {{
            running=!running; toggleButton.textContent=running?'Pause':'Resume';
            if(running && !started) {{ started=true; speak(segments[0].cue,segments[0].audio); }}
            if(running && !interval) interval=setInterval(()=>{{
              if(remaining>0) {{
                remaining--; stepRemaining--;
                if(stepRemaining<=0 && remaining>0) {{
                  stepIndex++; stepRemaining=segments[stepIndex].seconds;
                  speak(segments[stepIndex].cue,segments[stepIndex].audio);
                }}
                draw();
              }} else {{
                running=false;clearInterval(interval);interval=null;toggleButton.textContent='Finished ✓';
                speak({completion_cue},{completion_audio});
              }}
            }},1000);
          }}
          function resetTimer() {{remaining=total;stepIndex=0;stepRemaining=segments[0].seconds;started=false;
            running=false;clearInterval(interval);interval=null;
            toggleButton.textContent='Start timer';draw();}}
          draw();
        </script>
        """,
        height=245,
    )


def home_page() -> None:
    pending_dictation = st.session_state.pop("pending_checkin_dictation", None)
    if pending_dictation:
        field, text = pending_dictation
        st.session_state[f"checkin_{field}"] = text

    progress_header(0)
    st.markdown('<div class="fc-kicker">Personalized learning, one step at a time</div>', unsafe_allow_html=True)
    st.title("Focus Coach")
    st.markdown(
        '<div class="fc-hero"><div class="fc-hero-title">What are we working toward?</div>'
        '<div class="fc-hero-copy">Share the outcome. Focus Coach will analyze your materials, '
        'build one clear session, and help you prove what you learned.</div></div>',
        unsafe_allow_html=True,
    )
    motivation("Focus today. Never regret tomorrow.")

    subject_field, subject_voice = st.columns([0.9, 0.1])
    with subject_field:
        subject = st.text_input(
            "What subject are you studying?", placeholder="Calculus", key="checkin_subject"
        )
    with subject_voice:
        st.write("")
        with st.popover("🎙️", help="Speak to fill the subject field"):
            subject_audio = st.audio_input(
                "Speak subject", key="checkin_subject_audio", label_visibility="collapsed"
            )

    goal_field, goal_voice = st.columns([0.9, 0.1])
    with goal_field:
        goal = st.text_area(
            "What do you need to accomplish?",
            placeholder="Understand derivatives and practice the chain rule",
            key="checkin_goal",
        )
    with goal_voice:
        st.write("")
        with st.popover("🎙️", help="Speak to fill the study-goal field"):
            goal_audio = st.audio_input(
                "Speak study goal", key="checkin_goal_audio", label_visibility="collapsed"
            )

    deadline_field, deadline_voice = st.columns([0.9, 0.1])
    with deadline_field:
        deadline = st.text_input(
            "Exam or deadline", placeholder="Monday (optional)", key="checkin_deadline"
        )
    with deadline_voice:
        st.write("")
        with st.popover("🎙️", help="Speak to fill the deadline field"):
            deadline_audio = st.audio_input(
                "Speak deadline", key="checkin_deadline_audio", label_visibility="collapsed"
            )

    dictation_requests = (
        ("subject", subject_audio),
        ("goal", goal_audio),
        ("deadline", deadline_audio),
    )
    for field, recording in dictation_requests:
        if recording is not None:
            fingerprint = hashlib.sha256(recording.getvalue()).hexdigest()
            processed_key = f"processed_checkin_{field}_audio"
            if st.session_state.get(processed_key) != fingerprint:
                api_key = os.getenv("GEMINI_API_KEY", "").strip()
                if not api_key:
                    st.error("Voice typing requires GEMINI_API_KEY in `.env`.")
                else:
                    try:
                        with st.spinner("Converting speech to text…"):
                            spoken = transcribe_checkin(
                                api_key,
                                {field: recording},
                                {"subject": "", "goal": "", "deadline": ""},
                            )
                        st.session_state[processed_key] = fingerprint
                        st.session_state.pending_checkin_dictation = (
                            field,
                            spoken[field].strip(),
                        )
                        st.rerun()
                    except Exception:
                        st.error("I couldn't transcribe that recording. Please try again.")

    total_minutes = st.slider("Time available", 15, 180, 45, 5, format="%d minutes")
    energy = st.radio(
        "How focused do you feel?",
        ["😴 Low", "😐 Okay", "⚡ Ready"],
        index=1,
        horizontal=True,
    )
    study_materials = st.file_uploader(
        "Add notes or a study guide to personalize your experience (optional)",
        type=["pdf", "txt", "md", "docx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="Gemini will analyze every uploaded file to personalize your study plan, activities, and questions.",
    )
    submitted = st.button("✨ Build my study session", type="primary", use_container_width=True)

    if submitted:
        if not subject.strip() or not goal.strip():
            st.error("Add both a subject and a study goal to continue.")
        else:
            clean_energy = (energy or "😐 Okay").split(" ", 1)[-1]
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if api_key:
                try:
                    with st.spinner("Gemini is analyzing your materials and building the session…"):
                        st.session_state.plan = GeminiStudyPlanner(api_key).build_plan(
                            subject, goal, deadline, total_minutes, clean_energy, study_materials
                        )
                    st.session_state.planning_source = "gemini"
                    st.session_state.planning_error = ""
                except Exception as error:
                    st.session_state.plan = planner.build_plan(
                        subject, goal, deadline, total_minutes, clean_energy
                    )
                    st.session_state.planning_source = "offline"
                    st.session_state.planning_error = str(error)
            else:
                st.session_state.plan = planner.build_plan(
                    subject, goal, deadline, total_minutes, clean_energy
                )
                st.session_state.planning_source = "offline"
                st.session_state.planning_error = "GEMINI_API_KEY is missing"
            st.session_state.answers = []
            st.session_state.result = None
            st.session_state.focus_step = 0
            st.session_state.recall_evidence = []
            st.session_state.evaluation_source = "offline"
            st.session_state.evaluation_error = ""
            voice.speak("Your study plan is ready.")
            hardware.signal("session_started")
            go("focus")


def focus_page() -> None:
    pending_dictation = st.session_state.pop("pending_focus_dictation", None)
    if pending_dictation:
        step_number, text = pending_dictation
        st.session_state[f"notes_{step_number}"] = text

    plan = st.session_state.plan
    progress_header(1)
    st.markdown('<div class="fc-kicker">Your distraction-free study space</div>', unsafe_allow_html=True)
    st.title("Focus mode")
    st.caption(f"YOUR GOAL · {plan.objective}")
    if st.session_state.planning_source == "gemini":
        st.caption("✨ Personalized from your check-in and uploaded materials")
    else:
        st.warning("Gemini planning was unavailable, so a local focus session was created.")
    with st.expander("What Gemini found in your materials"):
        st.write(plan.material_summary)
    motivation("One goal. One activity. One step closer to mastery.")
    st.subheader("Your focus mission")
    for step in plan.steps:
        st.markdown(f"- **{step.title}** · {step.minutes} min")
    render_focus_timer(plan)
    hardware.show("Focus session", f"{plan.total_minutes} min")

    for index, step in enumerate(plan.steps):
        with st.container(border=True):
            st.subheader(f"{index + 1}. {step.title} · {step.minutes} min")
            st.markdown(step.instruction)
            answer_column, voice_column = st.columns([0.9, 0.1])
            with answer_column:
                st.text_area(
                    "Your response",
                    key=f"notes_{index}",
                    placeholder="Write or speak your answer…",
                )
            with voice_column:
                st.write("")
                with st.popover("🎙️", help=f"Speak your answer for {step.title}"):
                    audio_answer = st.audio_input(
                        "Speak your answer",
                        key=f"focus_audio_{index}",
                        label_visibility="collapsed",
                    )

            if audio_answer is not None:
                fingerprint = hashlib.sha256(audio_answer.getvalue()).hexdigest()
                processed_key = f"processed_focus_audio_{index}"
                if st.session_state.get(processed_key) != fingerprint:
                    api_key = os.getenv("GEMINI_API_KEY", "").strip()
                    if not api_key:
                        st.error("Voice typing requires GEMINI_API_KEY in `.env`.")
                    else:
                        try:
                            with st.spinner("Converting speech to text…"):
                                transcript = transcribe_audio(api_key, audio_answer)
                            st.session_state[processed_key] = fingerprint
                            st.session_state.pending_focus_dictation = (
                                index,
                                transcript,
                            )
                            st.rerun()
                        except Exception:
                            st.error("I couldn't transcribe that recording. Please try again.")

            if index in (1, 2):
                with st.expander("Need a hint?"):
                    st.write("Break the task into one cause, one process, and one result.")
                    st.write("If needed, study one worked example, cover it, and recreate the steps.")

    left, right = st.columns(2)
    if left.button("← Back to check-in", use_container_width=True):
        go("home")
    if right.button("Start learning check →", type="primary", use_container_width=True):
        hardware.signal("focus_completed")
        go("recall")


def recall_page() -> None:
    pending_dictation = st.session_state.pop("pending_recall_dictation", None)
    if pending_dictation:
        question_number, text = pending_dictation
        st.session_state[f"answer_{question_number}"] = text

    plan = st.session_state.plan
    progress_header(2)
    st.markdown('<div class="fc-kicker">Learning becomes durable when you retrieve it</div>', unsafe_allow_html=True)
    st.title("Let’s see what stuck")
    st.write("Close your notes. Type your answers, or upload a photo if you worked them out on paper.")
    motivation("Do not aim for perfect recall. Honest effort shows you exactly what to strengthen.")
    with st.container():
        answers = []
        question_evidence = []
        for number, question in enumerate(plan.questions, 1):
            st.subheader(f"{number}. {question.prompt}")
            st.caption(f"Hint: {question.hint}")
            answers.append(st.text_area("Your answer", key=f"answer_{number}", label_visibility="collapsed"))
            st.caption("Add handwritten work (optional)")
            attach_column, camera_column, record_column, spacer = st.columns(
                [0.1, 0.1, 0.1, 0.7]
            )
            with attach_column:
                with st.popover("📎", help=f"Upload work for Question {number}"):
                    st.caption(f"Upload work for Question {number}")
                    uploaded_work = st.file_uploader(
                        "Choose images or a PDF",
                        type=["png", "jpg", "jpeg", "webp", "pdf"],
                        accept_multiple_files=True,
                        key=f"upload_{number}",
                        label_visibility="collapsed",
                    )
            with camera_column:
                with st.popover("📷", help=f"Take a photo for Question {number}"):
                    st.caption(f"Take a photo of your work for Question {number}")
                    camera_image = st.camera_input(
                        "Open camera",
                        key=f"camera_{number}",
                        label_visibility="collapsed",
                    )
            with record_column:
                with st.popover("🎙️", help=f"Record an answer for Question {number}"):
                    st.caption(f"Record your answer to Question {number}")
                    audio_answer = st.audio_input(
                        "Record answer",
                        key=f"audio_{number}",
                        label_visibility="collapsed",
                    )
            if audio_answer is not None:
                fingerprint = hashlib.sha256(audio_answer.getvalue()).hexdigest()
                processed_key = f"processed_recall_audio_{number}"
                if st.session_state.get(processed_key) != fingerprint:
                    api_key = os.getenv("GEMINI_API_KEY", "").strip()
                    if not api_key:
                        st.error("Voice typing requires GEMINI_API_KEY in `.env`.")
                    else:
                        try:
                            with st.spinner("Converting speech to text…"):
                                transcript = transcribe_audio(api_key, audio_answer)
                            st.session_state[processed_key] = fingerprint
                            st.session_state.pending_recall_dictation = (
                                number,
                                transcript,
                            )
                            st.rerun()
                        except Exception:
                            st.error("I couldn't transcribe that recording. Please try again.")
            if uploaded_work or camera_image:
                attachment_count = (
                    len(uploaded_work or [])
                    + (1 if camera_image else 0)
                )
                spacer.success(f"{attachment_count} attached")
            question_evidence.append(
                (number, list(uploaded_work or []), camera_image)
            )
            st.divider()
        submitted = st.button("See my results →", type="primary", use_container_width=True)

    if submitted:
        evidence = []
        for number, uploaded_work, camera_image in question_evidence:
            files = list(uploaded_work)
            if camera_image is not None:
                files.append(camera_image)
            if files:
                evidence.append({"question": number, "files": files})

        if not any(answer.strip() for answer in answers) and not evidence:
            st.error("Type at least one answer or attach your handwritten work to a question.")
        else:
            st.session_state.answers = answers
            st.session_state.recall_evidence = evidence
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if api_key:
                try:
                    with st.spinner("Gemini is reading and evaluating your work…"):
                        st.session_state.result = GeminiRecallEvaluator(api_key).evaluate(
                            plan, answers, evidence
                        )
                    st.session_state.evaluation_source = "gemini"
                    st.session_state.evaluation_error = ""
                except Exception as error:
                    st.session_state.result = evaluator.evaluate(plan, answers)
                    st.session_state.evaluation_source = "offline"
                    st.session_state.evaluation_error = str(error)
            else:
                st.session_state.result = evaluator.evaluate(plan, answers)
                st.session_state.evaluation_source = "offline"
                st.session_state.evaluation_error = "GEMINI_API_KEY is missing from .env"
            hardware.signal("session_completed")
            go("results")


def results_page() -> None:
    plan, result = st.session_state.plan, st.session_state.result
    progress_header(3)
    st.markdown('<div class="fc-kicker">Turn today’s effort into tomorrow’s advantage</div>', unsafe_allow_html=True)
    st.title("Session complete")
    st.metric("Understanding", f"{result.score}%", f"{result.answered}/{result.total} prompts answered")
    st.progress(result.score / 100)
    motivation("Progress is not knowing everything. It is knowing what to work on next.")
    if st.session_state.evaluation_source == "gemini":
        st.caption("✨ Gemini evaluated the typed answers and attached work.")
    else:
        st.warning(
            "Gemini was not available, so the local estimate was used. "
            "Check `.env`, restart the app, and try again."
        )
    if st.session_state.recall_evidence:
        file_count = sum(len(item["files"]) for item in st.session_state.recall_evidence)
        st.success(
            f"Received {file_count} attachment(s) of handwritten work. "
            "They are included as learning evidence."
        )
        with st.expander("View submitted work"):
            for item in st.session_state.recall_evidence:
                st.markdown(f"**Question {item['question']}**")
                for submitted_file in item["files"]:
                    if submitted_file.type.startswith("image/"):
                        st.image(submitted_file, use_container_width=True)
                    elif submitted_file.type.startswith("audio/"):
                        st.audio(submitted_file)
                    else:
                        st.write(f"📄 {submitted_file.name}")
    if st.session_state.evaluation_source == "offline":
        st.caption("The local score estimates typed-answer completion and does not read attachments.")

    st.subheader("What went well")
    for item in result.strengths:
        st.success(item)
    st.subheader("Best next steps")
    for item in result.next_steps:
        st.write(f"• {item}")

    st.subheader("Coach diagnosis")
    st.info(result.diagnosis)
    st.write(
        f"**Recommended next action:** {result.recommended_minutes} more minutes on **{plan.subject}**, "
        "then stop and review again tomorrow."
    )

    st.subheader("Your session report")
    report = build_session_report(
        plan,
        result,
        st.session_state.answers,
        st.session_state.recall_evidence,
        st.session_state.evaluation_source,
    )
    with st.expander("Preview full report"):
        st.markdown(report)
    safe_subject = "".join(
        character.lower() if character.isalnum() else "-" for character in plan.subject
    ).strip("-")
    st.download_button(
        "⬇️ Download session report",
        data=report,
        file_name=f"focus-coach-{safe_subject or 'study'}-report.md",
        mime="text/markdown",
        use_container_width=True,
    )

    left, middle, right = st.columns(3)
    if left.button("Review answers", use_container_width=True):
        go("recall")
    if middle.button(f"Keep going · {result.recommended_minutes} min", type="primary", use_container_width=True):
        st.session_state.focus_step = max(0, len(plan.steps) - 2)
        go("focus")
    if right.button("Finish for today", use_container_width=True):
        st.session_state.clear()
        st.rerun()


initialize_state()
with st.sidebar:
    st.subheader("AI status")
    if os.getenv("GEMINI_API_KEY", "").strip():
        st.success("Gemini key loaded from .env")
    else:
        st.warning("GEMINI_API_KEY not found in .env")
if st.session_state.page != "home" and st.session_state.plan is None:
    st.session_state.page = "home"

{
    "home": home_page,
    "focus": focus_page,
    "recall": recall_page,
    "results": results_page,
}[st.session_state.page]()
