import json
import subprocess
from typing import List, Optional

from ffmpeg_progress_yield import FfmpegProgress

import facefusion.globals
from facefusion import logger
from facefusion.filesystem import get_temp_frames_pattern, get_temp_output_video_path
from facefusion.mytqdm import mytqdm
from facefusion.typing import OutputVideoPreset, Fps, AudioBuffer

TEMP_OUTPUT_VIDEO_NAME = 'temp.mp4'
LAST_VIDEO_INFO = None


def run_ffmpeg(args: List[str], status=None) -> bool:
    commands = ['ffmpeg', '-hide_banner', '-loglevel', 'error']
    commands.extend(args)
    try:
        if status:
            ff = FfmpegProgress(commands)
            with mytqdm(total=100, position=1, desc="Processing", state=status) as pbar:
                for progress in ff.run_command_with_progress():
                    pbar.update(progress - pbar.n)
        else:
            res = subprocess.run(commands, stderr=subprocess.PIPE, check=True)
            if res.stderr:
                print(res.stderr.decode('utf-8'))
                return False
        return True
    except subprocess.CalledProcessError as exception:
        logger.debug(exception.stderr.decode().strip(), 'FACEFUSION.FFMPEG')
        return False


def open_ffmpeg(args: List[str]) -> subprocess.Popen[bytes]:
    commands = ['ffmpeg', '-hide_banner', '-loglevel', 'error']
    commands.extend(args)
    return subprocess.Popen(commands, stdin=subprocess.PIPE)


def get_video_info(video_path):
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return json.loads(result.stdout)


def detect_hardware_acceleration():
    try:
        result = subprocess.run(['ffmpeg', '-hwaccels'], capture_output=True, text=True)
        output = result.stdout
        if 'vulkan' in output:
            return 'vulkan'
        elif 'cuda' in output:
            return 'cuda'
        elif 'vaapi' in output:
            return 'vaapi'
        else:
            return None
    except Exception as e:
        print(f"Error detecting hardware acceleration: {e}")
        return None


def extract_frames(target_path: str, video_resolution: str, video_fps: Fps, status=None) -> bool:
    temp_frame_compression = round(31 - (facefusion.globals.temp_frame_quality * 0.31))
    trim_frame_start = facefusion.globals.trim_frame_start
    trim_frame_end = facefusion.globals.trim_frame_end
    temp_frames_pattern = get_temp_frames_pattern(target_path, '%04d')
    commands = ['-hwaccel', 'auto', '-i', target_path, '-q:v', str(temp_frame_compression), '-pix_fmt', 'rgb24']
    if trim_frame_start is not None and trim_frame_end is not None:
        commands.extend(['-vf', 'trim=start_frame=' + str(trim_frame_start) + ':end_frame=' + str(
            trim_frame_end) + ',scale=' + str(video_resolution) + ',fps=' + str(video_fps)])
    elif trim_frame_start is not None:
        commands.extend(['-vf', 'trim=start_frame=' + str(trim_frame_start) + ',scale=' + str(
            video_resolution) + ',fps=' + str(video_fps)])
    elif trim_frame_end is not None:
        commands.extend(['-vf',
                         'trim=end_frame=' + str(trim_frame_end) + ',scale=' + str(video_resolution) + ',fps=' + str(
                             video_fps)])
    else:
        commands.extend(['-vf', 'scale=' + str(video_resolution) + ',fps=' + str(video_fps)])
    commands.extend(['-vsync', '0', temp_frames_pattern])
    return run_ffmpeg(commands, status)


def compress_image(output_path: str) -> bool:
    output_image_compression = round(31 - (facefusion.globals.output_image_quality * 0.31))
    commands = ['-hwaccel', 'auto', '-i', output_path, '-q:v', str(output_image_compression), '-y', output_path]
    return run_ffmpeg(commands)


def merge_video(target_path: str, fps: float, status=None) -> bool:
    temp_output_video_path = get_temp_output_video_path(target_path)
    temp_frames_pattern = get_temp_frames_pattern(target_path, '%04d')
    commands = ['-hwaccel', 'auto', '-r', str(fps), '-i', temp_frames_pattern, '-c:v',
                facefusion.globals.output_video_encoder]
    if facefusion.globals.output_video_encoder in ['libx264', 'libx265']:
        output_video_compression = round(51 - (facefusion.globals.output_video_quality * 0.51))
        commands.extend(['-crf', str(output_video_compression), '-preset', facefusion.globals.output_video_preset])
    if facefusion.globals.output_video_encoder in ['libvpx-vp9']:
        output_video_compression = round(63 - (facefusion.globals.output_video_quality * 0.63))
        commands.extend(['-crf', str(output_video_compression)])
    if facefusion.globals.output_video_encoder in ['h264_nvenc', 'hevc_nvenc']:
        output_video_compression = round(51 - (facefusion.globals.output_video_quality * 0.51))
        commands.extend(
            ['-cq', str(output_video_compression), '-preset', map_nvenc_preset(facefusion.globals.output_video_preset)])
    commands.extend(['-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-y', temp_output_video_path])
    return run_ffmpeg(commands, status)


def read_audio_buffer(target_path: str, sample_rate: int, channel_total: int) -> Optional[AudioBuffer]:
    commands = ['-i', target_path, '-vn', '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', str(sample_rate), '-ac',
                str(channel_total), '-']
    process = open_ffmpeg(commands)
    audio_buffer, error = process.communicate()
    if process.returncode == 0:
        return audio_buffer
    return None


def extract_audio_from_video(target_path: str) -> Optional[str]:
    audio_path = target_path.replace('.mp4', '.wav')
    commands = ['-i', target_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '2', '-y', audio_path]
    if run_ffmpeg(commands):
        return audio_path
    return None


def restore_audio(target_path: str, output_path: str, video_fps: Fps, status=None) -> bool:
    trim_frame_start = facefusion.globals.trim_frame_start
    trim_frame_end = facefusion.globals.trim_frame_end
    temp_output_video_path = get_temp_output_video_path(target_path)
    commands = ['-hwaccel', 'auto', '-i', temp_output_video_path]
    if trim_frame_start is not None:
        start_time = trim_frame_start / video_fps
        commands.extend(['-ss', str(start_time)])
    if trim_frame_end is not None:
        end_time = trim_frame_end / video_fps
        commands.extend(['-to', str(end_time)])
    commands.extend(['-i', target_path, '-c', 'copy', '-map', '0:v:0', '-map', '1:a:0', '-shortest', '-y', output_path])
    return run_ffmpeg(commands, status)


def replace_audio(target_path: str, audio_path: str, output_path: str) -> bool:
    temp_output_path = get_temp_output_video_path(target_path)
    commands = ['-hwaccel', 'auto', '-i', temp_output_path, '-i', audio_path, '-c:v', 'copy', '-af', 'apad',
                '-shortest', '-map', '0:v:0', '-map', '1:a:0', '-y', output_path]
    return run_ffmpeg(commands)


def map_nvenc_preset(output_video_preset: OutputVideoPreset) -> Optional[str]:
    if output_video_preset in ['ultrafast', 'superfast', 'veryfast']:
        return 'p1'
    if output_video_preset == 'faster':
        return 'p2'
    if output_video_preset == 'fast':
        return 'p3'
    if output_video_preset == 'medium':
        return 'p4'
    if output_video_preset == 'slow':
        return 'p5'
    if output_video_preset == 'slower':
        return 'p6'
    if output_video_preset == 'veryslow':
        return 'p7'
    return None
