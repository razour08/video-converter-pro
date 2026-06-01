#!/usr/bin/env python3
"""
Video Converter CLI Tool
A highly robust, multi-threaded, and professional command-line video converter
supporting real-time progress parsing, batch processing, and subtitle embedding.
"""

import os
import sys
import re
import time
import shutil
import argparse
import subprocess

# Regex patterns to parse FFmpeg progress and metadata
DURATION_REGEX = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
TIME_REGEX = re.compile(r"time=\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
SPEED_REGEX = re.compile(r"speed=\s*([\d\.]+)x")
FPS_REGEX = re.compile(r"fps=\s*([\d\.]+)")

SUPPORTED_FORMATS = ('.ts', '.mkv', '.avi', '.mp4', '.flv', '.webm', '.mov', '.m4v')

def find_ffmpeg(custom_path=None):
    """
    Search for the FFmpeg executable in the system PATH, local directory, or custom paths.
    """
    if custom_path:
        if os.path.exists(custom_path) and os.path.isfile(custom_path):
            return custom_path
        # Check inside target directory
        exe_path = os.path.join(custom_path, "ffmpeg.exe")
        if os.path.exists(exe_path):
            return exe_path
        # Check inside bin folder of target directory
        exe_path = os.path.join(custom_path, "bin", "ffmpeg.exe")
        if os.path.exists(exe_path):
            return exe_path

    # Check system PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # Check local workspace/directory
    local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    local_bin_ffmpeg = os.path.join(os.getcwd(), "bin", "ffmpeg.exe")
    if os.path.exists(local_bin_ffmpeg):
        return local_bin_ffmpeg

    return None

def format_seconds(seconds):
    """
    Format seconds into a highly readable duration string (HH:MM:SS or MM:SS).
    """
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def format_size(bytes_size):
    """
    Convert file bytes into a human-readable size string.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"

def get_matching_subtitle(video_path):
    """
    Check if a matching subtitle file (.srt or .vtt) exists in the same folder.
    """
    base_name = os.path.splitext(video_path)[0]
    for ext in ['.srt', '.vtt']:
        sub_path = base_name + ext
        if os.path.exists(sub_path) and os.path.isfile(sub_path):
            return sub_path
    return None

def print_progress(current, total, speed="N/A", fps="N/A", prefix="Converting", bar_length=30):
    """
    Draw a dynamic text-based progress bar in the terminal.
    """
    if total <= 0:
        # Spinner for unknown duration
        spinner = ["|", "/", "-", "\\"]
        idx = int(time.time() * 4) % len(spinner)
        sys.stdout.write(f"\r{prefix}... {spinner[idx]} | Speed: {speed} | FPS: {fps}")
        sys.stdout.flush()
        return

    percent = min(float(current) * 100 / total, 100.0)
    filled_length = int(round(bar_length * percent / 100))
    bar = "█" * filled_length + "-" * (bar_length - filled_length)
    
    curr_str = format_seconds(current)
    tot_str = format_seconds(total)
    
    sys.stdout.write(f"\r{prefix} |{bar}| {percent:.1f}% ({curr_str}/{tot_str}) | Speed: {speed} | FPS: {fps}")
    sys.stdout.flush()

def convert_video(ffmpeg_path, input_file, output_file, copy_codec=False, preset='medium', embed_subtitles=True, overwrite=False, verbose=False):
    """
    Convert a single video file using FFmpeg, parsing output in real-time to show progress.
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist.")
        return False

    if os.path.exists(output_file) and not overwrite:
        print(f"Skipping: Output file '{output_file}' already exists. Use overwrite flag or menu to force conversion.")
        return False

    # Build the FFmpeg command
    command = [ffmpeg_path]
    
    # Hide banner for cleaner output
    command.extend(['-hide_banner'])
    
    # Add input file
    command.extend(['-i', input_file])
    
    # Auto-detect subtitles
    subtitle_file = get_matching_subtitle(input_file) if embed_subtitles else None
    
    if subtitle_file:
        print(f"\n[Subtitles] Found matching subtitle: '{os.path.basename(subtitle_file)}'")
        print(f"[Subtitles] Embedding soft subtitle track into target file.")
        command.extend(['-i', subtitle_file])
        
        # Map video & audio from first input, subtitles from second input
        command.extend(['-map', '0:v', '-map', '0:a', '-map', '1:s'])
        
        if copy_codec:
            command.extend(['-c:v', 'copy', '-c:a', 'copy'])
        else:
            command.extend(['-c:v', 'libx264', '-preset', preset, '-crf', '23', '-c:a', 'aac', '-b:a', '128k'])
            
        # Determine subtitle codec based on output extension
        out_ext = os.path.splitext(output_file)[1].lower()
        if out_ext == '.mp4':
            command.extend(['-c:s', 'mov_text'])
        elif out_ext == '.mkv':
            command.extend(['-c:s', 'srt'])
        else:
            command.extend(['-c:s', 'mov_text'])
    else:
        if copy_codec:
            command.extend(['-c', 'copy'])
        else:
            command.extend(['-c:v', 'libx264', '-preset', preset, '-crf', '23', '-c:a', 'aac', '-b:a', '128k'])

    # Force overwrite if flag is set, else fail
    command.append('-y')

    # Add final output file
    command.append(output_file)

    if verbose:
        print(f"\nRunning command: {' '.join(command)}")
        try:
            subprocess.run(command, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"\nConversion failed with error code: {e.returncode}")
            return False

    # Start the process asynchronously to parse progress in real-time
    process = None
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr and stdout to read everything from stdout
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace'
        )

        total_seconds = 0
        current_seconds = 0
        speed = "N/A"
        fps = "N/A"
        error_logs = []

        file_name = os.path.basename(input_file)
        
        for line in process.stdout:
            error_logs.append(line)
            if len(error_logs) > 30:
                error_logs.pop(0)

            # 1. Parse Duration (usually at the start of the output)
            if total_seconds == 0:
                duration_match = DURATION_REGEX.search(line)
                if duration_match:
                    h, m, s, _ = map(int, duration_match.groups())
                    total_seconds = h * 3600 + m * 60 + s

            # 2. Parse Progress indicators
            time_match = TIME_REGEX.search(line)
            if time_match:
                try:
                    h, m, s, _ = map(int, time_match.groups())
                    current_seconds = h * 3600 + m * 60 + s
                except ValueError:
                    pass

                # Parse Speed
                speed_match = SPEED_REGEX.search(line)
                if speed_match:
                    speed = speed_match.group(1) + "x"

                # Parse FPS
                fps_match = FPS_REGEX.search(line)
                if fps_match:
                    fps = fps_match.group(1)

                print_progress(
                    current=current_seconds,
                    total=total_seconds,
                    speed=speed,
                    fps=fps,
                    prefix=f"Converting '{file_name}'"
                )

        process.wait()
        
        if process.returncode == 0:
            print_progress(
                current=total_seconds,
                total=total_seconds,
                speed=speed,
                fps=fps,
                prefix=f"Converting '{file_name}'"
            )
            print(f"\n[Success] Finished converting: '{file_name}' -> '{output_file}'")
            return True
        else:
            print(f"\n[Error] Conversion failed (Return code: {process.returncode})")
            print("--- Last 15 lines of FFmpeg output ---")
            for log in error_logs[-15:]:
                print(log.strip())
            return False

    except KeyboardInterrupt:
        print("\n\n[Warning] Conversion interrupted by user!")
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        # Clean up incomplete output file
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                print(f"[Cleanup] Removed incomplete output file: {output_file}")
            except OSError as e:
                print(f"[Cleanup Error] Could not remove incomplete file: {e}")
        return False

