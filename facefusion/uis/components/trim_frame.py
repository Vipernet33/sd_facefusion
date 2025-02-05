from typing import Any, Dict, Tuple, Optional

import gradio

import facefusion.globals
from facefusion import wording
from facefusion.vision import count_video_frame_total
from facefusion.filesystem import is_video
from facefusion.uis.core import get_ui_component, register_ui_component

TRIM_FRAME_START_SLIDER: Optional[gradio.Slider] = None
TRIM_FRAME_END_SLIDER: Optional[gradio.Slider] = None


def render() -> None:
    global TRIM_FRAME_START_SLIDER
    global TRIM_FRAME_END_SLIDER

    trim_frame_start_slider_args: Dict[str, Any] = \
        {
            'label': wording.get('uis.trim_frame_start_slider'),
            'step': 1,
            'minimum': 0,
            'maximum': 100,
            'visible': False
        }
    trim_frame_end_slider_args: Dict[str, Any] = \
        {
            'label': wording.get('uis.trim_frame_end_slider'),
            'step': 1,
            'minimum': 0,
            'maximum': 100,
            'visible': False
        }
    if is_video(facefusion.globals.target_path):
        video_frame_total = count_video_frame_total(facefusion.globals.target_path)
        trim_frame_start_slider_args['value'] = facefusion.globals.trim_frame_start or 0
        trim_frame_start_slider_args['maximum'] = video_frame_total
        trim_frame_start_slider_args['visible'] = True
        trim_frame_end_slider_args['value'] = facefusion.globals.trim_frame_end or video_frame_total
        trim_frame_end_slider_args['maximum'] = video_frame_total
        trim_frame_end_slider_args['visible'] = True
    with gradio.Row():
        TRIM_FRAME_START_SLIDER = gradio.Slider(**trim_frame_start_slider_args)
        TRIM_FRAME_END_SLIDER = gradio.Slider(**trim_frame_end_slider_args)
    register_ui_component('trim_frame_start_slider', TRIM_FRAME_START_SLIDER)
    register_ui_component('trim_frame_end_slider', TRIM_FRAME_END_SLIDER)


def listen() -> None:
    TRIM_FRAME_START_SLIDER.change(update_trim_frame_start, inputs=TRIM_FRAME_START_SLIDER)
    TRIM_FRAME_END_SLIDER.change(update_trim_frame_end, inputs=TRIM_FRAME_END_SLIDER)
    target_video = get_ui_component('target_video')
    if target_video:
        for method in ['upload', 'change', 'clear']:
            getattr(target_video, method)(remote_update, outputs=[TRIM_FRAME_START_SLIDER, TRIM_FRAME_END_SLIDER])


def remote_update() -> Tuple[gradio.update, gradio.update]:
    if is_video(facefusion.globals.target_path):
        video_frame_total = count_video_frame_total(facefusion.globals.target_path)
        facefusion.globals.trim_frame_start = None
        facefusion.globals.trim_frame_end = None
        return gradio.update(value=0, maximum=video_frame_total, visible=True), gradio.update(value=video_frame_total,
                                                                                              maximum=video_frame_total,
                                                                                              visible=True)
    return gradio.update(value=None, maximum=None, visible=False), gradio.update(value=None, maximum=None,
                                                                                 visible=False)


def update_trim_frame_start(trim_frame_start: int) -> None:
    facefusion.globals.trim_frame_start = trim_frame_start if trim_frame_start > 0 else None


def update_trim_frame_end(trim_frame_end: int) -> None:
    video_frame_total = count_video_frame_total(facefusion.globals.target_path)
    facefusion.globals.trim_frame_end = trim_frame_end if trim_frame_end < video_frame_total else None
