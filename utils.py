import string
import json
import os

import re
import uuid
from pydub import AudioSegment

# Ensure the 'subtitles' directory exists
if not os.path.exists("./subtitles"):
    os.makedirs("./subtitles", exist_ok=True)

def clean_file_name(file_path,unique_id=True):
    # Get the base file name and extension
    file_name = os.path.basename(file_path)
    file_name, file_extension = os.path.splitext(file_name)

    # Replace non-alphanumeric characters with an underscore
    cleaned = re.sub(r'[^a-zA-Z\d]+', '_', file_name)

    # Remove any multiple underscores
    clean_file_name = re.sub(r'_+', '_', cleaned).strip('_')

    # Generate a random UUID for uniqueness
    random_uuid = uuid.uuid4().hex[:6]
    if unique_id:
        clean_file_name = f"{clean_file_name}_{random_uuid}{file_extension}"
    else:
        clean_file_name = f"{clean_file_name}{file_extension}"
        
    return clean_file_name 

def convert_to_mono(file_path, output_format="mp3"):
    # Load the audio (any format supported by ffmpeg/pydub)
    audio = AudioSegment.from_file(file_path)

    # Convert to mono
    mono_audio = audio.set_channels(1)

    file_name = os.path.basename(file_path)
    file_name, file_extension = os.path.splitext(file_name)

    # Get the cleaned output file name and path
    cleaned_file_name = clean_file_name(file_name)
    output_file = f"./subtitles/{cleaned_file_name}.{output_format}"

    # Export the mono audio
    mono_audio.export(output_file, format=output_format)
    return output_file

def format_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    millisec = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{sec:02},{millisec:03}"

## Word Level SRT File
def write_word_srt(mono_audio_path,word_level_timestamps, skip_punctuation=True):
    extension = os.path.splitext(mono_audio_path)[1]
    output_file=mono_audio_path.replace(extension,"_word_level.srt")
    with open(output_file, "w", encoding="utf-8") as f:
        index = 1

        for entry in word_level_timestamps:
            word = entry["word"]

            if skip_punctuation and all(c in string.punctuation for c in word):
                continue

            start_srt = format_srt_time(entry["start"])
            end_srt = format_srt_time(entry["end"])

            f.write(f"{index}\n{start_srt} --> {end_srt}\n{word}\n\n")
            index += 1
    return output_file


## Speech To text File
def write_words_to_txt(mono_audio_path, word_level_timestamps):

    extension = os.path.splitext(mono_audio_path)[1]
    output_file=mono_audio_path.replace(extension,".txt")

    with open(output_file, "w", encoding="utf-8") as f:
        words = [
            entry["word"]
            for entry in word_level_timestamps
            if not all(c in string.punctuation for c in entry["word"])
        ]
        text = " ".join(words)
        f.write(text)
        return text, output_file