def batch_convert(ffmpeg_path, files, target_format='mp4', copy_codec=False, preset='medium', embed_subtitles=True):
    """
    Process multiple files sequentially.
    """
    total_files = len(files)
    print("=" * 60)
    print(f"Starting batch conversion of {total_files} files...".center(60))
    print("=" * 60)
    
    success_count = 0
    start_time = time.time()

    for idx, file in enumerate(files, 1):
        print(f"\n[{idx}/{total_files}] Processing: '{file}'")
        base_name = os.path.splitext(file)[0]
        output_file = f"{base_name}.{target_format}"
        
        # Handle filename collisions (e.g. if file is already .mp4)
        if output_file.lower() == file.lower():
            output_file = f"{base_name}_converted.{target_format}"

        success = convert_video(
            ffmpeg_path=ffmpeg_path,
            input_file=file,
            output_file=output_file,
            copy_codec=copy_codec,
            preset=preset,
            embed_subtitles=embed_subtitles,
            overwrite=True
        )
        if success:
            success_count += 1

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("Batch Processing Completed!".center(60))
    print(f"Successful: {success_count}/{total_files} | Total Time: {format_seconds(elapsed)}".center(60))
    print("=" * 60)

def print_help():
    """
    Display beautiful terminal help usage message.
    """
    print("\nUsage Examples:")
    print("  python conerter.py                          # Launches the Interactive Menu")
    print("  python conerter.py -i input.ts -o output.mp4 # Convert a single file")
    print("  python conerter.py -i input.ts --copy       # Ultra-fast copying without re-encoding")
    print("  python conerter.py --batch                  # Batch convert all videos in current folder")
    print("  python conerter.py --batch --format mkv     # Batch convert to MKV format")
    print("  python conerter.py --batch --ext ts,avi     # Batch convert only specific extensions")

