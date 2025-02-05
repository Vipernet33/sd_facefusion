import os
from typing import Any, List, Literal
from argparse import ArgumentParser
import cv2
import numpy

import facefusion.globals
import facefusion.processors.frame.core as frame_processors
from facefusion import config, wording
from facefusion.face_analyser import get_one_face, get_many_faces, find_similar_faces, clear_face_analyser
from facefusion.face_masker import create_static_box_mask, create_occlusion_mask, create_region_mask, \
    clear_face_occluder, clear_face_parser
from facefusion.face_helper import warp_face_by_face_landmark_5, categorize_age, categorize_gender
from facefusion.face_store import get_reference_faces
from facefusion.content_analyser import clear_content_analyser
from facefusion.processors.frame.modules.face_swapper import update_padding
from facefusion.typing import Face, VisionFrame, Update_Process, ProcessMode, QueuePayload
from facefusion.vision import read_image, read_static_image, write_image
from facefusion.processors.frame.typings import FaceDebuggerInputs
from facefusion.processors.frame import globals as frame_processors_globals, choices as frame_processors_choices

NAME = __name__.upper()


def get_frame_processor() -> None:
    pass


def clear_frame_processor() -> None:
    pass


def get_options(key: Literal['model']) -> None:
    pass


def set_options(key: Literal['model'], value: Any) -> None:
    pass


def register_args(program: ArgumentParser) -> None:
    program.add_argument('--face-debugger-items', help=wording.get('help.face_debugger_items').format(
        choices=', '.join(frame_processors_choices.face_debugger_items)),
                         default=config.get_str_list('frame_processors.face_debugger_items', 'landmark-5 face-mask'),
                         choices=frame_processors_choices.face_debugger_items, nargs='+', metavar='FACE_DEBUGGER_ITEMS')


def apply_args(program: ArgumentParser) -> None:
    args = program.parse_args()
    frame_processors_globals.face_debugger_items = args.face_debugger_items


def pre_check() -> bool:
    return True


def post_check() -> bool:
    return True


def pre_process(mode: ProcessMode) -> bool:
    return True


def post_process() -> None:
    read_static_image.cache_clear()
    if facefusion.globals.video_memory_strategy == 'strict' or facefusion.globals.video_memory_strategy == 'moderate':
        clear_frame_processor()
    if facefusion.globals.video_memory_strategy == 'strict':
        clear_face_analyser()
        clear_content_analyser()
        clear_face_occluder()
        clear_face_parser()


def debug_face(target_face: Face, temp_vision_frame: VisionFrame, frame_number=-1) -> VisionFrame:
    primary_color = (0, 0, 255)
    secondary_color = (0, 255, 0)
    bounding_box = target_face.bounding_box.astype(numpy.int32)
    temp_vision_frame = temp_vision_frame.copy()

    if 'bounding-box' in frame_processors_globals.face_debugger_items:
        cv2.rectangle(temp_vision_frame, (bounding_box[0], bounding_box[1]), (bounding_box[2], bounding_box[3]),
                      secondary_color, 2)
    if 'face-mask' in frame_processors_globals.face_debugger_items:
        crop_vision_frame, affine_matrix = warp_face_by_face_landmark_5(temp_vision_frame, target_face.landmark['5/68'],
                                                                        'arcface_128_v2', (512, 512))
        inverse_matrix = cv2.invertAffineTransform(affine_matrix)
        temp_size = temp_vision_frame.shape[:2][::-1]
        crop_mask_list = []
        if 'box' in facefusion.globals.face_mask_types:
            padding = facefusion.globals.face_mask_padding
            padding = update_padding(padding, frame_number)
            box_mask = create_static_box_mask(crop_vision_frame.shape[:2][::-1], 0, padding)
            crop_mask_list.append(box_mask)

        if 'occlusion' in facefusion.globals.face_mask_types:
            occlusion_mask = create_occlusion_mask(crop_vision_frame)
            crop_mask_list.append(occlusion_mask)
        if 'region' in facefusion.globals.face_mask_types:
            region_mask = create_region_mask(crop_vision_frame, facefusion.globals.face_mask_regions)
            crop_mask_list.append(region_mask)
        crop_mask = numpy.minimum.reduce(crop_mask_list).clip(0, 1)
        crop_mask = (crop_mask * 255).astype(numpy.uint8)
        inverse_vision_frame = cv2.warpAffine(crop_mask, inverse_matrix, temp_size)
        inverse_vision_frame = cv2.threshold(inverse_vision_frame, 100, 255, cv2.THRESH_BINARY)[1]
        inverse_vision_frame[inverse_vision_frame > 0] = 255
        inverse_contours = cv2.findContours(inverse_vision_frame, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0]
        cv2.drawContours(temp_vision_frame, inverse_contours, -1, primary_color, 2)
    if bounding_box[3] - bounding_box[1] > 60 and bounding_box[2] - bounding_box[0] > 60:
        top = bounding_box[1]
        left = bounding_box[0] + 20
        if 'landmark-5' in frame_processors_globals.face_debugger_items:
            face_landmark_5 = target_face.landmark['5/68'].astype(numpy.int32)
            for index in range(face_landmark_5.shape[0]):
                cv2.circle(temp_vision_frame, (face_landmark_5[index][0], face_landmark_5[index][1]), 3, primary_color,
                           -1)
        if 'landmark-68' in frame_processors_globals.face_debugger_items:
            face_landmark_68 = target_face.landmark['68'].astype(numpy.int32)
            for index in range(face_landmark_68.shape[0]):
                cv2.circle(temp_vision_frame, (face_landmark_68[index][0], face_landmark_68[index][1]), 3,
                           secondary_color, -1)
        if 'score' in frame_processors_globals.face_debugger_items:
            face_score_text = str(round(target_face.score, 2))
            top = top + 20
            cv2.putText(temp_vision_frame, face_score_text, (left, top), cv2.FONT_HERSHEY_SIMPLEX, 0.5, secondary_color,
                        2)
        if 'age' in frame_processors_globals.face_debugger_items:
            face_age_text = categorize_age(target_face.age)
            top = top + 20
            cv2.putText(temp_vision_frame, face_age_text, (left, top), cv2.FONT_HERSHEY_SIMPLEX, 0.5, secondary_color,
                        2)
        if 'gender' in frame_processors_globals.face_debugger_items:
            face_gender_text = categorize_gender(target_face.gender)
            top = top + 20
            cv2.putText(temp_vision_frame, face_gender_text, (left, top), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        secondary_color, 2)
    else:
        print(f"Face too small to debug: {bounding_box[3] - bounding_box[1]}x{bounding_box[2] - bounding_box[0]}")
    return temp_vision_frame


