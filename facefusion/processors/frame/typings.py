from typing import Literal, TypedDict

from facefusion.typing import Face, FaceSet, AudioFrame, VisionFrame

FaceDebuggerItem = Literal['bounding-box', 'landmark-5', 'landmark-68', 'face-mask', 'score', 'age', 'gender']
FaceEnhancerModel = Literal[
    'codeformer', 'gfpgan_1.2', 'gfpgan_1.3', 'gfpgan_1.4', 'gpen_bfr_256', 'gpen_bfr_512', 'restoreformer_plus_plus']
FaceSwapperModel = Literal[
    'blendswap_256', 'inswapper_128', 'inswapper_128_fp16', 'simswap_256', 'simswap_512_unofficial', 'uniface_256']
FrameEnhancerModel = Literal['real_esrgan_x2plus', 'real_esrgan_x4plus', 'real_esrnet_x4plus']
LipSyncerModel = Literal['wav2lip_gan']

FaceDebuggerInputs = TypedDict('FaceDebuggerInputs',
                               {
                                   'reference_faces': FaceSet,
                                   'reference_faces_2': FaceSet,
                                   'target_vision_frame': VisionFrame,
                                   'source_frame': VisionFrame,
                                   'target_frame_number': int
                               })
FaceEnhancerInputs = TypedDict('FaceEnhancerInputs',
                               {
                                   'reference_faces': FaceSet,
                                   'reference_faces_2': FaceSet,
                                   'target_vision_frame': VisionFrame
                               })
FaceSwapperInputs = TypedDict('FaceSwapperInputs',
                              {
                                  'reference_faces': FaceSet,
                                  'reference_faces_2': FaceSet,
                                  'source_face': Face,
                                  'source_face_2': Face,
                                  'target_vision_frame': VisionFrame,
                                  'target_frame_number': int
                              })
FrameEnhancerInputs = TypedDict('FrameEnhancerInputs',
                                {
                                    'target_vision_frame': VisionFrame
                                })
LipSyncerInputs = TypedDict('LipSyncerInputs',
                            {
                                'reference_faces': FaceSet,
                                'reference_faces_2': FaceSet,
                                'source_audio_frame': AudioFrame,
                                'target_vision_frame': VisionFrame
                            })
