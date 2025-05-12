import nemo.collections.asr as nemo_asr
import torch
import gc
import os
import subprocess
from pathlib import Path
import gradio as gr
import shutil
from utils import *

def run_nemo_asr(mono_audio_path):
  asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v2")
  output = asr_model.transcribe([mono_audio_path], timestamps=True)
  # by default, timestamps are enabled for char, word and segment level
  word_timestamps = output[0].timestamp['word'] # word level timestamps for first sample
  segment_timestamps = output[0].timestamp['segment'] # segment level timestamps
  char_timestamps = output[0].timestamp['char'] # char level timestamps
  # for stamp in segment_timestamps:
  #     print(f"{stamp['start']}s - {stamp['end']}s : {stamp['segment']}")
  del asr_model
  gc.collect()
  torch.cuda.empty_cache()
  return word_timestamps,segment_timestamps,char_timestamps



def process(file):
    file_path = file.name
    file_ext = Path(file_path).suffix.lower()

    if file_ext in [".mp4", ".mkv"]:
        new_file_path=clean_file_name(file_path,unique_id=False) #ffmpeg sometime don't work if you give bad file name stupid idea but still i will do this
        shutil.copy(file_path,new_file_path)
        audio_path = new_file_path.replace(file_ext, ".mp3")
        subprocess.run(["ffmpeg", "-i", new_file_path, audio_path, "-y"])
        os.remove(new_file_path)
    else:
        audio_path = file_path

    mono_audio_path = convert_to_mono(audio_path)
    word_timestamps, segment_timestamps, char_timestamps = run_nemo_asr(mono_audio_path)
    default_srt, word_srt, shorts_srt, text_path, json_path, raw_text = save_files(mono_audio_path, word_timestamps)

    if os.path.exists(mono_audio_path):
        os.remove(mono_audio_path)

    return default_srt, word_srt, shorts_srt, text_path, json_path, raw_text




import click
@click.command()
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode.")
@click.option("--share", is_flag=True, default=False, help="Enable sharing of the interface.")
def main(debug, share):
    with gr.Blocks() as demo:
        gr.Markdown("<center><h1 style='font-size: 40px;'>Auto Subtitle Generator Using parakeet-tdt-0.6b-v2</h1></center>")

        with gr.Row():
          with gr.Column():
            upload_file = gr.File(label="Upload Audio or Video File")
            with gr.Row():
              generate_btn = gr.Button("🚀 Generate Subtitle", variant="primary")

          with gr.Column():
            output_default_srt = gr.File(label="sentence Level SRT File")
            output_word_srt = gr.File(label="Word Level SRT File")

            with gr.Accordion("Others Format", open=False):
                output_shorts_srt = gr.File(label="Subtitle For Vertical Video [Shorts or Reels]")
                output_text_file = gr.File(label="Speech To Text File")
                output_json = gr.File(label="Word Timestamp JSON")
                output_text = gr.Text(label="Transcribed Text",lines=6)

        generate_btn.click(
            fn=process,
            inputs=[upload_file],
            outputs=[
                output_default_srt,
                output_word_srt,
                output_shorts_srt,
                output_text_file,
                output_json,
                output_text
            ]
        )

    demo.queue().launch(debug=debug, share=share)

if __name__ == "__main__":
    main()