## Sentence Level Srt File
def generate_professional_subtitles(mono_audio_path, word_timestamps, max_words_per_subtitle=8, max_subtitle_duration=5.0, min_pause_for_split=0.5):
    """
    Generates professional subtitles and saves to SRT file by:
    - Splitting at sentence boundaries (., ?, !) when possible
    - Respecting pauses (> min_pause_for_split) for natural breaks
    - Enforcing max_words_per_subtitle and max_subtitle_duration
    - Outputting standard SRT format with proper timing
    
    Returns:
        output_file: Path to the generated SRT file
        subtitles: List of subtitle dictionaries with text/start/end
    """
    subtitles = []
    current_sub = {
        "text": "",
        "start": None,
        "end": None,
        "word_count": 0
    }
    
    # Prepare output SRT file path
    extension = os.path.splitext(mono_audio_path)[1]
    output_file=mono_audio_path.replace(extension,".srt")

    
    # Process word timestamps to create subtitles
    for word_data in word_timestamps:
        word = word_data['word']
        word_start = word_data['start']
        word_end = word_data['end']

        # Check for sentence-ending punctuation
        is_end_of_sentence = word.endswith(('.', '?', '!'))

        # Check for a natural pause (silence between words)
        has_pause = (current_sub["end"] is not None and 
                    word_start - current_sub["end"] > min_pause_for_split)

        # Check if we need to split due to constraints
        should_split = (
            is_end_of_sentence or
            has_pause or
            current_sub["word_count"] >= max_words_per_subtitle or
            (current_sub["end"] is not None and 
             (word_end - current_sub["start"]) > max_subtitle_duration)
        )

        if should_split and current_sub["text"]:
            # Finalize current subtitle
            subtitles.append({
                "text": current_sub["text"].strip(),
                "start": current_sub["start"],
                "end": current_sub["end"]
            })
            # Reset for next subtitle
            current_sub = {
                "text": "",
                "start": None,
                "end": None,
                "word_count": 0
            }

        # Add current word to subtitle
        if current_sub["word_count"] == 0:
            current_sub["start"] = word_start
        current_sub["text"] += " " + word if current_sub["text"] else word
        current_sub["end"] = word_end
        current_sub["word_count"] += 1

    # Add last subtitle if exists
    if current_sub["text"]:
        subtitles.append({
            "text": current_sub["text"].strip(),
            "start": current_sub["start"],
            "end": current_sub["end"]
        })

    # Write to SRT file
    with open(output_file, "w", encoding="utf-8") as f:
        for i, sub in enumerate(subtitles, 1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n")
            f.write(f"{sub['text']}\n\n")
    
    return output_file, subtitles   


## For vertical Videos
def for_yt_shorts(mono_audio_path, word_timestamps, min_silence_between_words=0.3, max_characters_per_subtitle=17):
    """
    Generates optimized subtitles for YouTube Shorts/Instagram Reels by:
    - Combining hyphenated words (e.g., "co-" + "-worker" → "coworker")
    - Respecting max character limits per subtitle (default: 17)
    - Creating natural breaks at pauses (> min_silence_between_words)
    - Outputting properly formatted SRT files
    
    Returns:
        output_file: Path to generated SRT file
        subtitles: List of subtitle dictionaries (text/start/end)
    """
    subtitles = []
    current_sub = {
        "text": "",
        "start": None,
        "end": None,
        "char_count": 0
    }
    

    extension = os.path.splitext(mono_audio_path)[1]
    output_file=mono_audio_path.replace(extension,"_shorts.srt")

    i = 0
    while i < len(word_timestamps):
        # Process current word and any hyphenated continuations
        full_word = word_timestamps[i]['word']
        start_time = word_timestamps[i]['start']
        end_time = word_timestamps[i]['end']
        
        # Combine hyphenated words (e.g., "co-" + "-worker")
        while (i + 1 < len(word_timestamps) and 
               word_timestamps[i+1]['word'].startswith('-')):
            next_word = word_timestamps[i+1]['word'].lstrip('-')
            full_word += next_word
            end_time = word_timestamps[i+1]['end']
            i += 1
        
        # Check if adding this word would exceed character limit
        new_char_count = current_sub["char_count"] + len(full_word) + (1 if current_sub["text"] else 0)
        
        # Check for natural break conditions
        needs_break = (
            new_char_count > max_characters_per_subtitle or
            (current_sub["end"] is not None and 
             word_timestamps[i]['start'] - current_sub["end"] > min_silence_between_words)
        )
        
        if needs_break and current_sub["text"]:
            # Finalize current subtitle
            subtitles.append({
                "text": current_sub["text"].strip(),
                "start": current_sub["start"],
                "end": current_sub["end"]
            })
            # Start new subtitle
            current_sub = {
                "text": full_word,
                "start": start_time,
                "end": end_time,
                "char_count": len(full_word)
            }
        else:
            # Add to current subtitle
            if current_sub["text"]:
                current_sub["text"] += " " + full_word
                current_sub["char_count"] += 1 + len(full_word)  # Space + word
            else:
                current_sub["text"] = full_word
                current_sub["start"] = start_time
                current_sub["char_count"] = len(full_word)
            current_sub["end"] = end_time
        
        i += 1
    
    # Add final subtitle if exists
    if current_sub["text"]:
        subtitles.append({
            "text": current_sub["text"].strip(),
            "start": current_sub["start"],
            "end": current_sub["end"]
        })
    
    # Write SRT file
    with open(output_file, "w", encoding="utf-8") as f:
        for idx, sub in enumerate(subtitles, 1):
            f.write(f"{idx}\n")
            f.write(f"{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n")
            f.write(f"{sub['text']}\n\n")
    
    return output_file, subtitles



## Save word level timestamp for later use if you are a developer 
def word_timestamp_json(mono_audio_path, word_timestamps):
    """
    Save word timestamps as a JSON file with the same base name as the audio file.
    
    Args:
        mono_audio_path: Path to the audio file (e.g., "audio.wav")
        word_timestamps: List of word timestamp dictionaries
        
    Returns:
        output_file: Path to the generated JSON file
        word_timestamps: The original word timestamps (unchanged)
    """
    # Create output path
    extension = os.path.splitext(mono_audio_path)[1]
    output_file=mono_audio_path.replace(extension,"_word_timestamps.json")

    # Save as JSON with pretty formatting
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(word_timestamps, f, indent=2, ensure_ascii=False)
    
    return output_file    

## save all files 
def save_files(mono_audio_path, word_timestamps):
    """
    Processes word timestamps and generates multiple subtitle/text formats for different use cases.
    
    Generates:
    1. Professional SRT subtitles (for standard videos)
    2. Word-level SRT (for short-form content)
    3. Optimized vertical video subtitles (Shorts/Reels/TikTok)
    4. Raw speech-to-text transcript
    5. JSON timestamp data (for developers)
    6. Raw transcript text (for immediate use)
    
    Args:
        mono_audio_path: Path to the source audio file (WAV format)
        word_timestamps: List of dictionaries containing word-level timestamps
                        [{'word': str, 'start': float, 'end': float}, ...]
    
    Returns:
        Six separate values in this order:
        default_srt_path:       # Traditional subtitles (8 words max)
        word_level_srt_path:    # Single-word segments  
        shorts_srt_path:        # Vertical video optimized
        speech_text_path:       # Plain text transcript file
        timestamps_json_path:   # Raw timestamp data file
        text:                   # Raw transcript text string
    """
    
    # 1. Generate standard subtitles for traditional videos
    default_srt_path, _ = generate_professional_subtitles(
        mono_audio_path,
        word_timestamps,
        max_words_per_subtitle=8,
        max_subtitle_duration=5.0,
        min_pause_for_split=0.5
    )
    
    # 2. Create word-level SRT for short-form content
    word_level_srt_path = write_word_srt(mono_audio_path, word_timestamps)
    
    # 3. Generate optimized subtitles for vertical videos
    shorts_srt_path, _ = for_yt_shorts(
        mono_audio_path,
        word_timestamps,
        min_silence_between_words=0.3,
        max_characters_per_subtitle=17
    )
    
    # 4. Extract raw transcript text and save to file
    text, speech_text_path = write_words_to_txt(mono_audio_path, word_timestamps)
    
    # 5. Save developer-friendly timestamp data
    timestamps_json_path = word_timestamp_json(mono_audio_path, word_timestamps)
    
    # Return all six values separately
    return default_srt_path, word_level_srt_path, shorts_srt_path, speech_text_path, timestamps_json_path, text