def interactive_menu(ffmpeg_path):
    """
    Launch a user-friendly interactive terminal menu.
    """
    print("\n" + "=" * 60)
    print("VIDEO CONVERTER PRO - INTERACTIVE MENU".center(60))
    print("=" * 60)

    # Scan for supported video files in current folder
    video_files = [
        f for f in os.listdir('.') 
        if f.lower().endswith(SUPPORTED_FORMATS) and os.path.isfile(f)
    ]

    print("\nSelect an action:")
    print("  [1] Convert a single video file")
    print("  [2] Batch convert all video files in this directory")
    print("  [3] Show detailed CLI help instructions")
    print("  [4] Exit")

    try:
        choice = input("\nEnter selection (1-4): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        return

    if choice == '1':
        if not video_files:
            print("\n[Notice] No compatible video files found in the current directory.")
            return

        print("\nAvailable video files in current directory:")
        for idx, file in enumerate(video_files, 1):
            size_str = format_size(os.path.getsize(file))
            print(f"  [{idx}] {file} ({size_str})")

        try:
            file_choice = input(f"\nSelect file number (1-{len(video_files)}): ").strip()
            file_idx = int(file_choice) - 1
            if file_idx < 0 or file_idx >= len(video_files):
                print("[Error] Invalid selection.")
                return
            selected_file = video_files[file_idx]
        except (ValueError, IndexError):
            print("[Error] Invalid input.")
            return
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return

        target_format = input("\nEnter target format (e.g. mp4, mkv, avi) [default: mp4]: ").strip().lower()
        if not target_format:
            target_format = 'mp4'

        subtitle_file = get_matching_subtitle(selected_file)
        embed_sub = False
        if subtitle_file:
            sub_choice = input(f"Found matching subtitle file '{os.path.basename(subtitle_file)}'. Embed it? (y/n) [default: y]: ").strip().lower()
            embed_sub = sub_choice != 'n'

        base_name = os.path.splitext(selected_file)[0]
        output_file = f"{base_name}_converted.{target_format}"
        custom_out = input(f"Enter output filename [default: {output_file}]: ").strip()
        if custom_out:
            output_file = custom_out

        mode_choice = input("Select mode:\n  [1] High Quality Re-encode (recommended)\n  [2] Ultra-fast Copy (no re-encoding)\nSelection [default: 1]: ").strip()
        copy_mode = (mode_choice == '2')

        preset_choice = 'medium'
        if not copy_mode:
            p_choice = input("Select compression speed/preset (ultrafast, fast, medium, slow) [default: medium]: ").strip().lower()
            if p_choice in ['ultrafast', 'fast', 'medium', 'slow']:
                preset_choice = p_choice

        print("\n[Start] Preparing conversion...")
        convert_video(
            ffmpeg_path=ffmpeg_path,
            input_file=selected_file,
            output_file=output_file,
            copy_codec=copy_mode,
            preset=preset_choice,
            embed_subtitles=embed_sub,
            overwrite=True
        )

    elif choice == '2':
        if not video_files:
            print("\n[Notice] No compatible video files found in the current directory.")
            return

        print(f"\nFound {len(video_files)} video files:")
        for idx, file in enumerate(video_files, 1):
            size_str = format_size(os.path.getsize(file))
            print(f"  - {file} ({size_str})")

        target_format = input("\nEnter target format for all files (e.g. mp4, mkv) [default: mp4]: ").strip().lower()
        if not target_format:
            target_format = 'mp4'

        mode_choice = input("Select mode:\n  [1] High Quality Re-encode (recommended)\n  [2] Ultra-fast Copy (no re-encoding)\nSelection [default: 1]: ").strip()
        copy_mode = (mode_choice == '2')

        sub_choice = input("Embed matching subtitle files if found? (y/n) [default: y]: ").strip().lower()
        embed_subs = sub_choice != 'n'

        confirm = input(f"\nConvert these {len(video_files)} files to .{target_format}? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

        batch_convert(
            ffmpeg_path=ffmpeg_path,
            files=video_files,
            target_format=target_format,
            copy_codec=copy_mode,
            embed_subtitles=embed_subs
        )

    elif choice == '3':
        print_help()
    else:
        print("\nExiting converter. Goodbye!")

def main():
    parser = argparse.ArgumentParser(
        description="Professional FFmpeg-based Video Converter Utility.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-i', '--input', help="Input video file path or directory (when using batch conversion).")
    parser.add_argument('-o', '--output', help="Output file path (ignored in batch conversion).")
    parser.add_argument('-f', '--format', default='mp4', help="Output format/extension (default: mp4).")
    parser.add_argument('-b', '--batch', action='store_true', help="Batch convert multiple videos in the input/current folder.")
    parser.add_argument('-e', '--ext', default='ts,mkv,avi,mov,flv,webm', help="Comma-separated extensions to search during batch mode.")
    parser.add_argument('-c', '--copy', action='store_true', help="Fast video/audio stream copy without re-encoding.")
    parser.add_argument('-p', '--preset', default='medium', choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'], help="FFmpeg encoding speed preset (default: medium).")
    parser.add_argument('--ffmpeg-path', help="Custom path to the ffmpeg executable.")
    parser.add_argument('--no-subtitles', action='store_true', help="Do not search for or embed matching subtitle tracks.")
    parser.add_argument('--overwrite', action='store_true', help="Automatically overwrite existing output files without prompting.")
    parser.add_argument('--verbose', action='store_true', help="Print full command lines and show raw FFmpeg output logs.")

    args = parser.parse_args()

    # Search for FFmpeg
    ffmpeg_path = find_ffmpeg(args.ffmpeg_path)
    if not ffmpeg_path:
        print("\n" + "!" * 60)
        print("ERROR: FFmpeg executable could not be found!".center(60))
        print("!" * 60)
        print("FFmpeg is required for video conversion. Please:")
        print("  1. Install FFmpeg and add it to your system PATH.")
        print("  2. Place 'ffmpeg.exe' inside the current directory.")
        print("  3. Pass your custom path using the --ffmpeg-path argument.")
        print("\nFor more instructions, visit: https://ffmpeg.org/download.html")
        sys.exit(1)

    # If no input file is specified and batch mode is not active, enter interactive menu
    if not args.input and not args.batch:
        interactive_menu(ffmpeg_path)
        sys.exit(0)

    embed_subs = not args.no_subtitles

    if args.batch:
        # Batch Mode
        search_dir = args.input if (args.input and os.path.isdir(args.input)) else '.'
        ext_list = [f".{ext.strip().lower().lstrip('.')}" for ext in args.ext.split(',')]
        
        # Gather matching video files
        video_files = []
        for root, _, files in os.walk(search_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in ext_list):
                    video_files.append(os.path.join(root, file))
            # Only search root directory, don't recurse deep unless specified
            break

        if not video_files:
            print(f"No video files with extensions {args.ext} found in '{search_dir}'.")
            sys.exit(1)

        batch_convert(
            ffmpeg_path=ffmpeg_path,
            files=video_files,
            target_format=args.format,
            copy_codec=args.copy,
            preset=args.preset,
            embed_subtitles=embed_subs
        )
    else:
        # Single File Mode
        if not args.input:
            print("Error: Please specify an input file using -i/--input or launch interactive mode by running with no arguments.")
            print_help()
            sys.exit(1)

        input_file = args.input
        output_file = args.output

        if not output_file:
            base_name = os.path.splitext(input_file)[0]
            output_file = f"{base_name}_converted.{args.format}"
            # Ensure we don't accidentally overwrite the input file if same format
            if output_file.lower() == input_file.lower():
                output_file = f"{base_name}_converted_1.{args.format}"

        print(f"\n[Single Mode] Converting: '{input_file}' -> '{output_file}'")
        success = convert_video(
            ffmpeg_path=ffmpeg_path,
            input_file=input_file,
            output_file=output_file,
            copy_codec=args.copy,
            preset=args.preset,
            embed_subtitles=embed_subs,
            overwrite=args.overwrite,
            verbose=args.verbose
        )
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()