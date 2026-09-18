"""Legacy browser UI for Triceratops."""

from __future__ import annotations

import gradio as gr

from text2music.agent.service import MusicBrief, build_plan, plan_with_qwen, run_generation, validate_plan


def plan_from_form(description, genre, tempo, key, time_signature, measures, instruments, density, use_qwen, qwen_model):
    brief = MusicBrief(description=description, genre=genre, tempo=int(tempo), key=key,
                       time_signature=time_signature, measures=int(measures),
                       instruments=instruments, density=density)
    if use_qwen:
        try:
            return plan_with_qwen(brief, model=qwen_model.strip() or None)
        except RuntimeError as exc:
            raise gr.Error(str(exc)) from exc
    return build_plan(brief)


def validate_from_form(plan):
    findings = validate_plan(plan)
    return "Plan is ready for generation." if not findings else "\n".join(f"- {item}" for item in findings)


def generate_from_plan(plan):
    run_dir, files, status = run_generation(plan)
    return status, files, run_dir


with gr.Blocks(title="Triceratops") as demo:
    gr.Markdown("# Triceratops\nDescribe the music you want. The agent reads the project, plans, validates and generates a MIDI version.")
    with gr.Row():
        with gr.Column():
            description = gr.Textbox(label="Music brief", lines=4,
                value="Energetic alternative-rock song with a memorable guitar riff and a strong chorus.")
            genre = gr.Dropdown(["rock", "metal", "pop", "jazz", "classical", "symphony", "folk"], value="rock", label="Genre")
            with gr.Row():
                tempo = gr.Slider(40, 240, value=140, step=1, label="Tempo (BPM)")
                key = gr.Dropdown(["E minor", "A minor", "C", "G", "D", "A", "E", "F", "Bb", "Eb"], value="E minor", label="Key")
            with gr.Row():
                time_signature = gr.Dropdown(["4/4", "3/4", "6/8", "12/8"], value="4/4", label="Time signature")
                measures = gr.Slider(8, 128, value=32, step=1, label="Measures")
            instruments = gr.Textbox(label="MuseScore instruments", value="Electric Guitar, Electric Bass, Drumset")
            density = gr.Dropdown(["Low", "Moderate", "High"], value="Moderate", label="Note density")
            use_qwen = gr.Checkbox(value=True, label="Use Qwen to create the plan", info="Reads QWEN_API_KEY from the server environment; it is never saved by the app.")
            qwen_model = gr.Textbox(value="qwen-plus", label="Qwen model")
            draft = gr.Button("Create plan", variant="primary")
        with gr.Column():
            plan = gr.Textbox(label="Editable music plan", lines=24)
            validation = gr.Textbox(label="Plan validation", lines=3)
            validate = gr.Button("Validate plan")
            generate = gr.Button("Generate score", variant="primary")
            status = gr.Textbox(label="Generation status", lines=8)
            files = gr.File(label="Generated ABC / ABCI files", file_count="multiple")
            run_directory = gr.Textbox(label="Run directory")
    draft.click(plan_from_form, [description, genre, tempo, key, time_signature, measures, instruments, density, use_qwen, qwen_model], plan)
    validate.click(validate_from_form, plan, validation)
    generate.click(generate_from_plan, plan, [status, files, run_directory])


if __name__ == "__main__":
    demo.launch()