def get_reference_frame(source_face: Face, target_face: Face, temp_vision_frame: VisionFrame) -> VisionFrame:
    pass


def process_frame(inputs: FaceDebuggerInputs) -> VisionFrame:
    reference_faces = inputs['reference_faces']
    reference_faces_2 = inputs.get('reference_faces_2', None)
    target_vision_frame = inputs['target_vision_frame']
    source_frame = inputs.get('source_frame', target_vision_frame)
    target_frame_number = inputs['target_frame_number']

    if 'reference' in facefusion.globals.face_selector_mode:
        for ref_faces in [reference_faces, reference_faces_2]:
            similar_faces = find_similar_faces(ref_faces, source_frame,
                                               facefusion.globals.reference_face_distance)
            if similar_faces:
                for similar_face in similar_faces:
                    target_vision_frame = debug_face(similar_face, target_vision_frame, target_frame_number)
        else:
            print("No similar face found in the reference frame")
    if 'one' in facefusion.globals.face_selector_mode:
        target_face = get_one_face(source_frame)
        if target_face:
            target_vision_frame = debug_face(target_face, target_vision_frame, target_frame_number)
    if 'many' in facefusion.globals.face_selector_mode:
        many_faces = get_many_faces(source_frame)
        if many_faces:
            for target_face in many_faces:
                target_vision_frame = debug_face(target_face, target_vision_frame, target_frame_number)
    return target_vision_frame


def process_frames(source_paths: List[str], source_paths_2: List[str], queue_payloads: List[QueuePayload],
                   update_progress: Update_Process) -> None:
    reference_faces, reference_faces_2 = get_reference_faces() if 'reference' in facefusion.globals.face_selector_mode else None, None

    for queue_payload in queue_payloads:
        target_vision_path = queue_payload['frame_path']
        target_vision_frame = read_image(target_vision_path)
        result_frame = process_frame(
            {
                'reference_faces': reference_faces,
                'reference_faces_2': reference_faces_2,
                'target_vision_frame': target_vision_frame,
                'target_frame_number': queue_payload['frame_number']
            })
        write_image(target_vision_path, result_frame)
        update_progress(target_vision_path)


def process_image(source_paths: List[str], source_paths_2: List[str], target_path: str, output_path: str) -> None:
    reference_faces, reference_faces_2 = get_reference_faces() if 'reference' in facefusion.globals.face_selector_mode else None, None
    target_vision_frame = read_static_image(target_path)
    result_frame = process_frame(
        {
            'reference_faces': reference_faces,
            'target_vision_frame': target_vision_frame
        })
    write_image(output_path, result_frame)


def process_video(source_paths: List[str], source_paths_2: List[str], temp_frame_paths: List[str]) -> None:
    frame_processors.multi_process_frames(source_paths, source_paths_2, temp_frame_paths, process_frames)
